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
_SERVICE_STATE_GET_URL = "https://qyapi.weixin.qq.com/cgi-bin/kf/service_state/get"
_SERVICE_STATE_TRANS_URL = "https://qyapi.weixin.qq.com/cgi-bin/kf/service_state/trans"
_SERVICER_ADD_URL = "https://qyapi.weixin.qq.com/cgi-bin/kf/servicer/add"

# service_state constants
_STATE_UNTOUCHED = 0  # 未处理
_STATE_SERVING = 1  # 由智能助手接待
_STATE_HUMAN = 2  # 待接入池等待人工接待
_STATE_HUMAN_SERVING = 3  # 由人工接待
_STATE_CLOSED = 4  # 已结束/未开启


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

    # -- Session state management --

    def get_service_state(
        self,
        open_kfid: str,
        external_userid: str,
    ) -> dict[str, Any]:
        """Query the current service_state for a KF session."""
        access_token = self.token_manager.get_token()
        payload = {
            "open_kfid": open_kfid,
            "external_userid": external_userid,
        }
        try:
            resp = requests.post(
                _SERVICE_STATE_GET_URL,
                params={"access_token": access_token},
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except Exception:
            logger.exception("service_state/get failed")
            return {"errcode": -1}

        if data.get("errcode", 0) != 0:
            logger.error("service_state/get error: %s", data)
        return data

    def trans_service_state(
        self,
        open_kfid: str,
        external_userid: str,
        service_state: int,
        servicer_userid: str = "",
    ) -> dict[str, Any]:
        """Transition a KF session to a new service_state."""
        access_token = self.token_manager.get_token()
        payload: dict[str, Any] = {
            "open_kfid": open_kfid,
            "external_userid": external_userid,
            "service_state": service_state,
        }
        if servicer_userid:
            payload["servicer_userid"] = servicer_userid

        try:
            resp = requests.post(
                _SERVICE_STATE_TRANS_URL,
                params={"access_token": access_token},
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except Exception:
            logger.exception("service_state/trans failed")
            return {"errcode": -1}

        if data.get("errcode", 0) != 0:
            logger.error("service_state/trans error: %s", data)
        else:
            logger.info(
                "Session transitioned to state %d for %s",
                service_state,
                external_userid,
            )
        return data

    def ensure_session_serving(
        self,
        open_kfid: str,
        external_userid: str,
    ) -> bool:
        """Ensure the session is in a state where send_msg is allowed.

        Transitions to state 1 (智能助手接待) which does **not** require a
        ``servicer_userid``.  States 1 and 3 both allow send_msg.

        Returns ``True`` if the session is ready for send_msg, ``False`` otherwise.
        """
        state_data = self.get_service_state(open_kfid, external_userid)
        if state_data.get("errcode", -1) != 0:
            logger.warning(
                "Cannot read session state for %s — attempting blind transition",
                external_userid,
            )
            result = self.trans_service_state(
                open_kfid, external_userid, _STATE_SERVING
            )
            return result.get("errcode", -1) == 0

        current_state = state_data.get("service_state")
        if current_state in (_STATE_SERVING, _STATE_HUMAN_SERVING):
            return True

        result = self.trans_service_state(open_kfid, external_userid, _STATE_SERVING)
        return result.get("errcode", -1) == 0

    def add_servicer(
        self,
        open_kfid: str,
        userid_list: list[str],
    ) -> dict[str, Any]:
        """Register internal members as servicers on a KF account via API.

        Required for API-managed accounts where the admin console is locked.
        Servicers must be within the app's visibility range.
        """
        access_token = self.token_manager.get_token()
        payload = {
            "open_kfid": open_kfid,
            "userid_list": userid_list,
        }
        try:
            resp = requests.post(
                _SERVICER_ADD_URL,
                params={"access_token": access_token},
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
        except Exception:
            logger.exception("servicer/add failed")
            return {"errcode": -1}

        if data.get("errcode", 0) != 0:
            logger.error("servicer/add error: %s", data)
        else:
            logger.info("Registered servicers %s on %s", userid_list, open_kfid)
        return data

    def transfer_to_human(
        self,
        open_kfid: str,
        external_userid: str,
        servicer_userid: str = "",
    ) -> bool:
        """Transfer session to human agent.

        If ``servicer_userid`` is provided, assigns directly (state 3).
        Otherwise, puts user into the waiting pool (state 2).
        """
        if servicer_userid:
            result = self.trans_service_state(
                open_kfid, external_userid, _STATE_HUMAN_SERVING, servicer_userid
            )
        else:
            result = self.trans_service_state(open_kfid, external_userid, _STATE_HUMAN)
        return result.get("errcode", -1) == 0
