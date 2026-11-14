"""MCP tool implementations for qgis.raster, qgis.vector, qgis.spatial namespaces."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.vector_raster")


def raster_info(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.raster.info", params or {}, request_id="raster_info")


def vector_info(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.vector.info", params or {}, request_id="vector_info")


def spatial_info(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.spatial.info", params or {}, request_id="spatial_info")
