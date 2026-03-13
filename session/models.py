"""Session data models."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional


class SessionState(Enum):
    """Conversation state machine states."""

    NEW = "new"
    ACTIVE = "active"
    ENDED = "ended"


# 用户阶段类型
UserStage = Literal["unknown", "pre_sales", "mid_sales", "post_sales"]


@dataclass
class Session:
    """Represents a single user conversation session.

    扩展字段支持电商客服场景：
    - stage: 用户当前所处阶段（售前/售中/售后）
    - pending_issues: 待处理问题列表（售后归档）
    - user_preferences: 用户偏好标签
    """

    user_id: str
    state: SessionState = SessionState.NEW
    identity: Optional[str] = None
    chat_history: list[dict[str, str]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    # === 电商客服扩展字段 ===
    stage: UserStage = "unknown"
    pending_issues: list[str] = field(default_factory=list)
    user_preferences: dict[str, Any] = field(default_factory=dict)
    greeted: bool = False  # 是否已问候过，防止重复欢迎

    # -- helpers --

    def add_message(self, role: str, content: str) -> None:
        """Append a message to chat history and bump updated_at."""
        self.chat_history.append({"role": role, "content": content})
        self.updated_at = time.time()

    def get_recent_history(self, max_turns: int = 20) -> list[dict[str, str]]:
        """Return the last *max_turns* messages."""
        return self.chat_history[-max_turns:]

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "state": self.state.value,
            "identity": self.identity,
            "chat_history": self.chat_history,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
            "stage": self.stage,
            "pending_issues": self.pending_issues,
            "user_preferences": self.user_preferences,
            "greeted": self.greeted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        return cls(
            user_id=data["user_id"],
            state=SessionState(data["state"]),
            identity=data.get("identity"),
            chat_history=data.get("chat_history", []),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            metadata=data.get("metadata", {}),
            stage=data.get("stage", "unknown"),
            pending_issues=data.get("pending_issues", []),
            user_preferences=data.get("user_preferences", {}),
            greeted=data.get("greeted", False),
        )

    def add_pending_issue(self, issue: str) -> None:
        """归档售后问题"""
        if issue and issue not in self.pending_issues:
            self.pending_issues.append(issue)
            self.updated_at = time.time()

    def set_preference(self, key: str, value: Any) -> None:
        """记录用户偏好"""
        self.user_preferences[key] = value
        self.updated_at = time.time()
