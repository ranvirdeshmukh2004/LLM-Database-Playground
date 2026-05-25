"""
Provider routes — list available providers and their models.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.database import get_connection
from app.models.schemas import ProviderModel, ProviderResponse
from app.providers.registry import get_provider, list_provider_ids

logger = logging.getLogger("app.routes.providers")
router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("", response_model=list[ProviderResponse])
async def list_providers(user: AuthenticatedUser = Depends(get_current_user)):
    """List all available providers with user's key status."""
    # Fetch providers from DB
    async with get_connection() as conn:
        provider_rows = await conn.fetch(
            "SELECT * FROM public.providers WHERE is_active = TRUE ORDER BY id"
        )
        # Check which providers the user has keys for
        key_rows = await conn.fetch(
            """
            SELECT DISTINCT provider FROM public.api_keys
            WHERE user_id = $1 AND is_active = TRUE
            """,
            uuid.UUID(user.id),
        )

    user_providers = {row["provider"] for row in key_rows}

    result = []
    for row in provider_rows:
        models_data = row["models"]
        if isinstance(models_data, str):
            models_data = json.loads(models_data)

        models = [
            ProviderModel(
                id=m.get("id", ""),
                name=m.get("name", ""),
                context=m.get("context"),
            )
            for m in (models_data or [])
        ]

        result.append(ProviderResponse(
            id=row["id"],
            name=row["name"],
            api_type=row["api_type"],
            models=models,
            is_active=row["is_active"],
            has_user_key=row["id"] in user_providers,
        ))

    return result


@router.get("/{provider_id}/models")
async def get_provider_models(
    provider_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Get models for a specific provider.
    First checks DB for static models, then optionally queries the provider API.
    """
    # Get from DB first
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT models FROM public.providers WHERE id = $1",
            provider_id,
        )

    if row:
        models_data = row["models"]
        if isinstance(models_data, str):
            models_data = json.loads(models_data)
        return {"provider": provider_id, "models": models_data or []}

    return {"provider": provider_id, "models": []}
