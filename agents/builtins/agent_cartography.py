"""Cartography Agent — Symbology, labels, layouts, export."""

from agents.base_agent import SpecializedAgent


class CartographyAgent(SpecializedAgent):
    """Agent for cartography: symbology, labeling, print layouts, map export."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_cartography",
            name="Cartography Agent",
            description="Symbology, labels, layouts, export.",
            instructions=(
                "You create maps: symbology (categorized, graduated, rule-based), "
                "labeling, print layouts, atlas generation, and map export (PDF, PNG, SVG). "
                "Use qgis.algorithms.execute and layout tools."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="cartography",
            tool_namespace="qgis.algorithms",
        )
        
        self.cart_algorithms = {
            "categorized": "native:setstyleforvectorlayer",
            "graduated": "native:setstyleforvectorlayer",
            "rule_based": "native:setstyleforvectorlayer",
            "labeling": "native:setlabeling",
            "layout_create": "native:printlayout",
            "layout_export": "native:printlayouttoimage",
            "atlas": "native:atlas",
            "legend": "native:createstylelegend",
            "color_ramp": "native:createrampshader",
        }

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "map")
        params = task.get("params", {})

        self.add_to_history("user", f"Cartography: {action}", {"action": action})

        if action == "map":
            result = await self._create_map(params)
        elif action == "symbology":
            result = await self._symbology(params)
        elif action == "labeling":
            result = await self._labeling(params)
        elif action == "layout":
            result = await self._layout(params)
        elif action == "export":
            result = await self._export(params)
        elif action == "atlas":
            result = await self._atlas(params)
        elif action == "list_operations":
            result = {"operations": list(self.cart_algorithms.keys())}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _create_map(self, params: dict) -> dict:
        """Create a complete map with layout."""
        return {
            "note": "Map creation requires multiple steps: symbology, labeling, layout, export.",
            "steps": [
                "1. Apply symbology to layers",
                "2. Configure labeling",
                "3. Create print layout",
                "4. Add map, legend, scalebar, north arrow",
                "5. Export to PDF/PNG/SVG",
            ],
            "available_layouts": await self._get_layouts(),
        }

    async def _symbology(self, params: dict) -> dict:
        """Apply symbology to layer."""
        layer = params.get("layer")
        style_type = params.get("type", "categorized")  # categorized, graduated, single, rule_based
        field = params.get("field")
        
        if not layer:
            return {"error": "Missing layer"}
        
        return {
            "note": "Symbology application requires bridge support for setLayerStyle. "
                   "Use qgis.algorithms.execute with native:setstyleforvectorlayer.",
            "layer": layer,
            "type": style_type,
            "field": field,
        }

    async def _labeling(self, params: dict) -> dict:
        """Configure labeling."""
        layer = params.get("layer")
        field = params.get("field")
        
        if not layer or not field:
            return {"error": "Missing layer or field"}
        
        return {
            "note": "Labeling configuration requires bridge support. "
                   "Use native:setlabeling algorithm.",
            "layer": layer,
            "field": field,
            "options": params.get("options", {}),
        }

    async def _layout(self, params: dict) -> dict:
        """Create/manage print layout."""
        name = params.get("name", "New Layout")
        return {
            "note": "Layout creation requires bridge support for QgsPrintLayout. "
                   "Use native:printlayout algorithm.",
            "layout_name": name,
            "page_size": params.get("page_size", "A4"),
            "orientation": params.get("orientation", "landscape"),
        }

    async def _export(self, params: dict) -> dict:
        """Export map/layout."""
        layout = params.get("layout")
        format = params.get("format", "pdf")  # pdf, png, svg
        path = params.get("output_path")
        
        if not layout or not path:
            return {"error": "Missing layout or output_path"}
        
        return await self.call_tool(
            "qgis.algorithms.execute",
            {
                "algorithm": "native:printlayouttoimage",
                "parameters": {
                    "LAYOUT": layout,
                    "OUTPUT": path,
                    "FORMAT": format.upper(),
                    **params
                }
            }
        )

    async def _atlas(self, params: dict) -> dict:
        """Generate atlas."""
        layout = params.get("layout")
        coverage = params.get("coverage_layer")
        
        if not layout or not coverage:
            return {"error": "Missing layout or coverage_layer"}
        
        return {
            "note": "Atlas generation requires bridge support. "
                   "Configure atlas in layout, then use native:atlas algorithm.",
            "layout": layout,
            "coverage_layer": coverage,
        }

    async def _get_layouts(self) -> dict:
        return await self.call_tool("qgis.layout.info", {})

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": params}
        )