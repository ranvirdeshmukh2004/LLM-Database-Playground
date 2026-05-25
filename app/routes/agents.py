"""
Agent CRUD + chat routes.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.database import get_connection
from app.models.schemas import AgentCreate, AgentResponse, AgentUpdate, ChatRequest
from app.services.agent_service import chat_with_agent

logger = logging.getLogger("app.routes.agents")
router = APIRouter(prefix="/api/agents", tags=["agents"])


def _row_to_agent(row) -> AgentResponse:
    settings = row["settings"]
    if isinstance(settings, str):
        settings = json.loads(settings)
    tools = row["tools"]
    if isinstance(tools, str):
        tools = json.loads(tools)
    return AgentResponse(
        id=str(row["id"]),
        name=row["name"],
        description=row["description"],
        system_prompt=row["system_prompt"],
        provider=row["provider"],
        model=row["model"],
        settings=settings or {},
        tools=tools or [],
        is_public=row["is_public"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("", response_model=list[AgentResponse])
async def list_agents(user: AuthenticatedUser = Depends(get_current_user)):
    """List agents owned by or visible to the authenticated user."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM public.agents
            WHERE user_id = $1 OR is_public = TRUE
            ORDER BY updated_at DESC
            """,
            uuid.UUID(user.id),
        )
    return [_row_to_agent(row) for row in rows]


@router.post("", response_model=AgentResponse)
async def create_agent(
    body: AgentCreate,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Create a new agent configuration."""
    agent_id = uuid.uuid4()
    settings_json = json.dumps(body.settings or {"temperature": 0.7, "max_tokens": 2048})
    tools_json = json.dumps(body.tools or [])

    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO public.agents
                (id, user_id, name, description, system_prompt, provider, model, settings, tools, is_public)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10)
            RETURNING *
            """,
            agent_id,
            uuid.UUID(user.id),
            body.name,
            body.description,
            body.system_prompt,
            body.provider,
            body.model,
            settings_json,
            tools_json,
            body.is_public,
        )

    logger.info(f"Agent created: {body.name} by user={user.id[:8]}...")
    return _row_to_agent(row)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Get an agent by ID."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM public.agents
            WHERE id = $1 AND (user_id = $2 OR is_public = TRUE)
            """,
            uuid.UUID(agent_id),
            uuid.UUID(user.id),
        )

    if not row:
        raise HTTPException(404, "Agent not found")

    return _row_to_agent(row)


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    body: AgentUpdate,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Update an agent configuration."""
    updates = []
    params = [uuid.UUID(agent_id), uuid.UUID(user.id)]
    idx = 3

    for field in ["name", "description", "system_prompt", "provider", "model"]:
        value = getattr(body, field, None)
        if value is not None:
            updates.append(f"{field} = ${idx}")
            params.append(value)
            idx += 1

    if body.settings is not None:
        updates.append(f"settings = ${idx}::jsonb")
        params.append(json.dumps(body.settings))
        idx += 1

    if body.tools is not None:
        updates.append(f"tools = ${idx}::jsonb")
        params.append(json.dumps(body.tools))
        idx += 1

    if body.is_public is not None:
        updates.append(f"is_public = ${idx}")
        params.append(body.is_public)
        idx += 1

    if not updates:
        raise HTTPException(400, "No fields to update")

    query = f"""
        UPDATE public.agents
        SET {', '.join(updates)}
        WHERE id = $1 AND user_id = $2
        RETURNING *
    """

    async with get_connection() as conn:
        row = await conn.fetchrow(query, *params)

    if not row:
        raise HTTPException(404, "Agent not found or not owned by you")

    return _row_to_agent(row)


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Delete an agent."""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM public.agents WHERE id = $1 AND user_id = $2",
            uuid.UUID(agent_id),
            uuid.UUID(user.id),
        )

    if result == "DELETE 0":
        raise HTTPException(404, "Agent not found")

    return {"status": "deleted", "id": agent_id}


@router.post("/{agent_id}/chat")
async def agent_chat(
    agent_id: str,
    body: ChatRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Chat through an agent with its preset configuration."""
    try:
        messages_dicts = [{"role": m.role, "content": m.content} for m in body.messages]
        session_id, stream_gen = await chat_with_agent(
            agent_id=agent_id,
            user_id=user.id,
            messages=messages_dicts,
            session_id=body.session_id,
        )

        return StreamingResponse(
            stream_gen,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "X-Session-ID": session_id,
            },
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
