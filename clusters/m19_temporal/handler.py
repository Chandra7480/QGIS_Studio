"""M19 — Temporal GIS: time-enabled layers, temporal filtering, visualization, time-series analysis."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "enable_time": ["native:settime", "native:enabletemporal"],
    "temporal_filter": ["native:temporalfilter", "native:extractbytime"],
    "temporal_analysis": ["native:temporalstatistics", "saga:timeseriesanalysis"],
    "time_series_plot": ["native:timeseriesplot", "saga:timeseriesplot"],
    "animate_raster": ["native:animateraster", "native:temporalanimation"],
    "animate_vector": ["native:animatevector", "native:temporalanimation"],
    "temporal_join": ["native:jointemporal", "native:joinattributesbytime"],
    "time_slice": ["native:timeslice", "native:extractbytimerange"],
    "temporal_interpolation": ["native:temporalinterpolation", "saga:temporalinterpolation"],
    "change_over_time": ["native:rastercalculator", "otb:timeseriestrend"],
    "temporal_aggregation": ["native:temporalaggregate", "saga:temporalaggregate"],
    "time_manager": ["native:timemanager", "native:temporalcontroller"],
    "datetime_field": ["native:fieldcalculator", "native:tostring"],
    "temporal_raster_calculator": ["native:rastercalculator", "otb:bandmath"],
    "trajectory_analysis": ["native:pointstopath", "grass7:v.trajectory"],
}


class M19Temporal(ClusterBase):
    CLUSTER_ID = "M19"
    CLUSTER_NAME = "Temporal GIS"
    OPERATIONS = {k: f"Temporal {k}" for k in _ALGO_MAP}

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
    return M19Temporal(executor)