"""MCP tool implementations for qgis.remote_sensing namespace — 11 remote sensing tools."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.remote_sensing")


def _dispatch(tool: str, params: dict, request_id: str) -> dict:
    client = QgisBridgeClient()
    return client.dispatch(tool, params or {}, request_id=request_id)


def remote_sensing_satellite_import(params: dict) -> dict:
    """Import satellite imagery (GeoTIFF, SAFE, etc.) into QGIS."""
    return _dispatch("qgis.remote_sensing.satellite_import", params, request_id="rs_satellite_import")


def remote_sensing_band_combinations(params: dict) -> dict:
    """Create band combinations (RGB, false color, etc.) from multi-band imagery."""
    return _dispatch("qgis.remote_sensing.band_combinations", params, request_id="rs_band_combinations")


def remote_sensing_spectral_indices(params: dict) -> dict:
    """Calculate spectral indices (NDVI, EVI, SAVI, NBR, MNDWI, etc.)."""
    return _dispatch("qgis.remote_sensing.spectral_indices", params, request_id="rs_spectral_indices")


def remote_sensing_pan_sharpening(params: dict) -> dict:
    """Pan-sharpen multispectral imagery using panchromatic band."""
    return _dispatch("qgis.remote_sensing.pan_sharpening", params, request_id="rs_pan_sharpening")


def remote_sensing_atmospheric_correction(params: dict) -> dict:
    """Apply atmospheric correction (DOS, FLAASH, 6S, etc.)."""
    return _dispatch("qgis.remote_sensing.atmospheric_correction", params, request_id="rs_atmospheric_correction")


def remote_sensing_radiometric_correction(params: dict) -> dict:
    """Apply radiometric correction (calibration, normalization)."""
    return _dispatch("qgis.remote_sensing.radiometric_correction", params, request_id="rs_radiometric_correction")


def remote_sensing_geometric_correction(params: dict) -> dict:
    """Apply geometric correction (orthorectification, co-registration)."""
    return _dispatch("qgis.remote_sensing.geometric_correction", params, request_id="rs_geometric_correction")


def remote_sensing_image_preparation(params: dict) -> dict:
    """Prepare imagery: clip, reproject, resample, subset bands."""
    return _dispatch("qgis.remote_sensing.image_preparation", params, request_id="rs_image_preparation")


def remote_sensing_mosaic(params: dict) -> dict:
    """Mosaic multiple satellite scenes into single image."""
    return _dispatch("qgis.remote_sensing.mosaic", params, request_id="rs_mosaic")


def remote_sensing_resampling(params: dict) -> dict:
    """Resample imagery to different resolution or projection."""
    return _dispatch("qgis.remote_sensing.resampling", params, request_id="rs_resampling")


def remote_sensing_vegetation_indices(params: dict) -> dict:
    """Calculate vegetation indices (NDVI, EVI, SAVI, ARVI, etc.)."""
    return _dispatch("qgis.remote_sensing.vegetation_indices", params, request_id="rs_vegetation_indices")