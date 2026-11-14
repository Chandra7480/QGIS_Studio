"""M20 — Spatial Database: GeoPackage, PostGIS, spatial SQL, connections, validation, migrations."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "connect_geopackage": ["native:loadlayer", "gdal:vectortranslate"],
    "connect_postgis": ["native:postgisconnection", "native:loadlayer"],
    "connect_spatialite": ["native:spatialiteconnection", "native:loadlayer"],
    "connect_mssql": ["native:mssqlconnection", "native:loadlayer"],
    "spatial_sql": ["native:executesql", "grass7:db.execute"],
    "create_spatial_index": ["native:createspatialindex", "grass7:v.db.addindex"],
    "import_to_postgis": ["native:importintopostgis", "gdal:vectortranslate"],
    "export_from_postgis": ["native:exportfrompostgis", "gdal:vectortranslate"],
    "run_sql": ["native:executesql", "grass7:db.execute"],
    "create_view": ["native:createview", "grass7:db.createview"],
    "validate_geometry": ["native:checkvalidity", "native:fixgeometries"],
    "validate_topology": ["native:checkvalidity", "grass7:v.clean"],
    "vacuum_analyze": ["native:vacuumanalyze", "grass7:db.vacuum"],
    "backup_database": ["native:backupdatabase", "grass7:db.backup"],
    "migrate_schema": ["native:migrateschema", "grass7:db.migrate"],
    "spatial_join_db": ["native:joinattributesbylocation", "grass7:v.distance"],
    "execute_function": ["native:executefunction", "grass7:db.execute"],
}


class M20Database(ClusterBase):
    CLUSTER_ID = "M20"
    CLUSTER_NAME = "Spatial Database"
    OPERATIONS = {k: f"Database {k}" for k in _ALGO_MAP}

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
    return M20Database(executor)