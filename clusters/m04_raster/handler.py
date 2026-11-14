"""M04 — Raster Processing: calculation, reclassify, mosaic, clip, resample, convert, bands."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "raster_calculation": ["native:rastercalculator", "gdal:rastercalculator"],
    "reclassify": ["native:reclassifybytable", "gdal:reclassify"],
    "mosaic": ["native:mosaicrasterlayers", "gdal:merge"],
    "clip_raster": ["native:cliprasterbymasklayer", "gdal:cliprasterbymasklayer"],
    "resample": ["native:resample", "gdal:warm"],
    "convert": ["gdal:translate"],
    "band_operations": ["native:rastercalculator"],
}


class M04Raster(ClusterBase):
    CLUSTER_ID = "M04"
    CLUSTER_NAME = "Raster Processing"
    OPERATIONS = {k: f"Raster {k}" for k in _ALGO_MAP}

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
    return M04Raster(executor)
