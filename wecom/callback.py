"""Flask blueprint for the WeChat Work callback endpoint."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

from flask import Blueprint, Response, current_app, request

logger = logging.getLogger(__name__)

callback_bp = Blueprint("callback", __name__)


@callback_bp.route("/callback", methods=["GET"])
def verify() -> Response | str:
    """WeChat Work URL verification (GET).

    Query params: msg_signature, timestamp, nonce, echostr
    """
    crypto = current_app.config["crypto"]

    msg_signature = request.args.get("msg_signature", "")
    timestamp = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")
    echostr = request.args.get("echostr", "")

    if not all([msg_signature, timestamp, nonce, echostr]):
        logger.warning("Verification request missing parameters")
        return Response("missing params", status=400)

    if not crypto.verify_signature(msg_signature, timestamp, nonce, echostr):
        logger.warning("Signature verification failed")
        return Response("invalid signature", status=403)

    try:
        plaintext = crypto.decrypt(echostr)
        logger.info("Callback URL verified successfully")
        return plaintext
    except Exception:
        logger.exception("Failed to decrypt echostr")
        return Response("decrypt error", status=500)


@callback_bp.route("/callback", methods=["POST"])
def receive() -> str:
    """Receive messages / events from WeChat Work (POST).

    Must respond within 5 seconds — all heavy processing is dispatched
    to a background queue.
    """
    from wecom.message import parse_xml_message
    from wecom.handler import handle_message

    crypto = current_app.config["crypto"]

    msg_signature = request.args.get("msg_signature", "")
    timestamp = request.args.get("timestamp", "")
    nonce = request.args.get("nonce", "")

    if not all([msg_signature, timestamp, nonce]):
        logger.warning("POST callback missing query parameters")
        return "success"

    try:
        # Parse outer XML to extract <Encrypt> element
        body = request.data
        root = ET.fromstring(body)
        encrypt_el = root.find("Encrypt")
        if encrypt_el is None or encrypt_el.text is None:
            logger.warning("No <Encrypt> element in callback body")
            return "success"
        encrypt_text = encrypt_el.text

        # Verify signature
        if not crypto.verify_signature(msg_signature, timestamp, nonce, encrypt_text):
            logger.warning("POST callback signature mismatch")
            return "success"

        # Decrypt inner XML
        inner_xml = crypto.decrypt(encrypt_text)
        logger.debug("Decrypted message XML: %s", inner_xml)

        # Parse and dispatch
        message = parse_xml_message(inner_xml)
        logger.info(
            "Received %s from %s",
            message.get("MsgType", "unknown"),
            message.get("FromUserName", "unknown"),
        )
        handle_message(message)

    except Exception:
        logger.exception("Error processing callback POST")

    # Always return quickly
    return "success"
