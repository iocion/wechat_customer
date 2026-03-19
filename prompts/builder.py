"""提示词构建器"""

from __future__ import annotations

from typing import Any

from prompts.templates import PromptTemplates


class PromptBuilder:
    """构建提示词"""

    def __init__(self):
        self.templates = PromptTemplates()

    def build_for_stage(self, stage: str, context: dict[str, Any]) -> str:
        """根据阶段构建提示词"""
        user_context = self._format_context(context)

        template_map = {
            "pre_sales": self.templates.PRE_SALES,
            "mid_sales": self.templates.MID_SALES,
            "post_sales": self.templates.POST_SALES,
        }

        template = template_map.get(stage, self.templates.GENERAL_CHAT)
        return template.format(user_context=user_context)

    def build_stage_analysis(self, message: str, current_stage: str) -> str:
        """构建阶段分析提示词"""
        return self.templates.STAGE_ANALYSIS.format(
            message=message,
            current_stage=current_stage,
        )

    def _format_context(self, context: dict[str, Any]) -> str:
        """格式化上下文"""
        parts = []

        identity = context.get("identity", "朋友")
        parts.append(f"- 称呼: {identity}")

        profile = context.get("profile", "")
        if profile:
            parts.append(f"- 用户画像: {profile}")

        extracted = context.get("extracted_info", {})
        if extracted:
            parts.append(f"- 本次提取信息: {extracted}")

        return "\n".join(parts)
