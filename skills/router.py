"""Routes incoming messages to the appropriate skill."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from skills.base import BaseSkill

if TYPE_CHECKING:
    from session.models import Session

logger = logging.getLogger(__name__)


class SkillRouter:
    """Maintains a priority-ordered list of skills and routes messages."""

    def __init__(self) -> None:
        self._skills: list[BaseSkill] = []
        self._default_skill: Optional[BaseSkill] = None

    def register(self, skill: BaseSkill) -> None:
        """Register a skill, keeping the list sorted by descending priority."""
        self._skills.append(skill)
        self._skills.sort(key=lambda s: s.priority, reverse=True)
        logger.info("Registered skill: %s (priority=%d)", skill.name, skill.priority)

    def set_default(self, skill: BaseSkill) -> None:
        """Set the fallback skill used when no other skill matches."""
        self._default_skill = skill
        logger.info("Default skill set to: %s", skill.name)

    def route(self, message: dict, session: Session) -> Optional[BaseSkill]:
        """Return the first skill that can handle *message*, or the default."""
        for skill in self._skills:
            if skill.can_handle(message, session):
                logger.debug("Routed to skill: %s", skill.name)
                return skill
        if self._default_skill:
            logger.debug(
                "No match — falling back to default skill: %s", self._default_skill.name
            )
            return self._default_skill
        return None

    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """Look up a registered skill by name."""
        for skill in self._skills:
            if skill.name == name:
                return skill
        return None

    @property
    def skills(self) -> list[BaseSkill]:
        """All registered skills (ordered by priority)."""
        return list(self._skills)
