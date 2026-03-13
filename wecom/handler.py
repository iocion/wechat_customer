"""Message handler bridge — connects callback to the processing queue.

For kf mode, the callback only contains a notification. This handler
calls sync_msg to fetch actual messages, then normalizes them into
the standard format expected by the worker.
"""

from __future__ import annotations

import logging

from flask import current_app

logger = logging.getLogger(__name__)


def handle_message(message: dict) -> None:
    """Dispatch an incoming parsed callback message to the processing queue.

    For ``kf_msg_or_event`` events, calls the sync_msg API to pull
    actual customer messages before queuing them.
    """
    message_queue = current_app.config.get("message_queue")
    if message_queue is None:
        logger.error("Message queue not initialized!")
        return

    msg_type = message.get("MsgType", "")

    if msg_type == "text":
        message_queue.put({"message": message})
        logger.info(
            "Queued text message from %s", message.get("FromUserName", "unknown")
        )

    elif msg_type == "event":
        event = message.get("Event", "")

        if event == "kf_msg_or_event":
            _handle_kf_notification(message, message_queue)

        elif event in ("enter_session", "change_external_contact"):
            message_queue.put({"message": message})
            logger.info(
                "Queued event '%s' from %s",
                event,
                message.get("FromUserName", "unknown"),
            )
        else:
            logger.debug("Ignoring event type: %s", event)
    else:
        logger.debug("Ignoring message type: %s", msg_type)


def _handle_kf_notification(notification: dict, message_queue) -> None:  # type: ignore[type-arg]
    """Pull real messages via sync_msg and queue each one individually."""
    kf_client = current_app.config.get("kf_client")
    if kf_client is None:
        logger.error("kf_client not initialized — cannot fetch kf messages")
        return

    callback_token = notification.get("Token", "") or ""
    open_kfid = notification.get("OpenKfId", "") or ""

    if not open_kfid:
        app_config = current_app.config.get("app_config")
        if app_config:
            open_kfid = app_config.KF_OPEN_KFID
        if not open_kfid:
            logger.error("No OpenKfId in callback and no KF_OPEN_KFID configured")
            return

    logger.info(
        "kf_msg_or_event received — fetching messages for open_kfid=%s", open_kfid
    )

    customer_messages = kf_client.sync_messages(
        callback_token=callback_token,
        open_kfid=open_kfid,
    )

    if not customer_messages:
        logger.info("No customer messages returned from sync_msg")
        return

    for msg in customer_messages:
        normalized = _normalize_kf_message(msg, open_kfid)
        if normalized:
            message_queue.put({"message": normalized})
            logger.info(
                "Queued kf message from %s: %s",
                normalized.get("FromUserName", "unknown"),
                (normalized.get("Content") or "")[:50],
            )


def _normalize_kf_message(kf_msg: dict, open_kfid: str) -> dict | None:
    """Convert a sync_msg JSON item into the standard message dict format.

    The worker expects: FromUserName, MsgType, Content, OpenKfId.
    sync_msg returns: external_userid, msgtype, text.content, open_kfid.
    """
    msgtype = kf_msg.get("msgtype", "")

    if msgtype == "text":
        text_obj = kf_msg.get("text", {})
        content = text_obj.get("content", "") if isinstance(text_obj, dict) else ""
    elif msgtype == "event":
        content = ""
    else:
        logger.debug("Skipping unsupported kf msgtype: %s", msgtype)
        return None

    return {
        "FromUserName": kf_msg.get("external_userid", ""),
        "MsgType": msgtype,
        "Content": content,
        "MsgId": kf_msg.get("msgid", ""),
        "OpenKfId": open_kfid,
        "CreateTime": str(kf_msg.get("send_time", "")),
        "_kf_origin": kf_msg.get("origin"),
        "_kf_raw": kf_msg,
    }
