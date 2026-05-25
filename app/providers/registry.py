"""
Provider registry — factory for creating provider instances.
Maps provider IDs to their implementations.
"""

from __future__ import annotations

import logging

from app.providers.base import LLMProvider
from app.providers.openai_compat import OpenAICompatProvider
from app.providers.anthropic import AnthropicProvider
from app.providers.custom import CustomProvider

logger = logging.getLogger("app.providers.registry")

# ── Provider registry ─────────────────────────────────────────
# Maps provider_id → class constructor
_PROVIDERS: dict[str, type | callable] = {
    "openai": lambda: OpenAICompatProvider("openai"),
    "openrouter": lambda: OpenAICompatProvider("openrouter"),
    "xai": lambda: OpenAICompatProvider("xai"),
    "anthropic": lambda: AnthropicProvider(),
    "custom": lambda: CustomProvider(),
}

# Cache instantiated providers
_instances: dict[str, LLMProvider] = {}


def get_provider(provider_id: str) -> LLMProvider:
    """
    Get a provider instance by ID.

    Supported providers:
        - "openai"     → OpenAI API
        - "openrouter" → OpenRouter (multi-model gateway)
        - "xai"        → xAI Grok
        - "anthropic"  → Anthropic Claude
        - "custom"     → Self-hosted models

    Raises ValueError if the provider ID is not registered.
    """
    if provider_id in _instances:
        return _instances[provider_id]

    factory = _PROVIDERS.get(provider_id)
    if factory is None:
        raise ValueError(
            f"Unknown provider: '{provider_id}'. "
            f"Available: {list(_PROVIDERS.keys())}"
        )

    instance = factory()
    _instances[provider_id] = instance
    logger.info(f"Provider initialized: {provider_id}")
    return instance


def list_provider_ids() -> list[str]:
    """Return all registered provider IDs."""
    return list(_PROVIDERS.keys())


def register_provider(provider_id: str, factory: callable) -> None:
    """
    Register a new provider at runtime.
    Allows future extensibility without modifying this file.

    Example:
        register_provider("mistral", lambda: OpenAICompatProvider("mistral", "https://api.mistral.ai/v1"))
    """
    _PROVIDERS[provider_id] = factory
    # Clear cached instance if re-registering
    _instances.pop(provider_id, None)
    logger.info(f"Provider registered: {provider_id}")
