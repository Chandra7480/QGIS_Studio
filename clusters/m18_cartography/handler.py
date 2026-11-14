"""M18 — Cartography: symbology, labels, legends, scale bars, layouts, map production, atlas."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "create_layout": ["native:createprintlayout", "native:printlayout"],
    "export_layout": ["native:exportprintlayout", "native:layoutexport"],
    "apply_symbology": ["native:setlayerstyle", "native:categorizedrenderer"],
    "graduated_symbology": ["native:graduatedrenderer", "native:setlayerstyle"],
    "rule_based_symbology": ["native:rulebasedrenderer"],
    "heatmap_symbology": ["native:heatmaprenderer"],
    "point_displacement": ["native:pointdisplacement"],
    "labeling": ["native:setlabel", "native:labeling"],
    "label_placement": ["native:labelplacement", "native:labeling"],
    "create_legend": ["native:addlegend", "native:layoutlegend"],
    "create_scalebar": ["native:addscalebar", "native:layoutscalebar"],
    "create_north_arrow": ["native:addnortharrow", "native:layoutnortharrow"],
    "atlas_generation": ["native:atlas", "native:printlayoutatlas"],
    "map_series": ["native:mapseries", "native:atlas"],
    "layout_template": ["native:layoutfromtemplate", "native:loadlayouttemplate"],
    "export_atlas": ["native:exportatlas", "native:printlayoutatlas"],
    "overview_map": ["native:addoverview", "native:layoutoverview"],
    "grid_graticule": ["native:addgrid", "native:layoutgrid"],
    "map_annotation": ["native:addannotation", "native:layoutannotation"],
}


class M18Cartography(ClusterBase):
    CLUSTER_ID = "M18"
    CLUSTER_NAME = "Cartography"
    OPERATIONS = {k: f"Cartography {k}" for k in _ALGO_MAP}

    def execute(self, operation: str, params: dict) -> ClusterResult:
        patterns = _ALGO_MAP.get(operation)
        if not patterns:
            return ClusterResult(operation, False, "FAILED", {},
                                 error=f"Unknown operation: {operation}")
        algo = self.discover_algorithm(patterns)
        if not algo:
            return ClusterResult(operation, False, "FAILED", {},
                                 error=f"No processing algorithm found for {operation}")
        try:
            result = self.run_algorithm(algo, params.get("parameters", {}))
            return ClusterResult(operation, True, "SUCCESS",
                                 {"algorithm": algo, "outputs": result.get("outputs", {})})
        except Exception as exc:
            return ClusterResult(operation, False, "FAILED", {},
                                 error=str(exc))


def create_handler(executor):
    return M18Cartography(executor)