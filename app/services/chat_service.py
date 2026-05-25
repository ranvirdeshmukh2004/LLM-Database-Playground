"""
Chat service — orchestrates provider calls, message persistence, and session management.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import AsyncGenerator

from app.database import get_connection
from app.providers.registry import get_provider
from app.services.encryption import decrypt_api_key

logger = logging.getLogger("app.services.chat")


async def get_user_api_key(user_id: str, provider: str) -> str | None:
    """Fetch and decrypt the user's API key for a given provider."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT encrypted_key FROM public.api_keys
            WHERE user_id = $1 AND provider = $2 AND is_active = TRUE
            ORDER BY updated_at DESC LIMIT 1
            """,
            uuid.UUID(user_id),
            provider,
        )

    if not row:
        return None

    try:
        return decrypt_api_key(row["encrypted_key"])
    except ValueError:
        logger.error(f"Failed to decrypt API key for user={user_id}, provider={provider}")
        return None


async def update_key_last_used(user_id: str, provider: str) -> None:
    """Update last_used_at for the user's active key."""
    try:
        async with get_connection() as conn:
            await conn.execute(
                """
                UPDATE public.api_keys SET last_used_at = NOW()
                WHERE user_id = $1 AND provider = $2 AND is_active = TRUE
                """,
                uuid.UUID(user_id),
                provider,
            )
    except Exception as e:
        logger.warning(f"Failed to update key last_used: {e}")


async def create_session(
    user_id: str,
    provider: str,
    model: str,
    title: str = "New Chat",
    system_prompt: str = "You are a helpful AI assistant.",
    settings: dict | None = None,
) -> str:
    """Create a new chat session and return its ID."""
    session_id = uuid.uuid4()
    settings_json = json.dumps(settings or {"temperature": 0.7, "max_tokens": 2048, "top_p": 0.9})

    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO public.chat_sessions (id, user_id, title, provider, model, system_prompt, settings)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
            """,
            session_id,
            uuid.UUID(user_id),
            title,
            provider,
            model,
            system_prompt,
            settings_json,
        )

    return str(session_id)


async def save_message(
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    model: str | None = None,
    provider: str | None = None,
    token_count: int | None = None,
    latency_ms: int | None = None,
    metadata: dict | None = None,
) -> str:
    """Save a chat message and return its ID."""
    msg_id = uuid.uuid4()
    metadata_json = json.dumps(metadata or {})

    async with get_connection() as conn:
        await conn.execute(
            """
            INSERT INTO public.chat_messages
                (id, session_id, user_id, role, content, model, provider, token_count, latency_ms, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::jsonb)
            """,
            msg_id,
            uuid.UUID(session_id),
            uuid.UUID(user_id),
            role,
            content,
            model,
            provider,
            token_count,
            latency_ms,
            metadata_json,
        )

    return str(msg_id)


async def auto_title_session(session_id: str, first_message: str) -> None:
    """Auto-generate session title from first user message."""
    title = first_message[:50].strip()
    if len(first_message) > 50:
        title += "..."

    async with get_connection() as conn:
        await conn.execute(
            """
            UPDATE public.chat_sessions
            SET title = $1
            WHERE id = $2 AND title = 'New Chat'
            """,
            title,
            uuid.UUID(session_id),
        )


async def stream_chat(
    user_id: str,
    session_id: str,
    provider_id: str,
    model: str,
    messages: list[dict],
    api_key: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    top_p: float = 0.9,
    **kwargs,
) -> AsyncGenerator[str, None]:
    """
    Stream a chat completion, collecting the full response for persistence.

    Yields SSE chunks and saves the complete message to DB after streaming.
    """
    provider = get_provider(provider_id)
    t0 = time.monotonic()
    full_response = []

    logger.info(
        f"CHAT STREAM: user={user_id[:8]}... provider={provider_id} "
        f"model={model} msgs={len(messages)}"
    )

    async for chunk in provider.chat_stream(
        messages=messages,
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        **kwargs,
    ):
        yield chunk

        # Collect response text for persistence
        if chunk.startswith("data: ") and chunk.strip() != "data: [DONE]":
            try:
                data = json.loads(chunk[6:])
                delta = data.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if content:
                    full_response.append(content)
            except (json.JSONDecodeError, IndexError, KeyError):
                pass

    latency_ms = round((time.monotonic() - t0) * 1000)
    response_text = "".join(full_response)

    # Save assistant message to DB
    if response_text:
        try:
            await save_message(
                session_id=session_id,
                user_id=user_id,
                role="assistant",
                content=response_text,
                model=model,
                provider=provider_id,
                latency_ms=latency_ms,
            )
            await update_key_last_used(user_id, provider_id)
        except Exception as e:
            logger.error(f"Failed to save assistant message: {e}")

    logger.info(
        f"CHAT COMPLETE: provider={provider_id} model={model} "
        f"latency={latency_ms}ms chars={len(response_text)}"
    )
