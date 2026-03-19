"""用户画像管理器"""

from __future__ import annotations

import logging
from typing import Any, Optional

from storage.database import Database

logger = logging.getLogger(__name__)


class UserProfileManager:
    """管理用户画像，包括偏好、购买历史、问题记录"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()

    def get_profile(self, user_id: str) -> dict[str, Any]:
        return self.db.get_user_profile(user_id)

    def update_preferences(self, user_id: str, preferences: dict[str, Any]) -> None:
        profile = self.get_profile(user_id)
        current = profile.get("preferences", {})
        current.update(preferences)
        self.db.update_user_profile(user_id, preferences=current)
        logger.info("Updated preferences for user %s: %s", user_id, preferences)

    def add_purchase(self, user_id: str, purchase: dict[str, Any]) -> None:
        self.db.add_to_purchase_history(user_id, purchase)
        logger.info("Added purchase for user %s: %s", user_id, purchase)

    def add_issue(self, user_id: str, issue: dict[str, Any]) -> None:
        self.db.add_to_issues_history(user_id, issue)
        logger.info("Added issue for user %s: %s", user_id, issue)

    def update_key_info(self, user_id: str, key: str, value: Any) -> None:
        self.db.update_key_info(user_id, key, value)
        logger.info("Updated key info for user %s: %s = %s", user_id, key, value)

    def get_summary(self, user_id: str) -> str:
        profile = self.get_profile(user_id)
        return profile.get("conversation_summary", "")

    def update_summary(self, user_id: str, summary: str) -> None:
        self.db.update_user_profile(user_id, conversation_summary=summary)
        logger.info("Updated summary for user %s", user_id)

    def format_for_prompt(self, user_id: str) -> str:
        """格式化用户画像为提示词"""
        profile = self.get_profile(user_id)
        parts = []

        preferences = profile.get("preferences", {})
        if preferences:
            parts.append(f"用户偏好: {preferences}")

        key_info = profile.get("key_info", {})
        if key_info:
            info_parts = [f"{k}: {v.get('value', '')}" for k, v in key_info.items()]
            parts.append(f"用户信息: {', '.join(info_parts)}")

        issues = profile.get("issues_history", [])
        if issues:
            unresolved = [i for i in issues if not i.get("resolved")]
            if unresolved:
                parts.append(f"待处理问题: {len(unresolved)}个")

        summary = profile.get("conversation_summary")
        if summary:
            parts.append(f"对话摘要: {summary}")

        return "\n".join(parts) if parts else "新用户，暂无画像信息"
