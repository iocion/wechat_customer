"""Welcome + identity confirmation skill."""

from __future__ import annotations

from typing import TYPE_CHECKING

from session.models import SessionState
from skills.base import BaseSkill, SkillResponse

if TYPE_CHECKING:
    from session.models import Session

WELCOME_MESSAGE = (
    "您好！欢迎咨询我们的智能客服 🤝\n\n"
    "我是您的专属AI助手，可以为您解答各类问题。\n\n"
    "为了更好地为您服务，请先告诉我您的称呼（姓名或昵称）："
)

IDENTITY_CONFIRMED_MESSAGE = (
    "感谢您，{name}！很高兴为您服务 😊\n\n"
    "您现在可以直接向我提问，我会尽力为您解答。\n"
    "如需人工客服，请发送「转人工」。"
)


class WelcomeSkill(BaseSkill):
    """Handles first-contact flow: greeting → identity collection → activation."""

    @property
    def name(self) -> str:
        return "welcome"

    @property
    def description(self) -> str:
        return "Welcome new customers and confirm their identity"

    @property
    def priority(self) -> int:
        return 100  # highest — intercepts new / unidentified users

    def can_handle(self, message: dict, session: Session) -> bool:
        # Skip if user already has identity (already welcomed before)
        if session.identity:
            return False

        # Handle text messages from NEW or AWAITING_IDENTITY sessions
        if message.get("MsgType") == "text" and session.state in (
            SessionState.NEW,
            SessionState.AWAITING_IDENTITY,
        ):
            return True
        # Handle enter_session events for new users (customer opens chat window)
        if message.get("MsgType") == "event" and session.state == SessionState.NEW:
            return True
        return False

    def handle(self, message: dict, session: Session) -> SkillResponse:
        if session.state == SessionState.NEW:
            return SkillResponse(
                text=WELCOME_MESSAGE,
                next_state="AWAITING_IDENTITY",
                should_update_session=False,
            )

        # AWAITING_IDENTITY — user is providing their name
        name = (message.get("Content") or "").strip()
        if not name or len(name) > 50:
            return SkillResponse(
                text="请输入一个有效的称呼（1-50个字符）：",
                should_update_session=False,
            )

        session.identity = name
        return SkillResponse(
            text=IDENTITY_CONFIRMED_MESSAGE.format(name=name),
            next_state="ACTIVE",
            should_update_session=False,
        )
