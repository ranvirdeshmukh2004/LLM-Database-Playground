"""
Custom / Self-hosted provider implementation.
Handles self-hosted models on EC2 instances using the existing Playground API format.

Supports two API types:
  - "custom": POST /chat  {message, max_tokens, temperature, top_p}
  - "openai": Standard OpenAI-compatible /v1/chat/completions
"""

from __future__ import annotations

import json
import logging
import time
from typing import AsyncGenerator

import httpx

from app.providers.base import LLMProvider

logger = logging.getLogger("app.providers.custom")

TIMEOUT = httpx.Timeout(300.0, connect=15.0)


class CustomProvider(LLMProvider):
    """
    Provider for self-hosted models (existing Playground EC2 fleet).
    The base_url is user-configurable per model.
    """

    provider_id = "custom"
    display_name = "Self-Hosted"

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or "http://localhost:8080"

    def _build_user_message(self, messages: list[dict]) -> str:
        """Convert chat messages to a single string for custom API."""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"[System]: {content}")
            elif role == "user":
                parts.append(f"[User]: {content}")
            elif role == "assistant":
                parts.append(f"[Assistant]: {content}")
        return "\n".join(parts)

    async def chat_stream(
        self,
        messages: list[dict],
        model: str,
        api_key: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 512,
        top_p: float = 0.9,
        base_url: str | None = None,
        endpoint: str = "/chat",
        api_type: str = "custom",
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream from self-hosted model, converting to SSE format."""
        url = base_url or self.base_url

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                if api_type == "openai":
                    # OpenAI-compatible self-hosted (e.g., vLLM, TGI)
                    payload = {
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "top_p": top_p,
                        "stream": True,
                    }
                    headers = {}
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"

                    async with client.stream(
                        "POST",
                        f"{url}/v1/chat/completions",
                        json=payload,
                        headers=headers,
                    ) as response:
                        if response.status_code != 200:
                            body = await response.aread()
                            yield self._sse_error(f"HTTP {response.status_code}: {body.decode(errors='replace')[:200]}")
                            yield self._sse_done()
                            return

                        async for line in response.aiter_lines():
                            if line.startswith("data:"):
                                yield f"{line}\n\n"

                else:
                    # Custom API format (Playground agent_api.py)
                    user_message = self._build_user_message(messages)
                    payload = {
                        "message": user_message,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "top_p": top_p,
                    }

                    resp = await client.post(
                        f"{url}{endpoint}",
                        json=payload,
                    )

                    if resp.status_code != 200:
                        yield self._sse_error(f"HTTP {resp.status_code}: {resp.text[:200]}")
                        yield self._sse_done()
                        return

                    try:
                        data = resp.json()
                    except Exception:
                        data = {"response": resp.text}

                    response_text = (
                        data.get("response") or data.get("text") or data.get("content")
                        or data.get("message") or data.get("output")
                        or data.get("generated_text") or str(data)
                    )

                    # Simulate streaming by chunking the response
                    chunk_size = 4
                    for i in range(0, len(response_text), chunk_size):
                        chunk = response_text[i:i + chunk_size]
                        yield self._sse_chunk(chunk)

                    yield self._sse_chunk("", finish_reason="stop")

        except httpx.ConnectError:
            yield self._sse_error(f"Could not connect to model server at {url}")
        except httpx.TimeoutException:
            yield self._sse_error("Request to model server timed out")
        except Exception as e:
            logger.error(f"Custom provider stream error: {e}")
            yield self._sse_error(str(e))

        yield self._sse_done()

    async def chat_complete(
        self,
        messages: list[dict],
        model: str,
        api_key: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 512,
        top_p: float = 0.9,
        base_url: str | None = None,
        endpoint: str = "/chat",
        api_type: str = "custom",
        **kwargs,
    ) -> dict:
        """Non-streaming completion from self-hosted model."""
        url = base_url or self.base_url

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                t0 = time.monotonic()

                if api_type == "openai":
                    payload = {
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "top_p": top_p,
                        "stream": False,
                    }
                    headers = {}
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"

                    resp = await client.post(
                        f"{url}/v1/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    latency_ms = round((time.monotonic() - t0) * 1000)

                    if resp.status_code != 200:
                        raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

                    data = resp.json()
                    choice = data.get("choices", [{}])[0]
                    return {
                        "content": choice.get("message", {}).get("content", ""),
                        "model": model,
                        "token_count": data.get("usage", {}).get("total_tokens"),
                        "finish_reason": choice.get("finish_reason", "stop"),
                        "latency_ms": latency_ms,
                    }
                else:
                    user_message = self._build_user_message(messages)
                    resp = await client.post(
                        f"{url}{endpoint}",
                        json={"message": user_message, "max_tokens": max_tokens},
                    )
                    latency_ms = round((time.monotonic() - t0) * 1000)

                    if resp.status_code != 200:
                        raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")

                    data = resp.json()
                    response_text = (
                        data.get("response") or data.get("text") or data.get("content")
                        or data.get("message") or data.get("output") or str(data)
                    )
                    return {
                        "content": response_text,
                        "model": model,
                        "token_count": data.get("tokens_used"),
                        "finish_reason": "stop",
                        "latency_ms": latency_ms,
                    }

        except httpx.ConnectError:
            raise Exception(f"Could not connect to model server at {url}")
        except httpx.TimeoutException:
            raise Exception("Model server request timed out")

    async def test_key(self, api_key: str) -> dict:
        """Test connection to self-hosted model (key might be empty)."""
        url = self.base_url
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                t0 = time.monotonic()
                resp = await client.get(f"{url}/health")
                latency_ms = round((time.monotonic() - t0) * 1000)

                if resp.status_code == 200:
                    return {"status": "valid", "latency_ms": latency_ms}
                return {"status": "error", "detail": f"HTTP {resp.status_code}"}
        except httpx.ConnectError:
            return {"status": "error", "detail": "Could not connect"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    async def list_models(self, api_key: str) -> list[dict]:
        """Self-hosted models are configured manually, return empty."""
        return []
