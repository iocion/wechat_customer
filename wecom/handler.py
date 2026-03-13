"""Message handler bridge — connects callback to the processing queue."""

from __future__ import annotations

import logging

from flask import current_app

logger = logging.getLogger(__name__)


def handle_message(message: dict) -> None:
    """Put a message on the processing queue for background handling.

    Called from :func:`wecom.callback.receive`.
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
        if event in (
            "enter_session",
            "kf_msg_or_event",
            "change_external_contact",
        ):
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
