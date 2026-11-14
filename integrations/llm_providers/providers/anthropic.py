"""Anthropic Provider Implementation."""

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


class AnthropicProvider(LLMProvider):
    """Anthropic API provider (Claude 3.5 Sonnet, Opus, Haiku, etc.)."""

    PROVIDER_ID = "anthropic"
    PROVIDER_NAME = "Anthropic"
    DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
    SUPPORTS_STREAMING = True
    SUPPORTS_TOOLS = True
    SUPPORTS_VISION = True
    DEFAULT_MODELS = [
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]

    def __init__(self, config: Optional[LLMProviderConfig] = None, **kwargs):
        if config is None:
            config = LLMProviderConfig(**kwargs)
        if not config.base_url:
            config.base_url = self.DEFAULT_BASE_URL
        if not config.model:
            config.model = "claude-3-5-sonnet-20241022"
        super().__init__(config)

    def _init_client(self):
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.base_url,
                headers={
                    "x-api-key": self.config.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                    **self.config.extra_headers,
                },
                timeout=self.config.timeout,
            )

    def _prepare_messages(self, messages: list[LLMMessage]) -> list[dict]:
        result = []
        system_content = None

        for msg in messages:
            if msg.role == "system":
                system_content = msg.content
                continue

            msg_dict = {"role": msg.role}
            if msg.role == "tool":
                msg_dict["role"] = "user"
                msg_dict["content"] = [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                ]
            elif msg.tool_calls:
                # Assistant with tool calls
                content = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                msg_dict["content"] = content
            else:
                msg_dict["content"] = msg.content or ""

            result.append(msg_dict)

        return result, system_content

    def _prepare_tools(self, tools: list[LLMTool]) -> list[dict]:
        return [tool.to_anthropic_format() for tool in tools]

    def _parse_response(self, response: Any) -> LLMResponse:
        data = response.json()

        content = None
        tool_calls = []

        for block in data.get("content", []):
            if block["type"] == "text":
                content = block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(LLMToolCall(
                    id=block["id"],
                    name=block["name"],
                    arguments=block["input"],
                ))

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            model=data.get("model", self.config.model),
            usage=data.get("usage", {}),
            finish_reason=data.get("stop_reason", "end_turn"),
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
            event_type = data.get("type", "")

            if event_type == "content_block_delta":
                delta = data.get("delta", {})
                if delta.get("type") == "text_delta":
                    return LLMResponse(
                        content=delta.get("text", ""),
                        tool_calls=[],
                        model=self.config.model,
                        usage={},
                        finish_reason="",
                        raw_response=data,
                        provider=self.PROVIDER_ID,
                    )
            elif event_type == "content_block_start":
                block = data.get("content_block", {})
                if block.get("type") == "tool_use":
                    return LLMResponse(
                        content=None,
                        tool_calls=[LLMToolCall(
                            id=block.get("id", ""),
                            name=block.get("name", ""),
                            arguments=block.get("input", {}),
                        )],
                        model=self.config.model,
                        usage={},
                        finish_reason="",
                        raw_response=data,
                        provider=self.PROVIDER_ID,
                    )
            elif event_type == "message_delta":
                return LLMResponse(
                    content=None,
                    tool_calls=[],
                    model=self.config.model,
                    usage=data.get("usage", {}),
                    finish_reason=data.get("delta", {}).get("stop_reason", ""),
                    raw_response=data,
                    provider=self.PROVIDER_ID,
                )
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _do_chat(self, params: dict, stream: bool) -> LLMResponse:
        # Anthropic separates messages and system prompt
        messages = params.pop("messages")
        system = params.pop("system", None)

        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": params.get("max_tokens", self.config.max_tokens),
            "temperature": params.get("temperature", self.config.temperature),
            "top_p": params.get("top_p", self.config.top_p),
            "stream": stream,
        }

        if system:
            payload["system"] = system

        if "tools" in params:
            payload["tools"] = params["tools"]
            payload["tool_choice"] = params.get("tool_choice", {"type": "auto"})

        # Add extra params
        payload.update(self.config.extra_params)

        try:
            response = self._client.post("/messages", json=payload)
            self._handle_error(response)
            return self._parse_response(response)
        except httpx.TimeoutException:
            raise LLMConnectionError("Request timed out", provider=self.PROVIDER_ID)
        except httpx.RequestError as exc:
            raise LLMConnectionError(f"Connection error: {exc}", provider=self.PROVIDER_ID)

    def _do_chat_stream(self, params: dict):
        messages = params.pop("messages")
        system = params.pop("system", None)

        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": params.get("max_tokens", self.config.max_tokens),
            "temperature": params.get("temperature", self.config.temperature),
            "top_p": params.get("top_p", self.config.top_p),
            "stream": True,
        }

        if system:
            payload["system"] = system

        if "tools" in params:
            payload["tools"] = params["tools"]
            payload["tool_choice"] = params.get("tool_choice", {"type": "auto"})

        payload.update(self.config.extra_params)

        try:
            with self._client.stream("POST", "/messages", json=payload) as response:
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
            error_type = error_data.get("error", {}).get("type", "")
        except Exception:
            error_message = f"HTTP {response.status_code}"
            error_type = ""

        if response.status_code == 401:
            raise LLMAuthenticationError(error_message, provider=self.PROVIDER_ID, code=error_type, status_code=401)
        elif response.status_code == 429:
            raise LLMRateLimitError(error_message, provider=self.PROVIDER_ID, code=error_type, status_code=429)
        elif response.status_code >= 500:
            raise LLMServerError(error_message, provider=self.PROVIDER_ID, code=error_type, status_code=response.status_code)
        elif "context length" in error_message.lower() or "token limit" in error_message.lower():
            raise LLMContextLengthError(error_message, provider=self.PROVIDER_ID, code=error_type, status_code=response.status_code)
        else:
            raise LLMProviderError(error_message, provider=self.PROVIDER_ID, code=error_type, status_code=response.status_code)

    def list_models(self) -> list[dict]:
        """Anthropic doesn't have a models endpoint, return defaults."""
        return [{"id": m, "provider": self.PROVIDER_ID} for m in self.DEFAULT_MODELS]