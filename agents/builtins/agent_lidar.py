"""LiDAR Agent — Point-cloud inspection and terrain extraction."""

from agents.base_agent import SpecializedAgent


class LiDARAgent(SpecializedAgent):
    """Agent for LiDAR processing: point cloud inspection, classification, terrain extraction."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_lidar",
            name="LiDAR Agent",
            description="Point-cloud inspection and terrain extraction.",
            instructions=(
                "You process LiDAR data: LAS/LAZ import, point cloud classification, "
                "ground filtering, DSM/DTM generation, canopy height models, "
                "and point cloud statistics. Use PDAL, LAStools, and native algorithms."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="lidar",
            tool_namespace="qgis.algorithms",
        )
        
        self.lidar_algorithms = {
            "import_las": "pdal:importlas",
            "export_las": "pdal:exportlas",
            "ground_filter": "pdal:groundfilter",
            "dem": "pdal:dem",
            "dsm": "pdal:dsm",
            "chm": "pdal:chm",
            "statistics": "pdal:statistics",
            "clip": "pdal:clip",
            "merge": "pdal:merge",
            "reproject": "pdal:reproject",
            "thin": "pdal:thin",
            "classify": "pdal:classify",
        }

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "process")
        params = task.get("params", {})

        self.add_to_history("user", f"LiDAR: {action}", {"action": action})

        if action == "process":
            result = await self._process(params)
        elif action == "import":
            result = await self._import_las(params)
        elif action == "ground_filter":
            result = await self._ground_filter(params)
        elif action == "dem_dtm":
            result = await self._dem_dtm(params)
        elif action == "chm":
            result = await self._chm(params)
        elif action == "statistics":
            result = await self._statistics(params)
        elif action == "list_operations":
            result = {"operations": list(self.lidar_algorithms.keys())}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _process(self, params: dict) -> dict:
        operation = params.get("operation")
        if operation in self.lidar_algorithms:
            return await self._run_algorithm(self.lidar_algorithms[operation], params)
        return {"error": f"Unknown operation: {operation}", "available": list(self.lidar_algorithms.keys())}

    async def _import_las(self, params: dict) -> dict:
        """Import LAS/LAZ file."""
        if "input" not in params:
            return {"error": "Missing required parameter: input"}
        return await self._run_algorithm("pdal:importlas", params)

    async def _ground_filter(self, params: dict) -> dict:
        """Filter ground points."""
        if "input" not in params:
            return {"error": "Missing required parameter: input"}
        return await self._run_algorithm("pdal:groundfilter", params)

    async def _dem_dtm(self, params: dict) -> dict:
        """Generate DTM from ground points."""
        if "input" not in params:
            return {"error": "Missing required parameter: input"}
        return await self._run_algorithm("pdal:dem", params)

    async def _chm(self, params: dict) -> dict:
        """Generate Canopy Height Model."""
        if "input" not in params:
            return {"error": "Missing required parameter: input"}
        return await self._run_algorithm("pdal:chm", params)

    async def _statistics(self, params: dict) -> dict:
        """Point cloud statistics."""
        if "input" not in params:
            return {"error": "Missing required parameter: input"}
        return await self._run_algorithm("pdal:statistics", params)

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        alg_params = {k: v for k, v in params.items() if k != "operation"}
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": alg_params}
        )