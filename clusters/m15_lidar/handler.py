"""M15 — LiDAR: point-cloud inspection, filtering, classification, terrain extraction, point cloud processing."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "point_cloud_inspection": ["pdal:info", "native:zonalstatistics", "saga:pointcloudinfo"],
    "point_cloud_import": ["pdal:import", "native:importpointcloud"],
    "point_cloud_export": ["pdal:export", "gdal:translate"],
    "filtering": ["pdal:filter", "native:extractbyattribute", "saga:pointcloudfilter"],
    "classification": ["pdal:classify", "native:reclassifybytable", "saga:pointcloudclassification"],
    "ground_classification": ["pdal:ground", "saga:groundfilter", "grass7:v.lidar.ground"],
    "building_classification": ["pdal:buildings", "saga:buildingdetection", "grass7:v.lidar.edgedetection"],
    "vegetation_classification": ["pdal:vegetation", "saga:vegetationfilter"],
    "terrain_extraction": ["pdal:dem", "native:dem", "gdal:dem", "saga:dem"],
    "dsm_creation": ["pdal:dsm", "native:dem", "saga:dsm"],
    "dtm_creation": ["pdal:dtm", "native:dem", "saga:dtm"],
    "chm_creation": ["pdal:chm", "saga:chm", "native:rastercalculator"],
    "point_density": ["pdal:density", "saga:pointdensity", "native:pointdensity"],
    "normal_computation": ["pdal:normal", "saga:pointcloudnormals"],
    "outlier_removal": ["pdal:outlier", "saga:outlierremoval", "native:outlierremoval"],
    "point_cloud_merge": ["pdal:merge", "native:mergevectorlayers"],
    "point_cloud_clip": ["pdal:clip", "native:cliprasterbymasklayer"],
    "point_cloud_thin": ["pdal:thin", "saga:pointcloudthinning"],
}


class M15LiDAR(ClusterBase):
    CLUSTER_ID = "M15"
    CLUSTER_NAME = "LiDAR"
    OPERATIONS = {k: f"LiDAR {k}" for k in _ALGO_MAP}

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
    return M15LiDAR(executor)