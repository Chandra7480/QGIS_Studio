"""M25 — Quality Control: geometry, topology, CRS, attribute, completeness, reports, validation."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "geometry_validation": ["native:checkvalidity", "native:fixgeometries", "grass7:v.clean"],
    "topology_validation": ["native:checkvalidity", "grass7:v.clean", "native:topologychecker"],
    "crs_validation": ["native:assigncrs", "native:reprojectlayer", "gdal:warp"],
    "attribute_validation": ["native:fieldcalculator", "native:refactorfields", "native:checkvalidity"],
    "completeness": ["native:zonalstatistics", "native:fieldcalculator", "native:basicstatistics"],
    "duplicate_geometry": ["native:deleteduplicategeometries", "grass7:v.clean", "native:removeduplicates"],
    "self_intersection": ["native:checkvalidity", "grass7:v.clean", "native:fixgeometries"],
    "gap_detection": ["native:checkvalidity", "grass7:v.clean", "native:polygonize"],
    "overlap_detection": ["native:intersection", "native:checkvalidity", "grass7:v.clean"],
    "dangling_nodes": ["native:checkvalidity", "grass7:v.clean", "native:removedangles"],
    "spike_removal": ["native:fixgeometries", "grass7:v.clean", "native:removespikes"],
    "min_area_check": ["native:fieldcalculator", "native:addgeometryattributes", "native:extractbyattribute"],
    "min_angle_check": ["native:checkvalidity", "grass7:v.clean", "native:fieldcalculator"],
    "quality_report": ["native:basicstatistics", "native:zonalstatistics", "native:fieldcalculator"],
    "schema_validation": ["native:refactorfields", "native:checkvalidity", "native:fieldcalculator"],
    "data_consistency": ["native:joinattributesbyfieldvalue", "native:fieldcalculator", "native:checkvalidity"],
}


class M25Quality(ClusterBase):
    CLUSTER_ID = "M25"
    CLUSTER_NAME = "Quality Control"
    OPERATIONS = {k: f"Quality {k}" for k in _ALGO_MAP}

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
    return M25Quality(executor)