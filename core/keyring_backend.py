"""Universal AI GIS Studio — OS Credential Manager Backend.

Provides secure storage and retrieval of API keys and secrets using
the OS-native credential manager (Windows Credential Manager, macOS Keychain,
Linux Secret Service / libsecret).
"""

import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("uagis.core.keyring")


@dataclass
class Credential:
    """Represents a stored credential."""
    key: str
    value: str
    metadata: dict
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None


class KeyringBackend(ABC):
    """Abstract base for OS credential backends."""

    @abstractmethod
    def store(self, key: str, value: str, metadata: dict | None = None) -> bool:
        """Store a credential."""
        pass

    @abstractmethod
    def retrieve(self, key: str) -> Optional[Credential]:
        """Retrieve a credential by key."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a credential."""
        pass

    @abstractmethod
    def list_keys(self, prefix: str = "") -> list[str]:
        """List all credential keys matching prefix."""
        pass


class WindowsKeyring(KeyringBackend):
    """Windows Credential Manager backend using CredWrite/CredRead."""

    def __init__(self, target_prefix: str = "UAGIS:"):
        self.target_prefix = target_prefix
        self._load_libs()

    def _load_libs(self):
        """Load Windows credential management DLLs."""
        try:
            self.advapi32 = __import__("ctypes").windll.advapi32
            self.kernel32 = __import__("ctypes").windll.kernel32
            self.ctypes = __import__("ctypes")
            # Define CREDENTIAL structure
            class CREDENTIAL(self.ctypes.Structure):
                _fields_ = [
                    ("Flags", self.ctypes.c_ulong),
                    ("Type", self.ctypes.c_ulong),
                    ("TargetName", self.ctypes.c_wchar_p),
                    ("Comment", self.ctypes.c_wchar_p),
                    ("LastWritten", self.ctypes.c_ulonglong),  # FILETIME
                    ("CredentialBlobSize", self.ctypes.c_ulong),
                    ("CredentialBlob", self.ctypes.c_void_p),
                    ("Persist", self.ctypes.c_ulong),
                    ("AttributeCount", self.ctypes.c_ulong),
                    ("Attributes", self.ctypes.c_void_p),
                    ("TargetAlias", self.ctypes.c_wchar_p),
                    ("UserName", self.ctypes.c_wchar_p),
                ]
            self.CREDENTIAL = CREDENTIAL
        except Exception as exc:
            logger.error("Failed to load Windows credential APIs: %s", exc)
            raise RuntimeError("Windows credential manager not available") from exc

    def _target_name(self, key: str) -> str:
        return f"{self.target_prefix}{key}"

    def _filetime_to_datetime(self, ft: int) -> datetime:
        """Convert Windows FILETIME to datetime."""
        # FILETIME is 100-nanosecond intervals since Jan 1, 1601
        us = (ft - 116444736000000000) // 10  # Convert to microseconds since epoch
        return datetime.utcfromtimestamp(us / 1_000_000)

    def store(self, key: str, value: str, metadata: dict | None = None) -> bool:
        try:
            target = self._target_name(key)
            blob = json.dumps({"value": value, "metadata": metadata or {}}).encode("utf-8")

            cred = self.CREDENTIAL()
            cred.Flags = 0
            cred.Type = 1  # CRED_TYPE_GENERIC
            cred.TargetName = target
            cred.Comment = json.dumps(metadata or {})
            cred.CredentialBlobSize = len(blob)
            cred.CredentialBlob = self.ctypes.c_char_p(blob)
            cred.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE
            cred.AttributeCount = 0
            cred.Attributes = None
            cred.TargetAlias = None
            cred.UserName = None

            result = self.advapi32.CredWriteW(self.ctypes.byref(cred), 0)
            if not result:
                error = self.kernel32.GetLastError()
                logger.error("CredWrite failed with error %d", error)
                return False
            return True
        except Exception as exc:
            logger.exception("Failed to store credential %s", key)
            return False

    def retrieve(self, key: str) -> Optional[Credential]:
        try:
            target = self._target_name(key)
            pcred = self.ctypes.POINTER(self.CREDENTIAL)()
            result = self.advapi32.CredReadW(target, 1, 0, self.ctypes.byref(pcred))
            if not result:
                error = self.kernel32.GetLastError()
                if error == 1168:  # ERROR_NOT_FOUND
                    return None
                logger.error("CredRead failed with error %d", error)
                return None

            cred = pcred.contents
            blob = self.ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
            data = json.loads(blob.decode("utf-8"))

            # Parse metadata from comment
            try:
                metadata = json.loads(cred.Comment) if cred.Comment else {}
            except Exception:
                metadata = {}

            # Get created/updated times from FILETIME
            last_written = self._filetime_to_datetime(cred.LastWritten)

            return Credential(
                key=key,
                value=data.get("value", ""),
                metadata={**metadata, **data.get("metadata", {})},
                created_at=last_written,
                updated_at=last_written,
            )
        except Exception as exc:
            logger.exception("Failed to retrieve credential %s", key)
            return None
        finally:
            if 'pcred' in locals() and pcred:
                self.advapi32.CredFree(pcred)

    def delete(self, key: str) -> bool:
        try:
            target = self._target_name(key)
            result = self.advapi32.CredDeleteW(target, 1, 0)
            if not result:
                error = self.kernel32.GetLastError()
                if error == 1168:  # ERROR_NOT_FOUND
                    return False
                logger.error("CredDelete failed with error %d", error)
                return False
            return True
        except Exception as exc:
            logger.exception("Failed to delete credential %s", key)
            return False

    def list_keys(self, prefix: str = "") -> list[str]:
        # Windows CredEnumerate is complex; for now return empty
        # In production, implement with CredEnumerateW
        return []


