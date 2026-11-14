"""M03 — Vector Processing: buffer, clip, dissolve, intersection, union, difference, merge, split, repair."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "buffer": ["native:buffer"],
    "clip": ["native:clip"],
    "dissolve": ["native:dissolve"],
    "intersection": ["native:intersection"],
    "union": ["native:union"],
    "difference": ["native:difference"],
    "merge": ["native:mergevectorlayers"],
    "repair": ["native:fixgeometries"],
    "split": ["native:splitfeaturesbymaxdistance"],
}


class M03Vector(ClusterBase):
    CLUSTER_ID = "M03"
    CLUSTER_NAME = "Vector Processing"
    OPERATIONS = {k: f"Vector {k}" for k in _ALGO_MAP}

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
    return M03Vector(executor)
