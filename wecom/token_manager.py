"""Manages WeChat Work access_token with automatic refresh and caching."""

from __future__ import annotations

import logging
import threading
import time

import requests

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"


class TokenManager:
    """Thread-safe access_token manager with expiry-aware caching."""

    def __init__(self, corp_id: str, corp_secret: str) -> None:
        self.corp_id = corp_id
        self.corp_secret = corp_secret
        self._token: str = ""
        self._expires_at: float = 0.0
        self._lock = threading.Lock()

    def get_token(self) -> str:
        """Return a valid access_token, refreshing if needed."""
        with self._lock:
            # Refresh if missing or within 5 minutes of expiry
            if self._token and time.time() < self._expires_at - 300:
                return self._token
            return self._refresh()

    def _refresh(self) -> str:
        """Fetch a new access_token from WeChat Work API."""
        resp = requests.get(
            _TOKEN_URL,
            params={"corpid": self.corp_id, "corpsecret": self.corp_secret},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("errcode", 0) != 0:
            msg = f"Token refresh failed: {data}"
            logger.error(msg)
            raise RuntimeError(msg)

        self._token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 7200)
        logger.info(
            "Access token refreshed, expires in %ds", data.get("expires_in", 7200)
        )
        return self._token
