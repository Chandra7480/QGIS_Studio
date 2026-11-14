"""Universal AI GIS Studio - QGIS Plugin package."""

import os
import sys

# Add plugin directory to sys.path so that bridge.*, core.*, database.*, etc.
# (which are inside the plugin package) can be imported inside QGIS.
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))

# Verify plugin directory has required backend modules
def _verify_plugin_dir(path):
    return all(os.path.isdir(os.path.join(path, d)) for d in ('bridge', 'core', 'database'))

if not _verify_plugin_dir(_PLUGIN_DIR):
    # Plugin installed in QGIS profile - try environment variable override
    env_root = os.environ.get("UAGIS_PROJECT_ROOT", "")
    if env_root and _verify_plugin_dir(env_root):
        _PLUGIN_DIR = env_root

# Add plugin directory to sys.path FIRST so our bundled modules take precedence
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

# Also add the parent directory in case backend modules are at plugin root level
_plugin_parent = os.path.dirname(_PLUGIN_DIR)
if _plugin_parent not in sys.path:
    sys.path.insert(0, _plugin_parent)

__version__ = "1.0.0"

from .plugin import UniversalAIGISPlugin  # noqa: E402


def classFactory(iface):  # QGIS plugin entry point
    """Instantiate the Universal AI GIS Studio plugin."""
    return UniversalAIGISPlugin(iface)
