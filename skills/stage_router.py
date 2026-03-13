"""阶段路由技能 - AI 分析用户意图并更新 session.stage"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from ai.prompt_templates import STAGE_ANALYSIS_PROMPT
from session.models import SessionState, UserStage
from skills.base import BaseSkill, SkillResponse

if TYPE_CHECKING:
    from ai.glm_client import GLMClient
    from session.models import Session

logger = logging.getLogger(__name__)

STAGE_KEYWORDS = {
    "pre_sales": [
        "买",
        "想要",
        "推荐",
        "有没有",
        "多少钱",
        "价格",
        "款式",
        "尺码",
        "颜色",
    ],
    "mid_sales": ["订单", "物流", "快递", "发货", "什么时候到", "地址", "催", "付款"],
    "post_sales": [
        "退",
        "换",
        "坏了",
        "破损",
        "质量",
        "投诉",
        "不满意",
        "差评",
        "问题",
    ],
}


class StageRouterSkill(BaseSkill):
    """分析用户意图，更新 session.stage，然后让后续技能处理"""

    def __init__(self, glm_client: GLMClient) -> None:
        self.glm_client = glm_client

    @property
    def name(self) -> str:
        return "stage_router"

    @property
    def description(self) -> str:
        return "Analyze user intent and update session stage"

    @property
    def priority(self) -> int:
        return 90

    def can_handle(self, message: dict, session: Session) -> bool:
        if message.get("MsgType") != "text":
            return False
        return session.state == SessionState.ACTIVE

    def handle(self, message: dict, session: Session) -> SkillResponse:
        content = (message.get("Content") or "").strip()
        if not content:
            return SkillResponse(
                text="", should_update_session=False, pass_through=True
            )

        new_stage = self._detect_stage_fast(content, session.stage)

        if new_stage == "unknown" and session.stage == "unknown":
            new_stage = self._detect_stage_ai(content, session.stage)

        if new_stage != "unknown":
            session.stage = new_stage
            logger.info("User %s stage updated to: %s", session.user_id, new_stage)

        return SkillResponse(text="", should_update_session=False, pass_through=True)

    def _detect_stage_fast(self, content: str, current_stage: UserStage) -> UserStage:
        """基于关键词快速检测阶段"""
        for stage, keywords in STAGE_KEYWORDS.items():
            if any(kw in content for kw in keywords):
                return cast(UserStage, stage)
        return current_stage if current_stage != "unknown" else "unknown"

    def _detect_stage_ai(self, content: str, current_stage: UserStage) -> UserStage:
        """调用 AI 分析阶段（仅在关键词无法判断时使用）"""
        try:
            prompt = STAGE_ANALYSIS_PROMPT.format(
                message=content,
                current_stage=current_stage,
            )
            result = self.glm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=20,
            )
            stage = result.strip().lower()
            if stage in ("pre_sales", "mid_sales", "post_sales"):
                return cast(UserStage, stage)
        except Exception:
            logger.exception("Stage detection AI failed")
        return "unknown"
