"""Universal AI GIS Studio — Audit logging service with tamper-proof hash chain."""

import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from database.repositories.audit_repository import AuditRepository

logger = logging.getLogger("uagis.monitoring.audit")


class AuditService:
    """Audit logging with SHA256 hash chain and periodic external anchoring."""

    def __init__(self, db, anchor_interval: int = 100, anchor_file: str | None = None):
        self.repo = AuditRepository(db)
        self.anchor_interval = anchor_interval
        self.anchor_file = anchor_file or str(Path.cwd() / "audit_anchors.log")
        self._entries_since_anchor = 0
        self._lock = threading.Lock()

    def log(self, actor: str, action: str, target: str | None = None,
            outcome: str = "success", details: dict | None = None,
            ip: str | None = None) -> int:
        """Log an audit entry and return its ID."""
        with self._lock:
            entry_id = self.repo.log(actor, action, target, outcome, details, ip)
            self._entries_since_anchor += 1

            # Check if we should create an external anchor
            if self._entries_since_anchor >= self.anchor_interval:
                self._create_external_anchor(entry_id)
                self._entries_since_anchor = 0

            logger.info("AUDIT %s %s %s %s (id=%d)", actor, action, target, outcome, entry_id)
            return entry_id

    def _create_external_anchor(self, audit_log_id: int) -> None:
        """Create an external anchor for the given audit log entry."""
        try:
            # Get the hash to anchor
            row = self.repo.db.fetchone(
                "SELECT audit_hash FROM audit_logs WHERE id = ?", (audit_log_id,)
            )
            if not row:
                return

            audit_hash = row["audit_hash"]

            # Create anchor record in database
            self.repo.add_anchor(
                audit_log_id=audit_log_id,
                anchor_hash=audit_hash,
                anchor_type="file",
                anchor_location=self.anchor_file,
            )

            # Write to external anchor file (append-only)
            anchor_record = {
                "audit_log_id": audit_log_id,
                "anchor_hash": audit_hash,
                "anchor_type": "file",
                "anchor_location": self.anchor_file,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }

            with open(self.anchor_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(anchor_record, separators=(",", ":")) + "\n")

            # Also log to syslog if available (Windows Event Log)
            self._write_syslog_anchor(audit_log_id, audit_hash)

            logger.info("External anchor created for audit log %d: %s", audit_log_id, audit_hash[:16])

        except Exception as exc:
            logger.error("Failed to create external anchor: %s", exc)

    def _write_syslog_anchor(self, audit_log_id: int, audit_hash: str) -> None:
        """Write anchor to Windows Event Log or syslog."""
        try:
            import platform
            if platform.system() == "Windows":
                # Write to Windows Application Event Log
                import ctypes
                msg = f"UAGIS Audit Anchor: id={audit_log_id} hash={audit_hash[:16]}"
                ctypes.windll.advapi32.ReportEventW(
                    ctypes.windll.kernel32.GetCurrentProcessId(),  # event source (simplified)
                    4,  # EVENTLOG_INFORMATION_TYPE
                    0,  # category
                    0,  # event ID
                    None,  # user SID
                    [msg],  # strings
                    None,  # data
                )
            else:
                # Unix syslog
                import syslog
                syslog.syslog(syslog.LOG_INFO, f"UAGIS Audit Anchor: id={audit_log_id} hash={audit_hash[:16]}")
        except Exception:
            # Syslog not available, ignore
            pass

    def recent(self, limit: int = 50) -> list[dict]:
        """Get recent audit entries."""
        return self.repo.list(limit=limit)

    def verify_chain(self, start_id: int = 1, end_id: int | None = None) -> dict:
        """Verify the hash chain integrity."""
        return self.repo.verify_chain(start_id, end_id)

    def get_last_hash(self) -> str:
        """Get the hash of the last audit entry."""
        return self.repo.get_last_hash()

    def force_anchor(self, audit_log_id: int | None = None) -> None:
        """Force creation of an external anchor for a specific entry or the latest."""
        if audit_log_id is None:
            row = self.repo.db.fetchone("SELECT id FROM audit_logs ORDER BY id DESC LIMIT 1")
            if row:
                audit_log_id = row["id"]
        if audit_log_id:
            self._create_external_anchor(audit_log_id)