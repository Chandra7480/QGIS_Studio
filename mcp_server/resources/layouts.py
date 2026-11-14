"""Universal AI GIS Studio — Layout Resources.

Resources for QGIS print layouts and map compositions.
"""

from typing import Dict, Any, Optional
from mcp_server.resources.registry import ResourceSpec, ResourceType
from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.resources.layouts")


_client: Optional[QgisBridgeClient] = None


def get_client() -> QgisBridgeClient:
    global _client
    if _client is None:
        _client = QgisBridgeClient()
    return _client


def _fetch_layouts() -> Dict[str, Any]:
    """Fetch layouts from QGIS via bridge."""
    client = get_client()
    result = client.dispatch("qgis.layout.info", {}, "res_layout_info")
    return result.get("result", {})


# Resource Handlers
async def handle_layouts_list(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://layouts resource."""
    layouts = _fetch_layouts()
    return {
        "layouts": layouts.get("layouts", []),
        "count": layouts.get("count", 0),
        "resource": "qgis://layouts",
    }


async def handle_layout_detail(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://layout/{layout_name} resource."""
    layout_name = variables.get("layout_name", "")
    layouts = _fetch_layouts()
    for layout in layouts.get("layouts", []):
        if layout.get("name") == layout_name:
            return {
                "layout": layout,
                "resource": f"qgis://layout/{layout_name}",
            }
    return {
        "error": f"Layout not found: {layout_name}",
        "resource": f"qgis://layout/{layout_name}",
    }


async def handle_layout_items(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://layout/{layout_name}/items resource."""
    layout_name = variables.get("layout_name", "")
    layouts = _fetch_layouts()
    for layout in layouts.get("layouts", []):
        if layout.get("name") == layout_name:
            return {
                "layout_name": layout_name,
                "items": layout.get("items", []),
                "item_count": len(layout.get("items", [])),
                "resource": f"qgis://layout/{layout_name}/items",
            }
    return {
        "error": f"Layout not found: {layout_name}",
        "resource": f"qgis://layout/{layout_name}/items",
    }


def register_layout_resources(registry) -> None:
    """Register all layout-related resources."""

    registry.register(ResourceSpec(
        uri_pattern="qgis://layouts",
        name="All Layouts",
        description="List all print layouts in the current project.",
        mime_type="application/json",
        resource_type=ResourceType.STATIC,
        permissions=["qgis:layout:read"],
        handler=handle_layouts_list,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://layout/{layout_name}",
        name="Layout Detail",
        description="Detailed metadata for a specific print layout.",
        mime_type="application/json",
        resource_type=ResourceType.DYNAMIC,
        variables={"layout_name": "Layout name"},
        permissions=["qgis:layout:read"],
        handler=handle_layout_detail,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://layout/{layout_name}/items",
        name="Layout Items",
        description="List all items (map, legend, scalebar, label, etc.) in a layout.",
        mime_type="application/json",
        resource_type=ResourceType.DYNAMIC,
        variables={"layout_name": "Layout name"},
        permissions=["qgis:layout:read"],
        handler=handle_layout_items,
    ))