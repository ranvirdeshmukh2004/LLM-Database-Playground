"""
Agent service — execute chat through agent configurations.
Agents are user-defined presets with custom system prompts, models, and settings.
"""

from __future__ import annotations

import json
import logging
import uuid

from app.database import get_connection
from app.services.chat_service import (
    create_session,
    get_user_api_key,
    save_message,
    stream_chat,
)

logger = logging.getLogger("app.services.agent")


async def get_agent(agent_id: str, user_id: str) -> dict | None:
    """Fetch an agent by ID, respecting ownership and public visibility."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT * FROM public.agents
            WHERE id = $1 AND (user_id = $2 OR is_public = TRUE)
            """,
            uuid.UUID(agent_id),
            uuid.UUID(user_id),
        )

    if not row:
        return None

    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "name": row["name"],
        "description": row["description"],
        "system_prompt": row["system_prompt"],
        "provider": row["provider"],
        "model": row["model"],
        "settings": json.loads(row["settings"]) if isinstance(row["settings"], str) else row["settings"],
        "tools": json.loads(row["tools"]) if isinstance(row["tools"], str) else row["tools"],
        "is_public": row["is_public"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def chat_with_agent(
    agent_id: str,
    user_id: str,
    messages: list[dict],
    session_id: str | None = None,
):
    """
    Execute a chat through an agent configuration.
    Creates a session if needed and streams the response.
    """
    agent = await get_agent(agent_id, user_id)
    if not agent:
        raise ValueError(f"Agent not found: {agent_id}")

    # Get user's API key for the agent's provider
    api_key = await get_user_api_key(user_id, agent["provider"])
    if not api_key:
        raise ValueError(
            f"No API key found for provider '{agent['provider']}'. "
            "Please add your API key in Settings → API Keys."
        )

    # Create session if not provided
    if not session_id:
        settings = agent.get("settings", {})
        session_id = await create_session(
            user_id=user_id,
            provider=agent["provider"],
            model=agent["model"],
            title=f"Agent: {agent['name']}",
            system_prompt=agent["system_prompt"],
            settings=settings,
        )

    # Prepend system prompt from agent config
    full_messages = [
        {"role": "system", "content": agent["system_prompt"]},
        *messages,
    ]

    # Save user message
    user_msg = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    if user_msg:
        await save_message(
            session_id=session_id,
            user_id=user_id,
            role="user",
            content=user_msg,
        )

    settings = agent.get("settings", {})

    return session_id, stream_chat(
        user_id=user_id,
        session_id=session_id,
        provider_id=agent["provider"],
        model=agent["model"],
        messages=full_messages,
        api_key=api_key,
        temperature=settings.get("temperature", 0.7),
        max_tokens=settings.get("max_tokens", 2048),
        top_p=settings.get("top_p", 0.9),
    )
