"""
Chat routes — streaming and non-streaming chat endpoints.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.models.schemas import ChatCompletionResponse, ChatRequest
from app.services.chat_service import (
    auto_title_session,
    create_session,
    get_user_api_key,
    save_message,
    stream_chat,
)

logger = logging.getLogger("app.routes.chat")
router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
async def chat(
    body: ChatRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Send a chat message and stream the response via SSE.
    Creates a session if session_id is not provided.
    """
    # Get user's API key for the provider
    api_key = await get_user_api_key(user.id, body.provider)
    if not api_key:
        raise HTTPException(
            400,
            f"No API key found for provider '{body.provider}'. "
            "Please add your API key in Settings → API Keys."
        )

    # Create or reuse session
    session_id = body.session_id
    if not session_id:
        session_id = await create_session(
            user_id=user.id,
            provider=body.provider,
            model=body.model,
            system_prompt=body.system_prompt or "You are a helpful AI assistant.",
            settings={
                "temperature": body.temperature,
                "max_tokens": body.max_tokens,
                "top_p": body.top_p,
            },
        )

    # Save user message
    messages_dicts = [{"role": m.role, "content": m.content} for m in body.messages]
    user_msg = next((m.content for m in reversed(body.messages) if m.role == "user"), "")
    if user_msg:
        await save_message(
            session_id=session_id,
            user_id=user.id,
            role="user",
            content=user_msg,
        )
        # Auto-title session from first message
        await auto_title_session(session_id, user_msg)

    # Prepend system prompt if provided
    if body.system_prompt:
        messages_dicts.insert(0, {"role": "system", "content": body.system_prompt})

    logger.info(
        f"CHAT: user={user.id[:8]}... provider={body.provider} "
        f"model={body.model} session={session_id[:8]}..."
    )

    if body.stream:
        return StreamingResponse(
            stream_chat(
                user_id=user.id,
                session_id=session_id,
                provider_id=body.provider,
                model=body.model,
                messages=messages_dicts,
                api_key=api_key,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
                top_p=body.top_p,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Session-ID": session_id,
            },
        )
    else:
        # Non-streaming: use chat_complete
        from app.providers.registry import get_provider

        provider = get_provider(body.provider)
        result = await provider.chat_complete(
            messages=messages_dicts,
            model=body.model,
            api_key=api_key,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            top_p=body.top_p,
        )

        # Save assistant message
        await save_message(
            session_id=session_id,
            user_id=user.id,
            role="assistant",
            content=result["content"],
            model=body.model,
            provider=body.provider,
            token_count=result.get("token_count"),
            latency_ms=result.get("latency_ms"),
        )

        return ChatCompletionResponse(
            id=str(uuid.uuid4()),
            session_id=session_id,
            provider=body.provider,
            model=body.model,
            content=result["content"],
            token_count=result.get("token_count"),
            latency_ms=result.get("latency_ms"),
        )
