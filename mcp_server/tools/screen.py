"""MCP tool implementations for qgis.screen namespace."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.screen")


def screen_capture(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.screen.capture", params or {}, request_id="screen_capture")
