"""Universal AI GIS Studio — Configuration system.

Reads/writes platform settings backed by the SQLite `app_settings` table.
Provides typed accessors with defaults. Never stores API keys in plaintext;
credentials are handled by the Security module (OS credential manager).
"""

import json
import os
from typing import Any, Optional

from .exceptions import ConfigurationError
from .logging import get_logger

logger = get_logger("config")


class Config:
    """In-memory configuration cache backed by persistent storage."""

    DEFAULTS = {
        "app_name": "Universal AI GIS Studio",
        "app_version": "1.0.0",
        "qgis_install_path": r"C:\Program Files\QGIS 4.2.3",
        "qgis_python_exe": r"C:\Program Files\QGIS 4.2.3\apps\Python312\python.exe",
        "bridge_host": "127.0.0.1",
        "bridge_port": 8765,
        "bridge_auth_token": "",  # set at runtime; not stored plaintext long-term
        "mcp_stdio_enabled": True,
        "mcp_http_enabled": True,
        "mcp_http_port": 8766,
        "log_level": "INFO",
        "log_dir": "",
        "data_dir": "",
        "max_background_workers": 2,
        "job_timeout_seconds": 300,
        "screenshot_interval_seconds": 5,
        "cache_limit_mb": 256,
        "temp_cleanup_enabled": True,
        "emergency_stop_enabled": True,
        "default_ai_host": "opencode",
        "default_api_provider": "",
        "ai_image_capability_detection": True,
        # --- OpenCode Harness Configuration ---
        "opencode_host": "127.0.0.1",
        "opencode_port": 8080,
        "opencode_api_key": "",
        "opencode_enabled": True,
        # --- Codex Configuration ---
        "codex_config_json": "{}",
        "codex_enabled": True,
        # --- MCP Server Configuration ---
        "mcp_servers": "[]",  # JSON array of server configs: [{"name": "", "transport": "stdio|http", "command": "", "args": [], "url": "", "headers": {}}]
        # --- WebSocket Streaming Configuration ---
        "ws_host": "127.0.0.1",
        "ws_port": 8767,
        "ws_enabled": True,
        # --- LLM Provider Configuration ---
        "llm_active_provider": "openai",  # openai, anthropic, gemini, openrouter, custom
        "llm_providers": "{}",  # JSON object with provider configs
        "llm_model_presets": "{}",  # JSON object with model presets per provider
        "llm_default_system_prompt": "You are an expert GIS analyst and QGIS automation specialist. Help users with spatial analysis, mapping, geoprocessing, and GIS workflows using the available tools.",
        "llm_temperature": 0.7,
        "llm_max_tokens": 4096,
        "llm_top_p": 1.0,
        "llm_stream_responses": True,
        "llm_show_token_usage": True,
        # --- Version Control Info ---
        "git_version": "",
        "git_commit_hash": "",
        "git_branch": "",
        "build_date": "",
        "build_number": "",
    }

    def __init__(self, storage=None):
        self._storage = storage
        self._values = dict(self.DEFAULTS)
        self._loaded = False

    def load(self) -> None:
        """Load settings from storage (overrides defaults)."""
        if self._storage is None:
            self._loaded = True
            return
        try:
            rows = self._storage.get_all_settings()
            for key, value in rows.items():
                self._values[key] = self._coerce(key, value)
        except Exception as exc:  # pragma: no cover - storage may not exist yet
            logger.warning("Failed to load config from storage: %s", exc)
        self._loaded = True
        logger.info("Configuration loaded (%d settings)", len(self._values))

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def set(self, key: str, value: Any, persist: bool = True) -> None:
        self._values[key] = value
        if persist and self._storage is not None:
            try:
                self._storage.set_setting(key, self._serialize(value))
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to persist setting %s: %s", key, exc)

    def update(self, mapping: dict, persist: bool = True) -> None:
        for key, value in mapping.items():
            self.set(key, value, persist=persist)

    @staticmethod
    def _coerce(key: str, value: Any) -> Any:
        if key in ("max_background_workers", "job_timeout_seconds",
                   "screenshot_interval_seconds", "cache_limit_mb",
                     "bridge_port", "mcp_http_port",
                     "opencode_port", "ws_port",
                     "llm_max_tokens"):
            try:
                return int(value)
            except (TypeError, ValueError):
                return value
        if key in ("llm_temperature", "llm_top_p"):
            try:
                return float(value)
            except (TypeError, ValueError):
                return value
        if key in ("mcp_stdio_enabled", "mcp_http_enabled",
                   "temp_cleanup_enabled", "emergency_stop_enabled",
                   "ai_image_capability_detection",
                   "opencode_enabled", "codex_enabled", "ws_enabled",
                   "llm_stream_responses", "llm_show_token_usage"):
            return str(value).lower() in ("1", "true", "yes", "on")
        return value

    @staticmethod
    def _serialize(value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)


def default_data_dir() -> str:
    """Return the default platform data directory (Windows AppData)."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Universal AI GIS Studio")
