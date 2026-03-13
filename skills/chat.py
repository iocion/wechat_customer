"""General AI chat skill — delegates to GLM API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ai.prompt_templates import CUSTOMER_SERVICE_SYSTEM_PROMPT
from session.models import SessionState
from skills.base import BaseSkill, SkillResponse

if TYPE_CHECKING:
    from ai.glm_client import GLMClient
    from session.models import Session

logger = logging.getLogger(__name__)

_TRANSFER_KEYWORD = "转人工"
_TRANSFER_REPLY = "好的，{name}，我正在为您转接人工客服，请稍候..."
_ERROR_REPLY = "抱歉，我暂时无法处理您的请求，请稍后再试。"


class ChatSkill(BaseSkill):
    """Catch-all skill for active sessions — answers via GLM AI."""

    def __init__(self, glm_client: GLMClient) -> None:
        self.glm_client = glm_client

    @property
    def name(self) -> str:
        return "chat"

    @property
    def description(self) -> str:
        return "AI-powered chat responses using GLM"

    @property
    def priority(self) -> int:
        return 0  # lowest — only triggers when nothing else matches

    def can_handle(self, message: dict, session: Session) -> bool:
        return message.get("MsgType") == "text" and session.state == SessionState.ACTIVE

    def handle(self, message: dict, session: Session) -> SkillResponse:
        content = (message.get("Content") or "").strip()

        # Quick keyword check: transfer to human agent
        if content == _TRANSFER_KEYWORD:
            name = session.identity or "用户"
            return SkillResponse(
                text=_TRANSFER_REPLY.format(name=name),
                transfer_to_human=True,
            )

        # Build system prompt with user identity
        system_prompt = CUSTOMER_SERVICE_SYSTEM_PROMPT.format(
            identity=session.identity or "未知用户"
        )

        try:
            reply = self.glm_client.chat_with_history(
                system_prompt=system_prompt,
                chat_history=session.get_recent_history(max_turns=20),
                user_message=content,
            )
            return SkillResponse(text=reply)
        except Exception:
            logger.exception("GLM API call failed for user %s", session.user_id)
            return SkillResponse(text=_ERROR_REPLY)
