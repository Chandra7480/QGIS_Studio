"""Georeferencing Agent — Automatic georeferencing of scanned maps."""

from agents.base_agent import SpecializedAgent


class GeoreferencingAgent(SpecializedAgent):
    """Agent for georeferencing scanned maps and images."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_georeferencing",
            name="Georeferencing Agent",
            description="Automatic georeferencing of scanned maps.",
            instructions=(
                "You georeference scanned maps and images: analyze images, generate GCPs, "
                "validate control points, and apply transformations. Use qgis.georeference.* "
                "and qgis.gcp.* tools."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="georeferencing",
            tool_namespace="qgis.georeference",
        )

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "georeference")
        params = task.get("params", {})

        self.add_to_history("user", f"Georeferencing: {action}", {"action": action})

        if action == "georeference":
            result = await self._georeference(params)
        elif action == "analyze_image":
            result = await self._analyze_image(params)
        elif action == "generate_gcps":
            result = await self._generate_gcps(params)
        elif action == "validate_gcps":
            result = await self._validate_gcps(params)
        elif action == "apply_transform":
            result = await self._apply_transform(params)
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _georeference(self, params: dict) -> dict:
        """Full georeferencing workflow."""
        image_path = params.get("image_path")
        reference_source = params.get("reference_source")
        if not image_path:
            return {"error": "Missing image_path"}

        # Step 1: Analyze image
        analyze = await self.call_tool("qgis.georeference.analyze", {"image_path": image_path})
        
        # Step 2: Generate GCPs if reference provided
        gcps = []
        if reference_source:
            gcp_result = await self.call_tool(
                "qgis.gcp.generate",
                {"image_path": image_path, "reference_source": reference_source}
            )
            gcps = gcp_result.get("result", {}).get("gcps", [])

        # Step 3: Validate GCPs
        if gcps:
            validate = await self.call_tool("qgis.gcp.validate", {"gcps": gcps})
            gcps = validate.get("result", {}).get("valid_gcps", gcps)

        return {
            "image_path": image_path,
            "analysis": analyze.get("result", {}),
            "gcps_generated": len(gcps),
            "gcps": gcps,
            "next_step": "Apply transformation using qgis.algorithms.execute with gdal:georeference",
        }

    async def _analyze_image(self, params: dict) -> dict:
        """Analyze image for georeferencing suitability."""
        image_path = params.get("image_path")
        if not image_path:
            return {"error": "Missing image_path"}
        return await self.call_tool("qgis.georeference.analyze", {"image_path": image_path})

    async def _generate_gcps(self, params: dict) -> dict:
        """Generate candidate GCPs."""
        image_path = params.get("image_path")
        reference_source = params.get("reference_source")
        if not image_path or not reference_source:
            return {"error": "Missing image_path or reference_source"}
        return await self.call_tool(
            "qgis.gcp.generate",
            {"image_path": image_path, "reference_source": reference_source}
        )

    async def _validate_gcps(self, params: dict) -> dict:
        """Validate GCPs."""
        gcps = params.get("gcps", [])
        if not gcps:
            return {"error": "Missing gcps"}
        return await self.call_tool("qgis.gcp.validate", {"gcps": gcps})

    async def _apply_transform(self, params: dict) -> dict:
        """Apply georeferencing transformation."""
        # Use GDAL georeference algorithm
        return await self.call_tool(
            "qgis.algorithms.execute",
            {
                "algorithm": "gdal:georeference",
                "parameters": params.get("algorithm_params", {})
            }
        )