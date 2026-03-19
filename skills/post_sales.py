"""售后安抚技能"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from memory.context import ContextBuilder
from memory.profile import UserProfileManager
from prompts.builder import PromptBuilder
from session.models import SessionState
from skills.base import BaseSkill, SkillResponse

if TYPE_CHECKING:
    from ai.glm_client import GLMClient
    from session.models import Session

logger = logging.getLogger(__name__)

ISSUE_KEYWORDS = {
    "破损": "商品破损",
    "坏了": "商品损坏",
    "质量": "质量问题",
    "尺码": "尺码不合",
    "颜色": "颜色不符",
    "发错": "发错商品",
    "少发": "少发商品",
    "退款": "申请退款",
    "退货": "申请退货",
    "换货": "申请换货",
}


class PostSalesSkill(BaseSkill):
    """售后安抚 - 共情安抚、问题归档、给出方案"""

    def __init__(
        self,
        glm_client: GLMClient,
        context_builder: ContextBuilder | None = None,
        profile_manager: UserProfileManager | None = None,
    ) -> None:
        self.glm_client = glm_client
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_builder = PromptBuilder()
        self.profile_manager = profile_manager or UserProfileManager()

    @property
    def name(self) -> str:
        return "post_sales"

    @property
    def description(self) -> str:
        return "Post-sales support with issue archiving"

    @property
    def priority(self) -> int:
        return 20

    def can_handle(self, message: dict, session: Session) -> bool:
        if message.get("MsgType") != "text":
            return False
        if session.state != SessionState.ACTIVE:
            return False
        return session.stage == "post_sales"

    def handle(self, message: dict, session: Session) -> SkillResponse:
        content = (message.get("Content") or "").strip()

        self._archive_issues(content, session)

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
            logger.exception("PostSales AI failed for user %s", session.user_id)
            return SkillResponse(text="我来帮你处理，稍等~")

    def _archive_issues(self, content: str, session: Session) -> None:
        for keyword, issue_label in ISSUE_KEYWORDS.items():
            if keyword in content:
                self.profile_manager.add_issue(
                    user_id=session.user_id,
                    issue={"type": issue_label, "content": content},
                )
                logger.info(
                    "Archived issue for user %s: %s", session.user_id, issue_label
                )
