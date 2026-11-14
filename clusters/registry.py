"""Cluster registry: maps M01-M25 to their handler modules."""

import importlib
from core.capability_registry import CapabilityRegistry

CLUSTER_MODULES = {
    "M01": "clusters.m01_data_acquisition",
    "M02": "clusters.m02_data_management",
    "M03": "clusters.m03_vector",
    "M04": "clusters.m04_raster",
    "M05": "clusters.m05_georeferencing",
    "M06": "clusters.m06_crs",
    "M07": "clusters.m07_spatial",
    "M08": "clusters.m08_terrain",
    "M09": "clusters.m09_hydrology",
    "M10": "clusters.m10_network",
    "M11": "clusters.m11_remote_sensing",
    "M12": "clusters.m12_classification",
    "M13": "clusters.m13_change_detection",
    "M14": "clusters.m14_3d",
    "M15": "clusters.m15_lidar",
    "M16": "clusters.m16_survey",
    "M17": "clusters.m17_cadastral",
    "M18": "clusters.m18_cartography",
    "M19": "clusters.m19_temporal",
    "M20": "clusters.m20_database",
    "M21": "clusters.m21_web_gis",
    "M22": "clusters.m22_field_data",
    "M23": "clusters.m23_automation",
    "M24": "clusters.m24_ai_ml",
    "M25": "clusters.m25_quality",
}


def get_cluster_handler(cluster_id: str, executor):
    mod_base = CLUSTER_MODULES.get(cluster_id)
    if not mod_base:
        from core.exceptions import NotFoundError
        raise NotFoundError(f"Unknown cluster: {cluster_id}")
    mod_name = mod_base + ".handler"
    mod = importlib.import_module(mod_name)
    handler = mod.create_handler(executor)
    return handler


def register_clusters_capabilities(capability_registry: CapabilityRegistry) -> None:
    """Register all cluster capabilities with the CapabilityRegistry."""
    for cluster_id, module_name in CLUSTER_MODULES.items():
        try:
            mod = importlib.import_module(module_name + ".handler")
            # Get operations from the handler module
            if hasattr(mod, 'OPERATIONS'):
                for op_name, op_desc in mod.OPERATIONS.items():
                    capability_registry.register(
                        category="cluster",
                        name=f"{cluster_id}:{op_name}",
                        version="1.0.0",
                        available=True,
                        details={"cluster": cluster_id, "operation": op_name, "description": op_desc}
                    )
        except Exception as exc:
            # Silently skip if module can't be imported
            pass
