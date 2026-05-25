"""
Anthropic (Claude) provider implementation.

Uses the Anthropic Messages API which has a different format from OpenAI:
  - POST /v1/messages
  - Auth via x-api-key header (not Bearer)
  - Different request/response structure
  - Different streaming format (event types)
"""

from __future__ import annotations

import json
import logging
import time
from typing import AsyncGenerator

import httpx

from app.providers.base import LLMProvider

logger = logging.getLogger("app.providers.anthropic")

BASE_URL = "https://api.anthropic.com/v1"
API_VERSION = "2023-06-01"
TIMEOUT = httpx.Timeout(300.0, connect=15.0)


class AnthropicProvider(LLMProvider):
    """Provider for Anthropic's Claude models (Messages API)."""

    provider_id = "anthropic"
    display_name = "Anthropic (Claude)"

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or BASE_URL

    def _build_headers(self, api_key: str) -> dict:
        return {
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
            "Content-Type": "application/json",
        }

    def _convert_messages(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        """
        Convert OpenAI-style messages to Anthropic format.
        Extracts system prompt separately (Anthropic uses a top-level 'system' field).
        """
        system_prompt = None
        converted = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_prompt = content
            elif role in ("user", "assistant"):
                converted.append({"role": role, "content": content})

        # Anthropic requires messages to start with 'user'
        if converted and converted[0]["role"] == "assistant":
            converted.insert(0, {"role": "user", "content": "(continuing conversation)"})

        return system_prompt, converted

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
        """Stream chat using Anthropic's SSE format, converted to OpenAI format."""
        headers = self._build_headers(api_key)
        system_prompt, converted_msgs = self._convert_messages(messages)

        payload = {
            "model": model,
            "messages": converted_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/messages",
                    json=payload,
                    headers=headers,
                ) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        error_msg = self._parse_error(response.status_code, body)
                        yield self._sse_error(error_msg)
                        yield self._sse_done()
                        return

                    # Anthropic uses different event types:
                    # content_block_delta → delta.text
                    # message_stop → done
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            try:
                                event = json.loads(data_str)
                                event_type = event.get("type", "")

                                if event_type == "content_block_delta":
                                    text = event.get("delta", {}).get("text", "")
                                    if text:
                                        yield self._sse_chunk(text)

                                elif event_type == "message_stop":
                                    yield self._sse_chunk("", finish_reason="stop")
                                    yield self._sse_done()
                                    return

                                elif event_type == "error":
                                    error = event.get("error", {})
                                    yield self._sse_error(
                                        error.get("message", "Unknown error")
                                    )
                                    yield self._sse_done()
                                    return

                            except json.JSONDecodeError:
                                continue

        except httpx.ConnectError:
            yield self._sse_error("Could not connect to Anthropic API")
        except httpx.TimeoutException:
            yield self._sse_error("Request to Anthropic timed out")
        except Exception as e:
            logger.error(f"Anthropic stream error: {e}")
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
        """Non-streaming chat completion via Anthropic Messages API."""
        headers = self._build_headers(api_key)
        system_prompt, converted_msgs = self._convert_messages(messages)

        payload = {
            "model": model,
            "messages": converted_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                t0 = time.monotonic()
                resp = await client.post(
                    f"{self.base_url}/messages",
                    json=payload,
                    headers=headers,
                )
                latency_ms = round((time.monotonic() - t0) * 1000)

                if resp.status_code != 200:
                    error_msg = self._parse_error(resp.status_code, resp.content)
                    raise Exception(error_msg)

                data = resp.json()
                # Anthropic returns content as array of blocks
                content_blocks = data.get("content", [])
                content = "".join(
                    block.get("text", "")
                    for block in content_blocks
                    if block.get("type") == "text"
                )

                usage = data.get("usage", {})
                return {
                    "content": content,
                    "model": data.get("model", model),
                    "token_count": (
                        usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                    ),
                    "finish_reason": data.get("stop_reason", "end_turn"),
                    "latency_ms": latency_ms,
                }

        except httpx.ConnectError:
            raise Exception("Could not connect to Anthropic API")
        except httpx.TimeoutException:
            raise Exception("Request to Anthropic timed out")

    async def test_key(self, api_key: str) -> dict:
        """Test key by sending a minimal request."""
        headers = self._build_headers(api_key)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                t0 = time.monotonic()
                # Anthropic doesn't have /models endpoint, so we do a tiny request
                resp = await client.post(
                    f"{self.base_url}/messages",
                    json={
                        "model": "claude-haiku-3-5-20241022",
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 1,
                    },
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
                    body = resp.json()
                    detail = body.get("error", {}).get("message", f"HTTP {resp.status_code}")
                    return {"status": "error", "detail": detail}

        except Exception as e:
            return {"status": "error", "detail": str(e)}

    async def list_models(self, api_key: str) -> list[dict]:
        """Return hardcoded Claude models (Anthropic has no /models endpoint)."""
        return [
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "context": 200000},
            {"id": "claude-haiku-3-5-20241022", "name": "Claude 3.5 Haiku", "context": 200000},
            {"id": "claude-opus-4-20250514", "name": "Claude Opus 4", "context": 200000},
        ]

    def _parse_error(self, status_code: int, body: bytes) -> str:
        try:
            data = json.loads(body)
            error = data.get("error", {})
            if isinstance(error, dict):
                return error.get("message", f"HTTP {status_code}")
            return str(error)
        except Exception:
            return f"HTTP {status_code}: {body.decode(errors='replace')[:200]}"
