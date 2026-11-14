import os

_PLUGIN_DIR = r'C:\Users\shusi\AppData\Roaming\QGIS\QGIS4\profiles\default\python\plugins\universal_ai_gis'
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_PLUGIN_DIR))

def _verify_project_root(path):
    return all(os.path.isdir(os.path.join(path, d)) for d in ('bridge', 'core', 'database'))

print('_PROJECT_ROOT (detected):', _PROJECT_ROOT)
print('Verify detected root:', _verify_project_root(_PROJECT_ROOT))

if not _verify_project_root(_PROJECT_ROOT):
    for candidate in [
        r"D:\1 2 3 QGIS\Universal-AI-GIS-Studio",
        os.environ.get("UAGIS_PROJECT_ROOT", ""),
    ]:
        if candidate and _verify_project_root(candidate):
            _PROJECT_ROOT = candidate
            break

print('Final _PROJECT_ROOT:', _PROJECT_ROOT)
print('Verify final:', _verify_project_root(_PROJECT_ROOT))
print('bridge:', os.path.isdir(os.path.join(_PROJECT_ROOT, 'bridge')))
print('core:', os.path.isdir(os.path.join(_PROJECT_ROOT, 'core')))
print('database:', os.path.isdir(os.path.join(_PROJECT_ROOT, 'database')))