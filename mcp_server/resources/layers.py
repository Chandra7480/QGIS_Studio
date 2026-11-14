"""Universal AI GIS Studio — Layer Resources.

Resources for inspecting and accessing QGIS layer data.
"""

from typing import Dict, Any, List, Optional
from mcp_server.resources.registry import ResourceSpec, ResourceType
from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.resources.layers")


# Lazy client instance
_client: Optional[QgisBridgeClient] = None


def get_client() -> QgisBridgeClient:
    global _client
    if _client is None:
        _client = QgisBridgeClient()
    return _client


def _fetch_layers() -> List[Dict[str, Any]]:
    """Fetch all layers from QGIS via bridge."""
    client = get_client()
    result = client.dispatch("qgis.layers.inspect", {}, "res_layers_list")
    return result.get("result", {}).get("layers", [])


def _fetch_layer(layer_id: str) -> Dict[str, Any]:
    """Fetch a specific layer by ID."""
    client = get_client()
    # We need to filter from the full list since bridge doesn't have single layer endpoint
    layers = _fetch_layers()
    for layer in layers:
        if layer.get("id") == layer_id or layer.get("name") == layer_id:
            return layer
    return {}


# Resource Handlers
async def handle_layers_list(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://layers resource."""
    layers = _fetch_layers()
    return {
        "layers": layers,
        "count": len(layers),
        "resource": "qgis://layers",
    }


async def handle_layer_detail(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://layer/{layer_id} resource."""
    layer_id = variables.get("layer_id", "")
    layer = _fetch_layer(layer_id)
    if not layer:
        return {"error": f"Layer not found: {layer_id}", "resource": f"qgis://layer/{layer_id}"}
    return {
        "layer": layer,
        "resource": f"qgis://layer/{layer_id}",
    }


async def handle_layer_features(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://layer/{layer_id}/features resource template."""
    layer_id = variables.get("layer_id", "")
    limit = int(variables.get("limit", "100"))
    offset = int(variables.get("offset", "0"))

    # This would need a bridge endpoint for fetching features
    # For now, return layer info with feature query params
    layer = _fetch_layer(layer_id)
    if not layer:
        return {"error": f"Layer not found: {layer_id}", "resource": f"qgis://layer/{layer_id}/features"}

    return {
        "layer_id": layer_id,
        "layer_name": layer.get("name"),
        "feature_count": layer.get("feature_count", 0),
        "query": {"limit": limit, "offset": offset},
        "resource": f"qgis://layer/{layer_id}/features",
        "note": "Feature fetching requires bridge endpoint implementation",
    }


async def handle_layer_style(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://layer/{layer_id}/style resource."""
    layer_id = variables.get("layer_id", "")
    layer = _fetch_layer(layer_id)
    if not layer:
        return {"error": f"Layer not found: {layer_id}", "resource": f"qgis://layer/{layer_id}/style"}

    return {
        "layer_id": layer_id,
        "layer_name": layer.get("name"),
        "style": layer.get("style", {}),
        "renderer": layer.get("renderer", {}),
        "resource": f"qgis://layer/{layer_id}/style",
    }


async def handle_layer_extent(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://layer/{layer_id}/extent resource."""
    layer_id = variables.get("layer_id", "")
    layer = _fetch_layer(layer_id)
    if not layer:
        return {"error": f"Layer not found: {layer_id}", "resource": f"qgis://layer/{layer_id}/extent"}

    return {
        "layer_id": layer_id,
        "extent": layer.get("extent"),
        "crs": layer.get("crs"),
        "resource": f"qgis://layer/{layer_id}/extent",
    }


def register_layer_resources(registry) -> None:
    """Register all layer-related resources."""

    # Static: List all layers
    registry.register(ResourceSpec(
        uri_pattern="qgis://layers",
        name="All Layers",
        description="List all loaded layers with basic metadata (id, name, type, validity, CRS, extent, fields).",
        mime_type="application/json",
        resource_type=ResourceType.STATIC,
        permissions=["qgis:read"],
        handler=handle_layers_list,
    ))

    # Static: Single layer detail by ID
    registry.register(ResourceSpec(
        uri_pattern="qgis://layer/{layer_id}",
        name="Layer Detail",
        description="Get detailed metadata for a specific layer by ID.",
        mime_type="application/json",
        resource_type=ResourceType.DYNAMIC,
        variables={"layer_id": "Layer ID or name"},
        permissions=["qgis:read"],
        handler=handle_layer_detail,
    ))

    # Template: Layer features with pagination
    registry.register(ResourceSpec(
        uri_pattern="qgis://layer/{layer_id}/features?limit={limit}&offset={offset}",
        name="Layer Features",
        description="Fetch features from a vector layer with pagination.",
        mime_type="application/geo+json",
        resource_type=ResourceType.TEMPLATE,
        variables={
            "layer_id": "Layer ID or name",
            "limit": "Max features to return (default 100)",
            "offset": "Offset for pagination (default 0)",
        },
        permissions=["qgis:vector:read"],
        handler=handle_layer_features,
    ))

    # Static: Layer style
    registry.register(ResourceSpec(
        uri_pattern="qgis://layer/{layer_id}/style",
        name="Layer Style",
        description="Get the style/renderer configuration for a layer.",
        mime_type="application/json",
        resource_type=ResourceType.DYNAMIC,
        variables={"layer_id": "Layer ID or name"},
        permissions=["qgis:read"],
        handler=handle_layer_style,
    ))

    # Static: Layer extent
    registry.register(ResourceSpec(
        uri_pattern="qgis://layer/{layer_id}/extent",
        name="Layer Extent",
        description="Get the spatial extent (bounding box) of a layer.",
        mime_type="application/json",
        resource_type=ResourceType.DYNAMIC,
        variables={"layer_id": "Layer ID or name"},
        permissions=["qgis:read"],
        handler=handle_layer_extent,
    ))