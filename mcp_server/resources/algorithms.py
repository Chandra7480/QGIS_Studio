"""Universal AI GIS Studio — Algorithm Resources.

Resources for discovering and inspecting QGIS Processing algorithms.
"""

from typing import Dict, Any, Optional
from mcp_server.resources.registry import ResourceSpec, ResourceType
from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.resources.algorithms")


_client: Optional[QgisBridgeClient] = None


def get_client() -> QgisBridgeClient:
    global _client
    if _client is None:
        _client = QgisBridgeClient()
    return _client


# Cache for algorithm list
_algorithms_cache: Optional[Dict[str, Any]] = None


def _fetch_algorithms(force_refresh: bool = False) -> Dict[str, Any]:
    """Fetch all algorithms from QGIS via bridge."""
    global _algorithms_cache
    if _algorithms_cache is not None and not force_refresh:
        return _algorithms_cache

    client = get_client()
    result = client.dispatch("qgis.algorithms.discover", {}, "res_algo_discover")
    _algorithms_cache = result.get("result", {"algorithms": [], "count": 0})
    return _algorithms_cache


def _find_algorithm(algorithm_id: str) -> Optional[Dict[str, Any]]:
    """Find a specific algorithm by ID."""
    algos = _fetch_algorithms()
    for algo in algos.get("algorithms", []):
        if algo.get("id") == algorithm_id or algo.get("name") == algorithm_id:
            return algo
    return None


def _search_algorithms(query: str) -> list:
    """Search algorithms by name/description."""
    algos = _fetch_algorithms()
    query_lower = query.lower()
    results = []
    for algo in algos.get("algorithms", []):
        if (query_lower in algo.get("id", "").lower() or
            query_lower in algo.get("name", "").lower() or
            query_lower in algo.get("description", "").lower()):
            results.append(algo)
    return results


# Resource Handlers
async def handle_algorithms_list(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://algorithms resource."""
    algos = _fetch_algorithms()
    return {
        "algorithms": algos.get("algorithms", []),
        "count": algos.get("count", 0),
        "resource": "qgis://algorithms",
    }


async def handle_algorithm_detail(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://algorithm/{algorithm_id} resource."""
    algorithm_id = variables.get("algorithm_id", "")
    algo = _find_algorithm(algorithm_id)
    if not algo:
        return {
            "error": f"Algorithm not found: {algorithm_id}",
            "resource": f"qgis://algorithm/{algorithm_id}",
        }
    return {
        "algorithm": algo,
        "resource": f"qgis://algorithm/{algorithm_id}",
    }


async def handle_algorithm_parameters(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://algorithm/{algorithm_id}/parameters resource."""
    algorithm_id = variables.get("algorithm_id", "")
    algo = _find_algorithm(algorithm_id)
    if not algo:
        return {
            "error": f"Algorithm not found: {algorithm_id}",
            "resource": f"qgis://algorithm/{algorithm_id}/parameters",
        }
    return {
        "algorithm_id": algorithm_id,
        "parameters": algo.get("parameters", {}),
        "resource": f"qgis://algorithm/{algorithm_id}/parameters",
    }


async def handle_algorithm_search(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://algorithms/search?q={query} resource template."""
    query = variables.get("q", "")
    results = _search_algorithms(query)
    return {
        "query": query,
        "algorithms": results,
        "count": len(results),
        "resource": f"qgis://algorithms/search?q={query}",
    }


async def handle_algorithms_by_provider(variables: Dict[str, Any]) -> Dict[str, Any]:
    """Handler for qgis://algorithms/provider/{provider} resource."""
    provider = variables.get("provider", "")
    algos = _fetch_algorithms()
    results = [
        a for a in algos.get("algorithms", [])
        if a.get("provider", "").lower() == provider.lower()
    ]
    return {
        "provider": provider,
        "algorithms": results,
        "count": len(results),
        "resource": f"qgis://algorithms/provider/{provider}",
    }


def register_algorithm_resources(registry) -> None:
    """Register all algorithm-related resources."""

    registry.register(ResourceSpec(
        uri_pattern="qgis://algorithms",
        name="All Algorithms",
        description="Complete list of all available QGIS Processing algorithms with metadata.",
        mime_type="application/json",
        resource_type=ResourceType.STATIC,
        permissions=["qgis:read"],
        handler=handle_algorithms_list,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://algorithm/{algorithm_id}",
        name="Algorithm Detail",
        description="Detailed metadata for a specific processing algorithm (parameters, outputs, description).",
        mime_type="application/json",
        resource_type=ResourceType.DYNAMIC,
        variables={"algorithm_id": "Algorithm ID (e.g., native:buffer)"},
        permissions=["qgis:read"],
        handler=handle_algorithm_detail,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://algorithm/{algorithm_id}/parameters",
        name="Algorithm Parameters",
        description="Parameter schema for a specific algorithm.",
        mime_type="application/json",
        resource_type=ResourceType.DYNAMIC,
        variables={"algorithm_id": "Algorithm ID (e.g., native:buffer)"},
        permissions=["qgis:read"],
        handler=handle_algorithm_parameters,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://algorithms/search?q={q}",
        name="Algorithm Search",
        description="Search algorithms by name, ID, or description.",
        mime_type="application/json",
        resource_type=ResourceType.TEMPLATE,
        variables={"q": "Search query"},
        permissions=["qgis:read"],
        handler=handle_algorithm_search,
    ))

    registry.register(ResourceSpec(
        uri_pattern="qgis://algorithms/provider/{provider}",
        name="Algorithms by Provider",
        description="List algorithms from a specific provider (e.g., native, gdal, grass, saga).",
        mime_type="application/json",
        resource_type=ResourceType.DYNAMIC,
        variables={"provider": "Provider name (native, gdal, grass, saga, etc.)"},
        permissions=["qgis:read"],
        handler=handle_algorithms_by_provider,
    ))