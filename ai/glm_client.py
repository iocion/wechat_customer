"""GLM Coding Plan API client (OpenAI-compatible SDK)."""

from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)


class GLMClient:
    """Synchronous wrapper around the GLM chat completions API.

    Uses the ``openai`` SDK with a custom ``base_url`` pointing at the
    ZhipuAI / GLM Coding Plan endpoint.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.z.ai/api/coding/paas/v4/",
        model: str = "glm-4.5-flash",
    ) -> None:
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    def chat(
        self,
        messages: Any,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Send a chat completion request and return the assistant reply text."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content
            return content or ""
        except Exception:
            logger.exception("GLM API error")
            raise

    def chat_with_history(
        self,
        system_prompt: str,
        chat_history: list[dict[str, str]],
        user_message: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Build message list from prompt + history + new user message, then call chat()."""
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(chat_history)
        messages.append({"role": "user", "content": user_message})
        return self.chat(messages, temperature=temperature, max_tokens=max_tokens)
