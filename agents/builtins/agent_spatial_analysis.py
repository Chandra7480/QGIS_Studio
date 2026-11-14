"""Spatial Analysis Agent — Joins, proximity, overlay, interpolation."""

from agents.base_agent import SpecializedAgent


class SpatialAnalysisAgent(SpecializedAgent):
    """Agent for spatial analysis: joins, proximity, overlay, interpolation, statistics."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_spatial_analysis",
            name="Spatial Analysis Agent",
            description="Joins, proximity, overlay, interpolation.",
            instructions=(
                "You perform spatial analysis: spatial joins, proximity analysis (distance, "
                "nearest neighbor), overlay analysis, interpolation (IDW, Kriging), "
                "hotspot analysis, cluster detection, and spatial statistics. "
                "Use qgis.algorithms.execute with native and SAGA/GRASS algorithms."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="spatial_analysis",
            tool_namespace="qgis.algorithms",
        )
        
        self.spatial_algorithms = {
            "spatial_join": "native:joinattributesbylocation",
            "join_by_nearest": "native:joinbynearest",
            "distance_matrix": "native:distancematrix",
            "nearest_neighbor": "native:nearestneighboranalysis",
            "k_nearest": "native:knearestneighbors",
            "buffer": "native:buffer",
            "intersect": "native:intersection",
            "union": "native:union",
            "clip": "native:clip",
            "idw": "native:idwinterpolation",
            "kriging": "saga:ordinarykriging",
            "tin": "native:tininterpolation",
            "heatmap": "native:heatmapkerneldensityestimation",
            "hotspot": "native:optimizedhotspotanalysis",
            "cluster": "native:dbscanclustering",
            "mean_center": "native:meancoordinates",
            "std_distance": "native:standarddistances",
            "moran_i": "native:moransglobalspatialautocorrelation",
            "geary_c": "native:gearysglobalspatialautocorrelation",
            "getis_ord": "native:getisordgi",
            "summarize_within": "native:summarizewithin",
            "summarize_nearby": "native:summarizenearby",
        }

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "analyze")
        params = task.get("params", {})

        self.add_to_history("user", f"Spatial Analysis: {action}", {"action": action})

        if action == "analyze":
            result = await self._analyze(params)
        elif action == "spatial_join":
            result = await self._spatial_join(params)
        elif action == "proximity":
            result = await self._proximity(params)
        elif action == "interpolation":
            result = await self._interpolation(params)
        elif action == "hotspot":
            result = await self._hotspot(params)
        elif action == "cluster":
            result = await self._cluster(params)
        elif action == "statistics":
            result = await self._statistics(params)
        elif action == "list_operations":
            result = {"operations": list(self.spatial_algorithms.keys())}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _analyze(self, params: dict) -> dict:
        """General spatial analysis router."""
        operation = params.get("operation")
        if operation in self.spatial_algorithms:
            return await self._run_algorithm(self.spatial_algorithms[operation], params)
        return {"error": f"Unknown operation: {operation}", "available": list(self.spatial_algorithms.keys())}

    async def _spatial_join(self, params: dict) -> dict:
        """Spatial join (by location or nearest)."""
        join_type = params.get("join_type", "location")  # location, nearest
        algo = "native:joinattributesbylocation" if join_type == "location" else "native:joinbynearest"
        required = ["input", "join"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm(algo, params)

    async def _proximity(self, params: dict) -> dict:
        """Proximity analysis: distance matrix, nearest neighbor."""
        prox_type = params.get("proximity_type", "distance_matrix")
        algo_map = {
            "distance_matrix": "native:distancematrix",
            "nearest_neighbor": "native:nearestneighboranalysis",
            "k_nearest": "native:knearestneighbors",
        }
        algo = algo_map.get(prox_type, "native:distancematrix")
        required = ["input"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm(algo, params)

    async def _interpolation(self, params: dict) -> dict:
        """Spatial interpolation: IDW, Kriging, TIN."""
        interp_type = params.get("interpolation_type", "idw")
        algo_map = {
            "idw": "native:idwinterpolation",
            "kriging": "saga:ordinarykriging",
            "tin": "native:tininterpolation",
        }
        algo = algo_map.get(interp_type, "native:idwinterpolation")
        required = ["input", "field"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm(algo, params)

    async def _hotspot(self, params: dict) -> dict:
        """Hotspot analysis (Getis-Ord Gi*)."""
        if "input" not in params:
            return {"error": "Missing required parameter: input"}
        return await self._run_algorithm("native:optimizedhotspotanalysis", params)

    async def _cluster(self, params: dict) -> dict:
        """Clustering analysis (DBSCAN)."""
        if "input" not in params:
            return {"error": "Missing required parameter: input"}
        return await self._run_algorithm("native:dbscanclustering", params)

    async def _statistics(self, params: dict) -> dict:
        """Spatial statistics: Moran's I, Geary's C, Getis-Ord."""
        stat_type = params.get("statistic", "moran_i")
        algo_map = {
            "moran_i": "native:moransglobalspatialautocorrelation",
            "geary_c": "native:gearysglobalspatialautocorrelation",
            "getis_ord": "native:getisordgi",
        }
        algo = algo_map.get(stat_type, "native:moransglobalspatialautocorrelation")
        if "input" not in params:
            return {"error": "Missing required parameter: input"}
        return await self._run_algorithm(algo, params)

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        """Execute a processing algorithm."""
        alg_params = {k: v for k, v in params.items() 
                      if k not in ["operation", "join_type", "proximity_type", 
                                   "interpolation_type", "statistic"]}
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": alg_params}
        )