"""Vector Processing Agent — Buffer, clip, dissolve, overlay operations."""

from agents.base_agent import SpecializedAgent


class VectorProcessingAgent(SpecializedAgent):
    """Agent for vector processing operations: buffer, clip, dissolve, overlay, etc."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_vector_processing",
            name="Vector Processing Agent",
            description="Buffer, clip, dissolve, overlay operations.",
            instructions=(
                "You process vector data: buffer, clip, intersect, union, difference, "
                "dissolve, simplify, and other geometric operations. Use qgis.algorithms.execute "
                "with native vector processing algorithms."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="vector_processing",
            tool_namespace="qgis.algorithms",
        )
        
        # Common vector algorithm mappings
        self.vector_algorithms = {
            "buffer": "native:buffer",
            "clip": "native:clip",
            "intersect": "native:intersection",
            "union": "native:union",
            "difference": "native:difference",
            "symmetrical_difference": "native:symmetricaldifference",
            "dissolve": "native:dissolve",
            "simplify": "native:simplifygeometries",
            "centroids": "native:centroids",
            "convex_hull": "native:convexhull",
            "boundary": "native:boundary",
            "multipart_to_singlepart": "native:multiparttosingleparts",
            "singlepart_to_multipart": "native:singlepartstomultipart",
            "fix_geometries": "native:fixgeometries",
            "check_validity": "native:checkvalidity",
            "join_attributes": "native:joinattributesbylocation",
            "join_by_field": "native:joinattributestable",
        }

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "process_vector")
        params = task.get("params", {})

        self.add_to_history("user", f"Vector Processing: {action}", {"action": action})

        if action == "process_vector":
            result = await self._process_vector(params)
        elif action == "buffer":
            result = await self._buffer(params)
        elif action == "clip":
            result = await self._clip(params)
        elif action == "overlay":
            result = await self._overlay(params)
        elif action == "dissolve":
            result = await self._dissolve(params)
        elif action == "simplify":
            result = await self._simplify(params)
        elif action == "fix_geometries":
            result = await self._fix_geometries(params)
        elif action == "join_attributes":
            result = await self._join_attributes(params)
        elif action == "list_operations":
            result = {"operations": list(self.vector_algorithms.keys())}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _process_vector(self, params: dict) -> dict:
        """General vector processing - route to specific operation."""
        operation = params.get("operation")
        if operation in self.vector_algorithms:
            return await self._run_algorithm(self.vector_algorithms[operation], params)
        return {"error": f"Unknown operation: {operation}", "available": list(self.vector_algorithms.keys())}

    async def _buffer(self, params: dict) -> dict:
        """Buffer features."""
        required = ["input", "distance"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm("native:buffer", params)

    async def _clip(self, params: dict) -> dict:
        """Clip vector layer."""
        required = ["input", "overlay"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm("native:clip", params)

    async def _overlay(self, params: dict) -> dict:
        """Overlay operations (intersect, union, difference)."""
        op_type = params.get("overlay_type", "intersection")  # intersection, union, difference
        alg_map = {
            "intersection": "native:intersection",
            "union": "native:union",
            "difference": "native:difference",
        }
        algo = alg_map.get(op_type, "native:intersection")
        required = ["input", "overlay"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm(algo, params)

    async def _dissolve(self, params: dict) -> dict:
        """Dissolve features."""
        if "input" not in params:
            return {"error": "Missing required parameter: input"}
        return await self._run_algorithm("native:dissolve", params)

    async def _simplify(self, params: dict) -> dict:
        """Simplify geometries."""
        if "input" not in params:
            return {"error": "Missing required parameter: input"}
        return await self._run_algorithm("native:simplifygeometries", params)

    async def _fix_geometries(self, params: dict) -> dict:
        """Fix invalid geometries."""
        if "input" not in params:
            return {"error": "Missing required parameter: input"}
        return await self._run_algorithm("native:fixgeometries", params)

    async def _join_attributes(self, params: dict) -> dict:
        """Join attributes by location or field."""
        join_type = params.get("join_type", "location")  # location, field
        algo = "native:joinattributesbylocation" if join_type == "location" else "native:joinattributestable"
        required = ["input", "join"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm(algo, params)

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        """Execute a processing algorithm."""
        # Filter out non-algorithm parameters
        alg_params = {k: v for k, v in params.items() 
                      if k not in ["operation", "overlay_type", "join_type"]}
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": alg_params}
        )