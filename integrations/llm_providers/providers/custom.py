"""Custom OpenAI-Compatible Provider Implementation.

For local LLMs (Ollama, LM Studio, vLLM, etc.) and custom endpoints
that implement the OpenAI API format.
"""

from typing import Any, Optional
import json
import httpx

from .openai import OpenAIProvider
from ..base import LLMProviderConfig


class CustomProvider(OpenAIProvider):
    """Custom OpenAI-compatible API provider (Ollama, LM Studio, vLLM, etc.)."""

    PROVIDER_ID = "custom"
    PROVIDER_NAME = "Custom Endpoint"
    DEFAULT_BASE_URL = "http://localhost:11434/v1"  # Ollama default
    SUPPORTS_STREAMING = True
    SUPPORTS_TOOLS = True
    SUPPORTS_VISION = False  # Depends on the actual endpoint
    DEFAULT_MODELS = [
        "llama3.1",
        "llama3.1:70b",
        "llama3.2",
        "mistral",
        "mistral-nemo",
        "qwen2.5",
        "codellama",
        "phi3",
        "gemma2",
    ]

    def __init__(self, config: Optional[LLMProviderConfig] = None, **kwargs):
        if config is None:
            config = LLMProviderConfig(**kwargs)
        if not config.base_url:
            config.base_url = self.DEFAULT_BASE_URL
        if not config.model:
            config.model = "llama3.1"
        # Custom endpoints often don't require API keys
        super().__init__(config)

    def _init_client(self):
        if self._client is None:
            headers = {
                "Content-Type": "application/json",
                **self.config.extra_headers,
            }
            # Only add Authorization if API key is provided
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"

            self._client = httpx.Client(
                base_url=self.config.base_url,
                headers=headers,
                timeout=self.config.timeout,
            )

    def list_models(self) -> list[dict]:
        """Fetch available models from custom endpoint."""
        try:
            self._init_client()
            # Try OpenAI-compatible /models endpoint first
            response = self._client.get("/models")
            if response.status_code == 200:
                data = response.json()
                models = []
                for model in data.get("data", []):
                    model_id = model.get("id", "")
                    models.append({"id": model_id, "provider": self.PROVIDER_ID})
                if models:
                    return models
        except Exception:
            pass

        # Try Ollama /api/tags endpoint
        try:
            # Need to get base URL without /v1
            base = self.config.base_url.rstrip("/v1")
            ollama_client = httpx.Client(base_url=base, timeout=self.config.timeout)
            response = ollama_client.get("/api/tags")
            if response.status_code == 200:
                data = response.json()
                models = []
                for model in data.get("models", []):
                    model_id = model.get("name", "")
                    models.append({"id": model_id, "provider": self.PROVIDER_ID})
                if models:
                    return models
        except Exception:
            pass

        return [{"id": m, "provider": self.PROVIDER_ID} for m in self.DEFAULT_MODELS]

    def validate_key(self) -> tuple[bool, str]:
        """Validate connection to custom endpoint."""
        try:
            self._init_client()
            # Try a simple health check
            response = self._client.get("/models")
            if response.status_code == 200:
                return True, f"Connected to {self.config.base_url}"
            else:
                return False, f"HTTP {response.status_code}: {response.text[:200]}"
        except Exception as exc:
            return False, str(exc)