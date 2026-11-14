"""MCP tool implementations for qgis.keyboard namespace."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.keyboard")


def keyboard_type(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.keyboard.type", params or {}, request_id="keyboard_type")


def keyboard_hotkey(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.keyboard.hotkey", params or {}, request_id="keyboard_hotkey")
