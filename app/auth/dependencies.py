"""
Auth dependencies — Anonymous Browser Sessions via X-User-Id header.
Replaces the old JWT verification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings

logger = logging.getLogger("app.auth")


@dataclass
class AuthenticatedUser:
    """Represents a verified authenticated user from JWT claims."""
    id: str          # UUID from X-User-Id header
    email: str       # Anonymous
    role: str        # 'authenticated'
    aud: str         # 'authenticated'

    @property
    def is_service_role(self) -> bool:
        return self.role == "service_role"


async def get_current_user(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    """
    FastAPI dependency: extract X-User-Id from the request header.
    Returns an AuthenticatedUser with the anonymous UUID.
    """
    user_id = request.headers.get("X-User-Id")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header",
        )

    return AuthenticatedUser(
        id=user_id, 
        email="anonymous@local.host", 
        role="authenticated", 
        aud="authenticated"
    )


async def get_optional_user(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Optional[AuthenticatedUser]:
    """
    Optional auth dependency: returns None if no valid X-User-Id present.
    Useful for routes that work both authenticated and anonymously.
    """
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        return None

    return AuthenticatedUser(
        id=user_id,
        email="anonymous@local.host",
        role="authenticated",
        aud="authenticated",
    )
