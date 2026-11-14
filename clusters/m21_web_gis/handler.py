"""M21 — Web GIS: WMS, WFS, WMTS, XYZ tiles, OGC services, web map publishing, tile generation."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "add_wms": ["native:loadwmslayer", "gdal:wms"],
    "add_wfs": ["native:loadwfslayer", "gdal:wfs"],
    "add_wmts": ["native:loadwmtslayer", "gdal:wmts"],
    "add_xyz": ["native:loadxyzlayer", "gdal:xyz"],
    "add_wcs": ["native:loadwcslayer", "gdal:wcs"],
    "add_arcgis_rest": ["native:loadarcgislayer", "gdal:arcgisrest"],
    "add_geojson_url": ["native:loadgeojson", "gdal:geojson"],
    "add_vector_tiles": ["native:loadvectortiles", "gdal:mvt"],
    "publish_wms": ["native:publishwms", "qgis:wmsserver"],
    "publish_wfs": ["native:publishwfs", "qgis:wfsserver"],
    "generate_tiles": ["native:generatetiles", "gdal:gdal2tiles", "otb:tiling"],
    "create_xyz_tiles": ["native:createtiles", "gdal:gdal2tiles"],
    "export_webmap": ["native:exportwebmap", "native:printlayout"],
    "qgis_server": ["native:qgisserver", "native:projecttoweb"],
    "style_webmap": ["native:setlayerstyle", "native:sldexport"],
    "sld_import": ["native:sldimport", "native:setlayerstyle"],
    "sld_export": ["native:sldexport", "native:getlayerstyle"],
    "wms_getcapabilities": ["native:wmsgetcapabilities", "gdal:wms"],
    "wfs_getcapabilities": ["native:wfsgetcapabilities", "gdal:wfs"],
}


class M21WebGIS(ClusterBase):
    CLUSTER_ID = "M21"
    CLUSTER_NAME = "Web GIS"
    OPERATIONS = {k: f"Web GIS {k}" for k in _ALGO_MAP}

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
    return M21WebGIS(executor)