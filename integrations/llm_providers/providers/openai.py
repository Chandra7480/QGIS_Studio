"""OpenAI Provider Implementation."""

from typing import Any, Optional
import json
import httpx

from ..base import (
    LLMProvider,
    LLMProviderConfig,
    LLMMessage,
    LLMTool,
    LLMResponse,
    LLMToolCall,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMContextLengthError,
    LLMConnectionError,
    LLMServerError,
)


class OpenAIProvider(LLMProvider):
    """OpenAI API provider (GPT-4, GPT-4o, GPT-3.5, etc.)."""

    PROVIDER_ID = "openai"
    PROVIDER_NAME = "OpenAI"
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    SUPPORTS_STREAMING = True
    SUPPORTS_TOOLS = True
    SUPPORTS_VISION = True
    DEFAULT_MODELS = [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "o1-preview",
        "o1-mini",
    ]

    def __init__(self, config: Optional[LLMProviderConfig] = None, **kwargs):
        if config is None:
            config = LLMProviderConfig(**kwargs)
        if not config.base_url:
            config.base_url = self.DEFAULT_BASE_URL
        if not config.model:
            config.model = "gpt-4o-mini"
        super().__init__(config)

    def _init_client(self):
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.base_url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                    **self.config.extra_headers,
                },
                timeout=self.config.timeout,
            )

    def _prepare_messages(self, messages: list[LLMMessage]) -> list[dict]:
        result = []
        for msg in messages:
            msg_dict = msg.to_dict()
            # Handle tool calls in assistant messages
            if msg.role == "assistant" and msg.tool_calls:
                msg_dict["tool_calls"] = msg.tool_calls
            result.append(msg_dict)
        return result

    def _prepare_tools(self, tools: list[LLMTool]) -> list[dict]:
        return [tool.to_openai_format() for tool in tools]

    def _parse_response(self, response: Any) -> LLMResponse:
        data = response.json()
        choice = data["choices"][0]
        message = choice["message"]

        tool_calls = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                tool_calls.append(LLMToolCall(
                    id=tc["id"],
                    name=tc["function"]["name"],
                    arguments=json.loads(tc["function"]["arguments"]),
                ))

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            model=data.get("model", self.config.model),
            usage=data.get("usage", {}),
            finish_reason=choice.get("finish_reason", "stop"),
            raw_response=data,
            provider=self.PROVIDER_ID,
        )

    def _parse_stream_chunk(self, chunk: Any) -> Optional[LLMResponse]:
        if not chunk.strip() or chunk.strip() == "data: [DONE]":
            return None
        if chunk.startswith("data: "):
            chunk = chunk[6:]
        try:
            data = json.loads(chunk)
            choice = data["choices"][0]
            delta = choice.get("delta", {})

            tool_calls = []
            if delta.get("tool_calls"):
                for tc in delta["tool_calls"]:
                    if tc.get("function", {}).get("arguments"):
                        tool_calls.append(LLMToolCall(
                            id=tc.get("id", ""),
                            name=tc["function"].get("name", ""),
                            arguments=json.loads(tc["function"]["arguments"]),
                        ))

            return LLMResponse(
                content=delta.get("content"),
                tool_calls=tool_calls,
                model=data.get("model", self.config.model),
                usage={},
                finish_reason=choice.get("finish_reason", "stop"),
                raw_response=data,
                provider=self.PROVIDER_ID,
            )
        except (json.JSONDecodeError, KeyError, IndexError):
            return None

    def _do_chat(self, params: dict, stream: bool) -> LLMResponse:
        try:
            response = self._client.post(
                "/chat/completions",
                json={**params, "stream": stream},
            )
            self._handle_error(response)
            return self._parse_response(response)
        except httpx.TimeoutException:
            raise LLMConnectionError("Request timed out", provider=self.PROVIDER_ID)
        except httpx.RequestError as exc:
            raise LLMConnectionError(f"Connection error: {exc}", provider=self.PROVIDER_ID)

    def _do_chat_stream(self, params: dict):
        try:
            with self._client.stream("POST", "/chat/completions", json={**params, "stream": True}) as response:
                self._handle_error(response)
                for line in response.iter_lines():
                    if line:
                        parsed = self._parse_stream_chunk(line)
                        if parsed:
                            yield parsed
        except httpx.TimeoutException:
            raise LLMConnectionError("Request timed out", provider=self.PROVIDER_ID)
        except httpx.RequestError as exc:
            raise LLMConnectionError(f"Connection error: {exc}", provider=self.PROVIDER_ID)

    def _handle_error(self, response: httpx.Response):
        if response.status_code == 200:
            return

        try:
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", "Unknown error")
            error_code = error_data.get("error", {}).get("code", "")
        except Exception:
            error_message = f"HTTP {response.status_code}"
            error_code = ""

        if response.status_code == 401:
            raise LLMAuthenticationError(error_message, provider=self.PROVIDER_ID, code=error_code, status_code=401)
        elif response.status_code == 429:
            raise LLMRateLimitError(error_message, provider=self.PROVIDER_ID, code=error_code, status_code=429)
        elif response.status_code >= 500:
            raise LLMServerError(error_message, provider=self.PROVIDER_ID, code=error_code, status_code=response.status_code)
        elif "context length" in error_message.lower() or "token limit" in error_message.lower():
            raise LLMContextLengthError(error_message, provider=self.PROVIDER_ID, code=error_code, status_code=response.status_code)
        else:
            raise LLMProviderError(error_message, provider=self.PROVIDER_ID, code=error_code, status_code=response.status_code)

    def list_models(self) -> list[dict]:
        """Fetch available models from OpenAI API."""
        try:
            self._init_client()
            response = self._client.get("/models")
            self._handle_error(response)
            data = response.json()
            models = []
            for model in data.get("data", []):
                model_id = model.get("id", "")
                if any(model_id.startswith(prefix) for prefix in ["gpt-", "o1-", "text-embedding-"]):
                    models.append({"id": model_id, "provider": self.PROVIDER_ID, "owned_by": model.get("owned_by", "openai")})
            return models
        except Exception:
            # Fall back to default models
            return [{"id": m, "provider": self.PROVIDER_ID} for m in self.DEFAULT_MODELS]