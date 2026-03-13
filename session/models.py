"""Session data models."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SessionState(Enum):
    """Conversation state machine states."""

    NEW = "new"
    AWAITING_IDENTITY = "awaiting_identity"
    ACTIVE = "active"
    ENDED = "ended"


@dataclass
class Session:
    """Represents a single user conversation session."""

    user_id: str
    state: SessionState = SessionState.NEW
    identity: Optional[str] = None
    chat_history: list[dict[str, str]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

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
        )
