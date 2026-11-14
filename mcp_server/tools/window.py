"""MCP tool implementations for qgis.window and qgis.dialog namespaces."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.window")


def window_inspect(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.window.inspect", params or {}, request_id="window_inspect")


def dialog_inspect(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.dialog.inspect", params or {}, request_id="dialog_inspect")
