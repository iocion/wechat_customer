"""售中跟进技能"""

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


class MidSalesSkill(BaseSkill):
    """售中跟进 - 订单查询、物流跟踪、消除疑虑"""

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
        return "mid_sales"

    @property
    def description(self) -> str:
        return "Order tracking and mid-sales support"

    @property
    def priority(self) -> int:
        return 30

    def can_handle(self, message: dict, session: Session) -> bool:
        if message.get("MsgType") != "text":
            return False
        if session.state != SessionState.ACTIVE:
            return False
        return session.stage == "mid_sales"

    def handle(self, message: dict, session: Session) -> SkillResponse:
        content = (message.get("Content") or "").strip()

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
            logger.exception("MidSales AI failed for user %s", session.user_id)
            return SkillResponse(text="我帮你查一下，稍等~")
