# ============================================================
# FIXED: ADD PLUGIN PARENT TO sys.path
# Run in QGIS Python Console
# ============================================================

import os, shutil, urllib.request, json, time, sys
from pathlib import Path

PROJECT_ROOT = Path(r"D:\1 2 3 QGIS\Universal-AI-GIS-Studio")
PLUGIN_SRC = PROJECT_ROOT / "plugin" / "universal_ai_gis"
QGIS_PLUGIN_DIR = Path(os.environ['APPDATA']) / "QGIS" / "QGIS3" / "profiles" / "default" / "python" / "plugins" / "universal_ai_gis"

# 1. Copy plugin
if QGIS_PLUGIN_DIR.exists(): shutil.rmtree(QGIS_PLUGIN_DIR, ignore_errors=True)
shutil.copytree(PLUGIN_SRC, QGIS_PLUGIN_DIR)
print("Plugin copied")

# 2. ADD PLUGIN PARENT TO sys.path (critical!)
plugin_parent = str(QGIS_PLUGIN_DIR.parent)
if plugin_parent not in sys.path:
    sys.path.insert(0, plugin_parent)
    print(f"Added to sys.path: {plugin_parent}")

# Also add project root
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 3. Load plugin
import universal_ai_gis.plugin as plugin_module
from qgis.utils import iface
plugin_instance = plugin_module.classFactory(iface)
plugin_instance.initGui()
print("Plugin loaded")

import __main__
__main__.uagis_plugin = plugin_instance
print("Reference stored")

# 4. Verify bridge
for i in range(5):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=3) as r:
            d = json.loads(r.read().decode())
            print("Bridge OK! QGIS:", d.get("qgis_connected"), "Layers:", d.get("layer_count"))
            break
    except Exception as e:
        if i < 4: time.sleep(1)
        else: print("Bridge not ready:", e)