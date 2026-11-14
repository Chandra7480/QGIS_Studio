"""MCP tool implementations for qgis.automation namespace — 10 automation tools."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.automation")


def _dispatch(tool: str, params: dict, request_id: str) -> dict:
    client = QgisBridgeClient()
    return client.dispatch(tool, params or {}, request_id=request_id)


def automation_model_create(params: dict) -> dict:
    """Create Processing model (.model3) from parameters."""
    return _dispatch("qgis.automation.model_create", params, request_id="auto_model_create")


def automation_model_run(params: dict) -> dict:
    """Run Processing model with parameters."""
    return _dispatch("qgis.automation.model_run", params, request_id="auto_model_run")


def automation_model_export(params: dict) -> dict:
    """Export Processing model to file."""
    return _dispatch("qgis.automation.model_export", params, request_id="auto_model_export")


def automation_model_import(params: dict) -> dict:
    """Import Processing model from file."""
    return _dispatch("qgis.automation.model_import", params, request_id="auto_model_import")


def automation_batch_process(params: dict) -> dict:
    """Run batch processing for algorithm over multiple inputs."""
    return _dispatch("qgis.automation.batch_process", params, request_id="auto_batch_process")


def automation_batch_dialog(params: dict) -> dict:
    """Configure batch processing dialog."""
    return _dispatch("qgis.automation.batch_dialog", params, request_id="auto_batch_dialog")


def automation_history(params: dict) -> dict:
    """Get processing history."""
    return _dispatch("qgis.automation.history", params, request_id="auto_history")


def automation_model_validate(params: dict) -> dict:
    """Validate Processing model for errors."""
    return _dispatch("qgis.automation.model_validate", params, request_id="auto_model_validate")


def automation_model_document(params: dict) -> dict:
    """Generate documentation for Processing model."""
    return _dispatch("qgis.automation.model_document", params, request_id="auto_model_document")


def automation_script_run(params: dict) -> dict:
    """Run PyQGIS script from file or string."""
    return _dispatch("qgis.automation.script_run", params, request_id="auto_script_run")