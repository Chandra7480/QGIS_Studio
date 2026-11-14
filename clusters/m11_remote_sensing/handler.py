"""M11 — Remote Sensing: satellite processing, band combinations, spectral indices, preprocessing, pan-sharpening."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "satellite_import": ["gdal:translate", "gdal:warp", "native:importintogeopackage"],
    "band_combinations": ["native:rastercalculator", "gdal:calc"],
    "spectral_indices": ["native:rastercalculator", "otb:bandmath"],
    "pan_sharpening": ["otb:pansharpening", "gdal:pansharpen"],
    "atmospheric_correction": ["otb:opticalcalibration", "grass7:i.atcorr"],
    "radiometric_correction": ["otb:radiometricindices", "otb:radiometriccorrection"],
    "geometric_correction": ["otb:orthorectification", "gdal:warp"],
    "image_preparation": ["gdal:warp", "gdal:translate", "native:clip"],
    "mosaic": ["native:mosaicrasterlayers", "gdal:merge", "otb:mosaic"],
    "resampling": ["native:resample", "gdal:warp", "otb:resample"],
    "supervised_classification": ["otb:trainimagesclassifier", "otb:imageclassifier"],
    "unsupervised_classification": ["otb:kmeansclassification", "otb:svmclassification"],
    "object_based_classification": ["otb:hoovercompare", "otb:lsmssegmentation"],
    "change_detection_prep": ["otb:multitemporalchange", "native:rastercalculator"],
    "vegetation_indices": ["native:rastercalculator", "otb:vegetationindices"],
}


class M11RemoteSensing(ClusterBase):
    CLUSTER_ID = "M11"
    CLUSTER_NAME = "Remote Sensing"
    OPERATIONS = {k: f"Remote Sensing {k}" for k in _ALGO_MAP}

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
    return M11RemoteSensing(executor)