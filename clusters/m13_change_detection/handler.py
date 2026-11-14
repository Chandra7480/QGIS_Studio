"""M13 — Change Detection: temporal comparison, raster difference, land-cover change, reports, trend analysis."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "temporal_comparison": ["native:rastercalculator", "otb:multitemporalchange"],
    "raster_difference": ["native:rastercalculator", "gdal:calc", "saga:rasterdifference"],
    "landcover_change": ["native:rastercalculator", "otb:landcoverchange", "saga:landcoverchange"],
    "change_report": ["native:zonalstatistics", "otb:changereport"],
    "multitemporal_change": ["otb:multitemporalchange", "saga:multitemporalanalysis"],
    "image_ratio": ["native:rastercalculator", "otb:bandmath", "saga:rasterratio"],
    "image_difference": ["native:rastercalculator", "otb:bandmath", "saga:rasterdifference"],
    "ndvi_change": ["native:rastercalculator", "otb:vegetationindices"],
    "urban_expansion": ["native:rastercalculator", "otb:urbanchange", "saga:urbanexpansion"],
    "deforestation_detection": ["otb:deforestation", "saga:deforestationdetection", "native:rastercalculator"],
    "flood_mapping": ["otb:floodmapping", "saga:floodmapping", "native:rastercalculator"],
    "burned_area": ["otb:burnedarea", "saga:burnedarea", "native:rastercalculator"],
    "trend_analysis": ["saga:trendanalysis", "native:rastercalculator", "otb:timeseriestrend"],
    "time_series_analysis": ["otb:timeseriessmoothing", "saga:timeseriesanalysis"],
    "change_vector_analysis": ["saga:changevectoranalysis", "otb:changevector"],
}


class M13ChangeDetection(ClusterBase):
    CLUSTER_ID = "M13"
    CLUSTER_NAME = "Change Detection"
    OPERATIONS = {k: f"Change Detection {k}" for k in _ALGO_MAP}

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
    return M13ChangeDetection(executor)