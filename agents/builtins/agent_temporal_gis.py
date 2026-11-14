"""Temporal GIS Agent — Time-enabled layers and temporal analysis."""

from agents.base_agent import SpecializedAgent


class TemporalGISAgent(SpecializedAgent):
    """Agent for temporal GIS: time-enabled layers, animation, time series."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_temporal_gis",
            name="Temporal GIS Agent",
            description="Time-enabled layers and temporal analysis.",
            instructions=(
                "You handle temporal data: time-enabled layers, temporal controller, "
                "animation export, time series analysis, and temporal queries. "
                "Use qgis.algorithms.execute and temporal tools."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="temporal",
            tool_namespace="qgis.algorithms",
        )
        
        self.temporal_algorithms = {
            "enable_time": "native:setlayertemporalsettings",
            "animation": "native:temporalanimation",
            "time_slice": "native:timeslice",
            "aggregate_time": "native:aggregatetime",
            "interpolate_time": "native:interpolatetime",
        }

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "analyze")
        params = task.get("params", {})

        self.add_to_history("user", f"Temporal GIS: {action}", {"action": action})

        if action == "analyze":
            result = await self._analyze(params)
        elif action == "enable_time":
            result = await self._enable_time(params)
        elif action == "animate":
            result = await self._animate(params)
        elif action == "time_slice":
            result = await self._time_slice(params)
        elif action == "time_series":
            result = await self._time_series(params)
        elif action == "list_operations":
            result = {"operations": list(self.temporal_algorithms.keys())}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _analyze(self, params: dict) -> dict:
        operation = params.get("operation")
        if operation in self.temporal_algorithms:
            return await self._run_algorithm(self.temporal_algorithms[operation], params)
        return {"error": f"Unknown operation: {operation}", "available": list(self.temporal_algorithms.keys())}

    async def _enable_time(self, params: dict) -> dict:
        """Enable time on layer."""
        layer = params.get("layer")
        start_field = params.get("start_field")
        end_field = params.get("end_field")
        if not layer or not start_field:
            return {"error": "Missing layer or start_field"}
        return await self._run_algorithm("native:setlayertemporalsettings", params)

    async def _animate(self, params: dict) -> dict:
        """Create temporal animation."""
        layers = params.get("layers", [])
        output = params.get("output")
        if not layers or not output:
            return {"error": "Missing layers or output"}
        return await self._run_algorithm("native:temporalanimation", params)

    async def _time_slice(self, params: dict) -> dict:
        """Extract time slice."""
        layer = params.get("layer")
        datetime = params.get("datetime")
        if not layer or not datetime:
            return {"error": "Missing layer or datetime"}
        return await self._run_algorithm("native:timeslice", params)

    async def _time_series(self, params: dict) -> dict:
        """Time series analysis."""
        return {"note": "Time series analysis combines temporal slices. Use multiple time_slice calls."}

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": params}
        )