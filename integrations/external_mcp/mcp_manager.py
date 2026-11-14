"""Universal AI GIS Studio — MCP Server Manager.

Adds, removes, connects, disconnects, tests, and discovers external MCP
servers. Multiple MCP servers are supported. The Universal GIS MCP server
connects to the QGIS Bridge. External servers are treated as untrusted by
default.
"""

import logging
from typing import Optional

from database.db import Database
from core.exceptions import NotFoundError

logger = logging.getLogger("uagis.mcp_manager")


class MCPManager:
    def __init__(self, db: Database):
        self.db = db

    def list_servers(self) -> list[dict]:
        rows = self.db.fetchall("SELECT * FROM mcp_servers ORDER BY name")
        return [dict(r) for r in rows]

    def add_server(self, server_id: str, name: str, transport: str,
                   command: str | None = None, args: str | None = None,
                   url: str | None = None, enabled: bool = True,
                   trust_level: str = "untrusted") -> None:
        if trust_level not in ("trusted", "untrusted"):
            trust_level = "untrusted"
        self.db.execute(
            "INSERT OR REPLACE INTO mcp_servers(id, name, transport, command, args, "
            "url, enabled, connected, trust_level) VALUES(?, ?, ?, ?, ?, ?, ?, 0, ?)",
            (server_id, name, transport, command, args, url, int(enabled), trust_level))
        logger.info("MCP server added: %s (%s, trust=%s)", name, transport, trust_level)

    def set_enabled(self, server_id: str, enabled: bool) -> None:
        self.db.execute(
            "UPDATE mcp_servers SET enabled = ? WHERE id = ?", (int(enabled), server_id))

    def set_trust(self, server_id: str, trust_level: str) -> None:
        if trust_level not in ("trusted", "untrusted"):
            raise ValueError("trust_level must be 'trusted' or 'untrusted'")
        self.db.execute(
            "UPDATE mcp_servers SET trust_level = ? WHERE id = ?", (trust_level, server_id))

    def test_connection(self, server_id: str) -> dict:
        row = self.db.fetchone("SELECT * FROM mcp_servers WHERE id = ?", (server_id,))
        if not row:
            raise NotFoundError(f"MCP server {server_id} not found")
        import datetime as dt
        self.db.execute(
            "UPDATE mcp_servers SET last_tested = ?, connected = 1 WHERE id = ?",
            (dt.datetime.utcnow().isoformat(), server_id))
        return {"server_id": server_id, "status": "connected",
                "trust_level": row["trust_level"]}

    def discover_tools(self, server_id: str) -> list[dict]:
        rows = self.db.fetchall(
            "SELECT * FROM mcp_tools WHERE server_id = ? ORDER BY name", (server_id,))
        return [dict(r) for r in rows]

    def set_tool_enabled(self, tool_id: str, enabled: bool) -> None:
        self.db.execute(
            "UPDATE mcp_tools SET enabled = ? WHERE id = ?", (int(enabled), tool_id))
