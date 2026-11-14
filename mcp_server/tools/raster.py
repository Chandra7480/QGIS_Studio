"""MCP tool implementations for qgis.raster namespace — 25 raster processing tools."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.raster")


def _dispatch(tool: str, params: dict, request_id: str) -> dict:
    client = QgisBridgeClient()
    return client.dispatch(tool, params or {}, request_id=request_id)


# ---- Core raster operations (M04 cluster) ----

def raster_calculator(params: dict) -> dict:
    """Raster calculator with expression (e.g., 'A * 2 + B')."""
    return _dispatch("qgis.raster.calculator", params, request_id="raster_calculator")


def raster_reclassify(params: dict) -> dict:
    """Reclassify raster values by table or ranges."""
    return _dispatch("qgis.raster.reclassify", params, request_id="raster_reclassify")


def raster_mosaic(params: dict) -> dict:
    """Mosaic/merge multiple raster layers into one."""
    return _dispatch("qgis.raster.mosaic", params, request_id="raster_mosaic")


def raster_clip(params: dict) -> dict:
    """Clip raster by mask layer (vector polygon)."""
    return _dispatch("qgis.raster.clip", params, request_id="raster_clip")


def raster_resample(params: dict) -> dict:
    """Resample raster to different resolution/CRS."""
    return _dispatch("qgis.raster.resample", params, request_id="raster_resample")


def raster_convert(params: dict) -> dict:
    """Convert raster format (GeoTIFF, COG, etc.)."""
    return _dispatch("qgis.raster.convert", params, request_id="raster_convert")


def raster_band_ops(params: dict) -> dict:
    """Band operations: extract, reorder, math between bands."""
    return _dispatch("qgis.raster.band_ops", params, request_id="raster_band_ops")


# ---- Terrain analysis ----

def raster_hillshade(params: dict) -> dict:
    """Generate hillshade from DEM."""
    return _dispatch("qgis.raster.hillshade", params, request_id="raster_hillshade")


def raster_slope(params: dict) -> dict:
    """Calculate slope from DEM (degrees or percent)."""
    return _dispatch("qgis.raster.slope", params, request_id="raster_slope")


def raster_aspect(params: dict) -> dict:
    """Calculate aspect from DEM (direction of slope)."""
    return _dispatch("qgis.raster.aspect", params, request_id="raster_aspect")


def raster_roughness(params: dict) -> dict:
    """Calculate terrain roughness index (TRI)."""
    return _dispatch("qgis.raster.roughness", params, request_id="raster_roughness")


def raster_tpi(params: dict) -> dict:
    """Calculate Topographic Position Index (TPI)."""
    return _dispatch("qgis.raster.tpi", params, request_id="raster_tpi")


def raster_curvature(params: dict) -> dict:
    """Calculate curvature (profile, plan, total)."""
    return _dispatch("qgis.raster.curvature", params, request_id="raster_curvature")


# ---- Zonal statistics ----

def raster_zonal_stats(params: dict) -> dict:
    """Calculate zonal statistics (mean, sum, count, min, max, std) for zones."""
    return _dispatch("qgis.raster.zonal_stats", params, request_id="raster_zonal_stats")


def raster_zonal_histogram(params: dict) -> dict:
    """Calculate histogram of raster values per zone."""
    return _dispatch("qgis.raster.zonal_histogram", params, request_id="raster_zonal_histogram")


# ---- Raster analysis ----

def raster_proximity(params: dict) -> dict:
    """Calculate proximity (distance) to target values."""
    return _dispatch("qgis.raster.proximity", params, request_id="raster_proximity")


def raster_sieve(params: dict) -> dict:
    """Remove small raster polygons (sieve filter)."""
    return _dispatch("qgis.raster.sieve", params, request_id="raster_sieve")


def raster_polygonize(params: dict) -> dict:
    """Convert raster to vector polygons (raster to vector)."""
    return _dispatch("qgis.raster.polygonize", params, request_id="raster_polygonize")


def raster_fill_nodata(params: dict) -> dict:
    """Fill NoData areas by interpolation."""
    return _dispatch("qgis.raster.fill_nodata", params, request_id="raster_fill_nodata")


def raster_warp(params: dict) -> dict:
    """Warp/reproject raster to new CRS/resolution."""
    return _dispatch("qgis.raster.warp", params, request_id="raster_warp")


def raster_clip_extent(params: dict) -> dict:
    """Clip raster to extent [xmin, ymin, xmax, ymax]."""
    return _dispatch("qgis.raster.clip_extent", params, request_id="raster_clip_extent")


def raster_translate(params: dict) -> dict:
    """Translate/convert raster with options (compression, tiles, etc.)."""
    return _dispatch("qgis.raster.translate", params, request_id="raster_translate")


def raster_contour(params: dict) -> dict:
    """Generate contour lines from raster."""
    return _dispatch("qgis.raster.contour", params, request_id="raster_contour")


def raster_rgb_to_pct(params: dict) -> dict:
    """Convert RGB raster to paletted (color table)."""
    return _dispatch("qgis.raster.rgb_to_pct", params, request_id="raster_rgb_to_pct")


def raster_pct_to_rgb(params: dict) -> dict:
    """Convert paletted raster to RGB."""
    return _dispatch("qgis.raster.pct_to_rgb", params, request_id="raster_pct_to_rgb")


def raster_info(params: dict) -> dict:
    """Get raster layer information (bands, dimensions, CRS, extent)."""
    return _dispatch("qgis.raster.info", params, request_id="raster_info")