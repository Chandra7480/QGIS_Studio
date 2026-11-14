"""M05 — Georeferencing: image inspection, GCP detection/matching, transformation, validation."""

from clusters.base import ClusterBase, ClusterResult
from engines.georeferencing.georeferencing_engine import GeoreferencingEngine


class M05Georeferencing(ClusterBase):
    CLUSTER_ID = "M05"
    CLUSTER_NAME = "Georeferencing"
    OPERATIONS = {
        "inspect_image": "Inspect a scanned map image",
        "detect_landmarks": "Detect landmarks via computer vision",
        "generate_gcps": "Generate candidate GCPs",
        "validate_gcps": "Validate GCPs",
    }

    def __init__(self, executor):
        super().__init__(executor)
        self._engine = GeoreferencingEngine()

    def execute(self, operation: str, params: dict) -> ClusterResult:
        if operation == "inspect_image":
            return self._inspect_image(params)
        if operation == "detect_landmarks":
            return self._detect_landmarks(params)
        if operation == "generate_gcps":
            return self._generate_gcps(params)
        if operation == "validate_gcps":
            return self._validate_gcps(params)
        return ClusterResult(operation, False, "FAILED", {},
                             error=f"Unknown operation: {operation}")

    def _inspect_image(self, params: dict) -> ClusterResult:
        path = params.get("image_path")
        if not path:
            return ClusterResult("inspect_image", False, "FAILED", {},
                                 error="Missing image_path")
        try:
            info = self._engine.inspect_image(path)
            return ClusterResult("inspect_image", True, "SUCCESS", info)
        except Exception as exc:
            return ClusterResult("inspect_image", False, "FAILED", {},
                                 error=str(exc))

    def _detect_landmarks(self, params: dict) -> ClusterResult:
        path = params.get("image_path")
        if not path:
            return ClusterResult("detect_landmarks", False, "FAILED", {},
                                 error="Missing image_path")
        ref = params.get("reference_image_path")
        result = self._engine.detect_landmarks(path, ref)
        return ClusterResult("detect_landmarks", True, "SUCCESS", result)

    def _generate_gcps(self, params: dict) -> ClusterResult:
        path = params.get("image_path")
        gt = params.get("geotransform")
        crs = params.get("crs", "EPSG:4326")
        if not path or gt is None:
            return ClusterResult("generate_gcps", False, "FAILED", {},
                                 error="Missing image_path or geotransform")
        try:
            gcps = self._engine.generate_gcps(path, gt, crs)
            return ClusterResult("generate_gcps", True, "SUCCESS",
                                 {"gcps": [g.to_dict() for g in gcps],
                                  "count": len(gcps)})
        except Exception as exc:
            return ClusterResult("generate_gcps", False, "FAILED", {},
                                 error=str(exc))

    def _validate_gcps(self, params: dict) -> ClusterResult:
        gcps_data = params.get("gcps", [])
        gcps = []
        for d in gcps_data:
            from engines.georeferencing.georeferencing_engine import GCP
            gcps.append(GCP(**d))
        try:
            rep = self._engine.validate_gcps(gcps)
            return ClusterResult("validate_gcps", True, "SUCCESS", rep)
        except Exception as exc:
            return ClusterResult("validate_gcps", False, "FAILED", {},
                                 error=str(exc))


def create_handler(executor):
    return M05Georeferencing(executor)
