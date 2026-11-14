"""MCP tool implementations for qgis.layers namespace."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.layers")


def layers_inspect(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.layers.inspect", params or {}, request_id="layers_inspect")


def layers_load(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.layers.load", params or {}, request_id="layers_load")


def layers_remove(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.layers.remove", params or {}, request_id="layers_remove")
