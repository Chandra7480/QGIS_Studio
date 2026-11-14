"""OpenRouter Provider Implementation.

OpenRouter provides unified access to 100+ models from various providers
through a single OpenAI-compatible API.
"""

from typing import Any, Optional
import json
import httpx

from .openai import OpenAIProvider


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter API provider (unified access to GPT, Claude, Llama, etc.)."""

    PROVIDER_ID = "openrouter"
    PROVIDER_NAME = "OpenRouter"
    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    SUPPORTS_STREAMING = True
    SUPPORTS_TOOLS = True
    SUPPORTS_VISION = True
    DEFAULT_MODELS = [
        "openai/gpt-4o",
        "openai/gpt-4o-mini",
        "anthropic/claude-3.5-sonnet",
        "anthropic/claude-3.5-haiku",
        "google/gemini-pro-1.5",
        "google/gemini-flash-1.5",
        "meta-llama/llama-3.1-405b",
        "meta-llama/llama-3.1-70b",
        "mistralai/mistral-large",
        "mistralai/mistral-nemo",
    ]

    def __init__(self, config: Optional[LLMProviderConfig] = None, **kwargs):
        if config is None:
            config = LLMProviderConfig(**kwargs)
        if not config.base_url:
            config.base_url = self.DEFAULT_BASE_URL
        if not config.model:
            config.model = "openai/gpt-4o-mini"
        # OpenRouter recommends adding these headers
        if "HTTP-Referer" not in config.extra_headers:
            config.extra_headers["HTTP-Referer"] = "https://github.com/universal-ai-gis-studio"
        if "X-Title" not in config.extra_headers:
            config.extra_headers["X-Title"] = "Universal AI GIS Studio"
        super().__init__(config)

    def _init_client(self):
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.base_url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": self.config.extra_headers.get("HTTP-Referer", "https://github.com/universal-ai-gis-studio"),
                    "X-Title": self.config.extra_headers.get("X-Title", "Universal AI GIS Studio"),
                    **{k: v for k, v in self.config.extra_headers.items() if k not in ("HTTP-Referer", "X-Title")},
                },
                timeout=self.config.timeout,
            )

    def list_models(self) -> list[dict]:
        """Fetch available models from OpenRouter API."""
        try:
            self._init_client()
            response = self._client.get("/models")
            self._handle_error(response)
            data = response.json()
            models = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                models.append({
                    "id": model_id,
                    "provider": self.PROVIDER_ID,
                    "name": model.get("name", model_id),
                    "description": model.get("description", ""),
                    "context_length": model.get("context_length", 0),
                    "pricing": model.get("pricing", {}),
                    "top_provider": model.get("top_provider", {}),
                })
            return models
        except Exception:
            return [{"id": m, "provider": self.PROVIDER_ID} for m in self.DEFAULT_MODELS]