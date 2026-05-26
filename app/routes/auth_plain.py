"""
Auth routes for DB_MODE=plain — app-managed authentication.

Same endpoints as the Supabase auth routes (/api/auth/signup, /login, etc.)
but uses bcrypt + self-signed JWTs instead of GoTrue.
The frontend doesn't need to know which mode is active.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from jose import JWTError, jwt
from pydantic import BaseModel

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.auth.plain_auth import authenticate_user, create_tokens, create_user
from app.config import Settings, get_settings
from app.database import get_connection
from app.models.schemas import AuthLoginRequest, AuthSignUpRequest, UserProfile

logger = logging.getLogger("app.routes.auth_plain")
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup")
async def signup(body: AuthSignUpRequest):
    """Register a new user (plain mode — bcrypt + self-signed JWT)."""
    try:
        user = await create_user(body.email, body.password, body.display_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    tokens = create_tokens(user["id"], user["email"])

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "user": user,
    }


@router.post("/login")
async def login(body: AuthLoginRequest):
    """Login (plain mode — verify bcrypt, return self-signed JWT)."""
    try:
        user = await authenticate_user(body.email, body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    tokens = create_tokens(user["id"], user["email"])

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_in": tokens["expires_in"],
        "user": user,
    }


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh_token_endpoint(
    body: RefreshRequest,
    settings: Settings = Depends(get_settings),
):
    """Refresh an expired access token (plain mode)."""
    if not body.refresh_token:
        raise HTTPException(400, "refresh_token is required")

    try:
        payload = jwt.decode(
            body.refresh_token,
            settings.jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except JWTError:
        raise HTTPException(401, "Invalid or expired refresh token")

    user_id = payload.get("sub")
    email = payload.get("email", "")

    if not user_id:
        raise HTTPException(401, "Invalid refresh token")

    tokens = create_tokens(user_id, email)
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "expires_in": tokens["expires_in"],
    }


@router.post("/logout")
async def logout(user: AuthenticatedUser = Depends(get_current_user)):
    """Logout (plain mode — stateless, just acknowledge)."""
    return {"status": "logged_out"}


@router.get("/me", response_model=UserProfile)
async def get_me(user: AuthenticatedUser = Depends(get_current_user)):
    """Get current user's profile (plain mode)."""
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
