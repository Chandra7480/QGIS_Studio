"""Reporting Agent — Generates GIS reports and map exports."""

from agents.base_agent import SpecializedAgent


class ReportingAgent(SpecializedAgent):
    """Agent for reporting: GIS reports, map exports, atlases, dashboards."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_reporting",
            name="Reporting Agent",
            description="Generates GIS reports and map exports.",
            instructions=(
                "You generate reports: map exports (PDF, PNG, SVG), atlas generation, "
                "data reports, summary statistics, and custom report templates. "
                "Use qgis.algorithms.execute and layout tools."
            ),
            permission_level="read",
            max_steps=15,
            db=db,
            domain="reporting",
            tool_namespace="qgis.algorithms",
        )

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "report")
        params = task.get("params", {})

        self.add_to_history("user", f"Reporting: {action}", {"action": action})

        if action == "report":
            result = await self._generate_report(params)
        elif action == "export_map":
            result = await self._export_map(params)
        elif action == "atlas":
            result = await self._generate_atlas(params)
        elif action == "statistics":
            result = await self._statistics_report(params)
        elif action == "template":
            result = await self._template_report(params)
        elif action == "list_operations":
            result = {"operations": ["report", "export_map", "atlas", "statistics", "template"]}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _generate_report(self, params: dict) -> dict:
        """Generate a comprehensive GIS report."""
        layers = params.get("layers", [])
        template = params.get("template", "standard")
        output = params.get("output", "report.pdf")
        
        if not layers:
            return {"error": "Missing layers"}
        
        return {
            "note": "Report generation combines layout export and data summary. "
                   "Use export_map for map images and statistics for data tables.",
            "layers": layers,
            "template": template,
            "output": output,
        }

    async def _export_map(self, params: dict) -> dict:
        """Export map to image/PDF."""
        layout = params.get("layout")
        output = params.get("output")
        format = params.get("format", "pdf")
        
        if not layout or not output:
            return {"error": "Missing layout or output"}
        
        return await self.call_tool("qgis.algorithms.execute", {
            "algorithm": "native:printlayouttoimage",
            "parameters": {"LAYOUT": layout, "OUTPUT": output, "FORMAT": format.upper()}
        })

    async def _generate_atlas(self, params: dict) -> dict:
        """Generate atlas."""
        layout = params.get("layout")
        coverage = params.get("coverage_layer")
        output = params.get("output")
        
        if not layout or not coverage or not output:
            return {"error": "Missing layout, coverage_layer, or output"}
        
        return await self.call_tool("qgis.algorithms.execute", {
            "algorithm": "native:atlas",
            "parameters": {"LAYOUT": layout, "COVERAGE_LAYER": coverage, "OUTPUT": output}
        })

    async def _statistics_report(self, params: dict) -> dict:
        """Generate statistics report for layers."""
        layers = params.get("layers", [])
        if not layers:
            return {"error": "Missing layers"}
        
        results = {}
        for layer in layers:
            stats = await self.call_tool("qgis.algorithms.execute", {
                "algorithm": "native:basicstatisticsforfields",
                "parameters": {"INPUT": layer}
            })
            results[layer] = stats
        
        return {"statistics": results}

    async def _template_report(self, params: dict) -> dict:
        """Report from template."""
        return {"note": "Template-based reporting requires predefined QGIS layout templates."}