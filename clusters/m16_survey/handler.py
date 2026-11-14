"""M16 — Survey and GPS: GPS import, coordinate validation, survey handling, points/tracks, coordinate transformation."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "import_gps": ["native:importgps", "gdal:vectortranslate", "native:importintogeopackage"],
    "import_gpx": ["native:importgpx", "gdal:vectortranslate"],
    "import_nmea": ["native:importnmea", "gdal:vectortranslate"],
    "validate_coords": ["native:fieldcalculator", "native:checkvalidity"],
    "coordinate_transformation": ["native:reprojectlayer", "gdal:warp", "grass7:v.proj"],
    "process_tracks": ["native:pointstopath", "saga:trackanalysis"],
    "track_to_line": ["native:pointstopath", "saga:convertpointstolines"],
    "track_simplification": ["native:simplifygeometries", "gdal:simplify"],
    "waypoint_analysis": ["native:distancematrix", "grass7:v.distance"],
    "gps_accuracy_assessment": ["native:distancematrix", "native:zonalstatistics"],
    "georeference_photos": ["native:importphotos", "otb:georeference"],
    "survey_points_import": ["native:importcsv", "native:createpointsfromxy"],
    "bearing_distance": ["native:bearingdistance", "grass7:v.bearing"],
    "traverse_adjustment": ["grass7:v.traverse", "native:adjusttraverse"],
    "coordinate_conversion": ["native:reprojectlayer", "gdal:warp"],
}


class M16Survey(ClusterBase):
    CLUSTER_ID = "M16"
    CLUSTER_NAME = "Survey and GPS"
    OPERATIONS = {k: f"Survey {k}" for k in _ALGO_MAP}

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
    return M16Survey(executor)