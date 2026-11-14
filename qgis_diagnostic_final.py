# ============================================================
# FINAL DIAGNOSTIC TEST - RUN IN QGIS PYTHON CONSOLE
# After QGIS restart and plugin reload
# ============================================================

import os, shutil, urllib.request, json, time, sys
from pathlib import Path

PROJECT_ROOT = Path(r"D:\1 2 3 QGIS\Universal-AI-GIS-Studio")
QGIS_PLUGIN_DIR = Path(os.environ['APPDATA']) / "QGIS" / "QGIS3" / "profiles" / "default" / "python" / "plugins" / "universal_ai_gis"

# 1. Copy fresh plugin with all fixes
if QGIS_PLUGIN_DIR.exists(): shutil.rmtree(QGIS_PLUGIN_DIR, ignore_errors=True)
shutil.copytree(PROJECT_ROOT / "plugin" / "universal_ai_gis", QGIS_PLUGIN_DIR)
print("Plugin copied fresh with all fixes")

# 2. Add to sys.path
plugin_parent = str(QGIS_PLUGIN_DIR.parent)
if plugin_parent not in sys.path: sys.path.insert(0, plugin_parent)
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))

# 3. Load plugin fresh USING qgis.utils.loadPlugin (proper registration)
from qgis.utils import loadPlugin
loadPlugin("universal_ai_gis")
print("Plugin loaded via loadPlugin")

# 4. Get the properly registered plugin instance
from qgis.utils import plugins
plugin = plugins.get("universal_ai_gis")
if not plugin:
    print("ERROR: Plugin not in qgis.utils.plugins!")
else:
    print(f"Plugin found: {type(plugin).__name__}")

# 5. Start bridge if not already running
if plugin and plugin.bridge_server and not getattr(plugin.bridge_server, 'running', False):
    plugin.bridge_server.start(plugin.dispatcher)
    print("Bridge started manually")

import __main__
__main__.uagis_plugin = plugin
print("Reference stored")

# 6. WAIT for bridge to fully start
time.sleep(2)

# 7. Get executor from plugin
executor = plugin.executor if plugin else None
if executor:
    print(f"Executor found: {type(executor).__name__}")
else:
    print("Executor NOT found on plugin")

# 8. DIAGNOSTIC TESTS
print("\n=== DIAGNOSTIC TESTS ===")

# Test 1: Direct bridge HTTP call
print("\nTest 1: Direct bridge HTTP call")
try:
    req = urllib.request.Request("http://127.0.0.1:8765/dispatch", 
        data=json.dumps({"request_id":"diag1","tool":"qgis.system.health","params":{}}).encode(),
        headers={"Content-Type":"application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        result = json.loads(r.read().decode())
        print(f"  Bridge HTTP: {result.get('status')} - {result.get('verification_state')}")
        if result.get('status') == 'ok':
            print(f"  Result: {result.get('result')}")
except Exception as e:
    print(f"  FAILED: {e}")

# Test 2: Direct executor call
print("\nTest 2: Direct executor call")
if executor:
    try:
        result = executor.health()
        print(f"  Direct executor health: {result}")
    except Exception as e:
        print(f"  FAILED: {e}")
else:
    print("  Executor not available")

# Test 3: Direct executor inspect_project
print("\nTest 3: Direct executor inspect_project")
if executor:
    try:
        result = executor.inspect_project()
        print(f"  inspect_project: {json.dumps(result, default=str)[:200]}")
    except Exception as e:
        print(f"  FAILED: {e}")
else:
    print("  Executor not available")

# Test 4: Check main thread
print("\nTest 4: Thread check")
from qgis.PyQt.QtCore import QCoreApplication, QThread
app = QCoreApplication.instance()
current_id = QThread.currentThreadId()
main_id = app.thread().currentThreadId() if app else None
print(f"  Main thread ID: {main_id}")
print(f"  Current thread ID: {current_id}")
print(f"  Is main thread (int compare): {int(current_id) == int(main_id) if main_id else False}")

# Test 5: Check plugin reference
print("\nTest 5: Plugin reference")
print(f"  Plugin: {plugin is not None}")
if plugin and plugin.bridge_server:
    print(f"  Bridge server: {plugin.bridge_server}")
    print(f"  Bridge running: {plugin.bridge_server.running}")
    print(f"  Bridge port: {plugin.bridge_server.port}")

print("\n=== DIAGNOSTIC COMPLETE ===")