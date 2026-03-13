"""售前导购技能"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ai.prompt_templates import PRE_SALES_PROMPT
from session.models import SessionState
from skills.base import BaseSkill, SkillResponse

if TYPE_CHECKING:
    from ai.glm_client import GLMClient
    from session.models import Session

logger = logging.getLogger(__name__)


class PreSalesSkill(BaseSkill):
    """售前导购 - 挖掘需求、推荐商品、引导下单"""

    def __init__(self, glm_client: GLMClient) -> None:
        self.glm_client = glm_client

    @property
    def name(self) -> str:
        return "pre_sales"

    @property
    def description(self) -> str:
        return "Pre-sales consultation and product recommendation"

    @property
    def priority(self) -> int:
        return 40

    def can_handle(self, message: dict, session: Session) -> bool:
        if message.get("MsgType") != "text":
            return False
        if session.state != SessionState.ACTIVE:
            return False
        return session.stage == "pre_sales"

    def handle(self, message: dict, session: Session) -> SkillResponse:
        content = (message.get("Content") or "").strip()

        try:
            reply = self.glm_client.chat_with_history(
                system_prompt=PRE_SALES_PROMPT,
                chat_history=session.get_recent_history(max_turns=10),
                user_message=content,
            )
            return SkillResponse(text=reply)
        except Exception:
            logger.exception("PreSales AI failed for user %s", session.user_id)
            return SkillResponse(text="稍等，我帮你问下~")
