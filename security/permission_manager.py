"""Universal AI GIS Studio — Permission Manager.

Tool allowlists, agent permissions, user approval for destructive operations.
"""

import logging

from database.db import Database
from core.exceptions import UAGISPermissionError

logger = logging.getLogger("uagis.security.permission")


class PermissionManager:
    def __init__(self, db: Database):
        self.db = db

    def check_tool(self, agent_id: str, tool_id: str) -> bool:
        row = self.db.fetchone(
            "SELECT 1 FROM agent_tools WHERE agent_id = ? AND tool_id = ?",
            (agent_id, tool_id))
        if not row:
            logger.warning("Permission denied: agent %s -> tool %s", agent_id, tool_id)
            return False
        return True

    def require(self, agent_id: str, tool_id: str) -> None:
        if not self.check_tool(agent_id, tool_id):
            raise UAGISPermissionError(
                f"Agent {agent_id} not permitted to use tool {tool_id}")

    def destructive_approval_required(self, action_type: str) -> bool:
        """Certain actions always require user approval."""
        destructive = {"delete_layer", "overwrite_file", "remove_layer",
                       "destructive_db_op", "shell_command", "high_impact"}
        return action_type in destructive
