"""Universal AI GIS Studio — Approval Manager.

Handles approval gates for destructive operations. Tracks pending approvals
and provides grant/deny tools.
"""

import uuid
import time
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from threading import Lock

from core.logging import get_logger
from core.exceptions import MCPError

logger = get_logger("mcp.approval")


@dataclass
class ApprovalRequest:
    """A pending approval request."""
    approval_id: str
    tool_name: str
    params: dict
    request_id: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 300)  # 5 min
    status: str = "pending"  # pending, granted, denied, expired
    granted_by: Optional[str] = None


class ApprovalManager:
    """Manages approval requests for tools requiring human approval."""

    def __init__(self, ttl_seconds: int = 300):
        self._pending: Dict[str, ApprovalRequest] = {}
        self._lock = Lock()
        self._ttl_seconds = ttl_seconds

    def create_request(self, tool_name: str, params: dict, request_id: str) -> ApprovalRequest:
        """Create a new approval request."""
        approval_id = f"appr_{uuid.uuid4().hex[:12]}"
        request = ApprovalRequest(
            approval_id=approval_id,
            tool_name=tool_name,
            params=params,
            request_id=request_id,
            expires_at=time.time() + self._ttl_seconds,
        )
        with self._lock:
            self._pending[approval_id] = request
        logger.info("Created approval request %s for tool %s", approval_id, tool_name)
        return request

    def get_request(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Get a pending approval request by ID."""
        with self._lock:
            return self._pending.get(approval_id)

    def grant(self, approval_id: str, granted_by: str = "user") -> bool:
        """Grant an approval request."""
        with self._lock:
            request = self._pending.get(approval_id)
            if request is None or request.status != "pending":
                return False
            if time.time() > request.expires_at:
                request.status = "expired"
                return False
            request.status = "granted"
            request.granted_by = granted_by
            logger.info("Approval %s granted by %s", approval_id, granted_by)
            return True

    def deny(self, approval_id: str, denied_by: str = "user") -> bool:
        """Deny an approval request."""
        with self._lock:
            request = self._pending.get(approval_id)
            if request is None or request.status != "pending":
                return False
            request.status = "denied"
            request.granted_by = denied_by
            logger.info("Approval %s denied by %s", approval_id, denied_by)
            return True

    def check_and_consume(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Check if approval is granted and consume it (remove from pending)."""
        with self._lock:
            request = self._pending.get(approval_id)
            if request is None:
                return None
            if request.status == "granted":
                del self._pending[approval_id]
                return request
            elif request.status in ("denied", "expired"):
                del self._pending[approval_id]
            return None

    def cleanup_expired(self) -> int:
        """Remove expired approval requests. Returns count removed."""
        now = time.time()
        with self._lock:
            expired = [aid for aid, req in self._pending.items() if req.expires_at < now]
            for aid in expired:
                del self._pending[aid]
            return len(expired)

    def list_pending(self) -> list[ApprovalRequest]:
        """List all pending approval requests."""
        with self._lock:
            self.cleanup_expired()
            return list(self._pending.values())


# Global approval manager instance
_approval_manager: Optional[ApprovalManager] = None


def get_approval_manager() -> ApprovalManager:
    """Get or create the global approval manager."""
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = ApprovalManager()
    return _approval_manager


def check_approval_required(spec, params: dict, request_id: str) -> Optional[ApprovalRequest]:
    """Check if tool requires approval and create request if needed."""
    if not spec.require_approval:
        return None

    # Check for approval_token in params
    approval_token = params.pop("approval_token", None)
    if approval_token:
        # Try to consume existing approval
        manager = get_approval_manager()
        request = manager.check_and_consume(approval_token)
        if request and request.status == "granted":
            return None  # Approval granted, proceed
        elif request and request.status == "denied":
            raise MCPError(
                f"Approval denied for {spec.name}",
                error_code="APPROVAL_DENIED",
                context={"approval_id": approval_token},
            )
        else:
            raise MCPError(
                f"Invalid or expired approval token: {approval_token}",
                error_code="APPROVAL_INVALID",
                context={"approval_id": approval_token},
            )

    # No approval token - create new request
    manager = get_approval_manager()
    return manager.create_request(spec.name, params, request_id)