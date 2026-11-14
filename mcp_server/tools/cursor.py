"""MCP tool implementations for qgis.cursor namespace."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.cursor")


def cursor_move(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.cursor.move", params or {}, request_id="cursor_move")


def cursor_click(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.cursor.click", params or {}, request_id="cursor_click")


def cursor_drag(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.cursor.drag", params or {}, request_id="cursor_drag")
