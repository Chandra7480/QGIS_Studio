"""Universal AI GIS Studio — Project Resources.

Resources for inspecting QGIS project metadata and state.
"""

from typing import Dict, Any, Optional
from mcp_server.resources.registry import ResourceSpec, ResourceType
from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.resources.project")


_client: Optional[QgisBridgeClient] = None


def get_client() -> QgisBridgeClient:
    global _client
    if _client is None:
        _client = QgisBridgeClient()
    return _client


def _fetch_project() -> Dict[str, Any]:
    """Fetch project info from QGIS via bridge."""
    client = get_client()
    result = client.dispatch("qgis.project.inspect", {}, "res_project_info")
    return result.get("result", {})


# Resource Handlers
async def handle_project_info(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://project/info resource."""
    project = _fetch_project()
    return {
        "project": project,
        "resource": "qgis://project/info",
    }


async def handle_project_layers(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://project/layers resource."""
    project = _fetch_project()
    return {
        "project_file": project.get("project_file"),
        "project_title": project.get("project_title"),
        "layers": project.get("layers", []),
        "layer_count": project.get("layer_count", 0),
        "resource": "qgis://project/layers",
    }


async def handle_project_crs(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://project/crs resource."""
    project = _fetch_project()
    return {
        "project_file": project.get("project_file"),
        "crs": project.get("crs"),
        "crs_wkt": project.get("crs_wkt"),
        "resource": "qgis://project/crs",
    }


async def handle_project_metadata(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://project/metadata resource."""
    project = _fetch_project()
    return {
        "project_file": project.get("project_file"),
        "project_title": project.get("project_title"),
        "crs": project.get("crs"),
        "layer_count": project.get("layer_count", 0),
        "layers": project.get("layers", []),
        "extent": project.get("extent"),
        "resource": "qgis://project/metadata",
    }


def register_project_resources(registry) -> None:
    """Register all project-related resources."""

    registry.register(ResourceSpec(
        uri_pattern="qgis://project/info",
        name="Project Info",
        description="Current QGIS project metadata: file path, title, CRS, layer count.",
        mime_type="application/json",
        resource_type=ResourceType.STATIC,
        permissions=["qgis:read"],
        handler=handle_project_info,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://project/layers",
        name="Project Layers",
        description="List of all layers in the current project with basic metadata.",
        mime_type="application/json",
        resource_type=ResourceType.STATIC,
        permissions=["qgis:read"],
        handler=handle_project_layers,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://project/crs",
        name="Project CRS",
        description="Coordinate Reference System of the current project.",
        mime_type="application/json",
        resource_type=ResourceType.STATIC,
        permissions=["qgis:read"],
        handler=handle_project_crs,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://project/metadata",
        name="Project Metadata",
        description="Complete project metadata including layers, extent, and CRS details.",
        mime_type="application/json",
        resource_type=ResourceType.STATIC,
        permissions=["qgis:read"],
        handler=handle_project_metadata,
    ))