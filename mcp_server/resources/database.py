"""Universal AI GIS Studio — Database Connection Resources.

Resources for spatial database connections and tables.
"""

from typing import Dict, Any, Optional
from mcp_server.resources.registry import ResourceSpec, ResourceType
from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.resources.database")


_client: Optional[QgisBridgeClient] = None


def get_client() -> QgisBridgeClient:
    global _client
    if _client is None:
        _client = QgisBridgeClient()
    return _client


def _fetch_database_info() -> Dict[str, Any]:
    """Fetch database connections from QGIS via bridge."""
    client = get_client()
    result = client.dispatch("qgis.database.info", {}, "res_db_info")
    return result.get("result", {})


# Resource Handlers
async def handle_database_connections(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://database/connections resource."""
    db_info = _fetch_database_info()
    return {
        "connections": db_info.get("connections", []),
        "tables": db_info.get("tables", []),
        "resource": "qgis://database/connections",
    }


async def handle_database_tables(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://database/tables resource."""
    db_info = _fetch_database_info()
    return {
        "tables": db_info.get("tables", []),
        "resource": "qgis://database/tables",
    }


async def handle_connection_tables(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://database/connection/{connection_name}/tables resource."""
    connection_name = variables.get("connection_name", "")
    db_info = _fetch_database_info()

    # Filter tables by connection
    all_tables = db_info.get("tables", [])
    conn_tables = [t for t in all_tables if t.get("connection") == connection_name]

    return {
        "connection": connection_name,
        "tables": conn_tables,
        "count": len(conn_tables),
        "resource": f"qgis://database/connection/{connection_name}/tables",
    }


def register_database_resources(registry) -> None:
    """Register all database-related resources."""

    registry.register(ResourceSpec(
        uri_pattern="qgis://database/connections",
        name="Database Connections",
        description="List all configured spatial database connections.",
        mime_type="application/json",
        resource_type=ResourceType.STATIC,
        permissions=["qgis:database:read"],
        handler=handle_database_connections,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://database/tables",
        name="All Database Tables",
        description="List all tables across all database connections.",
        mime_type="application/json",
        resource_type=ResourceType.STATIC,
        permissions=["qgis:database:read"],
        handler=handle_database_tables,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://database/connection/{connection_name}/tables",
        name="Connection Tables",
        description="List tables for a specific database connection.",
        mime_type="application/json",
        resource_type=ResourceType.DYNAMIC,
        variables={"connection_name": "Database connection name"},
        permissions=["qgis:database:read"],
        handler=handle_connection_tables,
    ))