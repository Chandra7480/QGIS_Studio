"""Universal AI GIS Studio — Constants."""

import os

# Plugin directory
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))

# Settings prefix
SETTINGS_PREFIX = "uagis/mcp"

# Port configuration
DEFAULT_PORT = 9876
MIN_PORT = 1024
MAX_PORT = 65535


def env_port():
    """Get port from environment variable QGIS_MCP_PORT."""
    val = os.environ.get("QGIS_MCP_PORT", "").strip()
    if not val:
        return None
    try:
        return int(val)
    except ValueError:
        raise ValueError(f"Invalid QGIS_MCP_PORT: {val!r}")

# Plugin version
plugin_version = "1.0.0"