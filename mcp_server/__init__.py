"""Universal AI GIS Studio — Universal MCP Server package.

Exposes QGIS functionality to external AI clients via MCP (stdio and
Streamable HTTP). All tools call the QGIS Bridge and return verified,
structured results — never fabricated success.
"""

__version__ = "1.0.0"

# Export clients for external use
from mcp_server.qgis_client import (
    AsyncQgisBridgeClient,
    QgisBridgeClient,
    create_client,
    CircuitBreaker,
    RetryPolicy,
)

__all__ = [
    "AsyncQgisBridgeClient",
    "QgisBridgeClient",
    "create_client",
    "CircuitBreaker",
    "RetryPolicy",
]
