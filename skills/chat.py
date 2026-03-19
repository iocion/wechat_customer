"""通用聊天技能 - 阶段感知的兜底 AI 对话"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from memory.context import ContextBuilder
from prompts.builder import PromptBuilder
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

    def __init__(
        self,
        glm_client: GLMClient,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        self.glm_client = glm_client
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_builder = PromptBuilder()

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

        context = self.context_builder.build_context(
            user_id=session.user_id,
            session_id=session.session_id,
            user_message=content,
            stage=session.stage,
        )

        system_prompt = self.prompt_builder.build_for_stage(
            stage=session.stage,
            context=context,
        )

        try:
            reply = self.glm_client.chat_with_history(
                system_prompt=system_prompt,
                chat_history=context.get("chat_history", []),
                user_message=content,
            )
            return SkillResponse(text=reply)
        except Exception:
            logger.exception("Chat AI failed for user %s", session.user_id)
            return SkillResponse(text=_ERROR_REPLY)
