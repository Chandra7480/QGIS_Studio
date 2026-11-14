"""Google Gemini Provider Implementation."""

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


class GeminiProvider(LLMProvider):
    """Google Gemini API provider (Gemini 1.5 Pro, Flash, etc.)."""

    PROVIDER_ID = "gemini"
    PROVIDER_NAME = "Google Gemini"
    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    SUPPORTS_STREAMING = True
    SUPPORTS_TOOLS = True
    SUPPORTS_VISION = True
    DEFAULT_MODELS = [
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-1.5-pro-latest",
        "gemini-1.5-flash-latest",
        "gemini-1.0-pro",
    ]

    def __init__(self, config: Optional[LLMProviderConfig] = None, **kwargs):
        if config is None:
            config = LLMProviderConfig(**kwargs)
        if not config.base_url:
            config.base_url = self.DEFAULT_BASE_URL
        if not config.model:
            config.model = "gemini-1.5-flash"
        super().__init__(config)

    def _init_client(self):
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.base_url,
                headers={
                    "Content-Type": "application/json",
                    **self.config.extra_headers,
                },
                timeout=self.config.timeout,
            )

    def _get_api_key_param(self) -> dict:
        """Get API key as query parameter for Gemini."""
        return {"key": self.config.api_key}

    def _prepare_messages(self, messages: list[LLMMessage]) -> list[dict]:
        result = []
        for msg in messages:
            if msg.role == "system":
                # Gemini handles system prompt separately
                continue
            elif msg.role == "tool":
                result.append({
                    "role": "function",
                    "parts": [{
                        "function_response": {
                            "name": msg.name,
                            "response": {"result": msg.content},
                        }
                    }]
                })
            elif msg.tool_calls:
                parts = []
                if msg.content:
                    parts.append({"text": msg.content})
                for tc in msg.tool_calls:
                    parts.append({
                        "function_call": {
                            "name": tc.name,
                            "args": tc.arguments,
                        }
                    })
                result.append({"role": "model", "parts": parts})
            else:
                result.append({
                    "role": "user" if msg.role == "user" else "model",
                    "parts": [{"text": msg.content or ""}]
                })
        return result

    def _get_system_instruction(self, messages: list[LLMMessage]) -> Optional[dict]:
        for msg in messages:
            if msg.role == "system":
                return {"parts": [{"text": msg.content}]}
        return None

    def _prepare_tools(self, tools: list[LLMTool]) -> list[dict]:
        return [{
            "function_declarations": [tool.to_gemini_format() for tool in tools]
        }]

    def _parse_response(self, response: Any) -> LLMResponse:
        data = response.json()

        content = None
        tool_calls = []

        candidates = data.get("candidates", [])
        if candidates:
            candidate = candidates[0]
            content_parts = candidate.get("content", {}).get("parts", [])

            for part in content_parts:
                if "text" in part:
                    content = part["text"]
                elif "function_call" in part:
                    fc = part["function_call"]
                    tool_calls.append(LLMToolCall(
                        id=fc.get("name", ""),  # Gemini doesn't provide IDs
                        name=fc.get("name", ""),
                        arguments=fc.get("args", {}),
                    ))

            finish_reason = candidate.get("finishReason", "STOP")
            if finish_reason == "MAX_TOKENS":
                finish_reason = "length"
            elif finish_reason == "SAFETY":
                finish_reason = "content_filter"
            else:
                finish_reason = "stop"
        else:
            finish_reason = "stop"

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            model=self.config.model,
            usage=data.get("usageMetadata", {}),
            finish_reason=finish_reason.lower(),
            raw_response=data,
            provider=self.PROVIDER_ID,
        )

    def _parse_stream_chunk(self, chunk: Any) -> Optional[LLMResponse]:
        if not chunk.strip():
            return None
        if chunk.startswith("data: "):
            chunk = chunk[6:]
        try:
            data = json.loads(chunk)
            candidates = data.get("candidates", [])
            if not candidates:
                return None

            candidate = candidates[0]
            content_parts = candidate.get("content", {}).get("parts", [])

            content = None
            tool_calls = []

            for part in content_parts:
                if "text" in part:
                    content = part["text"]
                elif "function_call" in part:
                    fc = part["function_call"]
                    tool_calls.append(LLMToolCall(
                        id=fc.get("name", ""),
                        name=fc.get("name", ""),
                        arguments=fc.get("args", {}),
                    ))

            finish_reason = candidate.get("finishReason", "")
            if finish_reason == "MAX_TOKENS":
                finish_reason = "length"
            elif finish_reason == "SAFETY":
                finish_reason = "content_filter"
            elif finish_reason:
                finish_reason = "stop"

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                model=self.config.model,
                usage=data.get("usageMetadata", {}),
                finish_reason=finish_reason.lower() if finish_reason else "",
                raw_response=data,
                provider=self.PROVIDER_ID,
            )
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _do_chat(self, params: dict, stream: bool) -> LLMResponse:
        messages = params.pop("messages")
        system_instruction = self._get_system_instruction(params.get("_original_messages", []))

        payload = {
            "contents": messages,
            "generationConfig": {
                "temperature": params.get("temperature", self.config.temperature),
                "maxOutputTokens": params.get("max_tokens", self.config.max_tokens),
                "topP": params.get("top_p", self.config.top_p),
            },
        }

        if system_instruction:
            payload["systemInstruction"] = system_instruction

        if "tools" in params:
            payload["tools"] = params["tools"]
            payload["toolConfig"] = {
                "functionCallingConfig": {
                    "mode": "AUTO" if params.get("tool_choice", "auto") == "auto" else "ANY"
                }
            }

        # Add extra params
        if self.config.extra_params:
            payload["generationConfig"].update(self.config.extra_params)

        url = f"/models/{self.config.model}:generateContent"
        if stream:
            url = f"/models/{self.config.model}:streamGenerateContent"

        try:
            response = self._client.post(
                url,
                json=payload,
                params=self._get_api_key_param(),
            )
            self._handle_error(response)
            return self._parse_response(response)
        except httpx.TimeoutException:
            raise LLMConnectionError("Request timed out", provider=self.PROVIDER_ID)
        except httpx.RequestError as exc:
            raise LLMConnectionError(f"Connection error: {exc}", provider=self.PROVIDER_ID)

    def _do_chat_stream(self, params: dict):
        # Store original messages for system instruction extraction
        params["_original_messages"] = params.get("messages", [])
        messages = params.pop("messages")
        system_instruction = self._get_system_instruction(params["_original_messages"])

        payload = {
            "contents": messages,
            "generationConfig": {
                "temperature": params.get("temperature", self.config.temperature),
                "maxOutputTokens": params.get("max_tokens", self.config.max_tokens),
                "topP": params.get("top_p", self.config.top_p),
            },
        }

        if system_instruction:
            payload["systemInstruction"] = system_instruction

        if "tools" in params:
            payload["tools"] = params["tools"]
            payload["toolConfig"] = {
                "functionCallingConfig": {
                    "mode": "AUTO" if params.get("tool_choice", "auto") == "auto" else "ANY"
                }
            }

        if self.config.extra_params:
            payload["generationConfig"].update(self.config.extra_params)

        url = f"/models/{self.config.model}:streamGenerateContent"

        try:
            with self._client.stream(
                "POST",
                url,
                json=payload,
                params=self._get_api_key_param(),
            ) as response:
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
            error_status = error_data.get("error", {}).get("status", "")
        except Exception:
            error_message = f"HTTP {response.status_code}"
            error_code = ""
            error_status = ""

        if response.status_code == 400 and "API_KEY_INVALID" in error_message:
            raise LLMAuthenticationError(error_message, provider=self.PROVIDER_ID, code=error_code, status_code=401)
        elif response.status_code == 429:
            raise LLMRateLimitError(error_message, provider=self.PROVIDER_ID, code=error_code, status_code=429)
        elif response.status_code >= 500:
            raise LLMServerError(error_message, provider=self.PROVIDER_ID, code=error_code, status_code=response.status_code)
        elif "token limit" in error_message.lower() or "context length" in error_message.lower():
            raise LLMContextLengthError(error_message, provider=self.PROVIDER_ID, code=error_code, status_code=response.status_code)
        else:
            raise LLMProviderError(error_message, provider=self.PROVIDER_ID, code=error_code, status_code=response.status_code)

    def list_models(self) -> list[dict]:
        """Fetch available models from Gemini API."""
        try:
            self._init_client()
            response = self._client.get("/models", params=self._get_api_key_param())
            self._handle_error(response)
            data = response.json()
            models = []
            for model in data.get("models", []):
                model_id = model.get("name", "").replace("models/", "")
                if "gemini" in model_id.lower():
                    models.append({"id": model_id, "provider": self.PROVIDER_ID})
            return models
        except Exception:
            return [{"id": m, "provider": self.PROVIDER_ID} for m in self.DEFAULT_MODELS]