"""Message parsing (incoming XML) and sending (outgoing REST)."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Any, Optional

import requests

from wecom.token_manager import TokenManager

logger = logging.getLogger(__name__)

_KF_SEND_URL = "https://qyapi.weixin.qq.com/cgi-bin/kf/send_msg"
_AGENT_SEND_URL = "https://qyapi.weixin.qq.com/cgi-bin/message/send"


# ---------------------------------------------------------------------------
# XML Parsing
# ---------------------------------------------------------------------------


def parse_xml_message(xml_str: str) -> dict[str, Optional[str]]:
    """Parse a decrypted inner XML payload into a flat dict.

    Common fields extracted: ToUserName, FromUserName, CreateTime, MsgType,
    Content, MsgId, AgentID, Event, EventKey, ChangeType.
    Missing fields are set to ``None``.
    """
    fields = (
        "ToUserName",
        "FromUserName",
        "CreateTime",
        "MsgType",
        "Content",
        "MsgId",
        "AgentID",
        "Event",
        "EventKey",
        "ChangeType",
    )
    root = ET.fromstring(xml_str)
    result: dict[str, Optional[str]] = {}
    for f in fields:
        el = root.find(f)
        result[f] = el.text if el is not None else None
    return result


# ---------------------------------------------------------------------------
# Message Sending
# ---------------------------------------------------------------------------


class MessageSender:
    """Send messages via WeChat Work REST API."""

    def __init__(self, token_manager: TokenManager) -> None:
        self.token_manager = token_manager

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        token = self.token_manager.get_token()
        resp = requests.post(
            url,
            params={"access_token": token},
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        if data.get("errcode", 0) != 0:
            logger.error("Send message failed: %s", data)
        else:
            logger.info("Message sent successfully")
        return data

    def send_text(
        self,
        user_id: str,
        content: str,
        mode: str = "kf",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a plain-text message to a user.

        Parameters
        ----------
        mode:
            ``"kf"``   — WeChat Customer Service (微信客服) API
            ``"agent"`` — Internal agent messaging API
        """
        if mode == "kf":
            payload = {
                "touser": user_id,
                "open_kfid": kwargs.get("open_kfid", ""),
                "msgtype": "text",
                "text": {"content": content},
            }
            return self._post(_KF_SEND_URL, payload)

        # agent mode
        payload = {
            "touser": user_id,
            "msgtype": "text",
            "agentid": kwargs.get("agent_id", ""),
            "text": {"content": content},
        }
        return self._post(_AGENT_SEND_URL, payload)

    def send_markdown(
        self,
        user_id: str,
        content: str,
        mode: str = "agent",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Send a markdown message (only works in agent mode)."""
        payload = {
            "touser": user_id,
            "msgtype": "markdown",
            "agentid": kwargs.get("agent_id", ""),
            "markdown": {"content": content},
        }
        return self._post(_AGENT_SEND_URL, payload)
