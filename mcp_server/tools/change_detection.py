"""MCP tool implementations for qgis.change_detection namespace — 11 change detection tools."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.change_detection")


def _dispatch(tool: str, params: dict, request_id: str) -> dict:
    client = QgisBridgeClient()
    return client.dispatch(tool, params or {}, request_id=request_id)


def change_detection_temporal_comparison(params: dict) -> dict:
    """Compare two temporal images (t1, t2) for changes."""
    return _dispatch("qgis.change_detection.temporal_comparison", params, request_id="cd_temporal_comparison")


def change_detection_raster_difference(params: dict) -> dict:
    """Calculate raster difference (t2 - t1) or ratio (t2 / t1)."""
    return _dispatch("qgis.change_detection.raster_difference", params, request_id="cd_raster_difference")


def change_detection_landcover_change(params: dict) -> dict:
    """Detect land cover changes between two classified rasters."""
    return _dispatch("qgis.change_detection.landcover_change", params, request_id="cd_landcover_change")


def change_detection_change_report(params: dict) -> dict:
    """Generate change detection report with statistics and maps."""
    return _dispatch("qgis.change_detection.change_report", params, request_id="cd_change_report")


def change_detection_multitemporal_change(params: dict) -> dict:
    """Analyze changes across multiple time periods."""
    return _dispatch("qgis.change_detection.multitemporal_change", params, request_id="cd_multitemporal_change")


def change_detection_image_ratio(params: dict) -> dict:
    """Calculate image ratio (t2 / t1) for change enhancement."""
    return _dispatch("qgis.change_detection.image_ratio", params, request_id="cd_image_ratio")


def change_detection_image_difference(params: dict) -> dict:
    """Calculate image difference (t2 - t1) for change enhancement."""
    return _dispatch("qgis.change_detection.image_difference", params, request_id="cd_image_difference")


def change_detection_ndvi_change(params: dict) -> dict:
    """Calculate NDVI change between two dates."""
    return _dispatch("qgis.change_detection.ndvi_change", params, request_id="cd_ndvi_change")


def change_detection_urban_expansion(params: dict) -> dict:
    """Detect urban expansion from time series imagery."""
    return _dispatch("qgis.change_detection.urban_expansion", params, request_id="cd_urban_expansion")


def change_detection_deforestation(params: dict) -> dict:
    """Detect deforestation from time series imagery."""
    return _dispatch("qgis.change_detection.deforestation", params, request_id="cd_deforestation")


def change_detection_flood_mapping(params: dict) -> dict:
    """Map flood extent changes between dates."""
    return _dispatch("qgis.change_detection.flood_mapping", params, request_id="cd_flood_mapping")


def change_detection_burned_area(params: dict) -> dict:
    """Map burned area from pre/post fire imagery."""
    return _dispatch("qgis.change_detection.burned_area", params, request_id="cd_burned_area")


def change_detection_trend_analysis(params: dict) -> dict:
    """Analyze temporal trends in time series imagery."""
    return _dispatch("qgis.change_detection.trend_analysis", params, request_id="cd_trend_analysis")


def change_detection_time_series_analysis(params: dict) -> dict:
    """Time series analysis (smoothing, decomposition, forecasting)."""
    return _dispatch("qgis.change_detection.time_series_analysis", params, request_id="cd_time_series_analysis")


def change_detection_change_vector_analysis(params: dict) -> dict:
    """Change Vector Analysis (CVA) for multi-band change detection."""
    return _dispatch("qgis.change_detection.change_vector_analysis", params, request_id="cd_change_vector_analysis")