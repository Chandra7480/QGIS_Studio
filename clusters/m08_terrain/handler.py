"""M08 — Terrain Analysis: DEM derivatives, slope, aspect, hillshade, contours, ruggedness, curvature."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "slope": ["native:slope", "gdal:slope", "saga:slopeaspectcurvature"],
    "aspect": ["native:aspect", "gdal:aspect", "saga:slopeaspectcurvature"],
    "hillshade": ["native:hillshade", "gdal:hillshade", "saga:analyticalhillshading"],
    "contours": ["native:contour", "gdal:contour", "saga:contourlines"],
    "roughness": ["native:roughness", "saga:roughness"],
    "tpi": ["saga:tpi", "native:tpi"],
    "tri": ["saga:tri", "native:tri"],
    "curvature": ["saga:curvature", "native:curvature"],
    "profile_curvature": ["saga:profilecurvature"],
    "plan_curvature": ["saga:plancurvature"],
    "flow_direction": ["grass7:r.watershed", "saga:flowdirection"],
    "flow_accumulation": ["grass7:r.watershed", "saga:flowaccumulation"],
    "catchment_area": ["saga:catchmentarea", "grass7:r.watershed"],
    "terrain_ruggedness_index": ["saga:terrainruggednessindex"],
    "ls_factor": ["saga:lsfactor"],
    "dem_processing": ["gdal:dem"],
    "terrain_derivatives": ["native:roughness", "gdal:dem"],
}


class M08Terrain(ClusterBase):
    CLUSTER_ID = "M08"
    CLUSTER_NAME = "Terrain Analysis"
    OPERATIONS = {k: f"Terrain {k}" for k in _ALGO_MAP}

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
    return M08Terrain(executor)