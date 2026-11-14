"""MCP tool implementations for qgis.field_data namespace — 8 field data tools."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.field_data")


def _dispatch(tool: str, params: dict, request_id: str) -> dict:
    client = QgisBridgeClient()
    return client.dispatch(tool, params or {}, request_id=request_id)


def field_data_qfield_sync(params: dict) -> dict:
    """Sync project with QField/QFieldCloud."""
    return _dispatch("qgis.field_data.qfield_sync", params, request_id="fd_qfield_sync")


def field_data_mergin_sync(params: dict) -> dict:
    """Sync project with Mergin Maps."""
    return _dispatch("qgis.field_data.mergin_sync", params, request_id="fd_mergin_sync")


def field_data_gps_track(params: dict) -> dict:
    """Import GPS track as layer."""
    return _dispatch("qgis.field_data.gps_track", params, request_id="fd_gps_track")


def field_data_offline_package(params: dict) -> dict:
    """Create offline editing package."""
    return _dispatch("qgis.field_data.offline_package", params, request_id="fd_offline_package")


def field_data_feature_form(params: dict) -> dict:
    """Configure feature form for field data collection."""
    return _dispatch("qgis.field_data.feature_form", params, request_id="fd_feature_form")


def field_data_attachment(params: dict) -> dict:
    """Manage attachments (photos, docs) for features."""
    return _dispatch("qgis.field_data.attachment", params, request_id="fd_attachment")


def field_data_survey_design(params: dict) -> dict:
    """Design survey/field data collection form."""
    return _dispatch("qgis.field_data.survey_design", params, request_id="fd_survey_design")


def field_data_data_review(params: dict) -> dict:
    """Review and validate collected field data."""
    return _dispatch("qgis.field_data.data_review", params, request_id="fd_data_review")