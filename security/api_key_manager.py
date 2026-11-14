"""Universal AI GIS Studio — API Key Manager.

Manages API key rotation, expiration notifications, and fallback to previous keys.
"""

import json
import logging
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Optional

from core.keyring_backend import (
    get_credential_value,
    store_credential,
    delete_credential,
    retrieve_credential,
    Credential,
)

logger = logging.getLogger("uagis.security.api_keys")


class KeyStatus(Enum):
    ACTIVE = "active"
    ROTATING = "rotating"
    EXPIRED = "expired"
    REVOKED = "revoked"
    FAILED = "failed"


class RotationStrategy(Enum):
    SCHEDULED = "scheduled"      # Rotate on a fixed schedule
    MANUAL = "manual"            # Manual rotation only
    ON_FAILURE = "on_failure"    # Rotate when key fails


@dataclass
class APIKeyMetadata:
    """Metadata for an API key."""
    provider: str
    key_id: str
    status: KeyStatus = KeyStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    rotated_at: datetime | None = None
    previous_key_id: str | None = None
    rotation_strategy: RotationStrategy = RotationStrategy.SCHEDULED
    rotation_interval_days: int = 90
    notification_days_before: list[int] = field(default_factory=lambda: [7, 1])
    last_notification: datetime | None = None
    test_endpoint: str | None = None
    test_method: str = "GET"
    test_headers: dict = field(default_factory=dict)
    failure_count: int = 0
    max_failures_before_rotate: int = 3


class KeyRotationError(Exception):
    """Raised when key rotation fails."""
    pass


class KeyTester(ABC):
    """Abstract base for API key validation."""

    @abstractmethod
    def test_key(self, provider: str, key: str, metadata: APIKeyMetadata) -> bool:
        """Test if a key is valid. Returns True if valid."""
        pass


class DefaultKeyTester(KeyTester):
    """Default key tester using HTTP requests to provider endpoints."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def test_key(self, provider: str, key: str, metadata: APIKeyMetadata) -> bool:
        """Test key by making a request to the provider's test endpoint."""
        import requests

        test_url = metadata.test_endpoint
        if not test_url:
            # Default test endpoints per provider
            test_urls = {
                "openai": "https://api.openai.com/v1/models",
                "anthropic": "https://api.anthropic.com/v1/messages",
                "gemini": "https://generativelanguage.googleapis.com/v1/models",
                "openrouter": "https://openrouter.ai/api/v1/models",
            }
            test_url = test_urls.get(provider.lower())

        if not test_url:
            logger.warning("No test endpoint configured for provider %s", provider)
            return True  # Can't test, assume valid

        headers = metadata.test_headers.copy()
        if provider.lower() == "openai":
            headers["Authorization"] = f"Bearer {key}"
        elif provider.lower() == "anthropic":
            headers["x-api-key"] = key
            headers["anthropic-version"] = "2023-06-01"
        elif provider.lower() == "gemini":
            test_url += f"?key={key}"
        elif provider.lower() == "openrouter":
            headers["Authorization"] = f"Bearer {key}"
        else:
            headers["Authorization"] = f"Bearer {key}"

        try:
            response = requests.request(
                metadata.test_method,
                test_url,
                headers=headers,
                timeout=self.timeout,
            )
            return response.status_code == 200
        except Exception as exc:
            logger.error("Key test failed for %s: %s", provider, exc)
            return False


class NotificationHandler(ABC):
    """Abstract base for notification delivery."""

    @abstractmethod
    def notify(self, title: str, message: str, level: str = "info") -> None:
        """Send a notification."""
        pass


class LoggingNotificationHandler(NotificationHandler):
    """Logs notifications to the application log."""

    def notify(self, title: str, message: str, level: str = "info") -> None:
        log_func = getattr(logger, level.lower(), logger.info)
        log_func("%s: %s", title, message)


class WebhookNotificationHandler(NotificationHandler):
    """Sends notifications to a webhook URL."""

    def __init__(self, webhook_url: str, timeout: int = 5):
        self.webhook_url = webhook_url
        self.timeout = timeout

    def notify(self, title: str, message: str, level: str = "info") -> None:
        import requests
        try:
            requests.post(
                self.webhook_url,
                json={"title": title, "message": message, "level": level},
                timeout=self.timeout,
            )
        except Exception as exc:
            logger.error("Failed to send webhook notification: %s", exc)


