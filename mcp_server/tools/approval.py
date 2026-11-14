"""MCP tool implementations for qgis.approval namespace."""

from mcp_server.approval import get_approval_manager
from core.logging import get_logger

logger = get_logger("mcp.tools.approval")


def approval_grant(params: dict) -> dict:
    """Grant approval for a pending tool execution."""
    approval_id = params.get("approval_id")
    granted_by = params.get("granted_by", "user")

    if not approval_id:
        return {"granted": False, "approval_id": "", "error": "approval_id required"}

    manager = get_approval_manager()
    success = manager.grant(approval_id, granted_by)

    return {"granted": success, "approval_id": approval_id}


def approval_deny(params: dict) -> dict:
    """Deny approval for a pending tool execution."""
    approval_id = params.get("approval_id")
    denied_by = params.get("denied_by", "user")
    reason = params.get("reason", "")

    if not approval_id:
        return {"denied": False, "approval_id": "", "error": "approval_id required"}

    manager = get_approval_manager()
    success = manager.deny(approval_id, denied_by)

    return {"denied": success, "approval_id": approval_id, "reason": reason}


def approval_list(params: dict) -> dict:
    """List all pending approval requests."""
    manager = get_approval_manager()
    pending = manager.list_pending()

    return {
        "pending": [
            {
                "approval_id": req.approval_id,
                "tool_name": req.tool_name,
                "request_id": req.request_id,
                "created_at": req.created_at,
                "expires_at": req.expires_at,
                "params": req.params,
            }
            for req in pending
        ],
        "count": len(pending),
    }