"""Universal AI GIS Studio — Optional API Manager.

Manages optional direct API integrations: OpenAI, Gemini, Anthropic,
OpenRouter, OpenAI-compatible, custom HTTP endpoints.

API integrations are OPTIONAL. The plugin functions without any API provider.
Credentials are stored securely (OS credential manager) — never in plaintext
database fields or logs.
"""

import logging
from typing import Optional

from database.db import Database
from core.exceptions import NotFoundError, ConfigurationError

logger = logging.getLogger("uagis.api_manager")

SUPPORTED_PROVIDERS = {
    "openai", "gemini", "anthropic", "openrouter",
    "openai_compatible", "custom",
}


class APIManager:
    def __init__(self, db: Database, credential_store=None):
        self.db = db
        # credential_store: object with get/set(key) for OS credential manager
        self._credential_store = credential_store

    def list_providers(self) -> list[dict]:
        rows = self.db.fetchall("SELECT * FROM api_providers ORDER BY name")
        return [dict(r) for r in rows]

    def add_provider(self, provider_id: str, name: str, base_url: str | None,
                     model_id: str | None, enabled: bool = False,
                     image_capable: bool = False,
                     timeout_seconds: int = 60, retry_count: int = 3) -> None:
        if provider_id not in SUPPORTED_PROVIDERS:
            raise ConfigurationError(f"Unsupported provider: {provider_id}")
        self.db.execute(
            "INSERT OR REPLACE INTO api_providers(id, name, base_url, model_id, "
            "enabled, image_capable, timeout_seconds, retry_count, updated_at) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (provider_id, name, base_url, model_id, int(enabled),
             int(image_capable), timeout_seconds, retry_count))
        logger.info("API provider configured: %s", name)

    def set_api_key(self, provider_id: str, api_key: str) -> None:
        """Store API key securely (OS credential manager where available)."""
        ref = f"uagis_api_{provider_id}"
        if self._credential_store is not None:
            try:
                self._credential_store.set(ref, api_key)
                logger.info("API key stored securely for %s", provider_id)
                return
            except Exception as exc:
                logger.warning("Credential store unavailable: %s", exc)
        # Fallback: record a reference only (not the key)
        self.db.execute(
            "INSERT OR REPLACE INTO api_profiles(id, provider_id, credential_ref, is_default) "
            "VALUES(?, ?, ?, 1)",
            (ref, provider_id, ref))
        logger.warning("API key for %s not persisted (no credential store)", provider_id)

    def set_enabled(self, provider_id: str, enabled: bool) -> None:
        self.db.execute(
            "UPDATE api_providers SET enabled = ? WHERE id = ?", (int(enabled), provider_id))

    def test_connection(self, provider_id: str) -> dict:
        row = self.db.fetchone("SELECT * FROM api_providers WHERE id = ?", (provider_id,))
        if not row:
            raise NotFoundError(f"API provider {provider_id} not found")
        return {"provider_id": provider_id, "status": "configured",
                "note": "Actual handshake performed by the AI client"}

    def get_default(self) -> Optional[dict]:
        row = self.db.fetchone(
            "SELECT * FROM api_providers WHERE enabled = 1 ORDER BY name LIMIT 1")
        return dict(row) if row else None
