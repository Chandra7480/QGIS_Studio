"""Universal AI GIS Studio — LLM Provider Integrations.

Unified abstraction for multiple LLM providers with support for:
- OpenAI (GPT-4, GPT-3.5, etc.)
- Anthropic (Claude 3.5 Sonnet, Opus, Haiku)
- Google Gemini (Gemini 1.5 Pro, Flash)
- OpenRouter (unified access to 100+ models)
- Custom OpenAI-compatible endpoints

Features:
- Streaming responses
- Tool/function calling (for GIS tools via MCP)
- Model listing
- API key validation
- Error handling with retries
"""

from .base import LLMProvider, LLMMessage, LLMResponse, LLMTool, LLMToolCall
from .providers.openai import OpenAIProvider
from .providers.anthropic import AnthropicProvider
from .providers.gemini import GeminiProvider
from .providers.openrouter import OpenRouterProvider
from .providers.custom import CustomProvider

__all__ = [
    "LLMProvider",
    "LLMMessage",
    "LLMResponse",
    "LLMTool",
    "LLMToolCall",
    "OpenAIProvider",
    "AnthropicProvider",
    "GeminiProvider",
    "OpenRouterProvider",
    "CustomProvider",
    "get_provider",
    "list_providers",
]

# Provider registry
_PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "openrouter": OpenRouterProvider,
    "custom": CustomProvider,
}

_PROVIDER_METADATA = {
    "openai": {
        "name": "OpenAI",
        "description": "GPT-4, GPT-4o, GPT-3.5 Turbo and other OpenAI models",
        "default_base_url": "https://api.openai.com/v1",
        "requires_api_key": True,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
    },
    "anthropic": {
        "name": "Anthropic",
        "description": "Claude 3.5 Sonnet, Opus, Haiku and other Anthropic models",
        "default_base_url": "https://api.anthropic.com/v1",
        "requires_api_key": True,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
    },
    "gemini": {
        "name": "Google Gemini",
        "description": "Gemini 1.5 Pro, Flash and other Google models",
        "default_base_url": "https://generativelanguage.googleapis.com/v1beta",
        "requires_api_key": True,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
    },
    "openrouter": {
        "name": "OpenRouter",
        "description": "Unified access to 100+ models (GPT, Claude, Llama, etc.)",
        "default_base_url": "https://openrouter.ai/api/v1",
        "requires_api_key": True,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": True,
    },
    "custom": {
        "name": "Custom Endpoint",
        "description": "Any OpenAI-compatible API endpoint (local LLMs, proxies, etc.)",
        "default_base_url": "http://localhost:11434/v1",
        "requires_api_key": False,
        "supports_streaming": True,
        "supports_tools": True,
        "supports_vision": False,
    },
}


def get_provider(provider_id: str, **kwargs) -> LLMProvider:
    """Create an LLM provider instance by ID."""
    if provider_id not in _PROVIDERS:
        raise ValueError(f"Unknown provider: {provider_id}. Available: {list(_PROVIDERS.keys())}")
    return _PROVIDERS[provider_id](**kwargs)


def list_providers() -> list[dict]:
    """List all available providers with metadata."""
    return [
        {"id": pid, **meta}
        for pid, meta in _PROVIDER_METADATA.items()
    ]


def get_provider_metadata(provider_id: str) -> dict:
    """Get metadata for a specific provider."""
    if provider_id not in _PROVIDER_METADATA:
        raise ValueError(f"Unknown provider: {provider_id}")
    return _PROVIDER_METADATA[provider_id]