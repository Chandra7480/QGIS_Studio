"""Universal AI GIS Studio — Bridge Authentication & API Key Management.

Authenticated localhost IPC for the QGIS Bridge. Token-based with API key rotation support.
"""

import logging
from typing import Optional

from security.api_key_manager import get_api_key_manager, APIKeyManager

logger = logging.getLogger("uagis.security.auth")


class BridgeAuth:
    def __init__(self, token: str | None = None, api_key_manager: APIKeyManager | None = None):
        self.token = token
        self.api_key_manager = api_key_manager or get_api_key_manager()

    def required(self) -> bool:
        return self.token is not None

    def validate(self, provided: str | None) -> bool:
        if self.token is None:
            return True  # auth not configured
        return provided == self.token

    def get_provider_key(self, provider: str) -> Optional[str]:
        """Get active API key for a provider."""
        return self.api_key_manager.get_active_key(provider)

    def record_provider_failure(self, provider: str) -> bool:
        """Record a failure for a provider's key. Returns True if fallback triggered."""
        return self.api_key_manager.record_failure(provider)

    def record_provider_success(self, provider: str) -> None:
        """Record a success for a provider's key."""
        self.api_key_manager.record_success(provider)

    def rotate_provider_key(self, provider: str, new_key: str) -> str:
        """Rotate API key for a provider."""
        return self.api_key_manager.rotate_key(provider, new_key)

    def fallback_provider_key(self, provider: str) -> bool:
        """Fallback to previous key for a provider."""
        return self.api_key_manager.fallback_to_previous(provider)