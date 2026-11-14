"""Repository for audit_logs with tamper-proof hash chain."""

import hashlib
import json
from typing import Optional

from ..db import Database


class AuditRepository:
    def __init__(self, db: Database):
        self.db = db

    def log(self, actor: str, action: str, target: str | None, outcome: str,
            details: dict | None = None, ip: str | None = None,
            audit_hash: str | None = None) -> int:
        """Insert audit log entry with hash chain.

        If audit_hash is provided, it's used directly (for verification/replay).
        Otherwise, computes SHA256(prev_hash || current_data).
        """
        # Get previous hash
        prev_row = self.db.fetchone(
            "SELECT audit_hash FROM audit_logs ORDER BY id DESC LIMIT 1"
        )
        prev_hash = prev_row["audit_hash"] if prev_row and prev_row["audit_hash"] else "0" * 64

        # Prepare current data for hashing
        current_data = {
            "actor": actor,
            "action": action,
            "target": target,
            "outcome": outcome,
            "details": details,
            "ip": ip,
            "prev_hash": prev_hash,
        }

        if audit_hash is None:
            # Compute hash chain: SHA256(prev_hash || JSON(current_data))
            hash_input = prev_hash + json.dumps(current_data, sort_keys=True, separators=(",", ":"))
            audit_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        cursor = self.db.execute(
            """
            INSERT INTO audit_logs(actor, action, target, outcome, details, ip, audit_hash)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (actor, action, target, outcome,
             json.dumps(details) if details else None, ip, audit_hash),
        )
        return cursor.lastrowid

    def list(self, limit: int = 100) -> list:
        import json
        rows = self.db.fetchall(
            "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["details"] = json.loads(d["details"]) if d["details"] else None
            except Exception:
                pass
            result.append(d)
        return result

    def get_all_ordered(self) -> list:
        """Get all audit logs ordered by id (for verification)."""
        import json
        rows = self.db.fetchall("SELECT * FROM audit_logs ORDER BY id ASC")
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["details"] = json.loads(d["details"]) if d["details"] else None
            except Exception:
                pass
            result.append(d)
        return result

    def get_last_hash(self) -> str:
        """Get the hash of the last audit entry."""
        row = self.db.fetchone("SELECT audit_hash FROM audit_logs ORDER BY id DESC LIMIT 1")
        return row["audit_hash"] if row and row["audit_hash"] else "0" * 64

    def add_anchor(self, audit_log_id: int, anchor_hash: str, anchor_type: str, anchor_location: str) -> None:
        """Record an external anchor for an audit log entry."""
        self.db.execute(
            """
            INSERT INTO audit_anchors(audit_log_id, anchor_hash, anchor_type, anchor_location)
            VALUES(?, ?, ?, ?)
            """,
            (audit_log_id, anchor_hash, anchor_type, anchor_location),
        )

    def get_anchors(self, audit_log_id: int | None = None) -> list:
        """Get audit anchors."""
        if audit_log_id:
            rows = self.db.fetchall(
                "SELECT * FROM audit_anchors WHERE audit_log_id = ? ORDER BY created_at DESC",
                (audit_log_id,)
            )
        else:
            rows = self.db.fetchall("SELECT * FROM audit_anchors ORDER BY created_at DESC")
        return [dict(r) for r in rows]

    def verify_chain(self, start_id: int = 1, end_id: int | None = None) -> dict:
        """Verify the hash chain integrity.

        Returns dict with verification results.
        """
        import hashlib
        import json

        query = "SELECT * FROM audit_logs WHERE id >= ?"
        params = [start_id]
        if end_id:
            query += " AND id <= ?"
            params.append(end_id)
        query += " ORDER BY id ASC"

        rows = self.db.fetchall(query, tuple(params))

        errors = []
        verified_count = 0
        prev_hash = "0" * 64

        for row in rows:
            r = dict(row)
            stored_hash = r["audit_hash"]

            # Reconstruct the data that was hashed
            current_data = {
                "actor": r["actor"],
                "action": r["action"],
                "target": r["target"],
                "outcome": r["outcome"],
                "details": json.loads(r["details"]) if r["details"] else None,
                "ip": r["ip"],
                "prev_hash": prev_hash,
            }

            hash_input = prev_hash + json.dumps(current_data, sort_keys=True, separators=(",", ":"))
            computed_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

            if computed_hash != stored_hash:
                errors.append({
                    "id": r["id"],
                    "expected_hash": computed_hash,
                    "stored_hash": stored_hash,
                    "timestamp": r["timestamp"],
                })
            else:
                verified_count += 1

            prev_hash = stored_hash

        return {
            "verified": len(errors) == 0,
            "total_checked": len(rows),
            "verified_count": verified_count,
            "errors": errors,
            "last_hash": prev_hash if rows else "0" * 64,
        }