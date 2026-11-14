"""Universal AI GIS Studio — LLM Provider Base Classes.

Abstract base class and data structures for LLM provider implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
import json


@dataclass
class LLMMessage:
    """A message in the conversation."""
    role: str  # "system", "user", "assistant", "tool"
    content: Optional[str] = None
    name: Optional[str] = None  # For tool messages
    tool_call_id: Optional[str] = None  # For tool responses
    tool_calls: list = field(default_factory=list)  # For assistant tool calls
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for API calls."""
        result = {"role": self.role}
        if self.content is not None:
            result["content"] = self.content
        if self.name:
            result["name"] = self.name
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        return result

    @classmethod
    def system(cls, content: str) -> "LLMMessage":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "LLMMessage":
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: Optional[str] = None, tool_calls: list = None) -> "LLMMessage":
        return cls(role="assistant", content=content, tool_calls=tool_calls or [])

    @classmethod
    def tool(cls, tool_call_id: str, content: str, name: str = None) -> "LLMMessage":
        return cls(role="tool", content=content, tool_call_id=tool_call_id, name=name)


@dataclass
class LLMTool:
    """A tool/function definition for function calling."""
    name: str
    description: str
    parameters: dict  # JSON Schema
    namespace: Optional[str] = None  # For MCP tool namespacing

    def to_openai_format(self) -> dict:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }

    def to_anthropic_format(self) -> dict:
        """Convert to Anthropic tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }

    def to_gemini_format(self) -> dict:
        """Convert to Gemini function calling format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class LLMToolCall:
    """A tool call from the model."""
    id: str
    name: str
    arguments: dict
    namespace: Optional[str] = None

    def to_openai_format(self) -> dict:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": json.dumps(self.arguments),
            }
        }


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: Optional[str] = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    model: str = ""
    usage: dict = field(default_factory=dict)  # prompt_tokens, completion_tokens, total_tokens
    finish_reason: str = "stop"
    raw_response: Any = None
    provider: str = ""

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "tool_calls": [tc.to_openai_format() for tc in self.tool_calls],
            "model": self.model,
            "usage": self.usage,
            "finish_reason": self.finish_reason,
            "provider": self.provider,
        }


@dataclass
class LLMProviderConfig:
    """Configuration for an LLM provider."""
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: int = 60
    max_retries: int = 3
    extra_headers: dict = field(default_factory=dict)
    extra_params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "extra_headers": self.extra_headers,
            "extra_params": self.extra_params,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LLMProviderConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    # Provider identifier
    PROVIDER_ID: str = ""
    PROVIDER_NAME: str = ""
    DEFAULT_BASE_URL: str = ""
    SUPPORTS_STREAMING: bool = True
    SUPPORTS_TOOLS: bool = True
    SUPPORTS_VISION: bool = False
    DEFAULT_MODELS: list[str] = []

    def __init__(self, config: Optional[LLMProviderConfig] = None, **kwargs):
        self.config = config or LLMProviderConfig(**kwargs)
        self._client = None
        self._async_client = None

    @abstractmethod
    def _init_client(self):
        """Initialize the provider's HTTP client."""
        pass

    @abstractmethod
    def _prepare_messages(self, messages: list[LLMMessage]) -> list[dict]:
        """Convert internal messages to provider-specific format."""
        pass

    @abstractmethod
    def _prepare_tools(self, tools: list[LLMTool]) -> list[dict]:
        """Convert internal tools to provider-specific format."""
        pass

    @abstractmethod
    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse provider response into standard format."""
        pass

    @abstractmethod
    def _parse_stream_chunk(self, chunk: Any) -> Optional[LLMResponse]:
        """Parse a streaming chunk into standard format."""
        pass

    def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMTool] = None,
        stream: bool = False,
        **kwargs
    ) -> LLMResponse:
        """Send a chat completion request."""
        self._init_client()
        prepared_messages = self._prepare_messages(messages)
        prepared_tools = self._prepare_tools(tools) if tools else None

        # Merge config with kwargs
        params = {
            "model": self.config.model,
            "messages": prepared_messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "top_p": kwargs.get("top_p", self.config.top_p),
            "frequency_penalty": kwargs.get("frequency_penalty", self.config.frequency_penalty),
            "presence_penalty": kwargs.get("presence_penalty", self.config.presence_penalty),
        }

        if prepared_tools:
            params["tools"] = prepared_tools
            params["tool_choice"] = kwargs.get("tool_choice", "auto")

        # Add extra params from config
        params.update(self.config.extra_params)

        return self._do_chat(params, stream)

    @abstractmethod
    def _do_chat(self, params: dict, stream: bool) -> LLMResponse:
        """Execute the chat request."""
        pass

    def chat_stream(
        self,
        messages: list[LLMMessage],
        tools: list[LLMTool] = None,
        **kwargs
    ):
        """Stream chat completion response."""
        if not self.SUPPORTS_STREAMING:
            # Fall back to non-streaming
            response = self.chat(messages, tools, stream=False, **kwargs)
            yield response
            return

        self._init_client()
        prepared_messages = self._prepare_messages(messages)
        prepared_tools = self._prepare_tools(tools) if tools else None

        params = {
            "model": self.config.model,
            "messages": prepared_messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "top_p": kwargs.get("top_p", self.config.top_p),
            "stream": True,
        }

        if prepared_tools:
            params["tools"] = prepared_tools
            params["tool_choice"] = kwargs.get("tool_choice", "auto")

        params.update(self.config.extra_params)

        yield from self._do_chat_stream(params)

    @abstractmethod
    def _do_chat_stream(self, params: dict):
        """Execute streaming chat request."""
        pass

    def list_models(self) -> list[dict]:
        """List available models for this provider."""
        return [{"id": model, "provider": self.PROVIDER_ID} for model in self.DEFAULT_MODELS]

    def validate_key(self) -> tuple[bool, str]:
        """Validate the API key by making a test request."""
        try:
            test_msg = [LLMMessage.user("Hello")]
            response = self.chat(test_msg, stream=False)
            return True, f"Connected successfully. Model: {response.model}"
        except Exception as exc:
            return False, str(exc)

    def get_default_model(self) -> str:
        """Get the default model for this provider."""
        return self.config.model or (self.DEFAULT_MODELS[0] if self.DEFAULT_MODELS else "")

    def set_model(self, model: str):
        """Set the active model."""
        self.config.model = model

    def update_config(self, **kwargs):
        """Update provider configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    def __init__(self, message: str, provider: str = "", code: str = "", status_code: int = 0):
        super().__init__(message)
        self.provider = provider
        self.code = code
        self.status_code = status_code


class LLMAuthenticationError(LLMProviderError):
    """Authentication failed (invalid API key)."""
    pass


class LLMRateLimitError(LLMProviderError):
    """Rate limit exceeded."""
    pass


class LLMContextLengthError(LLMProviderError):
    """Context length exceeded."""
    pass


class LLMConnectionError(LLMProviderError):
    """Connection error."""
    pass


class LLMServerError(LLMProviderError):
    """Server error (5xx)."""
    pass