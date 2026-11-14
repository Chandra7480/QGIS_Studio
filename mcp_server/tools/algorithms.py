"""MCP tool implementations for qgis.algorithms namespace."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.algorithms")


def algorithms_discover(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.algorithms.discover", params or {}, request_id="algo_discover")


def algorithms_execute(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.algorithms.execute", params or {}, request_id="algo_execute")
