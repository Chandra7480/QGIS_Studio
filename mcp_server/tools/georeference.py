"""MCP tool implementations for qgis.georeference and qgis.gcp namespaces."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.georeference")


def georeference_analyze(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.georeference.analyze", params or {}, request_id="geo_analyze")


def gcp_generate(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.gcp.generate", params or {}, request_id="gcp_generate")


def gcp_validate(params: dict) -> dict:
    client = QgisBridgeClient()
    return client.dispatch("qgis.gcp.validate", params or {}, request_id="gcp_validate")