class EmailNotificationHandler(NotificationHandler):
    """Sends notifications via email (SMTP)."""

    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str,
                 from_addr: str, to_addrs: list[str], use_tls: bool = True):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.use_tls = use_tls

    def notify(self, title: str, message: str, level: str = "info") -> None:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        try:
            msg = MIMEMultipart()
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)
            msg["Subject"] = f"[UAGIS] {title}"
            msg.attach(MIMEText(message, "plain"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
        except Exception as exc:
            logger.error("Failed to send email notification: %s", exc)


class APIKeyManager:
    """Manages API key lifecycle: rotation, testing, notifications, fallback."""

    def __init__(
        self,
        key_tester: KeyTester | None = None,
        notification_handlers: list[NotificationHandler] | None = None,
        keyring_prefix: str = "api_key:",
    ):
        self.key_tester = key_tester or DefaultKeyTester()
        self.notification_handlers = notification_handlers or [LoggingNotificationHandler()]
        self.keyring_prefix = keyring_prefix
        self._lock = threading.RLock()
        self._rotation_timers: dict[str, threading.Timer] = {}
        self._notification_timers: dict[str, threading.Timer] = {}

    def _metadata_key(self, provider: str, key_id: str) -> str:
        return f"{self.keyring_prefix}{provider}:{key_id}:meta"

    def _key_value_key(self, provider: str, key_id: str) -> str:
        return f"{self.keyring_prefix}{provider}:{key_id}:value"

    def _active_key_id_key(self, provider: str) -> str:
        return f"{self.keyring_prefix}{provider}:active"

    def _store_metadata(self, metadata: APIKeyMetadata) -> bool:
        """Store key metadata in keyring."""
        key = self._metadata_key(metadata.provider, metadata.key_id)
        data = {
            "provider": metadata.provider,
            "key_id": metadata.key_id,
            "status": metadata.status.value,
            "created_at": metadata.created_at.isoformat(),
            "expires_at": metadata.expires_at.isoformat() if metadata.expires_at else None,
            "rotated_at": metadata.rotated_at.isoformat() if metadata.rotated_at else None,
            "previous_key_id": metadata.previous_key_id,
            "rotation_strategy": metadata.rotation_strategy.value,
            "rotation_interval_days": metadata.rotation_interval_days,
            "notification_days_before": metadata.notification_days_before,
            "last_notification": metadata.last_notification.isoformat() if metadata.last_notification else None,
            "test_endpoint": metadata.test_endpoint,
            "test_method": metadata.test_method,
            "test_headers": metadata.test_headers,
            "failure_count": metadata.failure_count,
            "max_failures_before_rotate": metadata.max_failures_before_rotate,
        }
        return store_credential(key, json.dumps(data))

    def _load_metadata(self, provider: str, key_id: str) -> Optional[APIKeyMetadata]:
        """Load key metadata from keyring."""
        key = self._metadata_key(provider, key_id)
        value = get_credential_value(key)
        if not value:
            return None
        try:
            data = json.loads(value)
            return APIKeyMetadata(
                provider=data["provider"],
                key_id=data["key_id"],
                status=KeyStatus(data["status"]),
                created_at=datetime.fromisoformat(data["created_at"]),
                expires_at=datetime.fromisoformat(data["expires_at"]) if data["expires_at"] else None,
                rotated_at=datetime.fromisoformat(data["rotated_at"]) if data["rotated_at"] else None,
                previous_key_id=data.get("previous_key_id"),
                rotation_strategy=RotationStrategy(data["rotation_strategy"]),
                rotation_interval_days=data["rotation_interval_days"],
                notification_days_before=data["notification_days_before"],
                last_notification=datetime.fromisoformat(data["last_notification"]) if data["last_notification"] else None,
                test_endpoint=data.get("test_endpoint"),
                test_method=data.get("test_method", "GET"),
                test_headers=data.get("test_headers", {}),
                failure_count=data.get("failure_count", 0),
                max_failures_before_rotate=data.get("max_failures_before_rotate", 3),
            )
        except Exception as exc:
            logger.error("Failed to parse metadata for %s:%s: %s", provider, key_id, exc)
            return None

    def _get_active_key_id(self, provider: str) -> Optional[str]:
        """Get the currently active key ID for a provider."""
        return get_credential_value(self._active_key_id_key(provider))

    def _set_active_key_id(self, provider: str, key_id: str) -> bool:
        """Set the active key ID for a provider."""
        return store_credential(self._active_key_id_key(provider), key_id)

    def register_key(
        self,
        provider: str,
        key_value: str,
        key_id: str | None = None,
        rotation_interval_days: int = 90,
        rotation_strategy: RotationStrategy = RotationStrategy.SCHEDULED,
        test_endpoint: str | None = None,
        test_headers: dict | None = None,
        notification_days_before: list[int] | None = None,
    ) -> str:
        """Register a new API key."""
        with self._lock:
            key_id = key_id or f"key_{uuid.uuid4().hex[:12]}"
            now = datetime.utcnow()
            expires_at = now + timedelta(days=rotation_interval_days)

            metadata = APIKeyMetadata(
                provider=provider,
                key_id=key_id,
                status=KeyStatus.ACTIVE,
                created_at=now,
                expires_at=expires_at,
                rotation_strategy=rotation_strategy,
                rotation_interval_days=rotation_interval_days,
                notification_days_before=notification_days_before or [7, 1],
                test_endpoint=test_endpoint,
                test_headers=test_headers or {},
            )

            # Store key value and metadata
            store_credential(self._key_value_key(provider, key_id), key_value)
            self._store_metadata(metadata)

            # If no active key, make this one active
            active = self._get_active_key_id(provider)
            if not active:
                self._set_active_key_id(provider, key_id)
                logger.info("First key for %s set as active: %s", provider, key_id)

            # Schedule rotation
            self._schedule_rotation(provider, key_id)

            # Schedule notifications
            self._schedule_notifications(provider, key_id)

            logger.info("Registered API key %s for provider %s (expires %s)",
                        key_id, provider, expires_at.date())
            return key_id

    def get_active_key(self, provider: str) -> Optional[str]:
        """Get the currently active key value for a provider."""
        with self._lock:
            key_id = self._get_active_key_id(provider)
            if not key_id:
                return None
            return get_credential_value(self._key_value_key(provider, key_id))

    def get_active_key_id(self, provider: str) -> Optional[str]:
        """Get the currently active key ID for a provider."""
        return self._get_active_key_id(provider)

    def get_key_metadata(self, provider: str, key_id: str) -> Optional[APIKeyMetadata]:
        """Get metadata for a specific key."""
        with self._lock:
            return self._load_metadata(provider, key_id)

    def list_keys(self, provider: str) -> list[APIKeyMetadata]:
        """List all keys for a provider."""
        # This is limited by keyring backend; in production use a proper index
        # For now, return empty list (would need keyring.list_keys())
        return []

    def rotate_key(self, provider: str, new_key_value: str | None = None,
                   key_id: str | None = None) -> str:
        """Rotate to a new key. If new_key_value is None, generates a placeholder.
        
        Returns the new key_id.
        """
        with self._lock:
            old_key_id = self._get_active_key_id(provider)
            if not old_key_id:
                raise KeyRotationError(f"No active key for provider {provider}")

            old_metadata = self._load_metadata(provider, old_key_id)
            if not old_metadata:
                raise KeyRotationError(f"Metadata not found for active key {old_key_id}")

            # Generate new key ID
            new_key_id = key_id or f"key_{uuid.uuid4().hex[:12]}"
            now = datetime.utcnow()
            expires_at = now + timedelta(days=old_metadata.rotation_interval_days)

            # Mark old key as rotating
            old_metadata.status = KeyStatus.ROTATING
            old_metadata.rotated_at = now
            self._store_metadata(old_metadata)

            # Create new key metadata
            new_metadata = APIKeyMetadata(
                provider=provider,
                key_id=new_key_id,
                status=KeyStatus.ACTIVE,
                created_at=now,
                expires_at=expires_at,
                previous_key_id=old_key_id,
                rotation_strategy=old_metadata.rotation_strategy,
                rotation_interval_days=old_metadata.rotation_interval_days,
                notification_days_before=old_metadata.notification_days_before,
                test_endpoint=old_metadata.test_endpoint,
                test_method=old_metadata.test_method,
                test_headers=old_metadata.test_headers,
                max_failures_before_rotate=old_metadata.max_failures_before_rotate,
            )

            # Store new key value (or placeholder)
            key_value = new_key_value or f"ROTATED_{new_key_id}_PENDING_MANUAL_UPDATE"
            store_credential(self._key_value_key(provider, new_key_id), key_value)
            self._store_metadata(new_metadata)

            # Test new key before switching
            if new_key_value:
                if not self.key_tester.test_key(provider, key_value, new_metadata):
                    # Revert: mark new as failed, old as active
                    new_metadata.status = KeyStatus.FAILED
                    self._store_metadata(new_metadata)
                    old_metadata.status = KeyStatus.ACTIVE
                    old_metadata.rotated_at = None
                    self._store_metadata(old_metadata)
                    raise KeyRotationError(f"New key {new_key_id} failed validation test")

            # Switch active key
            self._set_active_key_id(provider, new_key_id)

            # Mark old as expired
            old_metadata.status = KeyStatus.EXPIRED
            self._store_metadata(old_metadata)

            # Schedule rotation for new key
            self._schedule_rotation(provider, new_key_id)
            self._schedule_notifications(provider, new_key_id)

            # Cancel old timers
            self._cancel_timers(provider, old_key_id)

            logger.info("Rotated key for %s: %s -> %s", provider, old_key_id, new_key_id)
            self._notify_all(
                f"API Key Rotated: {provider}",
                f"Rotated from {old_key_id} to {new_key_id}",
                "info",
            )
            return new_key_id

    def fallback_to_previous(self, provider: str) -> bool:
        """Fallback to the previous key if current key fails."""
        with self._lock:
            current_key_id = self._get_active_key_id(provider)
            if not current_key_id:
                return False

            current_metadata = self._load_metadata(provider, current_key_id)
            if not current_metadata or not current_metadata.previous_key_id:
                logger.warning("No previous key to fallback to for %s", provider)
                return False

            previous_key_id = current_metadata.previous_key_id
            previous_metadata = self._load_metadata(provider, previous_key_id)
            if not previous_metadata:
                logger.error("Previous key metadata not found: %s", previous_key_id)
                return False

            # Test previous key
            previous_value = get_credential_value(self._key_value_key(provider, previous_key_id))
            if previous_value and self.key_tester.test_key(provider, previous_value, previous_metadata):
                # Switch back
                self._set_active_key_id(provider, previous_key_id)
                current_metadata.status = KeyStatus.FAILED
                self._store_metadata(current_metadata)
                previous_metadata.status = KeyStatus.ACTIVE
                self._store_metadata(previous_metadata)

                logger.warning("Fallback to previous key for %s: %s -> %s",
                               provider, current_key_id, previous_key_id)
                self._notify_all(
                    f"API Key Fallback: {provider}",
                    f"Fell back from {current_key_id} to {previous_key_id} due to failure",
                    "warning",
                )
                return True
            else:
                logger.error("Previous key %s also failed validation", previous_key_id)
                return False

    def record_failure(self, provider: str) -> bool:
        """Record a failure for the active key. Returns True if rotation triggered."""
        with self._lock:
            key_id = self._get_active_key_id(provider)
            if not key_id:
                return False

            metadata = self._load_metadata(provider, key_id)
            if not metadata:
                return False

            metadata.failure_count += 1
            self._store_metadata(metadata)

            if metadata.failure_count >= metadata.max_failures_before_rotate:
                logger.warning("Key %s for %s reached max failures (%d), attempting fallback",
                               key_id, provider, metadata.failure_count)
                return self.fallback_to_previous(provider)

            return False

    def record_success(self, provider: str) -> None:
        """Record a success for the active key (resets failure count)."""
        with self._lock:
            key_id = self._get_active_key_id(provider)
            if not key_id:
                return
            metadata = self._load_metadata(provider, key_id)
            if metadata and metadata.failure_count > 0:
                metadata.failure_count = 0
                self._store_metadata(metadata)

    def _schedule_rotation(self, provider: str, key_id: str) -> None:
        """Schedule automatic key rotation."""
        metadata = self._load_metadata(provider, key_id)
        if not metadata or metadata.rotation_strategy != RotationStrategy.SCHEDULED:
            return

        if not metadata.expires_at:
            return

        now = datetime.utcnow()
        if metadata.expires_at <= now:
            # Already expired, rotate immediately
            self._rotate_async(provider, key_id)
            return

        delay = (metadata.expires_at - now).total_seconds()
        if delay <= 0:
            return

        timer = threading.Timer(delay, self._rotate_async, args=(provider, key_id))
        timer.daemon = True
        timer.start()
        self._rotation_timers[f"{provider}:{key_id}"] = timer

    def _schedule_notifications(self, provider: str, key_id: str) -> None:
        """Schedule expiration notifications."""
        metadata = self._load_metadata(provider, key_id)
        if not metadata or not metadata.expires_at:
            return

        now = datetime.utcnow()
        for days_before in metadata.notification_days_before:
            notify_at = metadata.expires_at - timedelta(days=days_before)
            if notify_at <= now:
                continue

            delay = (notify_at - now).total_seconds()
            timer = threading.Timer(
                delay, self._send_expiration_notification,
                args=(provider, key_id, days_before)
            )
            timer.daemon = True
            timer.start()
            self._notification_timers[f"{provider}:{key_id}:{days_before}d"] = timer

    def _rotate_async(self, provider: str, key_id: str) -> None:
        """Async rotation callback (runs in timer thread)."""
        try:
            # This would need a new key value - in production, integrate with
            # provider's key generation API or require manual intervention
            logger.warning("Auto-rotation triggered for %s:%s but requires new key value",
                           provider, key_id)
            # Mark as expired to trigger manual rotation
            metadata = self._load_metadata(provider, key_id)
            if metadata:
                metadata.status = KeyStatus.EXPIRED
                self._store_metadata(metadata)
            self._notify_all(
                f"API Key Expired: {provider}",
                f"Key {key_id} has expired and requires manual rotation",
                "error",
            )
        except Exception as exc:
            logger.error("Auto-rotation failed for %s:%s: %s", provider, key_id, exc)

    def _send_expiration_notification(self, provider: str, key_id: str, days_before: int) -> None:
        """Send expiration notification."""
        metadata = self._load_metadata(provider, key_id)
        if not metadata:
            return

        metadata.last_notification = datetime.utcnow()
        self._store_metadata(metadata)

        self._notify_all(
            f"API Key Expiring Soon: {provider}",
            f"Key {key_id} expires in {days_before} day(s) on {metadata.expires_at.date()}. "
            f"Please rotate the key.",
            "warning",
        )

    def _cancel_timers(self, provider: str, key_id: str) -> None:
        """Cancel all timers for a key."""
        # Rotation timer
        timer_key = f"{provider}:{key_id}"
        if timer_key in self._rotation_timers:
            self._rotation_timers[timer_key].cancel()
            del self._rotation_timers[timer_key]

        # Notification timers
        for days in [7, 1, 30, 60]:  # Common intervals
            notify_key = f"{provider}:{key_id}:{days}d"
            if notify_key in self._notification_timers:
                self._notification_timers[notify_key].cancel()
                del self._notification_timers[notify_key]

    def _notify_all(self, title: str, message: str, level: str) -> None:
        """Send notification via all handlers."""
        for handler in self.notification_handlers:
            try:
                handler.notify(title, message, level)
            except Exception as exc:
                logger.error("Notification handler failed: %s", exc)

    def revoke_key(self, provider: str, key_id: str) -> bool:
        """Revoke a key immediately."""
        with self._lock:
            metadata = self._load_metadata(provider, key_id)
            if not metadata:
                return False

            # If this is the active key, try fallback
            active_id = self._get_active_key_id(provider)
            if active_id == key_id:
                self.fallback_to_previous(provider)

            metadata.status = KeyStatus.REVOKED
            self._store_metadata(metadata)
            self._cancel_timers(provider, key_id)

            # Delete key value from keyring
            delete_credential(self._key_value_key(provider, key_id))

            logger.info("Revoked key %s for %s", key_id, provider)
            return True

    def cleanup_expired(self, provider: str, keep_previous: bool = True) -> int:
        """Clean up expired/revoked keys. Returns count of cleaned keys."""
        # This is limited by keyring backend capabilities
        # In production, maintain an index of all keys
        return 0


# Global instance
_api_key_manager: APIKeyManager | None = None


def get_api_key_manager() -> APIKeyManager:
    """Get global API key manager instance."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


def init_api_key_manager(
    key_tester: KeyTester | None = None,
    notification_handlers: list[NotificationHandler] | None = None,
) -> APIKeyManager:
    """Initialize global API key manager."""
    global _api_key_manager
    _api_key_manager = APIKeyManager(key_tester, notification_handlers)
    return _api_key_manager