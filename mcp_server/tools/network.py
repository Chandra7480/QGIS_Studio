"""MCP tool implementations for qgis.network namespace — 12 network analysis tools."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.network")


def _dispatch(tool: str, params: dict, request_id: str) -> dict:
    client = QgisBridgeClient()
    return client.dispatch(tool, params or {}, request_id=request_id)


def network_shortest_path(params: dict) -> dict:
    """Calculate shortest path (point-to-point, layer-to-point, point-to-layer, layer-to-layer)."""
    return _dispatch("qgis.network.shortest_path", params, request_id="network_shortest_path")


def network_service_area(params: dict) -> dict:
    """Calculate service area / isochrones from point or layer."""
    return _dispatch("qgis.network.service_area", params, request_id="network_service_area")


def network_od_matrix(params: dict) -> dict:
    """Calculate Origin-Destination cost matrix between points."""
    return _dispatch("qgis.network.od_matrix", params, request_id="network_od_matrix")


def network_traveling_salesman(params: dict) -> dict:
    """Solve Traveling Salesman Problem for network."""
    return _dispatch("qgis.network.traveling_salesman", params, request_id="network_traveling_salesman")


def network_vehicle_routing(params: dict) -> dict:
    """Solve Vehicle Routing Problem (VRP) with capacity constraints."""
    return _dispatch("qgis.network.vehicle_routing", params, request_id="network_vehicle_routing")


def network_isochrone(params: dict) -> dict:
    """Generate isochrone (time-based service area) polygons."""
    return _dispatch("qgis.network.isochrone", params, request_id="network_isochrone")


def network_isodistance(params: dict) -> dict:
    """Generate isodistance (distance-based service area) polygons."""
    return _dispatch("qgis.network.isodistance", params, request_id="network_isodistance")


def network_build(params: dict) -> dict:
    """Build network topology from line layer (nodes, edges, connectivity)."""
    return _dispatch("qgis.network.build", params, request_id="network_build")


def network_topology_check(params: dict) -> dict:
    """Check network topology for errors (dangles, intersections, overshoots)."""
    return _dispatch("qgis.network.topology_check", params, request_id="network_topology_check")


def network_turn_restriction(params: dict) -> dict:
    """Add/manage turn restrictions on network edges."""
    return _dispatch("qgis.network.turn_restriction", params, request_id="network_turn_restriction")


def network_elevation_profile(params: dict) -> dict:
    """Extract elevation profile along network route."""
    return _dispatch("qgis.network.elevation_profile", params, request_id="network_elevation_profile")


def network_route_report(params: dict) -> dict:
    """Generate detailed route report (distance, time, turns, elevation)."""
    return _dispatch("qgis.network.route_report", params, request_id="network_route_report")