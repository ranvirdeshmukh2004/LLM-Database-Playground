"""
Pydantic schemas for API request/response models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
# Auth
# ═══════════════════════════════════════════════════════════════

class AuthSignUpRequest(BaseModel):
    email: str
    password: str = Field(min_length=6)
    display_name: Optional[str] = None


class AuthLoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict


class UserProfile(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    preferences: dict = {}
    created_at: Optional[datetime] = None


# ═══════════════════════════════════════════════════════════════
# API Keys
# ═══════════════════════════════════════════════════════════════

class APIKeyCreate(BaseModel):
    provider: str = Field(description="Provider ID: openrouter, anthropic, xai, openai, custom")
    api_key: str = Field(min_length=1, description="The actual API key (will be encrypted)")
    key_name: str = Field(default="default", description="Label for this key")


class APIKeyResponse(BaseModel):
    id: str
    provider: str
    key_name: str
    key_preview: str  # e.g., "sk-or-...abc123"
    is_active: bool
    last_used_at: Optional[datetime] = None
    created_at: datetime


class APIKeyTestResult(BaseModel):
    provider: str
    status: str  # "valid", "invalid", "error"
    detail: Optional[str] = None
    latency_ms: Optional[int] = None


# ═══════════════════════════════════════════════════════════════
# Chat
# ═══════════════════════════════════════════════════════════════

class ChatMessage(BaseModel):
    role: str = Field(description="'user', 'assistant', or 'system'")
    content: str


class ChatRequest(BaseModel):
    session_id: Optional[str] = None  # If None, creates new session
    provider: str
    model: str
    messages: list[ChatMessage]
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=1, le=200000)
    top_p: float = Field(default=0.9, ge=0, le=1)
    system_prompt: Optional[str] = None
    stream: bool = True


class ChatCompletionResponse(BaseModel):
    id: str
    session_id: str
    provider: str
    model: str
    content: str
    token_count: Optional[int] = None
    latency_ms: Optional[int] = None


# ═══════════════════════════════════════════════════════════════
# Sessions
# ═══════════════════════════════════════════════════════════════

class SessionCreate(BaseModel):
    title: Optional[str] = "New Chat"
    provider: str
    model: str
    system_prompt: Optional[str] = "You are a helpful AI assistant."
    settings: Optional[dict] = None


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    system_prompt: Optional[str] = None
    settings: Optional[dict] = None
    is_archived: Optional[bool] = None


class SessionResponse(BaseModel):
    id: str
    title: str
    provider: str
    model: str
    system_prompt: str
    settings: dict
    is_archived: bool
    message_count: int
    created_at: datetime
    updated_at: datetime


class SessionDetailResponse(SessionResponse):
    messages: list[MessageResponse] = []


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    token_count: Optional[int] = None
    latency_ms: Optional[int] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    created_at: datetime


# ═══════════════════════════════════════════════════════════════
# Agents
# ═══════════════════════════════════════════════════════════════

class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None
    system_prompt: str = Field(min_length=1)
    provider: str
    model: str
    settings: Optional[dict] = None
    tools: Optional[list] = None
    is_public: bool = False


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    settings: Optional[dict] = None
    tools: Optional[list] = None
    is_public: Optional[bool] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    system_prompt: str
    provider: str
    model: str
    settings: dict
    tools: list
    is_public: bool
    created_at: datetime
    updated_at: datetime


# ═══════════════════════════════════════════════════════════════
# Providers
# ═══════════════════════════════════════════════════════════════

class ProviderModel(BaseModel):
    id: str
    name: str
    context: Optional[int] = None


class ProviderResponse(BaseModel):
    id: str
    name: str
    api_type: str
    models: list[ProviderModel]
    is_active: bool
    has_user_key: bool = False  # Whether the current user has a key for this provider
