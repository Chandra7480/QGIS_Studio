"""MCP tool implementations for qgis.hydrology namespace — 12 hydrological analysis tools."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.hydrology")


def _dispatch(tool: str, params: dict, request_id: str) -> dict:
    client = QgisBridgeClient()
    return client.dispatch(tool, params or {}, request_id=request_id)


def hydrology_stream_order(params: dict) -> dict:
    """Calculate Strahler/Horton stream order from stream network."""
    return _dispatch("qgis.hydrology.stream_order", params, request_id="hydrology_stream_order")


def hydrology_catchment_area(params: dict) -> dict:
    """Calculate catchment area and drainage basins."""
    return _dispatch("qgis.hydrology.catchment_area", params, request_id="hydrology_catchment_area")


def hydrology_flood_mapping(params: dict) -> dict:
    """Generate flood risk mapping from DEM and hydrological parameters."""
    return _dispatch("qgis.hydrology.flood_mapping", params, request_id="hydrology_flood_mapping")


def hydrology_hec_ras_prep(params: dict) -> dict:
    """Prepare HEC-RAS input data from DEM and cross-sections."""
    return _dispatch("qgis.hydrology.hec_ras_prep", params, request_id="hydrology_hec_ras_prep")


def hydrology_stream_length(params: dict) -> dict:
    """Calculate stream length and longitudinal profiles."""
    return _dispatch("qgis.hydrology.stream_length", params, request_id="hydrology_stream_length")


def hydrology_flow_length(params: dict) -> dict:
    """Calculate flow path length from each cell to outlet."""
    return _dispatch("qgis.hydrology.flow_length", params, request_id="hydrology_flow_length")


def hydrology_topographic_index(params: dict) -> dict:
    """Calculate Topographic Wetness Index (TWI) and related indices."""
    return _dispatch("qgis.hydrology.topographic_index", params, request_id="hydrology_topographic_index")


def hydrology_sed_transport(params: dict) -> dict:
    """Calculate sediment transport capacity and yield."""
    return _dispatch("qgis.hydrology.sed_transport", params, request_id="hydrology_sed_transport")


def hydrology_flood_extent(params: dict) -> dict:
    """Map flood extent for given return periods or water levels."""
    return _dispatch("qgis.hydrology.flood_extent", params, request_id="hydrology_flood_extent")


def hydrology_flood_depth(params: dict) -> dict:
    """Calculate flood depth and velocity rasters."""
    return _dispatch("qgis.hydrology.flood_depth", params, request_id="hydrology_flood_depth")


def hydrology_culvert_analysis(params: dict) -> dict:
    """Analyze culvert hydraulics and capacity."""
    return _dispatch("qgis.hydrology.culvert", params, request_id="hydrology_culvert")


def hydrology_bridge_analysis(params: dict) -> dict:
    """Analyze bridge hydraulics, scour, and clearance."""
    return _dispatch("qgis.hydrology.bridge", params, request_id="hydrology_bridge")