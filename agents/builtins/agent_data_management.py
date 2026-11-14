"""Data Management Agent — Organizes layers, metadata, and project structure."""

from agents.base_agent import SpecializedAgent


class DataManagementAgent(SpecializedAgent):
    """Agent for managing GIS data: organizing layers, metadata, and project structure."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_data_management",
            name="Data Management Agent",
            description="Organizes layers and metadata.",
            instructions=(
                "You manage GIS data organization: layer grouping, renaming, metadata editing, "
                "CRS management, layer ordering, and project structure. Use qgis.layers.* "
                "and qgis.project.* tools."
            ),
            permission_level="standard",
            max_steps=10,
            db=db,
            domain="data_management",
            tool_namespace="qgis.layers",
        )

    async def execute(self, task: dict) -> dict:
        """Execute a data management task."""
        action = task.get("action", "organize")
        params = task.get("params", {})

        self.add_to_history("user", f"Data Management: {action}", {"action": action})

        if action == "organize":
            result = await self._organize_layers(params)
        elif action == "rename_layer":
            result = await self._rename_layer(params)
        elif action == "remove_layer":
            result = await self._remove_layer(params)
        elif action == "set_layer_crs":
            result = await self._set_layer_crs(params)
        elif action == "edit_metadata":
            result = await self._edit_metadata(params)
        elif action == "group_layers":
            result = await self._group_layers(params)
        elif action == "inspect_project":
            result = await self._inspect_project()
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _organize_layers(self, params: dict) -> dict:
        """Organize layers based on criteria."""
        layers_result = await self.call_tool("qgis.layers.inspect", {})
        layers = layers_result.get("result", {}).get("layers", [])
        
        # Group by type
        vector_layers = [l for l in layers if l.get("type") == "vector"]
        raster_layers = [l for l in layers if l.get("type") == "raster"]
        other_layers = [l for l in layers if l.get("type") not in ("vector", "raster")]
        
        return {
            "total_layers": len(layers),
            "vector_count": len(vector_layers),
            "raster_count": len(raster_layers),
            "other_count": len(other_layers),
            "layers": layers,
        }

    async def _rename_layer(self, params: dict) -> dict:
        """Rename a layer (via remove and reload with new name - simplified)."""
        layer_id = params.get("layer_id")
        new_name = params.get("new_name")
        if not layer_id or not new_name:
            return {"error": "Missing layer_id or new_name"}
        
        # Note: QGIS doesn't have a direct rename tool; this would need bridge support
        return {
            "note": "Layer rename not directly supported via current tools. "
                   "Remove and reload with new name, or use qgis.project.save after manual rename.",
            "layer_id": layer_id,
            "requested_name": new_name,
        }

    async def _remove_layer(self, params: dict) -> dict:
        """Remove a layer from the project."""
        layer_id = params.get("layer_id")
        if not layer_id:
            return {"error": "Missing layer_id"}
        
        return await self.call_tool("qgis.layers.remove", {"layer_id": layer_id})

    async def _set_layer_crs(self, params: dict) -> dict:
        """Set layer CRS (requires algorithm execution)."""
        layer_id = params.get("layer_id")
        crs = params.get("crs")
        if not layer_id or not crs:
            return {"error": "Missing layer_id or crs"}
        
        # Use reproject layer algorithm
        return await self.call_tool(
            "qgis.algorithms.execute",
            {
                "algorithm": "native:reprojectlayer",
                "parameters": {"INPUT": layer_id, "TARGET_CRS": crs, "OUTPUT": "memory:"}
            }
        )

    async def _edit_metadata(self, params: dict) -> dict:
        """Edit layer metadata (abstract - requires bridge support)."""
        layer_id = params.get("layer_id")
        metadata = params.get("metadata", {})
        if not layer_id:
            return {"error": "Missing layer_id"}
        
        return {
            "note": "Metadata editing requires bridge support for setLayerMetadata. "
                   "Use qgis.algorithms.execute with 'native:setlayerstyle' for style metadata.",
            "layer_id": layer_id,
            "requested_metadata": metadata,
        }

    async def _group_layers(self, params: dict) -> dict:
        """Group layers (abstract - requires bridge support)."""
        group_name = params.get("group_name", "New Group")
        layer_ids = params.get("layer_ids", [])
        
        return {
            "note": "Layer grouping requires bridge support for layer tree operations. "
                   "Currently not available via MCP tools.",
            "group_name": group_name,
            "layer_ids": layer_ids,
        }

    async def _inspect_project(self) -> dict:
        """Inspect current project."""
        return await self.call_tool("qgis.project.inspect", {})