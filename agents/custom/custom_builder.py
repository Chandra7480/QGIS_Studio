"""Custom Agent Builder: user-defined agents with permissions and tool limits."""

import uuid
import json
import datetime as dt
import logging

from database.db import Database
from core.exceptions import NotFoundError

logger = logging.getLogger("uagis.custom_agent")


class CustomAgentBuilder:
    def __init__(self, db: Database):
        self.db = db

    def create(self, spec: dict) -> str:
        """Create a custom agent.

        spec: name, description, instructions, ai_host or API profile,
              allowed_mcp_tools, assigned_skills, permission_level,
              max_steps, timeout, output_format
        """
        agent_id = f"agent_custom_{uuid.uuid4().hex[:10]}"
        now = dt.datetime.utcnow().isoformat()
        self.db.execute(
            "INSERT INTO agents(id, name, description, agent_type, instructions, "
            "ai_host_id, permission_level, max_steps, timeout_seconds, "
            "output_format, enabled, created_at, updated_at) "
            "VALUES(?, ?, ?, 'custom', ?, ?, ?, ?, ?, ?, 1, ?, ?)",
            (agent_id, spec.get("name", "Custom Agent"),
             spec.get("description", ""), spec.get("instructions", ""),
             spec.get("ai_host_id"), spec.get("permission_level", "standard"),
             int(spec.get("max_steps", 10)), int(spec.get("timeout_seconds", 300)),
             spec.get("output_format", "text"), now, now))
        # store allowed tools + skills as JSON in a flexible way
        self.db.execute(
            "INSERT OR REPLACE INTO agent_tools(agent_id, tool_id) VALUES(?, ?)",
            (agent_id, "__custom_spec__"))  # placeholder
        logger.info("Custom agent created: %s", agent_id)
        return agent_id

    def get(self, agent_id: str) -> dict | None:
        row = self.db.fetchone("SELECT * FROM agents WHERE id = ? AND agent_type = 'custom'",
                               (agent_id,))
        return dict(row) if row else None
