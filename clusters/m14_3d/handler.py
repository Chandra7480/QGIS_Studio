"""M14 — 3D GIS: 3D visualization, terrain models, 3D layers, 3D exports, point clouds."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "create_terrain_model": ["native:dem", "gdal:dem", "saga:dem"],
    "create_tin": ["native:tinmesh", "saga:tin"],
    "create_dem_from_points": ["native:gridinterpolation", "gdal:grid", "saga:gridinterpolation"],
    "create_dsm": ["native:dem", "pdal:dem", "saga:dsm"],
    "create_dtm": ["native:dem", "pdal:dtm", "saga:dtm"],
    "extrude_polygons": ["native:extrude", "saga:extrude"],
    "create_3d_buildings": ["native:extrude", "saga:buildings3d"],
    "terrain_shading": ["native:hillshade", "saga:analyticalhillshading", "gdal:hillshade"],
    "viewshed_analysis": ["native:viewshed", "grass7:r.viewshed", "saga:viewshed"],
    "line_of_sight": ["native:lineofsight", "grass7:r.los", "saga:lineofsight"],
    "sky_view_factor": ["saga:skyviewfactor", "grass7:r.skyview"],
    "solar_radiation": ["grass7:r.sun", "saga:solarradiation", "native:solarradiation"],
    "profile_tool": ["native:profiletool", "grass7:r.profile"],
    "contour_3d": ["native:contour", "saga:contourlines", "gdal:contour"],
    "export_3d": ["native:export3d", "gdal:translate"],
}


class M14_3D(ClusterBase):
    CLUSTER_ID = "M14"
    CLUSTER_NAME = "3D GIS"
    OPERATIONS = {k: f"3D {k}" for k in _ALGO_MAP}

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
    return M14_3D(executor)