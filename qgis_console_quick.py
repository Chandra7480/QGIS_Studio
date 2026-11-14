# ============================================================
# QUICK VERSION - MANUAL PLUGIN INITIALIZATION
# Copy-paste directly into QGIS Python Console (Ctrl+Alt+P)
# This manually instantiates the plugin with iface
# ============================================================

import os, shutil, urllib.request, json, time, sys
from pathlib import Path

# ---- CONFIG ----
PROJECT_ROOT = Path(r"D:\1 2 3 QGIS\Universal-AI-GIS-Studio")
PLUGIN_SRC = PROJECT_ROOT / "plugin" / "universal_ai_gis"
QGIS_PLUGIN_DIR = Path(os.environ['APPDATA']) / "QGIS" / "QGIS3" / "profiles" / "default" / "python" / "plugins" / "universal_ai_gis"

# ---- 1. COPY PLUGIN ----
if QGIS_PLUGIN_DIR.exists(): shutil.rmtree(QGIS_PLUGIN_DIR, ignore_errors=True)
shutil.copytree(PLUGIN_SRC, QGIS_PLUGIN_DIR)
print("✅ Plugin copied to QGIS profile")

# ---- 2. ADD TO SYS.PATH ----
if str(QGIS_PLUGIN_DIR.parent) not in sys.path:
    sys.path.insert(0, str(QGIS_PLUGIN_DIR.parent))

# ---- 3. MANUALLY INSTANTIATE PLUGIN ----
try:
    # Import the plugin module
    import universal_ai_gis.plugin as plugin_module
    
    # Get iface from qgis.utils (available in Python Console)
    from qgis.utils import iface
    
    # Manually call classFactory - this is what QGIS does internally
    plugin_instance = plugin_module.classFactory(iface)
    print(f"✅ Plugin instantiated: {type(plugin_instance).__name__}")
    
    # Call initGui to initialize core and start bridge
    plugin_instance.initGui()
    print("✅ Plugin initGui() called - bridge should be starting")
    
    # Keep reference globally so it doesn't get garbage collected
    import __main__
    __main__.uagis_plugin = plugin_instance
    print("✅ Plugin reference stored in __main__.uagis_plugin")
    
except Exception as e:
    print(f"❌ Plugin initialization error: {e}")
    import traceback
    traceback.print_exc()

# ---- 4. VERIFY BRIDGE ----
for i in range(8):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=3) as r:
            d = json.loads(r.read().decode())
            print(f"✅ Bridge OK! QGIS: {d.get('qgis_connected')}, Project: {d.get('project_open')}, Layers: {d.get('layer_count')}")
            break
    except Exception as e:
        if i < 7: 
            time.sleep(1.5)
        else: 
            print(f"❌ Bridge not responding after 8 attempts: {e}")
            print("   Check QGIS Log Messages panel for errors")