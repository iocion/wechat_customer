"""通用聊天技能 - 阶段感知的兜底 AI 对话"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ai.prompt_templates import GENERAL_CHAT_PROMPT
from session.models import SessionState
from skills.base import BaseSkill, SkillResponse

if TYPE_CHECKING:
    from ai.glm_client import GLMClient
    from session.models import Session

logger = logging.getLogger(__name__)

_TRANSFER_KEYWORD = "转人工"
_TRANSFER_REPLY = "好的，正在为你转接人工客服，请稍候..."
_ERROR_REPLY = "稍等，我处理一下~"


class ChatSkill(BaseSkill):
    """兜底技能 - 处理未被其他技能匹配的对话"""

    def __init__(self, glm_client: GLMClient) -> None:
        self.glm_client = glm_client

    @property
    def name(self) -> str:
        return "chat"

    @property
    def description(self) -> str:
        return "General AI chat fallback"

    @property
    def priority(self) -> int:
        return 0

    def can_handle(self, message: dict, session: Session) -> bool:
        if message.get("MsgType") != "text":
            return False
        return session.state == SessionState.ACTIVE

    def handle(self, message: dict, session: Session) -> SkillResponse:
        content = (message.get("Content") or "").strip()

        if content == _TRANSFER_KEYWORD:
            return SkillResponse(
                text=_TRANSFER_REPLY,
                transfer_to_human=True,
            )

        system_prompt = GENERAL_CHAT_PROMPT.format(
            identity=session.identity or "朋友",
            stage=self._stage_display(session.stage),
        )

        try:
            reply = self.glm_client.chat_with_history(
                system_prompt=system_prompt,
                chat_history=session.get_recent_history(max_turns=10),
                user_message=content,
            )
            return SkillResponse(text=reply)
        except Exception:
            logger.exception("Chat AI failed for user %s", session.user_id)
            return SkillResponse(text=_ERROR_REPLY)

    def _stage_display(self, stage: str) -> str:
        stage_map = {
            "unknown": "咨询中",
            "pre_sales": "选购中",
            "mid_sales": "已下单",
            "post_sales": "售后中",
        }
        return stage_map.get(stage, "咨询中")
