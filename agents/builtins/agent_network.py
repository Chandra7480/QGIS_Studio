"""Network Analysis Agent — Shortest path, service areas, routing."""

from agents.base_agent import SpecializedAgent


class NetworkAnalysisAgent(SpecializedAgent):
    """Agent for network analysis: shortest path, service areas, routing, travel time."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_network",
            name="Network Analysis Agent",
            description="Shortest path, service areas, routing.",
            instructions=(
                "You perform network analysis: shortest path, service areas (isochrones), "
                "vehicle routing, travel time matrices, and network connectivity. "
                "Use qgis.algorithms.execute with native and GRASS network algorithms."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="network",
            tool_namespace="qgis.algorithms",
        )
        
        self.network_algorithms = {
            "shortest_path": "native:shortestpathpointtopoint",
            "shortest_path_layer": "native:shortestpathlayer",
            "service_area": "native:serviceareafromlayer",
            "service_area_point": "native:serviceareafrompoint",
            "travel_time_matrix": "native:traveltimematrix",
            "closest_facility": "native:closestfacility",
            "vehicle_routing": "native:vehicleroutingproblem",
            "location_allocation": "native:locationallocation",
            "network_connectivity": "native:networkconnectivity",
            "dijkstra": "grass7:v.net.path",
            "all_pairs": "grass7:v.net.allpairs",
            "salesman": "grass7:v.net.salesman",
            "steiner": "grass7:v.net.steiner",
        }

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "analyze")
        params = task.get("params", {})

        self.add_to_history("user", f"Network Analysis: {action}", {"action": action})

        if action == "analyze":
            result = await self._analyze(params)
        elif action == "shortest_path":
            result = await self._shortest_path(params)
        elif action == "service_area":
            result = await self._service_area(params)
        elif action == "travel_time":
            result = await self._travel_time(params)
        elif action == "vehicle_routing":
            result = await self._vehicle_routing(params)
        elif action == "list_operations":
            result = {"operations": list(self.network_algorithms.keys())}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _analyze(self, params: dict) -> dict:
        operation = params.get("operation")
        if operation in self.network_algorithms:
            return await self._run_algorithm(self.network_algorithms[operation], params)
        return {"error": f"Unknown operation: {operation}", "available": list(self.network_algorithms.keys())}

    async def _shortest_path(self, params: dict) -> dict:
        """Calculate shortest path between points."""
        required = ["network", "start_point", "end_point"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm("native:shortestpathpointtopoint", params)

    async def _service_area(self, params: dict) -> dict:
        """Calculate service area (isochrones)."""
        if "network" not in params:
            return {"error": "Missing required parameter: network"}
        
        if "start_points" in params:
            return await self._run_algorithm("native:serviceareafromlayer", params)
        elif "start_point" in params:
            return await self._run_algorithm("native:serviceareafrompoint", params)
        return {"error": "Missing start_point or start_points"}

    async def _travel_time(self, params: dict) -> dict:
        """Calculate travel time matrix."""
        required = ["network", "points"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm("native:traveltimematrix", params)

    async def _vehicle_routing(self, params: dict) -> dict:
        """Solve vehicle routing problem."""
        required = ["network", "vehicles", "orders"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm("native:vehicleroutingproblem", params)

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        alg_params = {k: v for k, v in params.items() if k != "operation"}
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": alg_params}
        )