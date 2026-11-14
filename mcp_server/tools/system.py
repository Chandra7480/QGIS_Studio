"""MCP tool implementations for qgis.system namespace."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.system")


def system_inspect(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.system.inspect", params or {}, request_id="sys_inspect")


def system_health(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.system.health", params or {}, request_id="sys_health")
