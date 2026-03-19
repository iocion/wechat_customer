"""对话摘要器"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ai.glm_client import GLMClient

logger = logging.getLogger(__name__)


class ConversationSummarizer:
    """生成对话摘要"""

    def __init__(self, glm_client: GLMClient):
        self.glm_client = glm_client

    def summarize(self, chat_history: list[dict[str, str]], max_turns: int = 20) -> str:
        """生成对话摘要"""
        if len(chat_history) <= max_turns:
            return ""

        messages_to_summarize = chat_history[:-max_turns]
        summary = self._generate_summary(messages_to_summarize)

        recent_messages = chat_history[-max_turns:]
        return f"{summary}\n\n[最近对话继续]"

    def _generate_summary(self, messages: list[dict[str, str]]) -> str:
        """调用 AI 生成摘要"""
        content = "\n".join([f"{m['role']}: {m['content']}" for m in messages])

        prompt = f"""请将以下客服对话总结为100字以内的摘要，保留关键信息（用户需求、问题、订单信息等）：

{content}

摘要："""

        try:
            result = self.glm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200,
            )
            return result.strip()
        except Exception:
            logger.exception("Summary generation failed")
            return ""

    def should_summarize(
        self, chat_history: list[dict[str, str]], threshold: int = 20
    ) -> bool:
        """判断是否需要生成摘要"""
        return len(chat_history) > threshold
