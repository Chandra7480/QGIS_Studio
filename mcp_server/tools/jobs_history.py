"""MCP tool implementations for qgis.jobs, qgis.history, qgis.plugins namespaces."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.jobs_history")


def jobs_cancel(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.jobs.cancel", params or {}, request_id="jobs_cancel")


def history_inspect(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.history.inspect", params or {}, request_id="history_inspect")


def plugins_list(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.plugins.list", params or {}, request_id="plugins_list")
