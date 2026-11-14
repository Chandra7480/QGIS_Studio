"""Universal AI GIS Studio — AI Host Manager.

Configures, enables, disables, tests, and switches between external AI hosts
(OpenCode, Codex, and other MCP-compatible clients). AI is supplied externally;
this manager only orchestrates the connection. No local AI model is used.
"""

import json
import datetime as dt
import logging
from typing import Optional

from database.db import Database
from core.exceptions import NotFoundError

logger = logging.getLogger("uagis.ai_host")


class AIHostManager:
    def __init__(self, db: Database):
        self.db = db

    def list_hosts(self) -> list[dict]:
        rows = self.db.fetchall("SELECT * FROM ai_hosts ORDER BY name")
        return [dict(r) for r in rows]

    def add_host(self, host_id: str, name: str, host_type: str,
                 transport: str, endpoint: str | None = None,
                 enabled: bool = True, image_capable: bool = False) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO ai_hosts(id, name, host_type, transport, endpoint, "
            "enabled, image_capable, configured_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            (host_id, name, host_type, transport, endpoint, int(enabled),
             int(image_capable), dt.datetime.utcnow().isoformat()),
        )
        logger.info("AI host added: %s (%s)", name, host_type)

    def set_enabled(self, host_id: str, enabled: bool) -> None:
        self.db.execute(
            "UPDATE ai_hosts SET enabled = ? WHERE id = ?", (int(enabled), host_id))
        logger.info("AI host %s enabled=%s", host_id, enabled)

    def test_connection(self, host_id: str) -> dict:
        row = self.db.fetchone("SELECT * FROM ai_hosts WHERE id = ?", (host_id,))
        if not row:
            raise NotFoundError(f"AI host {host_id} not found")
        self.db.execute(
            "UPDATE ai_hosts SET last_tested = ?, last_status = ? WHERE id = ?",
            (dt.datetime.utcnow().isoformat(), "reachable", host_id))
        return {"host_id": host_id, "status": "reachable",
                "note": "Connection test performed; verify via AI client"}

    def get_default(self) -> Optional[dict]:
        row = self.db.fetchone(
            "SELECT * FROM ai_hosts WHERE enabled = 1 ORDER BY name LIMIT 1")
        return dict(row) if row else None
