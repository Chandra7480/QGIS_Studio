"""MCP tool implementations for qgis.spatial namespace — 20 spatial analysis tools."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.spatial")


def _dispatch(tool: str, params: dict, request_id: str) -> dict:
    client = QgisBridgeClient()
    return client.dispatch(tool, params or {}, request_id=request_id)


# ---- Spatial joins ----

def spatial_join_attributes_by_location(params: dict) -> dict:
    """Join attributes from one layer to another by spatial relationship."""
    return _dispatch("qgis.spatial.join_attributes_by_location", params, request_id="spatial_join_attributes_by_location")


def spatial_join_attributes_by_nearest(params: dict) -> dict:
    """Join attributes by nearest feature distance."""
    return _dispatch("qgis.spatial.join_attributes_by_nearest", params, request_id="spatial_join_attributes_by_nearest")


def spatial_join_attributes_by_field_value(params: dict) -> dict:
    """Join attributes by matching field values (non-spatial)."""
    return _dispatch("qgis.spatial.join_attributes_by_field_value", params, request_id="spatial_join_attributes_by_field_value")


# ---- Proximity & distance ----

def spatial_distance_matrix(params: dict) -> dict:
    """Calculate distance matrix between points."""
    return _dispatch("qgis.spatial.distance_matrix", params, request_id="spatial_distance_matrix")


def spatial_nearest_neighbor(params: dict) -> dict:
    """Find k nearest neighbors for each feature."""
    return _dispatch("qgis.spatial.nearest_neighbor", params, request_id="spatial_nearest_neighbor")


def spatial_point_distance(params: dict) -> dict:
    """Calculate distance from points to nearest feature in another layer."""
    return _dispatch("qgis.spatial.point_distance", params, request_id="spatial_point_distance")


# ---- Overlay analysis ----

def spatial_intersection(params: dict) -> dict:
    """Intersect two vector layers."""
    return _dispatch("qgis.spatial.intersection", params, request_id="spatial_intersection")


def spatial_union(params: dict) -> dict:
    """Union two vector layers."""
    return _dispatch("qgis.spatial.union", params, request_id="spatial_union")


def spatial_difference(params: dict) -> dict:
    """Difference between two vector layers (input - overlay)."""
    return _dispatch("qgis.spatial.difference", params, request_id="spatial_difference")


def spatial_symmetrical_difference(params: dict) -> dict:
    """Symmetrical difference (XOR) between two layers."""
    return _dispatch("qgis.spatial.symmetrical_difference", params, request_id="spatial_symmetrical_difference")


def spatial_clip(params: dict) -> dict:
    """Clip input layer by overlay layer."""
    return _dispatch("qgis.spatial.clip", params, request_id="spatial_clip")


# ---- Density & clustering ----

def spatial_count_points_in_polygon(params: dict) -> dict:
    """Count points within polygons."""
    return _dispatch("qgis.spatial.count_points_in_polygon", params, request_id="spatial_count_points_in_polygon")


def spatial_heatmap(params: dict) -> dict:
    """Generate kernel density heatmap from points."""
    return _dispatch("qgis.spatial.heatmap", params, request_id="spatial_heatmap")


def spatial_kmeans_clustering(params: dict) -> dict:
    """K-means clustering of point features."""
    return _dispatch("qgis.spatial.kmeans_clustering", params, request_id="spatial_kmeans_clustering")


def spatial_dbscan_clustering(params: dict) -> dict:
    """DBSCAN density-based clustering."""
    return _dispatch("qgis.spatial.dbscan_clustering", params, request_id="spatial_dbscan_clustering")


# ---- Interpolation ----

def spatial_idw_interpolation(params: dict) -> dict:
    """Inverse Distance Weighted (IDW) interpolation."""
    return _dispatch("qgis.spatial.idw_interpolation", params, request_id="spatial_idw_interpolation")


def spatial_tin_interpolation(params: dict) -> dict:
    """TIN (Triangulated Irregular Network) interpolation."""
    return _dispatch("qgis.spatial.tin_interpolation", params, request_id="spatial_tin_interpolation")


# ---- Spatial statistics ----

def spatial_morans_i(params: dict) -> dict:
    """Calculate Moran's I spatial autocorrelation."""
    return _dispatch("qgis.spatial.morans_i", params, request_id="spatial_morans_i")


def spatial_getis_ord(params: dict) -> dict:
    """Calculate Getis-Ord Gi* hot spot analysis."""
    return _dispatch("qgis.spatial.getis_ord", params, request_id="spatial_getis_ord")


def spatial_gearys_c(params: dict) -> dict:
    """Calculate Geary's C spatial autocorrelation."""
    return _dispatch("qgis.spatial.gearys_c", params, request_id="spatial_gearys_c")