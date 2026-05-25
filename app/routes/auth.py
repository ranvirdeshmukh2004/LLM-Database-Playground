"""
Auth routes — proxy sign-up/login/logout to Supabase GoTrue.
Calls GoTrue directly (not through Kong) to avoid API key issues.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.config import Settings, get_settings
from app.database import get_connection
from app.models.schemas import AuthLoginRequest, AuthSignUpRequest, UserProfile

logger = logging.getLogger("app.routes.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])

TIMEOUT = httpx.Timeout(10.0)

# GoTrue is called directly — not through Kong — to avoid apikey issues
GOTRUE_URL = "http://supabase-auth:9999"


@router.post("/signup")
async def signup(
    body: AuthSignUpRequest,
    settings: Settings = Depends(get_settings),
):
    """Register a new user via Supabase GoTrue."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{GOTRUE_URL}/signup",
                json={
                    "email": body.email,
                    "password": body.password,
                    "data": {"display_name": body.display_name or body.email.split("@")[0]},
                },
                headers={
                    "Content-Type": "application/json",
                },
            )

            if resp.status_code not in (200, 201):
                data = resp.json()
                detail = data.get("msg") or data.get("error_description") or data.get("message", "Signup failed")
                raise HTTPException(status_code=resp.status_code, detail=detail)

            data = resp.json()
            return {
                "access_token": data.get("access_token", ""),
                "refresh_token": data.get("refresh_token", ""),
                "user": {
                    "id": data.get("user", {}).get("id", ""),
                    "email": data.get("user", {}).get("email", body.email),
                },
            }
    except httpx.ConnectError:
        raise HTTPException(502, "Could not connect to auth service")


@router.post("/login")
async def login(
    body: AuthLoginRequest,
    settings: Settings = Depends(get_settings),
):
    """Login via Supabase GoTrue and get JWT tokens."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{GOTRUE_URL}/token?grant_type=password",
                json={
                    "email": body.email,
                    "password": body.password,
                },
                headers={
                    "Content-Type": "application/json",
                },
            )

            if resp.status_code != 200:
                data = resp.json()
                detail = data.get("error_description") or data.get("msg") or "Login failed"
                raise HTTPException(status_code=400, detail=detail)

            data = resp.json()
            return {
                "access_token": data.get("access_token", ""),
                "refresh_token": data.get("refresh_token", ""),
                "expires_in": data.get("expires_in", 3600),
                "user": data.get("user", {}),
            }
    except httpx.ConnectError:
        raise HTTPException(502, "Could not connect to auth service")


@router.post("/refresh")
async def refresh_token(
    settings: Settings = Depends(get_settings),
    refresh_token: str = "",
):
    """Refresh an expired access token."""
    if not refresh_token:
        raise HTTPException(400, "refresh_token is required")

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{GOTRUE_URL}/token?grant_type=refresh_token",
                json={"refresh_token": refresh_token},
                headers={
                    "Content-Type": "application/json",
                },
            )

            if resp.status_code != 200:
                raise HTTPException(401, "Token refresh failed")

            data = resp.json()
            return {
                "access_token": data.get("access_token", ""),
                "refresh_token": data.get("refresh_token", ""),
                "expires_in": data.get("expires_in", 3600),
            }
    except httpx.ConnectError:
        raise HTTPException(502, "Could not connect to auth service")


@router.post("/logout")
async def logout(
    user: AuthenticatedUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """Logout / invalidate the current session."""
    # Supabase handles session invalidation on the client side
    # This endpoint is a no-op but can be extended
    return {"status": "logged_out"}


@router.get("/me", response_model=UserProfile)
async def get_me(user: AuthenticatedUser = Depends(get_current_user)):
    """Get current user's profile."""
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM public.profiles WHERE id = $1",
            __import__("uuid").UUID(user.id),
        )

    if not row:
        return UserProfile(id=user.id, email=user.email)

    return UserProfile(
        id=str(row["id"]),
        email=user.email,
        display_name=row["display_name"],
        avatar_url=row["avatar_url"],
        preferences=row["preferences"] or {},
        created_at=row["created_at"],
    )
