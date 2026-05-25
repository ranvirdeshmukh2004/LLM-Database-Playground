"""
API key management routes — CRUD for encrypted user API keys.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.database import get_connection
from app.models.schemas import APIKeyCreate, APIKeyResponse, APIKeyTestResult
from app.providers.registry import get_provider
from app.services.encryption import decrypt_api_key, encrypt_api_key, mask_api_key

logger = logging.getLogger("app.routes.api_keys")
router = APIRouter(prefix="/api/keys", tags=["api-keys"])


@router.get("", response_model=list[APIKeyResponse])
async def list_keys(user: AuthenticatedUser = Depends(get_current_user)):
    """List all API keys for the authenticated user (masked)."""
    async with get_connection() as conn:
        rows = await conn.fetch(
            """
            SELECT id, provider, key_name, encrypted_key, is_active, last_used_at, created_at
            FROM public.api_keys
            WHERE user_id = $1
            ORDER BY provider, key_name
            """,
            uuid.UUID(user.id),
        )

    keys = []
    for row in rows:
        # Decrypt just for masking preview
        try:
            plaintext = decrypt_api_key(row["encrypted_key"])
            preview = mask_api_key(plaintext)
        except Exception:
            preview = "***decryption error***"

        keys.append(APIKeyResponse(
            id=str(row["id"]),
            provider=row["provider"],
            key_name=row["key_name"],
            key_preview=preview,
            is_active=row["is_active"],
            last_used_at=row["last_used_at"],
            created_at=row["created_at"],
        ))

    return keys


@router.post("", response_model=APIKeyResponse)
async def create_or_update_key(
    body: APIKeyCreate,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Add or update an API key for a provider.
    If a key with the same provider + key_name exists, it's updated.
    """
    encrypted = encrypt_api_key(body.api_key)
    key_id = uuid.uuid4()

    async with get_connection() as conn:
        # Upsert: insert or update on (user_id, provider, key_name)
        row = await conn.fetchrow(
            """
            INSERT INTO public.api_keys (id, user_id, provider, key_name, encrypted_key)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id, provider, key_name)
            DO UPDATE SET encrypted_key = $5, is_active = TRUE, updated_at = NOW()
            RETURNING id, provider, key_name, is_active, last_used_at, created_at
            """,
            key_id,
            uuid.UUID(user.id),
            body.provider,
            body.key_name,
            encrypted,
        )

    preview = mask_api_key(body.api_key)
    logger.info(f"API key saved: user={user.id[:8]}... provider={body.provider}")

    return APIKeyResponse(
        id=str(row["id"]),
        provider=row["provider"],
        key_name=row["key_name"],
        key_preview=preview,
        is_active=row["is_active"],
        last_used_at=row["last_used_at"],
        created_at=row["created_at"],
    )


@router.delete("/{key_id}")
async def delete_key(
    key_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Delete an API key."""
    async with get_connection() as conn:
        result = await conn.execute(
            "DELETE FROM public.api_keys WHERE id = $1 AND user_id = $2",
            uuid.UUID(key_id),
            uuid.UUID(user.id),
        )

    if result == "DELETE 0":
        raise HTTPException(404, "API key not found")

    logger.info(f"API key deleted: user={user.id[:8]}... key={key_id[:8]}...")
    return {"status": "deleted", "id": key_id}


@router.post("/{key_id}/test", response_model=APIKeyTestResult)
async def test_key(
    key_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Test if an API key is valid by making a lightweight provider call."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            """
            SELECT provider, encrypted_key FROM public.api_keys
            WHERE id = $1 AND user_id = $2
            """,
            uuid.UUID(key_id),
            uuid.UUID(user.id),
        )

    if not row:
        raise HTTPException(404, "API key not found")

    try:
        plaintext = decrypt_api_key(row["encrypted_key"])
    except ValueError:
        return APIKeyTestResult(provider=row["provider"], status="error", detail="Decryption failed")

    try:
        provider = get_provider(row["provider"])
        result = await provider.test_key(plaintext)
        return APIKeyTestResult(
            provider=row["provider"],
            status=result["status"],
            detail=result.get("detail"),
            latency_ms=result.get("latency_ms"),
        )
    except ValueError as e:
        return APIKeyTestResult(provider=row["provider"], status="error", detail=str(e))
