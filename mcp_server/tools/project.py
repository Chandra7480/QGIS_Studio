"""MCP tool implementations for qgis.project namespace."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.project")


def project_inspect(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.project.inspect", params or {}, request_id="proj_inspect")


def project_open(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.project.open", params or {}, request_id="proj_open")


def project_save(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.project.save", params or {}, request_id="proj_save")
