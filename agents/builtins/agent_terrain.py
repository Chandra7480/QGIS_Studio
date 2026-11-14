"""Terrain Analysis Agent — Slope, aspect, hillshade, contours."""

from agents.base_agent import SpecializedAgent


class TerrainAnalysisAgent(SpecializedAgent):
    """Agent for terrain analysis: slope, aspect, hillshade, contours, viewshed, etc."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_terrain",
            name="Terrain Analysis Agent",
            description="Slope, aspect, hillshade, contours.",
            instructions=(
                "You analyze terrain: slope, aspect, hillshade, contours, viewshed, "
                "roughness, TPI, TRI, and other terrain derivatives from DEMs. "
                "Use qgis.algorithms.execute with native, GDAL, SAGA, and GRASS algorithms."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="terrain",
            tool_namespace="qgis.algorithms",
        )
        
        self.terrain_algorithms = {
            "slope": "native:slope",
            "aspect": "native:aspect",
            "hillshade": "native:hillshade",
            "contours": "gdal:contour",
            "roughness": "native:roughness",
            "tpi": "native:topographicpositionindex",
            "tri": "native:terrainruggednessindex",
            "viewshed": "native:viewshed",
            "flow_direction": "saga:flowdirection",
            "flow_accumulation": "saga:flowaccumulation",
            "stream_network": "saga:channelnetwork",
            "watershed": "saga:upslopearea",
            "curvature": "saga:curvature",
            "convergence": "saga:convergenceindex",
            "solar_radiation": "saga:insolation",
            "sky_view_factor": "saga:skyviewfactor",
        }

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "analyze")
        params = task.get("params", {})

        self.add_to_history("user", f"Terrain Analysis: {action}", {"action": action})

        if action == "analyze":
            result = await self._analyze(params)
        elif action == "slope_aspect":
            result = await self._slope_aspect(params)
        elif action == "hillshade":
            result = await self._hillshade(params)
        elif action == "contours":
            result = await self._contours(params)
        elif action == "roughness":
            result = await self._roughness(params)
        elif action == "viewshed":
            result = await self._viewshed(params)
        elif action == "hydrology_prep":
            result = await self._hydrology_prep(params)
        elif action == "curvature":
            result = await self._curvature(params)
        elif action == "list_operations":
            result = {"operations": list(self.terrain_algorithms.keys())}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _analyze(self, params: dict) -> dict:
        """General terrain analysis router."""
        operation = params.get("operation")
        if operation in self.terrain_algorithms:
            return await self._run_algorithm(self.terrain_algorithms[operation], params)
        return {"error": f"Unknown operation: {operation}", "available": list(self.terrain_algorithms.keys())}

    async def _slope_aspect(self, params: dict) -> dict:
        """Calculate slope and/or aspect."""
        dem = params.get("dem")
        if not dem:
            return {"error": "Missing required parameter: dem"}
        
        results = {}
        if params.get("slope", True):
            slope_result = await self._run_algorithm("native:slope", {"INPUT": dem, **params})
            results["slope"] = slope_result
        if params.get("aspect", True):
            aspect_result = await self._run_algorithm("native:aspect", {"INPUT": dem, **params})
            results["aspect"] = aspect_result
        return results

    async def _hillshade(self, params: dict) -> dict:
        """Generate hillshade."""
        dem = params.get("dem")
        if not dem:
            return {"error": "Missing required parameter: dem"}
        return await self._run_algorithm("native:hillshade", {"INPUT": dem, **params})

    async def _contours(self, params: dict) -> dict:
        """Generate contour lines."""
        dem = params.get("dem")
        interval = params.get("interval", 10)
        if not dem:
            return {"error": "Missing required parameter: dem"}
        return await self._run_algorithm("gdal:contour", {"INPUT": dem, "INTERVAL": interval, **params})

    async def _roughness(self, params: dict) -> dict:
        """Calculate terrain roughness/TPI/TRI."""
        dem = params.get("dem")
        if not dem:
            return {"error": "Missing required parameter: dem"}
        
        metric = params.get("metric", "roughness")  # roughness, tpi, tri
        algo_map = {
            "roughness": "native:roughness",
            "tpi": "native:topographicpositionindex",
            "tri": "native:terrainruggednessindex",
        }
        algo = algo_map.get(metric, "native:roughness")
        return await self._run_algorithm(algo, {"INPUT": dem, **params})

    async def _viewshed(self, params: dict) -> dict:
        """Calculate viewshed from observer point."""
        dem = params.get("dem")
        observer = params.get("observer_point")  # [x, y] or point layer
        if not dem or not observer:
            return {"error": "Missing required parameters: dem and observer_point"}
        return await self._run_algorithm("native:viewshed", {"INPUT": dem, "OBSERVER_POINTS": observer, **params})

    async def _hydrology_prep(self, params: dict) -> dict:
        """Prepare DEM for hydrology (fill sinks, flow direction)."""
        dem = params.get("dem")
        if not dem:
            return {"error": "Missing required parameter: dem"}
        
        # Fill sinks first
        filled = await self._run_algorithm("native:fillsinks", {"INPUT": dem, **params})
        if filled.get("status") != "ok":
            return filled
        
        # Flow direction
        flow_dir = await self._run_algorithm("saga:flowdirection", {"DEM": filled.get("result", {}).get("OUTPUT", dem), **params})
        return {"filled_dem": filled, "flow_direction": flow_dir}

    async def _curvature(self, params: dict) -> dict:
        """Calculate terrain curvature."""
        dem = params.get("dem")
        if not dem:
            return {"error": "Missing required parameter: dem"}
        
        curvature_type = params.get("curvature_type", "profile")  # profile, plan, total
        return await self._run_algorithm("saga:curvature", {"DEM": dem, "METHOD": curvature_type, **params})

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        """Execute a processing algorithm."""
        alg_params = {k: v for k, v in params.items() 
                      if k not in ["operation", "metric", "curvature_type"]}
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": alg_params}
        )