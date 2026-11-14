"""Digitization Agent — Digitizes features from imagery/maps."""

from agents.base_agent import SpecializedAgent


class DigitizationAgent(SpecializedAgent):
    """Agent for digitizing features from imagery, scanned maps, or canvas."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_digitization",
            name="Digitization Agent",
            description="Digitizes features from imagery/maps.",
            instructions=(
                "You digitize vector features: create points, lines, polygons from imagery "
                "or scanned maps. Use qgis.algorithms.execute with digitizing algorithms, "
                "and visual desktop control for interactive digitizing."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="digitization",
            tool_namespace="qgis.algorithms",
        )

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "digitize")
        params = task.get("params", {})

        self.add_to_history("user", f"Digitization: {action}", {"action": action})

        if action == "digitize":
            result = await self._digitize_features(params)
        elif action == "create_layer":
            result = await self._create_layer(params)
        elif action == "add_features":
            result = await self._add_features(params)
        elif action == "trace_raster":
            result = await self._trace_raster(params)
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _digitize_features(self, params: dict) -> dict:
        """Digitize features using visual control or algorithms."""
        layer_id = params.get("layer_id")
        geometry_type = params.get("geometry_type", "polygon")  # point, line, polygon
        method = params.get("method", "visual")  # visual, algorithm

        if method == "visual":
            # Use visual desktop control for interactive digitizing
            return await self.call_tool(
                "qgis.algorithms.execute",
                {
                    "algorithm": "native:createlayer",
                    "parameters": {
                        "TYPE": {"Point": 0, "LineString": 1, "Polygon": 2}.get(geometry_type, 2),
                        "CRS": params.get("crs", "EPSG:4326"),
                        "OUTPUT": "memory:"
                    }
                }
            )
        else:
            return {"note": "Algorithm-based digitizing requires specific geometry input"}

    async def _create_layer(self, params: dict) -> dict:
        """Create a new empty vector layer for digitizing."""
        geometry_type = params.get("geometry_type", "polygon")
        crs = params.get("crs", "EPSG:4326")
        fields = params.get("fields", [])
        
        return await self.call_tool(
            "qgis.algorithms.execute",
            {
                "algorithm": "native:createlayer",
                "parameters": {
                    "TYPE": {"Point": 0, "LineString": 1, "Polygon": 2}.get(geometry_type, 2),
                    "CRS": crs,
                    "FIELDS": fields,
                    "OUTPUT": "memory:"
                }
            }
        )

    async def _add_features(self, params: dict) -> dict:
        """Add features to existing layer (requires visual control)."""
        layer_id = params.get("layer_id")
        features = params.get("features", [])
        
        return {
            "note": "Adding features programmatically requires bridge support. "
                   "Use visual desktop control agent for interactive digitizing.",
            "layer_id": layer_id,
            "feature_count": len(features),
        }

    async def _trace_raster(self, params: dict) -> dict:
        """Trace raster features (requires raster vectorization algorithms)."""
        raster_layer = params.get("raster_layer")
        if not raster_layer:
            return {"error": "Missing raster_layer"}
        
        return await self.call_tool(
            "qgis.algorithms.execute",
            {
                "algorithm": "gdal:polygonize",
                "parameters": {"INPUT": raster_layer, "OUTPUT": "memory:"}
            }
        )