"""MCP tool implementations for qgis.web_gis namespace — 10 web GIS tools."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.web_gis")


def _dispatch(tool: str, params: dict, request_id: str) -> dict:
    client = QgisBridgeClient()
    return client.dispatch(tool, params or {}, request_id=request_id)


def web_gis_wms_load(params: dict) -> dict:
    """Load WMS (Web Map Service) layer."""
    return _dispatch("qgis.web_gis.wms_load", params, request_id="webgis_wms_load")


def web_gis_wfs_load(params: dict) -> dict:
    """Load WFS (Web Feature Service) layer."""
    return _dispatch("qgis.web_gis.wfs_load", params, request_id="webgis_wfs_load")


def web_gis_wmts_load(params: dict) -> dict:
    """Load WMTS (Web Map Tile Service) layer."""
    return _dispatch("qgis.web_gis.wmts_load", params, request_id="webgis_wmts_load")


def web_gis_xyz_tiles(params: dict) -> dict:
    """Load XYZ tile layer (OSM, Google, etc.)."""
    return _dispatch("qgis.web_gis.xyz_tiles", params, request_id="webgis_xyz_tiles")


def web_gis_ogc_api(params: dict) -> dict:
    """Load OGC API - Features layer."""
    return _dispatch("qgis.web_gis.ogc_api", params, request_id="webgis_ogc_api")


def web_gis_server_publish(params: dict) -> dict:
    """Publish layer/project to QGIS Server."""
    return _dispatch("qgis.web_gis.server_publish", params, request_id="webgis_server_publish")


def web_gis_getcapabilities(params: dict) -> dict:
    """Get capabilities document from OGC service."""
    return _dispatch("qgis.web_gis.getcapabilities", params, request_id="webgis_getcapabilities")


def web_gis_getfeature(params: dict) -> dict:
    """Get features from WFS/OGC API service."""
    return _dispatch("qgis.web_gis.getfeature", params, request_id="webgis_getfeature")


def web_gis_getcoverage(params: dict) -> dict:
    """Get coverage from WCS service."""
    return _dispatch("qgis.web_gis.getcoverage", params, request_id="webgis_getcoverage")


def web_gis_tile_cache(params: dict) -> dict:
    """Manage tile cache for web services."""
    return _dispatch("qgis.web_gis.tile_cache", params, request_id="webgis_tile_cache")