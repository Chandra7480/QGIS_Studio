"""MCP tool implementations for qgis.vector namespace — 25 vector processing tools."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.vector")


def _dispatch(tool: str, params: dict, request_id: str) -> dict:
    client = QgisBridgeClient()
    return client.dispatch(tool, params or {}, request_id=request_id)


# ---- Core vector operations (M03 cluster) ----

def vector_buffer(params: dict) -> dict:
    """Buffer geometries by distance."""
    return _dispatch("qgis.vector.buffer", params, request_id="vector_buffer")


def vector_clip(params: dict) -> dict:
    """Clip vector layer by another layer."""
    return _dispatch("qgis.vector.clip", params, request_id="vector_clip")


def vector_dissolve(params: dict) -> dict:
    """Dissolve features by attribute or all."""
    return _dispatch("qgis.vector.dissolve", params, request_id="vector_dissolve")


def vector_intersection(params: dict) -> dict:
    """Intersect two vector layers."""
    return _dispatch("qgis.vector.intersection", params, request_id="vector_intersection")


def vector_union(params: dict) -> dict:
    """Union two vector layers."""
    return _dispatch("qgis.vector.union", params, request_id="vector_union")


def vector_difference(params: dict) -> dict:
    """Difference between two vector layers (input - overlay)."""
    return _dispatch("qgis.vector.difference", params, request_id="vector_difference")


def vector_merge(params: dict) -> dict:
    """Merge multiple vector layers into one."""
    return _dispatch("qgis.vector.merge", params, request_id="vector_merge")


def vector_repair(params: dict) -> dict:
    """Repair/fix invalid geometries."""
    return _dispatch("qgis.vector.repair", params, request_id="vector_repair")


def vector_split(params: dict) -> dict:
    """Split features by maximum distance or other criteria."""
    return _dispatch("qgis.vector.split", params, request_id="vector_split")


# ---- Geometry processing ----

def vector_centroids(params: dict) -> dict:
    """Calculate centroids of features."""
    return _dispatch("qgis.vector.centroids", params, request_id="vector_centroids")


def vector_convex_hull(params: dict) -> dict:
    """Generate convex hull(s) of features."""
    return _dispatch("qgis.vector.convex_hull", params, request_id="vector_convex_hull")


def vector_bounds(params: dict) -> dict:
    """Generate bounding boxes of features."""
    return _dispatch("qgis.vector.bounds", params, request_id="vector_bounds")


def vector_envelope(params: dict) -> dict:
    """Generate envelope (rectangular bounds) of features."""
    return _dispatch("qgis.vector.envelope", params, request_id="vector_envelope")


def vector_simplify(params: dict) -> dict:
    """Simplify geometries by tolerance."""
    return _dispatch("qgis.vector.simplify", params, request_id="vector_simplify")


def vector_smooth(params: dict) -> dict:
    """Smooth geometries by iterations/offset."""
    return _dispatch("qgis.vector.smooth", params, request_id="vector_smooth")


def vector_offset(params: dict) -> dict:
    """Offset line geometries by distance."""
    return _dispatch("qgis.vector.offset", params, request_id="vector_offset")


def vector_polygonize(params: dict) -> dict:
    """Polygonize line geometries."""
    return _dispatch("qgis.vector.polygonize", params, request_id="vector_polygonize")


def vector_lines_to_polygons(params: dict) -> dict:
    """Convert lines to polygons."""
    return _dispatch("qgis.vector.lines_to_polygons", params, request_id="vector_lines_to_polygons")


def vector_polygons_to_lines(params: dict) -> dict:
    """Convert polygons to lines (boundaries)."""
    return _dispatch("qgis.vector.polygons_to_lines", params, request_id="vector_polygons_to_lines")


def vector_multipart_to_singlepart(params: dict) -> dict:
    """Convert multipart features to singlepart."""
    return _dispatch("qgis.vector.multipart_to_singlepart", params, request_id="vector_multipart_to_singlepart")


def vector_singlepart_to_multipart(params: dict) -> dict:
    """Convert singlepart features to multipart by attribute."""
    return _dispatch("qgis.vector.singlepart_to_multipart", params, request_id="vector_singlepart_to_multipart")


def vector_extract_vertices(params: dict) -> dict:
    """Extract vertices from geometries as points."""
    return _dispatch("qgis.vector.extract_vertices", params, request_id="vector_extract_vertices")


def vector_add_geometry_attributes(params: dict) -> dict:
    """Add geometry attributes (area, length, perimeter, etc.)."""
    return _dispatch("qgis.vector.add_geometry_attributes", params, request_id="vector_add_geometry_attributes")


def vector_drop_m_z(params: dict) -> dict:
    """Drop M and/or Z values from geometries."""
    return _dispatch("qgis.vector.drop_m_z", params, request_id="vector_drop_m_z")


def vector_set_m_z(params: dict) -> dict:
    """Set M and/or Z values on geometries."""
    return _dispatch("qgis.vector.set_m_z", params, request_id="vector_set_m_z")