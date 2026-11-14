"""MCP tool implementations for qgis.agents, qgis.skills, qgis.verify namespaces."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.agents_skills")


def agents_list(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.agents.list", params or {}, request_id="agents_list")


def skills_list(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.skills.list", params or {}, request_id="skills_list")


def verify_status(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.verify.status", params or {}, request_id="verify_status")
