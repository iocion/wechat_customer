"""WeChat Customer Service (微信客服) sync_msg API client.

In kf mode, the callback only contains a notification (kf_msg_or_event).
Actual message content must be pulled via the sync_msg REST endpoint.
"""

from __future__ import annotations

import logging
import threading
from typing import Any

import requests

from wecom.token_manager import TokenManager

logger = logging.getLogger(__name__)

_SYNC_MSG_URL = "https://qyapi.weixin.qq.com/cgi-bin/kf/sync_msg"


class KfClient:
    """Pulls customer messages via sync_msg, tracking per-kfid cursors."""

    def __init__(self, token_manager: TokenManager) -> None:
        self.token_manager = token_manager
        self._cursors: dict[str, str] = {}
        self._lock = threading.Lock()

    def sync_messages(
        self,
        callback_token: str,
        open_kfid: str,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Pull new customer messages (origin==3) for *open_kfid*."""
        cursor = self._get_cursor(open_kfid)

        access_token = self.token_manager.get_token()
        payload: dict[str, Any] = {
            "limit": limit,
            "open_kfid": open_kfid,
        }
        if cursor:
            payload["cursor"] = cursor
        if callback_token:
            payload["token"] = callback_token

        logger.info(
            "sync_msg request: open_kfid=%s, cursor=%s",
            open_kfid,
            cursor or "(initial)",
        )

        try:
            resp = requests.post(
                _SYNC_MSG_URL,
                params={"access_token": access_token},
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except Exception:
            logger.exception("sync_msg API call failed")
            return []

        errcode = data.get("errcode", 0)
        if errcode != 0:
            logger.error("sync_msg error: %s", data)
            return []

        next_cursor = data.get("next_cursor", "")
        if next_cursor:
            self._set_cursor(open_kfid, next_cursor)

        msg_list: list[dict[str, Any]] = data.get("msg_list", [])
        has_more = data.get("has_more", 0)

        logger.info(
            "sync_msg returned %d messages (has_more=%s)",
            len(msg_list),
            has_more,
        )

        # origin == 3 means external customer; 4 = servicer, 5 = system
        customer_messages = [m for m in msg_list if m.get("origin") == 3]
        logger.info(
            "Filtered to %d customer messages (origin=3)", len(customer_messages)
        )

        if has_more:
            customer_messages.extend(
                self.sync_messages(callback_token, open_kfid, limit)
            )

        return customer_messages

    def _get_cursor(self, open_kfid: str) -> str:
        with self._lock:
            return self._cursors.get(open_kfid, "")

    def _set_cursor(self, open_kfid: str, cursor: str) -> None:
        with self._lock:
            self._cursors[open_kfid] = cursor
            logger.debug("Updated cursor for %s: %s", open_kfid, cursor)
