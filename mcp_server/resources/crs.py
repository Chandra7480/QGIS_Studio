"""Universal AI GIS Studio — CRS Resources.

Resources for Coordinate Reference System information and lookup.
"""

from typing import Dict, Any, Optional, List
from mcp_server.resources.registry import ResourceSpec, ResourceType
from core.logging import get_logger

logger = get_logger("mcp.resources.crs")


# Common CRS database - in production this would query QGIS/proj.db
_CRS_DATABASE: Dict[str, Dict[str, Any]] = {
    "EPSG:4326": {
        "auth_id": "EPSG:4326",
        "name": "WGS 84",
        "type": "Geographic 2D",
        "area": "World",
        "bbox": [-180, -90, 180, 90],
        "proj4": "+proj=longlat +datum=WGS84 +no_defs",
        "wkt": 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]',
    },
    "EPSG:3857": {
        "auth_id": "EPSG:3857",
        "name": "WGS 84 / Pseudo-Mercator",
        "type": "Projected",
        "area": "World - 85°S to 85°N",
        "bbox": [-180, -85.06, 180, 85.06],
        "proj4": "+proj=merc +a=6378137 +b=6378137 +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +k=1 +units=m +nadgrids=@null +wktext +no_defs",
        "wkt": 'PROJCS["WGS 84 / Pseudo-Mercator",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],PROJECTION["Mercator_1SP"],PARAMETER["central_meridian",0],PARAMETER["scale_factor",1],PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["X",EAST],AXIS["Y",NORTH],AUTHORITY["EPSG","3857"]]',
    },
    "EPSG:32633": {
        "auth_id": "EPSG:32633",
        "name": "WGS 84 / UTM zone 33N",
        "type": "Projected",
        "area": "Between 12°E and 18°E, northern hemisphere",
        "bbox": [12, 0, 18, 84],
        "proj4": "+proj=utm +zone=33 +datum=WGS84 +units=m +no_defs",
    },
    "EPSG:32632": {
        "auth_id": "EPSG:32632",
        "name": "WGS 84 / UTM zone 32N",
        "type": "Projected",
        "area": "Between 6°E and 12°E, northern hemisphere",
        "bbox": [6, 0, 12, 84],
        "proj4": "+proj=utm +zone=32 +datum=WGS84 +units=m +no_defs",
    },
    "EPSG:25832": {
        "auth_id": "EPSG:25832",
        "name": "ETRS89 / UTM zone 32N",
        "type": "Projected",
        "area": "Europe - 6°E to 12°E",
        "bbox": [6, 35, 12, 84],
        "proj4": "+proj=utm +zone=32 +ellps=GRS80 +units=m +no_defs",
    },
    "EPSG:25833": {
        "auth_id": "EPSG:25833",
        "name": "ETRS89 / UTM zone 33N",
        "type": "Projected",
        "area": "Europe - 12°E to 18°E",
        "bbox": [12, 35, 18, 84],
        "proj4": "+proj=utm +zone=33 +ellps=GRS80 +units=m +no_defs",
    },
}


def _search_crs(query: str) -> List[Dict[str, Any]]:
    """Search CRS by auth ID, name, or area."""
    query_lower = query.lower()
    results = []
    for crs in _CRS_DATABASE.values():
        if (query_lower in crs.get("auth_id", "").lower() or
            query_lower in crs.get("name", "").lower() or
            query_lower in crs.get("area", "").lower()):
            results.append(crs)
    return results


# Resource Handlers
async def handle_crs_list(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://crs resource."""
    return {
        "crs_list": list(_CRS_DATABASE.values()),
        "count": len(_CRS_DATABASE),
        "resource": "qgis://crs",
    }


async def handle_crs_detail(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://crs/{auth_id} resource."""
    auth_id = variables.get("auth_id", "").upper()
    crs = _CRS_DATABASE.get(auth_id)
    if not crs:
        return {
            "error": f"CRS not found: {auth_id}",
            "resource": f"qgis://crs/{auth_id}",
            "suggestion": "Use qgis://crs/search?q={query} to find CRS",
        }
    return {
        "crs": crs,
        "resource": f"qgis://crs/{auth_id}",
    }


async def handle_crs_search(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://crs/search?q={q} resource template."""
    query = variables.get("q", "")
    results = _search_crs(query)
    return {
        "query": query,
        "crs_list": results,
        "count": len(results),
        "resource": f"qgis://crs/search?q={query}",
    }


async def handle_crs_transform(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://crs/transform?from={from_crs}&to={to_crs} resource template."""
    from_crs = variables.get("from_crs", "").upper()
    to_crs = variables.get("to_crs", "").upper()

    from_info = _CRS_DATABASE.get(from_crs)
    to_info = _CRS_DATABASE.get(to_crs)

    return {
        "from_crs": from_crs,
        "to_crs": to_crs,
        "from_info": from_info,
        "to_info": to_info,
        "transform_available": from_info is not None and to_info is not None,
        "resource": f"qgis://crs/transform?from={from_crs}&to={to_crs}",
        "note": "Actual transformation requires QGIS/proj. This resource provides metadata only.",
    }


def register_crs_resources(registry) -> None:
    """Register all CRS-related resources."""

    registry.register(ResourceSpec(
        uri_pattern="qgis://crs",
        name="CRS Database",
        description="List of common Coordinate Reference Systems with metadata.",
        mime_type="application/json",
        resource_type=ResourceType.STATIC,
        permissions=["qgis:read"],
        handler=handle_crs_list,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://crs/{auth_id}",
        name="CRS Detail",
        description="Detailed information for a specific CRS (WKT, PROJ4, bounds, area of use).",
        mime_type="application/json",
        resource_type=ResourceType.DYNAMIC,
        variables={"auth_id": "CRS authority ID (e.g., EPSG:4326)"},
        permissions=["qgis:read"],
        handler=handle_crs_detail,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://crs/search?q={q}",
        name="CRS Search",
        description="Search CRS by authority ID, name, or area of use.",
        mime_type="application/json",
        resource_type=ResourceType.TEMPLATE,
        variables={"q": "Search query (e.g., 'WGS 84', 'UTM', 'Germany')"},
        permissions=["qgis:read"],
        handler=handle_crs_search,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://crs/transform?from={from_crs}&to={to_crs}",
        name="CRS Transform Info",
        description="Metadata about transforming between two CRS (requires QGIS for actual transform).",
        mime_type="application/json",
        resource_type=ResourceType.TEMPLATE,
        variables={
            "from_crs": "Source CRS (e.g., EPSG:4326)",
            "to_crs": "Target CRS (e.g., EPSG:3857)",
        },
        permissions=["qgis:read"],
        handler=handle_crs_transform,
    ))