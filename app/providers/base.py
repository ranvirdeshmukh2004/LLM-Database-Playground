"""
Abstract base class for LLM providers.
All provider implementations must inherit from this.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import AsyncGenerator


class LLMProvider(ABC):
    """
    Base interface for all LLM providers.

    Each provider implementation handles:
      - API authentication (different header styles)
      - Request format translation
      - Response streaming (SSE)
      - Error handling specific to the provider
    """

    provider_id: str
    display_name: str

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        model: str,
        api_key: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.9,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat completion as Server-Sent Events (SSE).

        Yields SSE-formatted strings:
            data: {"choices":[{"delta":{"content":"..."}}]}

        Final yield:
            data: [DONE]
        """
        ...

    @abstractmethod
    async def chat_complete(
        self,
        messages: list[dict],
        model: str,
        api_key: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.9,
        **kwargs,
    ) -> dict:
        """
        Non-streaming chat completion.

        Returns:
            {
                "content": "response text",
                "model": "model-id",
                "token_count": 123,
                "finish_reason": "stop"
            }
        """
        ...

    @abstractmethod
    async def test_key(self, api_key: str) -> dict:
        """
        Test if an API key is valid.

        Returns:
            {"status": "valid"|"invalid"|"error", "detail": "..."}
        """
        ...

    @abstractmethod
    async def list_models(self, api_key: str) -> list[dict]:
        """
        List available models for this provider.

        Returns:
            [{"id": "model-id", "name": "Display Name", "context": 128000}, ...]
        """
        ...

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _sse_chunk(content: str, finish_reason: str | None = None) -> str:
        """Format a content chunk as an SSE data line."""
        data = {
            "choices": [{
                "delta": {"content": content} if content else {},
                "index": 0,
                "finish_reason": finish_reason,
            }]
        }
        return f"data: {json.dumps(data)}\n\n"

    @staticmethod
    def _sse_done() -> str:
        """Format the SSE stream termination signal."""
        return "data: [DONE]\n\n"

    @staticmethod
    def _sse_error(message: str) -> str:
        """Format an error as an SSE data line."""
        return f"data: {json.dumps({'error': message})}\n\n"
