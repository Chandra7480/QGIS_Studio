"""MCP tool implementations for qgis.temporal namespace — 10 temporal analysis tools."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.temporal")


def _dispatch(tool: str, params: dict, request_id: str) -> dict:
    client = QgisBridgeClient()
    return client.dispatch(tool, params or {}, request_id=request_id)


def temporal_enable(params: dict) -> dict:
    """Enable temporal control on layer."""
    return _dispatch("qgis.temporal.enable", params, request_id="temporal_enable")


def temporal_filter(params: dict) -> dict:
    """Apply temporal filter to layer."""
    return _dispatch("qgis.temporal.filter", params, request_id="temporal_filter")


def temporal_animate(params: dict) -> dict:
    """Create temporal animation from time-enabled layers."""
    return _dispatch("qgis.temporal.animate", params, request_id="temporal_animate")


def temporal_time_series(params: dict) -> dict:
    """Extract time series data from temporal layers."""
    return _dispatch("qgis.temporal.time_series", params, request_id="temporal_time_series")


def temporal_controller(params: dict) -> dict:
    """Control temporal controller (play, pause, seek, speed)."""
    return _dispatch("qgis.temporal.controller", params, request_id="temporal_controller")


def temporal_keyframe(params: dict) -> dict:
    """Manage temporal keyframes for animation."""
    return _dispatch("qgis.temporal.keyframe", params, request_id="temporal_keyframe")


def temporal_playback(params: dict) -> dict:
    """Configure temporal playback settings."""
    return _dispatch("qgis.temporal.playback", params, request_id="temporal_playback")


def temporal_range(params: dict) -> dict:
    """Set temporal range for project or layers."""
    return _dispatch("qgis.temporal.range", params, request_id="temporal_range")


def temporal_join(params: dict) -> dict:
    """Join temporal attributes between layers."""
    return _dispatch("qgis.temporal.join", params, request_id="temporal_join")


def temporal_timestamp(params: dict) -> dict:
    """Add/extract timestamp from features."""
    return _dispatch("qgis.temporal.timestamp", params, request_id="temporal_timestamp")