"""M06 — CRS Operations: detection, assignment, reprojection, transformation, validation."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "detect_crs": ["native:assigncrs", "native:identifycrs"],
    "assign_crs": ["native:assigncrs"],
    "reproject": ["native:reprojectlayer"],
    "transform": ["native:reprojectlayer"],
    "validate_crs": ["native:assigncrs"],
}


class M06CRS(ClusterBase):
    CLUSTER_ID = "M06"
    CLUSTER_NAME = "CRS Operations"
    OPERATIONS = {k: f"CRS {k}" for k in _ALGO_MAP}

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
    return M06CRS(executor)
