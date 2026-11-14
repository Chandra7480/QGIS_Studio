"""M22 — Field Data: import, survey sync, attribute collection, validation, mobile data."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "import_field": ["native:importcsv", "native:createpointsfromxy", "gdal:vectortranslate"],
    "import_kobo": ["native:importkobo", "native:importjson"],
    "import_odk": ["native:importodk", "native:importjson"],
    "import_qfield": ["native:importqfield", "native:loadlayer"],
    "import_geopaparazzi": ["native:importgeopaparazzi", "gdal:vectortranslate"],
    "sync_survey": ["native:syncsurvey", "native:offlinesync"],
    "collect_attributes": ["native:fieldcalculator", "native:addfield", "native:refactorfields"],
    "validate_geometry": ["native:checkvalidity", "native:fixgeometries"],
    "validate_attributes": ["native:fieldcalculator", "native:refactorfields"],
    "validate_completeness": ["native:zonalstatistics", "native:fieldcalculator"],
    "photo_attachment": ["native:importphotos", "native:attachphotos"],
    "audio_attachment": ["native:importaudio", "native:attachaudio"],
    "form_design": ["native:createform", "native:formdesigner"],
    "offline_package": ["native:createofflinepackage", "native:offlineediting"],
    "field_sync": ["native:syncfielddata", "native:offlinesync"],
    "gps_tracking": ["native:gpstracking", "native:importgps"],
    "survey_analysis": ["native:zonalstatistics", "native:fieldcalculator"],
}


class M22FieldData(ClusterBase):
    CLUSTER_ID = "M22"
    CLUSTER_NAME = "Field Data"
    OPERATIONS = {k: f"Field Data {k}" for k in _ALGO_MAP}

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
    return M22FieldData(executor)