"""Cadastral Agent — Parcel management and boundary digitization."""

from agents.base_agent import SpecializedAgent


class CadastralAgent(SpecializedAgent):
    """Agent for cadastral: parcel management, boundary digitization, subdivision."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_cadastral",
            name="Cadastral Agent",
            description="Parcel management and boundary digitization.",
            instructions=(
                "You manage cadastral data: parcel boundaries, subdivision, merging, "
                "coordinate geometry (COGO), deed plotting, and parcel fabric. "
                "Use qgis.algorithms.execute with COGO and parcel tools."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="cadastral",
            tool_namespace="qgis.algorithms",
        )
        
        self.cadastral_algorithms = {
            "parcel_fabric": "native:parcelfabric",
            "subdivide": "native:subdivide",
            "merge_parcels": "native:mergevectorlayers",
            "cogo": "native:cogo",
            "deed_plot": "custom:deedplot",
            "boundary_clean": "native:snapgeometries",
            "parcel_numbers": "native:fieldcalculator",
            "area_calculation": "native:fieldcalculator",
            "perimeter": "native:fieldcalculator",
        }

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "manage")
        params = task.get("params", {})

        self.add_to_history("user", f"Cadastral: {action}", {"action": action})

        if action == "manage":
            result = await self._manage(params)
        elif action == "subdivide":
            result = await self._subdivide(params)
        elif action == "merge":
            result = await self._merge(params)
        elif action == "cogo":
            result = await self._cogo(params)
        elif action == "clean_boundaries":
            result = await self._clean_boundaries(params)
        elif action == "calculate_areas":
            result = await self._calculate_areas(params)
        elif action == "list_operations":
            result = {"operations": list(self.cadastral_algorithms.keys())}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _manage(self, params: dict) -> dict:
        operation = params.get("operation")
        if operation in self.cadastral_algorithms:
            return await self._run_algorithm(self.cadastral_algorithms[operation], params)
        return {"error": f"Unknown operation: {operation}", "available": list(self.cadastral_algorithms.keys())}

    async def _subdivide(self, params: dict) -> dict:
        """Subdivide parcels."""
        required = ["input", "method"]  # method: equal_area, by_line, by_percentage
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm("native:subdivide", params)

    async def _merge(self, params: dict) -> dict:
        """Merge adjacent parcels."""
        if "input" not in params:
            return {"error": "Missing input layer"}
        return await self._run_algorithm("native:mergevectorlayers", params)

    async def _cogo(self, params: dict) -> dict:
        """Coordinate geometry (COGO) operations."""
        return {
            "note": "COGO operations (bearing/distance, curve calculations) require "
                   "QGIS COGO plugin or Python scripting. Basic support via field calculator.",
            "operations": ["traverse", "inverse", "intersection", "curve"],
        }

    async def _clean_boundaries(self, params: dict) -> dict:
        """Clean parcel boundaries (snap, remove gaps/overlaps)."""
        if "input" not in params:
            return {"error": "Missing input layer"}
        return await self._run_algorithm("native:snapgeometries", params)

    async def _calculate_areas(self, params: dict) -> dict:
        """Calculate parcel areas and perimeters."""
        if "input" not in params:
            return {"error": "Missing input layer"}
        return await self._run_algorithm("native:fieldcalculator", {
            "INPUT": params["input"],
            "FIELD_NAME": "area",
            "FORMULA": "$area",
            "FIELD_TYPE": 0,  # Decimal
            "FIELD_LENGTH": 20,
            "FIELD_PRECISION": 4,
            "OUTPUT": "memory:"
        })

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        alg_params = {k: v for k, v in params.items() if k != "operation"}
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": alg_params}
        )