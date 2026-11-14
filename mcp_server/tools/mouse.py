"""MCP tool implementations for qgis.mouse namespace."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.mouse")


def mouse_scroll(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.mouse.scroll", params or {}, request_id="mouse_scroll")
