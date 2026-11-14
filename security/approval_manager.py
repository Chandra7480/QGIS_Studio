"""Universal AI GIS Studio — Approval Manager.

User consent required before destructive operations.
"""

import uuid
import datetime as dt
import logging

from database.db import Database
from core.exceptions import NotFoundError

logger = logging.getLogger("uagis.security.approval")


class ApprovalManager:
    def __init__(self, db: Database):
        self.db = db

    def request(self, action_type: str, target: str, requested_by: str) -> str:
        aid = f"approval_{uuid.uuid4().hex[:10]}"
        self.db.execute(
            "INSERT INTO approvals(id, action_type, target, requested_by, status) "
            "VALUES(?, ?, ?, ?, 'pending')",
            (aid, action_type, target, requested_by))
        logger.info("Approval requested: %s %s by %s", action_type, target, requested_by)
        return aid

    def decide(self, approval_id: str, decision: str, decided_by: str) -> None:
        if decision not in ("approved", "denied"):
            raise ValueError("decision must be 'approved' or 'denied'")
        row = self.db.fetchone("SELECT * FROM approvals WHERE id = ?", (approval_id,))
        if not row:
            raise NotFoundError(f"Approval {approval_id} not found")
        self.db.execute(
            "UPDATE approvals SET status = ?, decided_at = datetime('now'), decided_by = ? "
            "WHERE id = ?",
            (decision, decided_by, approval_id))
        logger.info("Approval %s: %s by %s", approval_id, decision, decided_by)

    def is_approved(self, approval_id: str) -> bool:
        row = self.db.fetchone("SELECT status FROM approvals WHERE id = ?", (approval_id,))
        return bool(row and row["status"] == "approved")
