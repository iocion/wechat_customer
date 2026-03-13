"""自然问候技能 - 非阻塞式首次问候"""

from __future__ import annotations

from typing import TYPE_CHECKING

from session.models import SessionState
from skills.base import BaseSkill, SkillResponse

if TYPE_CHECKING:
    from session.models import Session


class GreetingSkill(BaseSkill):
    """首次接触时自然问候，不阻塞后续对话"""

    @property
    def name(self) -> str:
        return "greeting"

    @property
    def description(self) -> str:
        return "Natural first-contact greeting without blocking"

    @property
    def priority(self) -> int:
        return 100

    def can_handle(self, message: dict, session: Session) -> bool:
        if session.greeted:
            return False
        if session.state != SessionState.NEW:
            return False
        msg_type = message.get("MsgType", "")
        return msg_type in ("text", "event")

    def handle(self, message: dict, session: Session) -> SkillResponse:
        session.greeted = True
        session.state = SessionState.ACTIVE

        content = (message.get("Content") or "").strip()

        if not content or message.get("MsgType") == "event":
            return SkillResponse(
                text="有什么可以帮你的？",
                should_update_session=False,
            )

        return SkillResponse(
            text=f"收到~ {self._get_quick_ack(content)}",
            should_update_session=False,
            next_state="ACTIVE",
        )

    def _get_quick_ack(self, content: str) -> str:
        """根据内容给出简短确认"""
        keywords_map = {
            ("买", "想要", "推荐", "有没有"): "我来帮你挑~",
            ("订单", "物流", "快递", "发货"): "我帮你查一下",
            ("退", "换", "坏", "问题", "投诉"): "我来处理",
        }
        for keywords, response in keywords_map.items():
            if any(kw in content for kw in keywords):
                return response
        return "我来看看"
