"""MCP tool implementations for qgis.database namespace — 10 database tools."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.database")


def _dispatch(tool: str, params: dict, request_id: str) -> dict:
    client = QgisBridgeClient()
    return client.dispatch(tool, params or {}, request_id=request_id)


def database_postgis_connect(params: dict) -> dict:
    """Connect to PostGIS database."""
    return _dispatch("qgis.database.postgis_connect", params, request_id="db_postgis_connect")


def database_geopackage_connect(params: dict) -> dict:
    """Connect to GeoPackage database."""
    return _dispatch("qgis.database.geopackage_connect", params, request_id="db_geopackage_connect")


def database_spatialite_connect(params: dict) -> dict:
    """Connect to SpatiaLite database."""
    return _dispatch("qgis.database.spatialite_connect", params, request_id="db_spatialite_connect")


def database_virtual_layer(params: dict) -> dict:
    """Create virtual layer from SQL query."""
    return _dispatch("qgis.database.virtual_layer", params, request_id="db_virtual_layer")


def database_spatial_sql(params: dict) -> dict:
    """Execute spatial SQL query on database."""
    return _dispatch("qgis.database.spatial_sql", params, request_id="db_spatial_sql")


def database_db_import(params: dict) -> dict:
    """Import layer into database."""
    return _dispatch("qgis.database.db_import", params, request_id="db_db_import")


def database_db_export(params: dict) -> dict:
    """Export layer from database."""
    return _dispatch("qgis.database.db_export", params, request_id="db_db_export")


def database_sql_builder(params: dict) -> dict:
    """Build spatial SQL query visually."""
    return _dispatch("qgis.database.sql_builder", params, request_id="db_sql_builder")


def database_connection_test(params: dict) -> dict:
    """Test database connection."""
    return _dispatch("qgis.database.connection_test", params, request_id="db_connection_test")


def database_schema_inspect(params: dict) -> dict:
    """Inspect database schema (tables, columns, indexes, constraints)."""
    return _dispatch("qgis.database.schema_inspect", params, request_id="db_schema_inspect")