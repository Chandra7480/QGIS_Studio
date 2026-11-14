"""MCP tool implementations for qgis.canvas namespace."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.canvas")


def canvas_inspect(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.canvas.inspect", params or {}, request_id="canvas_inspect")
