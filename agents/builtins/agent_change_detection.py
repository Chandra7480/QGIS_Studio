"""Change Detection Agent — Temporal comparison, land-cover change."""

from agents.base_agent import SpecializedAgent


class ChangeDetectionAgent(SpecializedAgent):
    """Agent for change detection: temporal comparison, land cover change, difference analysis."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_change_detection",
            name="Change Detection Agent",
            description="Temporal comparison, land-cover change.",
            instructions=(
                "You detect changes: image differencing, ratioing, change vector analysis, "
                "post-classification comparison, time series breakpoints, and trend analysis. "
                "Use qgis.algorithms.execute with raster calculator and temporal algorithms."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="change_detection",
            tool_namespace="qgis.algorithms",
        )
        
        self.change_algorithms = {
            "difference": "qgis:rastercalculator",
            "ratio": "qgis:rastercalculator",
            "change_vector": "saga:changevectoranalysis",
            "post_classification": "custom:post_classification",
            "bfast": "custom:bfast",
            "trend": "saga:trendanalysis",
            "correlation": "saga:correlationanalysis",
            "temporal_profile": "custom:temporal_profile",
        }

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "detect")
        params = task.get("params", {})

        self.add_to_history("user", f"Change Detection: {action}", {"action": action})

        if action == "detect":
            result = await self._detect(params)
        elif action == "difference":
            result = await self._difference(params)
        elif action == "ratio":
            result = await self._ratio(params)
        elif action == "change_vector":
            result = await self._change_vector(params)
        elif action == "post_classification":
            result = await self._post_classification(params)
        elif action == "time_series":
            result = await self._time_series(params)
        elif action == "list_operations":
            result = {"operations": list(self.change_algorithms.keys())}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _detect(self, params: dict) -> dict:
        method = params.get("method", "difference")
        if method in self.change_algorithms:
            return await self._run_algorithm(self.change_algorithms[method], params)
        return {"error": f"Unknown method: {method}", "available": list(self.change_algorithms.keys())}

    async def _difference(self, params: dict) -> dict:
        """Image differencing (t2 - t1)."""
        required = ["before", "after"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm("qgis:rastercalculator", {
            "expression": f"{params['after']} - {params['before']}",
            "layers": [params['before'], params['after']],
            "output": params.get("output", "memory:")
        })

    async def _ratio(self, params: dict) -> dict:
        """Image ratioing (t2 / t1)."""
        required = ["before", "after"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm("qgis:rastercalculator", {
            "expression": f"{params['after']} / {params['before']}",
            "layers": [params['before'], params['after']],
            "output": params.get("output", "memory:")
        })

    async def _change_vector(self, params: dict) -> dict:
        """Change vector analysis (multiband)."""
        required = ["before", "after"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm("saga:changevectoranalysis", params)

    async def _post_classification(self, params: dict) -> dict:
        """Post-classification comparison."""
        required = ["classified_before", "classified_after"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm("qgis:rastercalculator", {
            "expression": f"{params['classified_after']} != {params['classified_before']}",
            "layers": [params['classified_before'], params['classified_after']],
            "output": params.get("output", "memory:")
        })

    async def _time_series(self, params: dict) -> dict:
        """Time series change analysis."""
        images = params.get("images", [])
        if len(images) < 2:
            return {"error": "Need at least 2 images for time series"}
        return {"note": "Time series analysis requires multiple dates. Use agent_temporal_gis."}

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        alg_params = {k: v for k, v in params.items() if k != "method"}
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": alg_params}
        )