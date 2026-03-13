"""WeChat Work callback encryption / decryption.

Implements AES-256-CBC with PKCS#7 padding, following the official
WeChat Work callback protocol (no dependency on wechatpy for crypto).
"""

from __future__ import annotations

import base64
import hashlib
import os
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class WeChatCrypto:
    """Handles signature verification and message encryption/decryption
    for the WeChat Work callback API.
    """

    BLOCK_SIZE = 32  # AES block size used by WeChat (256-bit key)

    def __init__(self, token: str, encoding_aes_key: str, corp_id: str) -> None:
        self.token = token
        self.corp_id = corp_id
        # EncodingAESKey is 43-char base64 (without padding) → decode to 32-byte key
        self.aes_key = base64.b64decode(encoding_aes_key + "=")
        self.iv = self.aes_key[:16]

    # -- Signature --

    def _make_signature(self, *parts: str) -> str:
        """SHA-1 of sorted concatenation of parts."""
        items = sorted(parts)
        return hashlib.sha1("".join(items).encode("utf-8")).hexdigest()

    def verify_signature(
        self,
        signature: str,
        timestamp: str,
        nonce: str,
        encrypt_msg: str = "",
    ) -> bool:
        """Verify a WeChat callback signature."""
        expected = self._make_signature(self.token, timestamp, nonce, encrypt_msg)
        return expected == signature

    def generate_signature(self, timestamp: str, nonce: str, encrypt_msg: str) -> str:
        """Create a signature for an outgoing encrypted reply."""
        return self._make_signature(self.token, timestamp, nonce, encrypt_msg)

    # -- PKCS#7 helpers --

    @classmethod
    def _pkcs7_pad(cls, data: bytes) -> bytes:
        pad_len = cls.BLOCK_SIZE - (len(data) % cls.BLOCK_SIZE)
        return data + bytes([pad_len] * pad_len)

    @staticmethod
    def _pkcs7_unpad(data: bytes) -> bytes:
        pad_len = data[-1]
        return data[:-pad_len]

    # -- AES encrypt / decrypt --

    def _aes_encrypt(self, plaintext: bytes) -> bytes:
        padded = self._pkcs7_pad(plaintext)
        cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(self.iv))
        encryptor = cipher.encryptor()
        return encryptor.update(padded) + encryptor.finalize()

    def _aes_decrypt(self, ciphertext: bytes) -> bytes:
        cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(self.iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        return self._pkcs7_unpad(padded)

    # -- Public API --

    def decrypt(self, encrypt_msg: str) -> str:
        """Decrypt an encrypted message from the WeChat callback.

        Format of decrypted payload:
            16-byte random | 4-byte msg_len (network order) | msg | corp_id
        """
        ciphertext = base64.b64decode(encrypt_msg)
        plaintext = self._aes_decrypt(ciphertext)

        # Skip 16-byte random prefix
        msg_len = struct.unpack("!I", plaintext[16:20])[0]
        msg = plaintext[20 : 20 + msg_len]
        from_corp_id = plaintext[20 + msg_len :].decode("utf-8")

        if from_corp_id != self.corp_id:
            raise ValueError(
                f"CorpID mismatch: expected {self.corp_id!r}, got {from_corp_id!r}"
            )
        return msg.decode("utf-8")

    def encrypt(self, reply_msg: str) -> str:
        """Encrypt a reply message for passive callback response.

        Returns base64-encoded ciphertext.
        """
        msg_bytes = reply_msg.encode("utf-8")
        # 16 random bytes + 4-byte length (network order) + msg + corp_id
        payload = (
            os.urandom(16)
            + struct.pack("!I", len(msg_bytes))
            + msg_bytes
            + self.corp_id.encode("utf-8")
        )
        encrypted = self._aes_encrypt(payload)
        return base64.b64encode(encrypted).decode("utf-8")
