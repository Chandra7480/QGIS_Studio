"""M10 — Network Analysis: shortest path, service areas, routing, connectivity, travel time."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "shortest_path_point_to_point": ["native:shortestpathpointtopoint"],
    "shortest_path_layer_to_point": ["native:shortestpathlayertopoint"],
    "shortest_path_point_to_layer": ["native:shortestpathpointtolayer"],
    "shortest_path_layer_to_layer": ["native:shortestpathlayerlayer"],
    "service_area_from_layer": ["native:serviceareafromlayer"],
    "service_area_from_point": ["native:serviceareafrompoint"],
    "service_area_isochrones": ["native:serviceareaisochrones"],
    "connectivity": ["native:connectivity"],
    "travel_time": ["native:traveltime"],
    "cost_distance": ["native:costdistance"],
    "least_cost_path": ["native:leastcostpath"],
    "network_centrality": ["grass7:v.net.centrality"],
    "network_allocation": ["grass7:v.net.alloc"],
    "network_isochrones": ["native:networkisochrones"],
    "road_network_analysis": ["grass7:v.net.salesman"],
}


class M10Network(ClusterBase):
    CLUSTER_ID = "M10"
    CLUSTER_NAME = "Network Analysis"
    OPERATIONS = {k: f"Network {k}" for k in _ALGO_MAP}

    def execute(self, operation: str, params: dict) -> ClusterResult:
        patterns = _ALGO_MAP.get(operation)
        if not patterns:
            return ClusterResult(operation, False, "FAILED", {},
                                 error=f"Unknown operation: {operation}")
        algo = self.discover_algorithm(patterns)
        if not algo:
            return ClusterResult(operation, False, "FAILED", {},
                                 error=f"No processing algorithm found for {operation}")
        try:
            result = self.run_algorithm(algo, params.get("parameters", {}))
            return ClusterResult(operation, True, "SUCCESS",
                                 {"algorithm": algo, "outputs": result.get("outputs", {})})
        except Exception as exc:
            return ClusterResult(operation, False, "FAILED", {},
                                 error=str(exc))


def create_handler(executor):
    return M10Network(executor)