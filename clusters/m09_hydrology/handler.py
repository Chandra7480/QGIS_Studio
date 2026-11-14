"""M09 — Hydrological Analysis: flow direction, accumulation, watershed, streams, drainage, sinks."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "flow_direction": ["grass7:r.watershed", "saga:flowdirection", "native:flowdirection"],
    "flow_accumulation": ["grass7:r.watershed", "saga:flowaccumulation", "native:flowaccumulation"],
    "watershed": ["grass7:r.watershed", "saga:watershedbasins"],
    "stream_extraction": ["saga:channelnetwork", "grass7:r.stream.extract"],
    "drainage_network": ["grass7:r.stream.extract", "saga:channelnetworkanddrainagebasins"],
    "sink_filling": ["saga:sinkremoval", "grass7:r.fill.dir"],
    "flow_path_length": ["grass7:r.flow", "saga:flowpathlength"],
    "topographic_wetness_index": ["saga:topographicwetnessindextwi"],
    "stream_power_index": ["saga:streampowerindex"],
    "sediment_transport_index": ["saga:sedimenttransportindex"],
    "drainage_density": ["saga:drainagedensity"],
    "basin_morphometry": ["saga:basinmorphometry"],
    "hypsometric_curve": ["saga:hypsometriccurve"],
    "river_longitudinal_profile": ["saga:riverlongitudinalprofile"],
    "flood_risk_mapping": ["native:rastercalculator"],
}


class M09Hydrology(ClusterBase):
    CLUSTER_ID = "M09"
    CLUSTER_NAME = "Hydrological Analysis"
    OPERATIONS = {k: f"Hydrology {k}" for k in _ALGO_MAP}

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
    return M09Hydrology(executor)