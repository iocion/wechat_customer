"""Abstract base class for all skills."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from session.models import Session


@dataclass
class SkillResponse:
    """Value object returned by a skill after handling a message."""

    text: str
    should_update_session: bool = True
    next_state: Optional[str] = (
        None  # target SessionState name, e.g. "AWAITING_IDENTITY"
    )


class BaseSkill(ABC):
    """Every skill must subclass this and implement the three abstract members."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill identifier."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description."""

    @abstractmethod
    def can_handle(self, message: dict, session: Session) -> bool:
        """Return ``True`` if this skill should process *message*."""

    @abstractmethod
    def handle(self, message: dict, session: Session) -> SkillResponse:
        """Process the message and return a response.

        Runs inside a background worker thread, so blocking I/O is fine.
        """

    @property
    def priority(self) -> int:
        """Higher-priority skills are checked first.  Default ``0``."""
        return 0
