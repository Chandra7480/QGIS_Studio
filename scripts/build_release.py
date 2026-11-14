"""Build installable release ZIPs for Universal AI GIS Studio.

Produces:
  release/universal_ai_gis_plugin.zip   -> QGIS Plugin Manager install
  release/universal-ai-gis-studio-1.0.0.zip -> full platform
"""

import os
import zipfile
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE = os.path.join(ROOT, "release")
PLUGIN_SRC = os.path.join(ROOT, "plugin", "universal_ai_gis")

os.makedirs(RELEASE, exist_ok=True)

# ---- 1. QGIS plugin ZIP (install via QGIS Plugin Manager) ----
plugin_zip = os.path.join(RELEASE, "universal_ai_gis_plugin.zip")
if os.path.exists(plugin_zip):
    os.remove(plugin_zip)
with zipfile.ZipFile(plugin_zip, "w", zipfile.ZIP_DEFLATED) as zf:
    for dirpath, dirnames, filenames in os.walk(PLUGIN_SRC):
        dirnames[:] = [dn for dn in dirnames if dn != "__pycache__"]
        for fn in filenames:
            if fn.endswith((".pyc", ".pyo")):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, os.path.join(ROOT, "plugin"))
            zf.write(full, rel)
print("Wrote", plugin_zip)

# ---- 2. Full platform ZIP ----
platform_zip = os.path.join(RELEASE, "universal-ai-gis-studio-1.0.0.zip")
if os.path.exists(platform_zip):
    os.remove(platform_zip)

include_dirs = [
    "plugin", "bridge", "mcp_server", "core", "database", "integrations",
    "agents", "skills", "clusters", "workflows", "extensions", "security",
    "monitoring", "resources", "utils", "tests", "requirements", "docs",
]
include_files = [
    "pyproject.toml", "README.md", "CHANGELOG.md", "LICENSE",
]

with zipfile.ZipFile(platform_zip, "w", zipfile.ZIP_DEFLATED) as zf:
    for d in include_dirs:
        dp = os.path.join(ROOT, d)
        if not os.path.isdir(dp):
            continue
        for dirpath, dirnames, filenames in os.walk(dp):
            # skip __pycache__ and .pytest_cache
            dirnames[:] = [dn for dn in dirnames
                           if dn not in ("__pycache__", ".pytest_cache")]
            for fn in filenames:
                if fn.endswith((".pyc", ".pyo")):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, ROOT)
                zf.write(full, rel)
    for f in include_files:
        fp = os.path.join(ROOT, f)
        if os.path.exists(fp):
            zf.write(fp, f)
print("Wrote", platform_zip)
