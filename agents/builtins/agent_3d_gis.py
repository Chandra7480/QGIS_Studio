"""3D GIS Agent — 3D visualization and terrain models."""

from agents.base_agent import SpecializedAgent


class Agent3DGIS(SpecializedAgent):
    """Agent for 3D GIS: 3D visualization, terrain models, 3D analysis."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_3d_gis",
            name="3D GIS Agent",
            description="3D visualization and terrain models.",
            instructions=(
                "You create 3D visualizations: 3D map views, terrain models, 3D features, "
                "extrusion, 3D symbols, and 3D analysis. Use QGIS 3D view capabilities "
                "and processing algorithms for 3D data preparation."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="3d_gis",
            tool_namespace="qgis.algorithms",
        )

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "visualize")
        params = task.get("params", {})

        self.add_to_history("user", f"3D GIS: {action}", {"action": action})

        if action == "visualize":
            result = await self._visualize(params)
        elif action == "extrude":
            result = await self._extrude(params)
        elif action == "terrain_model":
            result = await self._terrain_model(params)
        elif action == "create_3d_layer":
            result = await self._create_3d_layer(params)
        elif action == "export_3d":
            result = await self._export_3d(params)
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _visualize(self, params: dict) -> dict:
        """Create 3D visualization setup."""
        dem = params.get("dem")
        layers = params.get("layers", [])
        
        return {
            "note": "3D visualization in QGIS is interactive. Use qgis.canvas.inspect to check canvas, "
                   "then enable 3D map view manually or via Python console.",
            "dem": dem,
            "layers": layers,
            "setup_steps": [
                "1. Open 3D Map View (View > New 3D Map View)",
                "2. Configure terrain with DEM",
                "3. Add vector layers with 3D symbology",
                "4. Set camera position and lighting",
            ]
        }

    async def _extrude(self, params: dict) -> dict:
        """Extrude vector features to 3D."""
        layer = params.get("layer")
        height_field = params.get("height_field")
        height = params.get("height", 10)
        
        if not layer:
            return {"error": "Missing required parameter: layer"}
        
        return await self.call_tool(
            "qgis.algorithms.execute",
            {
                "algorithm": "native:setzvalue",
                "parameters": {
                    "INPUT": layer,
                    "Z_VALUE": height if not height_field else f"@{height_field}",
                    "OUTPUT": "memory:"
                }
            }
        )

    async def _terrain_model(self, params: dict) -> dict:
        """Create 3D terrain model from DEM."""
        dem = params.get("dem")
        if not dem:
            return {"error": "Missing required parameter: dem"}
        
        return {
            "note": "Use the DEM as terrain in 3D Map View. Configure in 3D view settings.",
            "dem": dem,
            "vertical_exaggeration": params.get("vertical_exaggeration", 1.0),
        }

    async def _create_3d_layer(self, params: dict) -> dict:
        """Create a 3D-enabled vector layer."""
        return {
            "note": "3D layers require setting 3D symbology properties. Use native:setzvalue for extrusion.",
            "symbol_types": ["sphere", "cube", "cylinder", "cone", "3D model"],
        }

    async def _export_3d(self, params: dict) -> dict:
        """Export 3D scene (requires manual steps)."""
        return {
            "note": "3D export options: QGIS 3D view screenshot, or export to 3D tiles/Cesium via plugins.",
            "formats": ["PNG (screenshot)", "3D Tiles (plugin)", "glTF (plugin)", "OBJ (plugin)"],
        }