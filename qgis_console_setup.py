# ============================================================
# Universal AI GIS Studio - QGIS Python Console Setup Script
# Copy-paste this ENTIRE script into QGIS Python Console
# (Plugins → Python Console → Show Editor → Paste → Run)
# ============================================================

import os
import sys
import subprocess
import shutil
from pathlib import Path

print("=" * 60)
print("Universal AI GIS Studio - QGIS Console Setup")
print("=" * 60)

# ----------------------------------------------------------
# CONFIGURATION - Adjust paths if needed
# ----------------------------------------------------------
PROJECT_ROOT = Path(r"D:\1 2 3 QGIS\Universal-AI-GIS-Studio")
PLUGIN_SOURCE = PROJECT_ROOT / "plugin" / "universal_ai_gis"
QGIS_PLUGIN_DIR = Path(os.environ.get('APPDATA', '')) / "QGIS" / "QGIS3" / "profiles" / "default" / "python" / "plugins" / "universal_ai_gis"

# ----------------------------------------------------------
# STEP 1: Verify plugin source exists
# ----------------------------------------------------------
print(f"\n[1/5] Checking plugin source: {PLUGIN_SOURCE}")
if not PLUGIN_SOURCE.exists():
    print(f"❌ ERROR: Plugin source not found at {PLUGIN_SOURCE}")
    print("   Check PROJECT_ROOT path at top of script")
    raise SystemExit(1)

if not (PLUGIN_SOURCE / "metadata.txt").exists():
    print(f"❌ ERROR: metadata.txt not found in plugin source")
    raise SystemExit(1)

print(f"✅ Plugin source found: {PLUGIN_SOURCE}")

# ----------------------------------------------------------
# STEP 2: Copy plugin to QGIS profile (force update)
# ----------------------------------------------------------
print(f"\n[2/5] Installing plugin to QGIS profile...")
print(f"   Target: {QGIS_PLUGIN_DIR}")

# Remove old version
if QGIS_PLUGIN_DIR.exists():
    print("   Removing old version...")
    shutil.rmtree(QGIS_PLUGIN_DIR, ignore_errors=True)

# Copy new version
shutil.copytree(PLUGIN_SOURCE, QGIS_PLUGIN_DIR)
print(f"✅ Plugin copied to QGIS profile")

# Verify
if (QGIS_PLUGIN_DIR / "metadata.txt").exists():
    print(f"✅ metadata.txt verified")
else:
    print(f"❌ metadata.txt missing after copy!")
    raise SystemExit(1)

# ----------------------------------------------------------
# STEP 3: Enable plugin via QGIS API
# ----------------------------------------------------------
print(f"\n[3/5] Enabling plugin in QGIS...")

from qgis.utils import plugins, active_plugins
from qgis.core import QgsApplication

# Get plugin manager
plugin_manager = QgsApplication.pluginManager()

# Check if already loaded
plugin_name = "universal_ai_gis"

# Add plugin path if not already there
if str(QGIS_PLUGIN_DIR.parent) not in plugin_manager.pluginPaths():
    plugin_manager.addPluginPath(str(QGIS_PLUGIN_DIR.parent))
    print(f"   Added plugin path: {QGIS_PLUGIN_DIR.parent}")

# Load plugin
try:
    if plugin_name not in active_plugins:
        plugin_manager.loadPlugin(plugin_name)
        print(f"✅ Plugin loaded: {plugin_name}")
    else:
        print(f"ℹ️  Plugin already loaded")
except Exception as e:
    print(f"❌ Failed to load plugin: {e}")
    # Try alternative method
    try:
        from qgis.utils import loadPlugin
        loadPlugin(plugin_name)
        print(f"✅ Plugin loaded via loadPlugin()")
    except Exception as e2:
        print(f"❌ loadPlugin also failed: {e2}")

# ----------------------------------------------------------
# STEP 4: Start Bridge Server
# ----------------------------------------------------------
print(f"\n[4/5] Starting Bridge Server...")

try:
    # Import the plugin module
    import universal_ai_gis.plugin as plugin_module
    
    # Get plugin instance
    plugin_instance = plugins.get(plugin_name)
    if plugin_instance:
        # Start bridge
        if hasattr(plugin_instance, 'start_bridge'):
            plugin_instance.start_bridge()
            print(f"✅ Bridge started via plugin_instance.start_bridge()")
        elif hasattr(plugin_instance, 'bridge_server') and plugin_instance.bridge_server:
            if not plugin_instance.bridge_server.is_running:
                plugin_instance.bridge_server.start()
                print(f"✅ Bridge started via bridge_server.start()")
            else:
                print(f"ℹ️  Bridge already running")
        else:
            print(f"⚠️  Plugin loaded but no start_bridge method found")
            print(f"   Available methods: {[m for m in dir(plugin_instance) if not m.startswith('_')]}")
    else:
        print(f"⚠️  Plugin not in qgis.utils.plugins dict")
        print(f"   Available plugins: {list(plugins.keys())}")
        
except Exception as e:
    print(f"❌ Error starting bridge: {e}")
    import traceback
    traceback.print_exc()

# ----------------------------------------------------------
# STEP 5: Verify Bridge is Running
# ----------------------------------------------------------
print(f"\n[5/5] Verifying bridge connection...")

import urllib.request
import json
import time

bridge_url = "http://127.0.0.1:8765/health"
max_retries = 5

for i in range(max_retries):
    try:
        req = urllib.request.Request(bridge_url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            print(f"✅ Bridge responding!")
            print(f"   QGIS Connected: {data.get('qgis_connected', 'unknown')}")
            print(f"   Project Open: {data.get('project_open', 'unknown')}")
            print(f"   Layer Count: {data.get('layer_count', 'unknown')}")
            break
    except Exception as e:
        if i < max_retries - 1:
            print(f"   Waiting for bridge... ({i+1}/{max_retries})")
            time.sleep(1)
        else:
            print(f"❌ Bridge not responding after {max_retries} attempts")
            print(f"   Last error: {e}")
            print(f"\n   Try clicking the 🔗 Bridge button manually in QGIS toolbar")

print("\n" + "=" * 60)
print("SETUP COMPLETE!")
print("=" * 60)
print("\nNext steps:")
print("1. Keep QGIS running with bridge active")
print("2. Open NEW terminal and run:")
print(f"   cd {PROJECT_ROOT}")
print(f"   .\\run_mcp_stdio.bat")
print("3. Or test with:")
print(f"   .\\run_test_client.bat")
print("\nBridge URL: http://127.0.0.1:8765")
print("MCP Server will connect to bridge automatically")