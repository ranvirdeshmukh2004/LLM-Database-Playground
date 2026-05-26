"""
Plain auth module — app-managed authentication for DB_MODE=plain.

Handles user registration and login WITHOUT Supabase GoTrue.
Uses bcrypt for password hashing and python-jose for JWT signing.
JWTs are signed with the same JWT_SECRET so the existing
get_current_user dependency works unchanged.
"""

from __future__ import annotations

import logging
import time
import uuid

from jose import jwt
from passlib.hash import bcrypt

from app.config import get_settings
from app.database import get_connection

logger = logging.getLogger("app.auth.plain")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.verify(password, hashed)


def create_tokens(user_id: str, email: str, role: str = "authenticated") -> dict:
    """
    Create access + refresh JWTs signed with JWT_SECRET.

    The token format matches GoTrue's output so the frontend
    and get_current_user dependency work without changes.
    """
    settings = get_settings()
    now = int(time.time())

    access_payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "aud": "authenticated",
        "iss": "app-plain-auth",
        "iat": now,
        "exp": now + 3600,  # 1 hour
    }

    refresh_payload = {
        "sub": user_id,
        "email": email,
        "type": "refresh",
        "iat": now,
        "exp": now + 7 * 24 * 3600,  # 7 days
    }

    access_token = jwt.encode(access_payload, settings.jwt_secret, algorithm="HS256")
    refresh_token = jwt.encode(refresh_payload, settings.jwt_secret, algorithm="HS256")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": 3600,
    }


async def create_user(email: str, password: str, display_name: str | None = None) -> dict:
    """
    Create a new user in app_users table.
    Returns user dict with id and email.
    """
    user_id = uuid.uuid4()
    pw_hash = hash_password(password)
    name = display_name or email.split("@")[0]

    async with get_connection() as conn:
        # Check if email already exists
        existing = await conn.fetchrow(
            "SELECT id FROM public.app_users WHERE email = $1", email
        )
        if existing:
            raise ValueError("User already registered")

        await conn.execute(
            """
            INSERT INTO public.app_users (id, email, password_hash, display_name)
            VALUES ($1, $2, $3, $4)
            """,
            user_id, email, pw_hash, name,
        )

        # Also create a profile row (mirrors GoTrue's on_auth_user_created trigger)
        await conn.execute(
            """
            INSERT INTO public.profiles (id, display_name)
            VALUES ($1, $2)
            ON CONFLICT (id) DO NOTHING
            """,
            user_id, name,
        )

    logger.info(f"User created: {email} (plain mode)")
    return {"id": str(user_id), "email": email}


async def authenticate_user(email: str, password: str) -> dict:
    """
    Verify credentials against app_users table.
    Returns user dict with id and email.
    Raises ValueError if credentials are invalid.
    """
    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, password_hash FROM public.app_users WHERE email = $1",
            email,
        )

    if not row:
        raise ValueError("Invalid login credentials")

    if not verify_password(password, row["password_hash"]):
        raise ValueError("Invalid login credentials")

    return {"id": str(row["id"]), "email": row["email"]}
