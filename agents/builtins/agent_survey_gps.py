"""Survey and GPS Agent — GPS import and coordinate validation."""

from agents.base_agent import SpecializedAgent


class SurveyGPSAgent(SpecializedAgent):
    """Agent for survey/GPS: GPS import, coordinate transformation, traverse adjustment."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_survey_gps",
            name="Survey and GPS Agent",
            description="GPS import and coordinate validation.",
            instructions=(
                "You handle survey and GPS data: GPS file import (GPX, NMEA, CSV), "
                "coordinate transformation, traverse adjustment, coordinate validation, "
                "and survey calculations. Use qgis.algorithms.execute and native tools."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="survey_gps",
            tool_namespace="qgis.algorithms",
        )
        
        self.survey_algorithms = {
            "import_gpx": "native:importgpx",
            "import_csv": "native:importcsv",
            "reproject": "native:reprojectlayer",
            "add_xy": "native:addxyfieldstolayer",
            "distance_matrix": "native:distancematrix",
            "azimuth_distance": "native:azimuthdistance",
            "traverse": "custom:traverse_adjustment",
            "coordinate_check": "native:checkvalidity",
            "create_points": "native:createpointsfromtable",
        }

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "process")
        params = task.get("params", {})

        self.add_to_history("user", f"Survey/GPS: {action}", {"action": action})

        if action == "process":
            result = await self._process(params)
        elif action == "import_gps":
            result = await self._import_gps(params)
        elif action == "reproject":
            result = await self._reproject(params)
        elif action == "validate_coords":
            result = await self._validate_coords(params)
        elif action == "traverse":
            result = await self._traverse(params)
        elif action == "create_points":
            result = await self._create_points(params)
        elif action == "list_operations":
            result = {"operations": list(self.survey_algorithms.keys())}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _process(self, params: dict) -> dict:
        operation = params.get("operation")
        if operation in self.survey_algorithms:
            return await self._run_algorithm(self.survey_algorithms[operation], params)
        return {"error": f"Unknown operation: {operation}", "available": list(self.survey_algorithms.keys())}

    async def _import_gps(self, params: dict) -> dict:
        """Import GPS data (GPX, CSV, etc.)."""
        file_path = params.get("file_path")
        file_type = params.get("type", "gpx")
        
        if not file_path:
            return {"error": "Missing required parameter: file_path"}
        
        if file_type == "gpx":
            return await self._run_algorithm("native:importgpx", {"INPUT": file_path, **params})
        elif file_type == "csv":
            return await self._run_algorithm("native:importcsv", {"INPUT": file_path, **params})
        return {"error": f"Unknown file type: {file_type}"}

    async def _reproject(self, params: dict) -> dict:
        """Reproject survey data."""
        if "input" not in params or "target_crs" not in params:
            return {"error": "Missing input or target_crs"}
        return await self._run_algorithm("native:reprojectlayer", params)

    async def _validate_coords(self, params: dict) -> dict:
        """Validate coordinates."""
        if "input" not in params:
            return {"error": "Missing input layer"}
        return await self._run_algorithm("native:checkvalidity", params)

    async def _traverse(self, params: dict) -> dict:
        """Traverse adjustment (simplified)."""
        return {
            "note": "Traverse adjustment requires specialized algorithms. "
                   "Use QGIS plugins like 'Traverse' or 'Survey' for full support.",
            "input": params.get("input"),
            "method": params.get("method", "compass_rule"),
        }

    async def _create_points(self, params: dict) -> dict:
        """Create points from coordinate table."""
        required = ["x_field", "y_field", "table"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm("native:createpointsfromtable", params)

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        alg_params = {k: v for k, v in params.items() if k != "operation"}
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": alg_params}
        )