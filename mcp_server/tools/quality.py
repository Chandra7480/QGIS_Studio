"""MCP tool implementations for qgis.quality namespace — 15 quality assurance tools."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.quality")


def _dispatch(tool: str, params: dict, request_id: str) -> dict:
    client = QgisBridgeClient()
    return client.dispatch(tool, params or {}, request_id=request_id)


def quality_topology_check(params: dict) -> dict:
    """Check vector topology (dangles, intersections, gaps, overlaps)."""
    return _dispatch("qgis.quality.topology_check", params, request_id="qual_topology_check")


def quality_geometry_valid(params: dict) -> dict:
    """Validate geometry validity and fix errors."""
    return _dispatch("qgis.quality.geometry_valid", params, request_id="qual_geometry_valid")


def quality_duplicates(params: dict) -> dict:
    """Find duplicate features (geometry and/or attributes)."""
    return _dispatch("qgis.quality.duplicates", params, request_id="qual_duplicates")


def quality_self_intersect(params: dict) -> dict:
    """Find self-intersections in polygons."""
    return _dispatch("qgis.quality.self_intersect", params, request_id="qual_self_intersect")


def quality_gaps(params: dict) -> dict:
    """Find gaps between adjacent polygons."""
    return _dispatch("qgis.quality.gaps", params, request_id="qual_gaps")


def quality_overlaps(params: dict) -> dict:
    """Find overlaps between polygons."""
    return _dispatch("qgis.quality.overlaps", params, request_id="qual_overlaps")


def quality_attr_rules(params: dict) -> dict:
    """Validate attribute rules (constraints, expressions)."""
    return _dispatch("qgis.quality.attr_rules", params, request_id="qual_attr_rules")


def quality_domain_check(params: dict) -> dict:
    """Check attribute values against domain/coded values."""
    return _dispatch("qgis.quality.domain_check", params, request_id="qual_domain_check")


def quality_completeness(params: dict) -> dict:
    """Check data completeness (missing values, required fields)."""
    return _dispatch("qgis.quality.completeness", params, request_id="qual_completeness")


def quality_consistency(params: dict) -> dict:
    """Check cross-layer consistency (referential integrity)."""
    return _dispatch("qgis.quality.consistency", params, request_id="qual_consistency")


def quality_accuracy(params: dict) -> dict:
    """Check positional accuracy against reference."""
    return _dispatch("qgis.quality.accuracy", params, request_id="qual_accuracy")


def quality_precision(params: dict) -> dict:
    """Check coordinate precision and snapping."""
    return _dispatch("qgis.quality.precision", params, request_id="qual_precision")


def quality_lineage(params: dict) -> dict:
    """Track data lineage and provenance."""
    return _dispatch("qgis.quality.lineage", params, request_id="qual_lineage")


def quality_metadata(params: dict) -> dict:
    """Validate and manage metadata (ISO 19115/19139)."""
    return _dispatch("qgis.quality.metadata", params, request_id="qual_metadata")


def quality_report(params: dict) -> dict:
    """Generate quality assurance report."""
    return _dispatch("qgis.quality.report", params, request_id="qual_report")