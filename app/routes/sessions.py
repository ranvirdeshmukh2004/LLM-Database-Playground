"""
Chat session management routes.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.database import get_connection
from app.models.schemas import (
    MessageResponse,
    SessionCreate,
    SessionDetailResponse,
    SessionResponse,
    SessionUpdate,
)

logger = logging.getLogger("app.routes.sessions")
router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _row_to_session(row) -> SessionResponse:
    """Convert a DB row to SessionResponse."""
    settings = row["settings"]
    if isinstance(settings, str):
        settings = json.loads(settings)
    return SessionResponse(
        id=str(row["id"]),
        title=row["title"],
        provider=row["provider"],
        model=row["model"],
        system_prompt=row["system_prompt"],
        settings=settings or {},
        is_archived=row["is_archived"],
        message_count=row["message_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    archived: bool = False,
    limit: int = 50,
    offset: int = 0,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """List chat sessions for the authenticated user."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM public.chat_sessions
            WHERE user_id = $1 AND is_archived = $2
            ORDER BY updated_at DESC
            LIMIT $3 OFFSET $4
            """,
            uuid.UUID(user.id),
            archived,
            limit,
            offset,
        )

    return [_row_to_session(row) for row in rows]


@router.post("", response_model=SessionResponse)
async def create_session(
    body: SessionCreate,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Create a new chat session."""
    session_id = uuid.uuid4()
    settings_json = json.dumps(body.settings or {"temperature": 0.7, "max_tokens": 2048, "top_p": 0.9})

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO public.chat_sessions (id, user_id, title, provider, model, system_prompt, settings)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
            RETURNING *
            """,
            session_id,
            uuid.UUID(user.id),
            body.title or "New Chat",
            body.provider,
            body.model,
            body.system_prompt or "You are a helpful AI assistant.",
            settings_json,
        )

    return _row_to_session(row)


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Get a session with its messages."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM public.chat_sessions WHERE id = $1 AND user_id = $2",
            uuid.UUID(session_id),
            uuid.UUID(user.id),
        )

        if not row:
            raise HTTPException(404, "Session not found")

        msg_rows = await conn.fetch(
            """
            SELECT * FROM public.chat_messages
            WHERE session_id = $1
            ORDER BY created_at ASC
            """,
            uuid.UUID(session_id),
        )

    session = _row_to_session(row)
    messages = [
        MessageResponse(
            id=str(m["id"]),
            role=m["role"],
            content=m["content"],
            token_count=m["token_count"],
            latency_ms=m["latency_ms"],
            model=m["model"],
            provider=m["provider"],
            created_at=m["created_at"],
        )
        for m in msg_rows
    ]

    return SessionDetailResponse(**session.model_dump(), messages=messages)


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    body: SessionUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Update session title, prompt, settings, or archive status."""
    updates = []
    params = [uuid.UUID(session_id), uuid.UUID(user.id)]
    idx = 3

    if body.title is not None:
        updates.append(f"title = ${idx}")
        params.append(body.title)
        idx += 1

    if body.system_prompt is not None:
        updates.append(f"system_prompt = ${idx}")
        params.append(body.system_prompt)
        idx += 1

    if body.settings is not None:
        updates.append(f"settings = ${idx}::jsonb")
        params.append(json.dumps(body.settings))
        idx += 1

    if body.is_archived is not None:
        updates.append(f"is_archived = ${idx}")
        params.append(body.is_archived)
        idx += 1

    if not updates:
        raise HTTPException(400, "No fields to update")

    query = f"""
        UPDATE public.chat_sessions
        SET {', '.join(updates)}
        WHERE id = $1 AND user_id = $2
        RETURNING *
    """

    async with get_connection() as conn:
        row = await conn.fetchrow(query, *params)

    if not row:
        raise HTTPException(404, "Session not found")

    return _row_to_session(row)


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Delete a session and all its messages."""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM public.chat_sessions WHERE id = $1 AND user_id = $2",
            uuid.UUID(session_id),
            uuid.UUID(user.id),
        )

    if result == "DELETE 0":
        raise HTTPException(404, "Session not found")

    return {"status": "deleted", "id": session_id}
