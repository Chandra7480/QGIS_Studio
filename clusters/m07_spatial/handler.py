"""M07 — Spatial Analysis: joins, proximity, overlay, density, interpolation, suitability."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "spatial_join": ["native:joinattributesbylocation"],
    "proximity": ["native:distancematrix", "gdal:proximity"],
    "overlay": ["native:intersection", "native:union", "native:clip"],
    "density": ["native:countpointsinpolygon"],
    "interpolation": ["native:idwinterpolation", "gdal:grid"],
    "suitability": ["native:rastercalculator"],
}


class M07Spatial(ClusterBase):
    CLUSTER_ID = "M07"
    CLUSTER_NAME = "Spatial Analysis"
    OPERATIONS = {k: f"Spatial {k}" for k in _ALGO_MAP}

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
    return M07Spatial(executor)
