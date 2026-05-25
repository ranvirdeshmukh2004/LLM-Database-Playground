"""
OpenAI-compatible provider implementation.
Handles: OpenAI, OpenRouter, xAI (Grok), and any OpenAI-compatible API.

All these providers use the same request/response format:
  POST /v1/chat/completions
  Authorization: Bearer <key>
"""

from __future__ import annotations

import json
import logging
import time
from typing import AsyncGenerator

import httpx

from app.providers.base import LLMProvider

logger = logging.getLogger("app.providers.openai_compat")

# Provider-specific configurations
PROVIDER_CONFIGS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "display_name": "OpenAI",
        "extra_headers": {},
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "display_name": "OpenRouter",
        "extra_headers": {
            "HTTP-Referer": "https://ai-agent-platform.local",
            "X-Title": "AI Agent Platform",
        },
    },
    "xai": {
        "base_url": "https://api.x.ai/v1",
        "display_name": "xAI (Grok)",
        "extra_headers": {},
    },
}

TIMEOUT = httpx.Timeout(300.0, connect=15.0)


class OpenAICompatProvider(LLMProvider):
    """
    Provider for any OpenAI-compatible API.
    Covers: OpenAI, OpenRouter, xAI (Grok).
    """

    def __init__(self, provider_id: str, base_url: str | None = None):
        config = PROVIDER_CONFIGS.get(provider_id, {})
        self.provider_id = provider_id
        self.display_name = config.get("display_name", provider_id.title())
        self.base_url = base_url or config.get("base_url", "")
        self.extra_headers = config.get("extra_headers", {})

    def _build_headers(self, api_key: str) -> dict:
        """Build request headers with auth and provider-specific extras."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        return headers

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
        """Stream chat completion using OpenAI SSE format."""
        headers = self._build_headers(api_key)
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": True,
        }

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        error_msg = self._parse_error(response.status_code, body)
                        yield self._sse_error(error_msg)
                        yield self._sse_done()
                        return

                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                yield self._sse_done()
                                return
                            yield f"data: {data_str}\n\n"

        except httpx.ConnectError:
            yield self._sse_error(f"Could not connect to {self.display_name} API")
        except httpx.TimeoutException:
            yield self._sse_error(f"Request to {self.display_name} timed out")
        except Exception as e:
            logger.error(f"Stream error ({self.provider_id}): {e}")
            yield self._sse_error(str(e))

        yield self._sse_done()

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
        """Non-streaming chat completion."""
        headers = self._build_headers(api_key)
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                t0 = time.monotonic()
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                latency_ms = round((time.monotonic() - t0) * 1000)

                if resp.status_code != 200:
                    error_msg = self._parse_error(resp.status_code, resp.content)
                    raise Exception(error_msg)

                data = resp.json()
                choice = data.get("choices", [{}])[0]
                return {
                    "content": choice.get("message", {}).get("content", ""),
                    "model": data.get("model", model),
                    "token_count": data.get("usage", {}).get("total_tokens"),
                    "finish_reason": choice.get("finish_reason", "stop"),
                    "latency_ms": latency_ms,
                }

        except httpx.ConnectError:
            raise Exception(f"Could not connect to {self.display_name} API")
        except httpx.TimeoutException:
            raise Exception(f"Request to {self.display_name} timed out")

    async def test_key(self, api_key: str) -> dict:
        """Test API key by listing models."""
        headers = self._build_headers(api_key)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                t0 = time.monotonic()
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers=headers,
                )
                latency_ms = round((time.monotonic() - t0) * 1000)

                if resp.status_code == 200:
                    return {"status": "valid", "latency_ms": latency_ms}
                elif resp.status_code == 401:
                    return {"status": "invalid", "detail": "Invalid API key"}
                elif resp.status_code == 403:
                    return {"status": "invalid", "detail": "Access denied"}
                else:
                    return {"status": "error", "detail": f"HTTP {resp.status_code}"}

        except httpx.ConnectError:
            return {"status": "error", "detail": "Could not connect"}
        except httpx.TimeoutException:
            return {"status": "error", "detail": "Connection timed out"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    async def list_models(self, api_key: str) -> list[dict]:
        """List available models from the provider."""
        headers = self._build_headers(api_key)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    models = data.get("data", [])
                    return [
                        {
                            "id": m.get("id", ""),
                            "name": m.get("id", "").split("/")[-1],
                            "context": m.get("context_length"),
                        }
                        for m in models
                        if m.get("id")
                    ]
                return []
        except Exception as e:
            logger.warning(f"Failed to list models for {self.provider_id}: {e}")
            return []

    def _parse_error(self, status_code: int, body: bytes) -> str:
        """Parse error response body into a human-readable message."""
        try:
            data = json.loads(body)
            if "error" in data:
                err = data["error"]
                if isinstance(err, dict):
                    return err.get("message", str(err))
                return str(err)
            return f"HTTP {status_code}: {body.decode(errors='replace')[:200]}"
        except Exception:
            return f"HTTP {status_code}: {body.decode(errors='replace')[:200]}"
