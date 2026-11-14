"""MCP tool implementations for qgis.terrain namespace — 13 terrain analysis tools."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.terrain")


def _dispatch(tool: str, params: dict, request_id: str) -> dict:
    client = QgisBridgeClient()
    return client.dispatch(tool, params or {}, request_id=request_id)


def terrain_slope(params: dict) -> dict:
    """Calculate slope from DEM (degrees or percent)."""
    return _dispatch("qgis.terrain.slope", params, request_id="terrain_slope")


def terrain_aspect(params: dict) -> dict:
    """Calculate aspect from DEM (direction of slope)."""
    return _dispatch("qgis.terrain.aspect", params, request_id="terrain_aspect")


def terrain_hillshade(params: dict) -> dict:
    """Generate hillshade from DEM."""
    return _dispatch("qgis.terrain.hillshade", params, request_id="terrain_hillshade")


def terrain_contours(params: dict) -> dict:
    """Generate contour lines from DEM."""
    return _dispatch("qgis.terrain.contours", params, request_id="terrain_contours")


def terrain_roughness(params: dict) -> dict:
    """Calculate terrain roughness index."""
    return _dispatch("qgis.terrain.roughness", params, request_id="terrain_roughness")


def terrain_tpi(params: dict) -> dict:
    """Calculate Topographic Position Index (TPI)."""
    return _dispatch("qgis.terrain.tpi", params, request_id="terrain_tpi")


def terrain_tri(params: dict) -> dict:
    """Calculate Terrain Ruggedness Index (TRI)."""
    return _dispatch("qgis.terrain.tri", params, request_id="terrain_tri")


def terrain_curvature(params: dict) -> dict:
    """Calculate curvature (profile, plan, total)."""
    return _dispatch("qgis.terrain.curvature", params, request_id="terrain_curvature")


def terrain_profile_curvature(params: dict) -> dict:
    """Calculate profile curvature."""
    return _dispatch("qgis.terrain.profile_curvature", params, request_id="terrain_profile_curvature")


def terrain_plan_curvature(params: dict) -> dict:
    """Calculate plan curvature."""
    return _dispatch("qgis.terrain.plan_curvature", params, request_id="terrain_plan_curvature")


def terrain_flow_direction(params: dict) -> dict:
    """Calculate flow direction from DEM."""
    return _dispatch("qgis.terrain.flow_direction", params, request_id="terrain_flow_direction")


def terrain_flow_accumulation(params: dict) -> dict:
    """Calculate flow accumulation from DEM."""
    return _dispatch("qgis.terrain.flow_accumulation", params, request_id="terrain_flow_accumulation")


def terrain_catchment_area(params: dict) -> dict:
    """Calculate catchment area (specific catchment area)."""
    return _dispatch("qgis.terrain.catchment_area", params, request_id="terrain_catchment_area")


def terrain_ls_factor(params: dict) -> dict:
    """Calculate LS factor (slope length and steepness) for erosion modeling."""
    return _dispatch("qgis.terrain.ls_factor", params, request_id="terrain_ls_factor")


def terrain_ruggedness_index(params: dict) -> dict:
    """Calculate terrain ruggedness index (TRI from Riley et al.)."""
    return _dispatch("qgis.terrain.ruggedness_index", params, request_id="terrain_ruggedness_index")


def terrain_dem_processing(params: dict) -> dict:
    """Process DEM with multiple derivatives (slope, aspect, hillshade, etc.)."""
    return _dispatch("qgis.terrain.dem_processing", params, request_id="terrain_dem_processing")