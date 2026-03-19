"""上下文构建器"""

from __future__ import annotations

import logging
from typing import Any, Optional

from memory.profile import UserProfileManager
from memory.extractor import InformationExtractor
from memory.summarizer import ConversationSummarizer
from storage.database import Database

logger = logging.getLogger(__name__)


class ContextBuilder:
    """构建 AI 上下文"""

    def __init__(
        self,
        db: Optional[Database] = None,
        profile_manager: Optional[UserProfileManager] = None,
        extractor: Optional[InformationExtractor] = None,
        summarizer: Optional[ConversationSummarizer] = None,
    ):
        self.db = db or Database()
        self.profile_manager = profile_manager or UserProfileManager(self.db)
        self.extractor = extractor or InformationExtractor()
        self.summarizer = summarizer

    def build_context(
        self,
        user_id: str,
        session_id: str,
        user_message: str,
        stage: str = "unknown",
    ) -> dict[str, Any]:
        """构建完整的上下文"""
        user = self.db.get_or_create_user(user_id)
        profile = self.profile_manager.get_profile(user_id)

        extracted = self.extractor.extract_all(user_message)
        self._update_profile_from_extracted(user_id, extracted, profile)

        chat_history = self.db.get_recent_messages(session_id, max_turns=10)

        if self.summarizer and self.summarizer.should_summarize(chat_history):
            summary = self.summarizer.summarize(chat_history)
            self.profile_manager.update_summary(user_id, summary)

        context = {
            "user_id": user_id,
            "identity": user.get("identity") or "朋友",
            "stage": stage,
            "total_messages": user.get("total_messages", 0),
            "profile": self.profile_manager.format_for_prompt(user_id),
            "chat_history": chat_history,
            "extracted_info": extracted,
        }

        return context

    def _update_profile_from_extracted(
        self,
        user_id: str,
        extracted: dict[str, Any],
        profile: dict[str, Any],
    ) -> None:
        """从提取的信息更新用户画像"""
        if "phone" in extracted:
            self.profile_manager.update_key_info(user_id, "phone", extracted["phone"])

        if "address" in extracted:
            self.profile_manager.update_key_info(
                user_id, "address", extracted["address"]
            )

        if "preferences" in extracted:
            self.profile_manager.update_preferences(user_id, extracted["preferences"])

    def format_context_for_prompt(self, context: dict[str, Any]) -> str:
        """格式化上下文为提示词"""
        parts = [
            f"用户称呼: {context['identity']}",
            f"当前阶段: {context['stage']}",
            f"用户画像:\n{context['profile']}",
        ]

        if context.get("extracted_info"):
            parts.append(f"本次对话提取信息: {context['extracted_info']}")

        return "\n".join(parts)
