"""上下文注入器"""

from __future__ import annotations

from typing import Any


class ContextInjector:
    """将上下文注入到提示词中"""

    def inject(self, system_prompt: str, context: dict[str, Any]) -> str:
        """注入上下文到系统提示词"""
        user_context = self._format_context(context)
        return system_prompt.replace("{user_context}", user_context)

    def _format_context(self, context: dict[str, Any]) -> str:
        """格式化上下文"""
        parts = []

        identity = context.get("identity", "朋友")
        parts.append(f"- 称呼: {identity}")

        stage = context.get("stage", "unknown")
        parts.append(f"- 当前阶段: {stage}")

        profile = context.get("profile", "")
        if profile:
            parts.append(f"- 用户画像:\n{profile}")

        total_messages = context.get("total_messages", 0)
        if total_messages > 0:
            parts.append(f"- 历史消息数: {total_messages}")

        extracted = context.get("extracted_info", {})
        if extracted:
            parts.append(f"- 本次提取信息: {extracted}")

        return "\n".join(parts)
