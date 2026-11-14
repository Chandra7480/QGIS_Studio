"""M17 — Cadastral GIS: parcel management, boundary digitization, area, topology, subdivision."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "manage_parcel": ["native:splitfeaturesbymaxdistance", "native:mergevectorlayers"],
    "calculate_area": ["native:fieldcalculator", "native:addgeometryattributes", "grass7:v.to.db"],
    "calculate_perimeter": ["native:fieldcalculator", "native:addgeometryattributes"],
    "validate_topology": ["native:checkvalidity", "native:fixgeometries", "grass7:v.clean"],
    "parcel_subdivision": ["native:splitfeaturesbymaxdistance", "grass7:v.split"],
    "parcel_merging": ["native:mergevectorlayers", "native:dissolve"],
    "boundary_digitization": ["native:splitwithlines", "native:polygonize"],
    "boundary_cleaning": ["native:snapgeometries", "grass7:v.clean", "native:fixgeometries"],
    "overlay_parcels": ["native:intersection", "native:union", "native:difference"],
    "parcel_buffer": ["native:buffer", "grass7:v.buffer"],
    "setback_calculation": ["native:buffer", "native:offsetcurve"],
    "easement_analysis": ["native:intersection", "native:difference", "native:clip"],
    "adjacency_matrix": ["native:joinattributesbylocation", "grass7:v.distance"],
    "topology_report": ["native:checkvalidity", "native:fieldcalculator"],
    "cadastral_join": ["native:joinattributesbyfieldvalue", "native:joinattributesbylocation"],
    "area_correction": ["native:fieldcalculator", "native:addgeometryattributes"],
    "boundary_offset": ["native:offsetcurve", "native:buffer"],
}


class M17Cadastral(ClusterBase):
    CLUSTER_ID = "M17"
    CLUSTER_NAME = "Cadastral GIS"
    OPERATIONS = {k: f"Cadastral {k}" for k in _ALGO_MAP}

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
    return M17Cadastral(executor)