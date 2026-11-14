"""Universal AI GIS Studio — Style Resources.

Resources for QGIS layer styles and style libraries.
"""

from typing import Dict, Any, Optional, List
from mcp_server.resources.registry import ResourceSpec, ResourceType
from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.resources.styles")


_client: Optional[QgisBridgeClient] = None


def get_client() -> QgisBridgeClient:
    global _client
    if _client is None:
        _client = QgisBridgeClient()
    return _client


# Built-in style templates
_STYLE_TEMPLATES = {
    "categorized": {
        "name": "Categorized",
        "description": "Categorized renderer for nominal/ordinal attributes",
        "geometry_types": ["Point", "Line", "Polygon"],
        "parameters": ["field", "color_ramp", "symbol"],
    },
    "graduated": {
        "name": "Graduated",
        "description": "Graduated renderer for numerical attributes",
        "geometry_types": ["Point", "Line", "Polygon"],
        "parameters": ["field", "color_ramp", "classes", "mode"],
    },
    "single_symbol": {
        "name": "Single Symbol",
        "description": "Simple single symbol renderer",
        "geometry_types": ["Point", "Line", "Polygon"],
        "parameters": ["symbol", "color", "size"],
    },
    "rule_based": {
        "name": "Rule-based",
        "description": "Rule-based renderer with multiple symbol rules",
        "geometry_types": ["Point", "Line", "Polygon"],
        "parameters": ["rules"],
    },
    "heatmap": {
        "name": "Heatmap",
        "description": "Heatmap renderer for point density",
        "geometry_types": ["Point"],
        "parameters": ["radius", "weight", "color_ramp"],
    },
    "point_displacement": {
        "name": "Point Displacement",
        "description": "Displace overlapping points",
        "geometry_types": ["Point"],
        "parameters": ["distance", "placement"],
    },
    "inverted_polygon": {
        "name": "Inverted Polygon",
        "description": "Render outside of polygons",
        "geometry_types": ["Polygon"],
        "parameters": ["sub_renderer"],
    },
    "25d": {
        "name": "2.5D",
        "description": "Extruded 3D-like polygon renderer",
        "geometry_types": ["Polygon"],
        "parameters": ["height", "angle", "roof_color", "wall_color"],
    },
}


# Resource Handlers
async def handle_style_templates(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://styles/templates resource."""
    return {
        "templates": _STYLE_TEMPLATES,
        "count": len(_STYLE_TEMPLATES),
        "resource": "qgis://styles/templates",
    }


async def handle_style_template_detail(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://styles/template/{template_name} resource."""
    template_name = variables.get("template_name", "")
    template = _STYLE_TEMPLATES.get(template_name)
    if not template:
        return {
            "error": f"Style template not found: {template_name}",
            "available": list(_STYLE_TEMPLATES.keys()),
            "resource": f"qgis://styles/template/{template_name}",
        }
    return {
        "template": template,
        "resource": f"qgis://styles/template/{template_name}",
    }


async def handle_layer_style(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://layer/{layer_id}/style resource (delegates to layers module)."""
    # This is handled in layers.py, but we can provide a style-focused view
    client = get_client()
    layer_id = variables.get("layer_id", "")
    # Fetch layer and return style-specific info
    result = client.dispatch("qgis.layers.inspect", {}, "res_layer_style")
    layers = result.get("result", {}).get("layers", [])

    for layer in layers:
        if layer.get("id") == layer_id or layer.get("name") == layer_id:
            return {
                "layer_id": layer_id,
                "layer_name": layer.get("name"),
                "renderer": layer.get("renderer", {}),
                "style": layer.get("style", {}),
                "resource": f"qgis://layer/{layer_id}/style",
            }

    return {
        "error": f"Layer not found: {layer_id}",
        "resource": f"qgis://layer/{layer_id}/style",
    }


def register_style_resources(registry) -> None:
    """Register all style-related resources."""

    registry.register(ResourceSpec(
        uri_pattern="qgis://styles/templates",
        name="Style Templates",
        description="Built-in QGIS renderer templates with parameters.",
        mime_type="application/json",
        resource_type=ResourceType.STATIC,
        permissions=["qgis:read"],
        handler=handle_style_templates,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://styles/template/{template_name}",
        name="Style Template Detail",
        description="Detailed parameters for a specific style template.",
        mime_type="application/json",
        resource_type=ResourceType.DYNAMIC,
        variables={"template_name": "Template name (categorized, graduated, single_symbol, etc.)"},
        permissions=["qgis:read"],
        handler=handle_style_template_detail,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://layer/{layer_id}/style",
        name="Layer Style",
        description="Current style/renderer configuration for a layer.",
        mime_type="application/json",
        resource_type=ResourceType.DYNAMIC,
        variables={"layer_id": "Layer ID or name"},
        permissions=["qgis:read"],
        handler=handle_layer_style,
    ))