class MacOSKeyring(KeyringBackend):
    """macOS Keychain backend using security command."""

    def __init__(self, service: str = "UAGIS"):
        self.service = service

    def store(self, key: str, value: str, metadata: dict | None = None) -> bool:
        import subprocess
        try:
            account = f"{self.service}:{key}"
            # Store metadata as comment
            comment = json.dumps(metadata or {})
            result = subprocess.run([
                "security", "add-generic-password",
                "-s", self.service,
                "-a", account,
                "-w", value,
                "-c", comment,
                "-U",  # Update if exists
            ], capture_output=True, text=True)
            if result.returncode != 0:
                logger.error("security add-generic-password failed: %s", result.stderr)
                return False
            return True
        except Exception as exc:
            logger.exception("Failed to store credential %s", key)
            return False

    def retrieve(self, key: str) -> Optional[Credential]:
        import subprocess
        try:
            account = f"{self.service}:{key}"
            result = subprocess.run([
                "security", "find-generic-password",
                "-s", self.service,
                "-a", account,
                "-w",
            ], capture_output=True, text=True)
            if result.returncode != 0:
                return None
            value = result.stdout.strip()

            # Get metadata from comment
            result = subprocess.run([
                "security", "find-generic-password",
                "-s", self.service,
                "-a", account,
                "-g",  # Show all attributes
            ], capture_output=True, text=True)
            metadata = {}
            if result.returncode == 0:
                for line in result.stderr.splitlines():
                    if "comment" in line.lower():
                        try:
                            comment = line.split('"')[-2]
                            metadata = json.loads(comment)
                        except Exception:
                            pass

            return Credential(
                key=key,
                value=value,
                metadata=metadata,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        except Exception as exc:
            logger.exception("Failed to retrieve credential %s", key)
            return None

    def delete(self, key: str) -> bool:
        import subprocess
        try:
            account = f"{self.service}:{key}"
            result = subprocess.run([
                "security", "delete-generic-password",
                "-s", self.service,
                "-a", account,
            ], capture_output=True, text=True)
            return result.returncode == 0
        except Exception as exc:
            logger.exception("Failed to delete credential %s", key)
            return False

    def list_keys(self, prefix: str = "") -> list[str]:
        # Not easily implemented with security CLI
        return []


class LinuxKeyring(KeyringBackend):
    """Linux Secret Service backend using libsecret via secret-tool."""

    def __init__(self, schema: str = "UAGIS"):
        self.schema = schema

    def store(self, key: str, value: str, metadata: dict | None = None) -> bool:
        import subprocess
        try:
            attrs = [f"key={key}", f"schema={self.schema}"]
            if metadata:
                for k, v in metadata.items():
                    attrs.append(f"{k}={v}")
            result = subprocess.run([
                "secret-tool", "store", *attrs
            ], input=value, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error("secret-tool store failed: %s", result.stderr)
                return False
            return True
        except FileNotFoundError:
            logger.error("secret-tool not found. Install libsecret-tools.")
            return False
        except Exception as exc:
            logger.exception("Failed to store credential %s", key)
            return False

    def retrieve(self, key: str) -> Optional[Credential]:
        import subprocess
        try:
            result = subprocess.run([
                "secret-tool", "lookup", "key", key, "schema", self.schema
            ], capture_output=True, text=True)
            if result.returncode != 0:
                return None
            value = result.stdout.strip()
            return Credential(
                key=key,
                value=value,
                metadata={},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        except Exception as exc:
            logger.exception("Failed to retrieve credential %s", key)
            return None

    def delete(self, key: str) -> bool:
        import subprocess
        try:
            result = subprocess.run([
                "secret-tool", "clear", "key", key, "schema", self.schema
            ], capture_output=True, text=True)
            return result.returncode == 0
        except Exception as exc:
            logger.exception("Failed to delete credential %s", key)
            return False

    def list_keys(self, prefix: str = "") -> list[str]:
        return []


class FallbackKeyring(KeyringBackend):
    """Fallback file-based storage (encrypted with Fernet if available)."""

    def __init__(self, storage_dir: str | None = None):
        import base64
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

        if storage_dir is None:
            import os
            base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            storage_dir = os.path.join(base, "Universal AI GIS Studio", "credentials")
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.storage_dir / "index.json"

        # Generate/load encryption key
        key_file = self.storage_dir / ".key"
        if key_file.exists():
            key = key_file.read_bytes()
        else:
            # Derive from machine-specific data
            import platform
            machine_id = platform.node().encode() + platform.machine().encode()
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"uagis-salt",
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(machine_id))
            key_file.write_bytes(key)
            key_file.chmod(0o600)

        self.fernet = Fernet(key)
        self._load_index()

    def _load_index(self):
        if self.index_file.exists():
            try:
                self.index = json.loads(self.index_file.read_text())
            except Exception:
                self.index = {}
        else:
            self.index = {}

    def _save_index(self):
        self.index_file.write_text(json.dumps(self.index))

    def _cred_path(self, key: str) -> Path:
        safe_key = key.replace("/", "_").replace("\\", "_").replace(":", "_")
        return self.storage_dir / f"{safe_key}.cred"

    def store(self, key: str, value: str, metadata: dict | None = None) -> bool:
        try:
            data = {
                "value": value,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            encrypted = self.fernet.encrypt(json.dumps(data).encode())
            self._cred_path(key).write_bytes(encrypted)
            self.index[key] = {"updated_at": data["updated_at"]}
            self._save_index()
            return True
        except Exception as exc:
            logger.exception("Failed to store credential %s", key)
            return False

    def retrieve(self, key: str) -> Optional[Credential]:
        try:
            path = self._cred_path(key)
            if not path.exists():
                return None
            encrypted = path.read_bytes()
            data = json.loads(self.fernet.decrypt(encrypted).decode())
            return Credential(
                key=key,
                value=data["value"],
                metadata=data.get("metadata", {}),
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data["updated_at"]),
            )
        except Exception as exc:
            logger.exception("Failed to retrieve credential %s", key)
            return None

    def delete(self, key: str) -> bool:
        try:
            path = self._cred_path(key)
            if path.exists():
                path.unlink()
            if key in self.index:
                del self.index[key]
                self._save_index()
            return True
        except Exception as exc:
            logger.exception("Failed to delete credential %s", key)
            return False

    def list_keys(self, prefix: str = "") -> list[str]:
        return [k for k in self.index.keys() if k.startswith(prefix)]


def get_keyring_backend() -> KeyringBackend:
    """Get the appropriate OS credential backend."""
    import platform

    system = platform.system()
    if system == "Windows":
        try:
            return WindowsKeyring()
        except Exception as exc:
            logger.warning("Windows keyring unavailable, falling back: %s", exc)
    elif system == "Darwin":
        try:
            return MacOSKeyring()
        except Exception as exc:
            logger.warning("macOS keyring unavailable, falling back: %s", exc)
    elif system == "Linux":
        try:
            return LinuxKeyring()
        except Exception as exc:
            logger.warning("Linux keyring unavailable, falling back: %s", exc)

    logger.info("Using fallback file-based credential storage")
    return FallbackKeyring()


# Convenience functions
_keyring: KeyringBackend | None = None


def get_keyring() -> KeyringBackend:
    """Get global keyring instance (singleton)."""
    global _keyring
    if _keyring is None:
        _keyring = get_keyring_backend()
    return _keyring


def store_credential(key: str, value: str, metadata: dict | None = None) -> bool:
    """Store a credential using the system keyring."""
    return get_keyring().store(key, value, metadata)


def retrieve_credential(key: str) -> Optional[Credential]:
    """Retrieve a credential from the system keyring."""
    return get_keyring().retrieve(key)


def get_credential_value(key: str) -> Optional[str]:
    """Get just the value of a credential."""
    cred = retrieve_credential(key)
    return cred.value if cred else None


def delete_credential(key: str) -> bool:
    """Delete a credential."""
    return get_keyring().delete(key)


def list_credentials(prefix: str = "") -> list[str]:
    """List credential keys."""
    return get_keyring().list_keys(prefix)