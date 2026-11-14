# ============================================================
# CLEAR CACHE + RESTART BRIDGE (FINAL FIX)
# Run in QGIS Python Console
# ============================================================

import os, shutil, urllib.request, json, time, sys
from pathlib import Path

PROJECT_ROOT = Path(r"D:\1 2 3 QGIS\Universal-AI-GIS-Studio")
QGIS_PLUGIN_DIR = Path(os.environ['APPDATA']) / "QGIS" / "QGIS3" / "profiles" / "default" / "python" / "plugins" / "universal_ai_gis"

# 1. CLEAR ALL .pyc CACHE FILES
for root, dirs, files in os.walk(QGIS_PLUGIN_DIR):
    for f in files:
        if f.endswith('.pyc'):
            try: os.remove(os.path.join(root, f))
            except: pass
    if '__pycache__' in dirs:
        try: shutil.rmtree(os.path.join(root, '__pycache__'), ignore_errors=True)
        except: pass
print("Cleared .pyc cache")

# 2. Stop existing bridge
from qgis.utils import plugins
existing = plugins.get("universal_ai_gis")
if existing and existing.bridge_server:
    existing.bridge_server.stop()
    print("Stopped old bridge")

# 3. Remove plugin from plugins dict to force reload
if "universal_ai_gis" in plugins:
    del plugins["universal_ai_gis"]
print("Removed from plugins cache")

# 4. Re-instantiate plugin
import universal_ai_gis.plugin as plugin_module
from qgis.utils import iface
plugin_instance = plugin_module.classFactory(iface)
plugin_instance.initGui()
print("Plugin reinitialized")

# 5. Keep reference
import __main__
__main__.uagis_plugin = plugin_instance
print("Reference stored")

# 6. Verify bridge
for i in range(8):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=3) as r:
            d = json.loads(r.read().decode())
            print("Bridge OK! QGIS:", d.get("qgis_connected"), "Project:", d.get("project_open"), "Layers:", d.get("layer_count"))
            break
    except Exception as e:
        if i < 7: time.sleep(1.5)
        else: print("Bridge not responding:", e)