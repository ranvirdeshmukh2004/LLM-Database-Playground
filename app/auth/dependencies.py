"""
Auth dependencies — JWT verification for FastAPI route protection.
Verifies the Supabase-issued JWT using the shared JWT_SECRET.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

from app.config import Settings, get_settings

logger = logging.getLogger("app.auth")


@dataclass
class AuthenticatedUser:
    """Represents a verified authenticated user from JWT claims."""
    id: str          # UUID from auth.users
    email: str
    role: str        # 'authenticated', 'anon', 'service_role'
    aud: str         # 'authenticated'

    @property
    def is_service_role(self) -> bool:
        return self.role == "service_role"


def _extract_token(request: Request) -> str:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_header[7:]  # Remove "Bearer " prefix


def _verify_jwt(token: str, jwt_secret: str) -> dict:
    """Verify and decode a Supabase JWT."""
    try:
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """
    FastAPI dependency: extract and verify the JWT from the request.
    Returns an AuthenticatedUser with the user's ID and email.
    """
    token = _extract_token(request)
    payload = _verify_jwt(token, settings.jwt_secret)

    user_id = payload.get("sub")
    email = payload.get("email", "")
    role = payload.get("role", "authenticated")
    aud = payload.get("aud", "authenticated")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing user ID",
        )

    return AuthenticatedUser(id=user_id, email=email, role=role, aud=aud)


async def get_optional_user(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Optional[AuthenticatedUser]:
    """
    Optional auth dependency: returns None if no valid token present.
    Useful for routes that work both authenticated and anonymously.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    try:
        token = auth_header[7:]
        payload = _verify_jwt(token, settings.jwt_secret)
        user_id = payload.get("sub")
        if not user_id:
            return None
        return AuthenticatedUser(
            id=user_id,
            email=payload.get("email", ""),
            role=payload.get("role", "authenticated"),
            aud=payload.get("aud", "authenticated"),
        )
    except HTTPException:
        return None
