"""MCP tool implementations for qgis.database, qgis.layout, qgis.workflow namespaces."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.database_layout")


def database_info(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.database.info", params or {}, request_id="db_info")


def layout_info(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.layout.info", params or {}, request_id="layout_info")


def workflow_execute(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.workflow.execute", params or {}, request_id="workflow_exec")
