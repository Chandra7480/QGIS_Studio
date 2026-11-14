"""Universal AI GIS Studio — MCP Tool Registry.

Defines every MCP tool as a typed ToolSpec: name, namespace, description,
strict input/output JSON schemas, permission requirements, timeout, and
verification rules. The registry is the single source of truth for what
the MCP server exposes.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolSpec:
    name: str                      # e.g. "qgis.system.inspect"
    namespace: str                 # e.g. "qgis.system"
    description: str
    input_schema: dict             # JSON Schema (strict)
    output_schema: dict            # JSON Schema
    permissions: list[str] = field(default_factory=list)
    timeout_seconds: int = 300
    require_approval: bool = False
    verification_rules: list[str] = field(default_factory=list)

    def to_mcp_tool(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def all(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return sorted(self._tools.keys())

    def namespaces(self) -> list[str]:
        return sorted({t.namespace for t in self._tools.values()})


# --------------------------------------------------------------------------- #
# Common schema fragments
# --------------------------------------------------------------------------- #
_STR = {"type": "string"}
_OBJ = {"type": "object"}
_ARR = {"type": "array"}


def _str_prop(desc: str = "value") -> dict:
    return {"type": "string", "description": desc}


def _bool_prop(desc: str = "value") -> dict:
    return {"type": "boolean", "description": desc}


def _int_prop(desc: str = "value") -> dict:
    return {"type": "integer", "description": desc}


def _num_prop(desc: str = "value") -> dict:
    return {"type": "number", "description": desc}


def _list_prop(desc: str = "value", item_type: str = "string") -> dict:
    return {"type": "array", "description": desc, "items": {"type": item_type}}


def base_input(required: list[str] | None = None, properties: dict | None = None) -> dict:
    props = properties or {}
    req = required or []
    return {
        "type": "object",
        "properties": props,
        "required": req,
        "additionalProperties": False,
    }


def base_output(props: dict) -> dict:
    return {
        "type": "object",
        "properties": props,
        "additionalProperties": False,
    }


# --------------------------------------------------------------------------- #
# Tool specifications (all qgis.* namespaces)
# --------------------------------------------------------------------------- #
def build_registry() -> ToolRegistry:
    r = ToolRegistry()

    def add(name, namespace, description, input_spec, output_spec,
            permissions=None, timeout=300, approval=False, verification=None):
        r.register(ToolSpec(
            name=name, namespace=namespace, description=description,
            input_schema=input_spec, output_schema=output_spec,
            permissions=permissions or [], timeout_seconds=timeout,
            require_approval=approval,
            verification_rules=verification or [],
        ))

    # ---- qgis.system ----
    add(
        "qgis.system.inspect", "qgis.system",
        "Inspect the QGIS installation: version, GDAL version, Python version, bridge status.",
        base_input(),
        base_output({"qgis_version": _str_prop("QGIS version"),
                     "gdal_version": _str_prop("GDAL version"),
                     "python_version": _str_prop("Python version"),
                     "bridge_connected": _bool_prop("Whether the bridge is connected")}),
        permissions=["qgis:read"],
    )
    add(
        "qgis.system.health", "qgis.system",
        "Check health of the QGIS Bridge and active QGIS instance.",
        base_input(),
        base_output({"qgis_connected": _bool_prop("value"),
                     "project_open": _bool_prop("value"),
                     "layer_count": _int_prop("Number of loaded layers"),
                     "main_thread": _bool_prop("main thread")}),
        permissions=["qgis:read"],
    )

    # ---- qgis.project ----
    add(
        "qgis.project.open", "qgis.project",
        "Open a QGIS project file (.qgz/.qgs).",
        base_input(required=["path"], properties={"path": _str_prop("Path to the project file")}),
        base_output({"project_file": _str_prop(),
                     "project_title": _str_prop(),
                     "crs": _str_prop(),
                     "layer_count": _int_prop()}),
        permissions=["qgis:project:write"],
        approval=True,
        verification=["file_exists", "project_valid"],
    )
    add(
        "qgis.project.save", "qgis.project",
        "Save the current QGIS project.",
        base_input(properties={"path": _str_prop("Optional path to save to")}),
        base_output({"saved": _bool_prop("value"), "project_file": _str_prop()}),
        permissions=["qgis:project:write"],
        approval=False,
        verification=["file_written"],
    )
    add(
        "qgis.project.inspect", "qgis.project",
        "Inspect the current QGIS project: metadata, CRS, layers.",
        base_input(),
        base_output({"project_file": _str_prop(),
                     "project_title": _str_prop(),
                     "crs": _str_prop(),
                     "layer_count": _int_prop(),
                     "layers": _list_prop("layers")}),
        permissions=["qgis:read"],
    )

    # ---- qgis.layers ----
    add(
        "qgis.layers.inspect", "qgis.layers",
        "Inspect all loaded layers: id, name, type, validity, CRS, extent, fields.",
        base_input(),
        base_output({"layers": _list_prop("layer list"),
                     "count": _int_prop()}),
        permissions=["qgis:read"],
    )
    add(
        "qgis.layers.load", "qgis.layers",
        "Load a GIS dataset (vector or raster) into the project.",
        base_input(required=["path"], properties={
            "path": _str_prop("File path to load"),
            "layer_name": _str_prop("Optional layer name"),
            "provider": _str_prop("Provider hint: vector|raster"),
        }),
        base_output({"id": _str_prop(), "name": _str_prop(),
                     "type": _str_prop(), "valid": _bool_prop("value"), "crs": _str_prop()}),
        permissions=["qgis:layer:write"],
        approval=False,
        verification=["file_exists", "layer_valid"],
    )
    add(
        "qgis.layers.remove", "qgis.layers",
        "Remove a layer from the project by layer id.",
        base_input(required=["layer_id"], properties={"layer_id": _str_prop("Layer id to remove")}),
        base_output({"removed": _bool_prop("value"), "id": _str_prop()}),
        permissions=["qgis:layer:write"],
        approval=True,
        verification=["layer_removed"],
    )

    # ---- qgis.canvas ----
    add(
        "qgis.canvas.inspect", "qgis.canvas",
        "Inspect the map canvas: extent, CRS, scale, rotation, visible layers.",
        base_input(),
        base_output({"extent": _list_prop("canvas extent", "number"),
                     "crs": _str_prop(), "scale": _num_prop(),
                     "rotation": _num_prop(), "layers": _list_prop("layer ids")}),
        permissions=["qgis:read"],
    )

    # ---- qgis.screen ----
    add(
        "qgis.screen.capture", "qgis.screen",
        "Capture a screenshot of the QGIS map canvas. Returns PNG as base64.",
        base_input(),
        base_output({"image_base64": _str_prop("PNG base64"),
                     "width": _int_prop(), "height": _int_prop(),
                     "format": _str_prop()}),
        permissions=["qgis:screen:read"],
    )

    # ---- qgis.cursor ----
    for tool, desc, pname in [
        ("qgis.cursor.move", "Move the AI cursor to a screen position.", [("x", _int_prop("Screen X")), ("y", _int_prop("Screen Y"))]),
        ("qgis.cursor.click", "Click at the current AI cursor position.", []),
        ("qgis.cursor.drag", "Drag from one screen position to another.", [("x1", _int_prop("Start X")), ("y1", _int_prop("Start Y")), ("x2", _int_prop("End X")), ("y2", _int_prop("End Y"))]),
    ]:
        props = {n: p for n, p in pname}
        add(tool, "qgis.cursor", desc,
            base_input(required=[n for n, _ in pname], properties=props),
            base_output({"ok": _bool_prop("main thread")}),
            permissions=["qgis:cursor:write"],
        )

    # ---- qgis.keyboard ----
    add(
        "qgis.keyboard.type", "qgis.keyboard",
        "Type text into the focused QGIS control.",
        base_input(required=["text"], properties={"text": _str_prop("Text to type")}),
        base_output({"ok": _bool_prop("main thread")}),
        permissions=["qgis:keyboard:write"],
    )
    add(
        "qgis.keyboard.hotkey", "qgis.keyboard",
        "Press a keyboard shortcut (comma-separated keys).",
        base_input(required=["keys"], properties={"keys": _str_prop("Keys, e.g. ctrl,s")}),
        base_output({"ok": _bool_prop("main thread")}),
        permissions=["qgis:keyboard:write"],
    )

    # ---- qgis.mouse ----
    add(
        "qgis.mouse.scroll", "qgis.mouse",
        "Scroll the mouse wheel at the current position.",
        base_input(properties={"delta": _int_prop("Scroll delta")}),
        base_output({"ok": _bool_prop("main thread")}),
        permissions=["qgis:mouse:write"],
    )

    # ---- qgis.window / qgis.dialog ----
    add(
        "qgis.window.inspect", "qgis.window",
        "Inspect the QGIS main window: title, size, state.",
        base_input(),
        base_output({"title": _str_prop(), "size": _list_prop("size", "number")}),
        permissions=["qgis:read"],
    )
    add(
        "qgis.dialog.inspect", "qgis.dialog",
        "Inspect open QGIS dialogs.",
        base_input(),
        base_output({"dialogs": _list_prop("open dialogs")}),
        permissions=["qgis:read"],
    )

    # ---- qgis.algorithms ----
    add(
        "qgis.algorithms.discover", "qgis.algorithms",
        "Discover installed QGIS Processing algorithms (dynamic, version-aware).",
        base_input(),
        base_output({"algorithms": _list_prop("algorithms"), "count": _int_prop()}),
        permissions=["qgis:read"],
    )
    add(
        "qgis.algorithms.execute", "qgis.algorithms",
        "Execute a QGIS Processing algorithm by id with parameters.",
        base_input(required=["algorithm"], properties={
            "algorithm": _str_prop("Algorithm id, e.g. native:buffer"),
            "parameters": {"type": "object", "description": "Algorithm parameters"},
        }),
        base_output({"outputs": {"type": "object"}, "algorithm": _str_prop()}),
        permissions=["qgis:algorithm:execute"],
        approval=False,
        verification=["output_exists", "output_valid"],
    )

    # ---- qgis.georeferencing / qgis.gcp ----
    add(
        "qgis.georeference.analyze", "qgis.georeference",
        "Analyze an image for georeferencing: dimensions, quality, landmarks, rotation.",
        base_input(required=["image_path"], properties={"image_path": _str_prop("Path to the scanned map image")}),
        base_output({"dimensions": _list_prop("dimensions", "number"),
                     "quality_score": _num_prop(),
                     "landmarks": _list_prop("landmarks"),
                     "rotation": _num_prop()}),
        permissions=["qgis:georeference:read"],
    )
    add(
        "qgis.gcp.generate", "qgis.gcp",
        "Generate candidate Ground Control Points from image + reference data.",
        base_input(required=["image_path"], properties={
            "image_path": _str_prop(),
            "reference_source": _str_prop("Reference raster or dataset"),
        }),
        base_output({"gcps": _list_prop("gcp candidates"),
                     "count": _int_prop()}),
        permissions=["qgis:gcp:write"],
        verification=["confidence_scored", "outliers_rejected"],
    )
    add(
        "qgis.gcp.validate", "qgis.gcp",
        "Validate candidate GCPs: duplicates, outliers, distribution, residuals.",
        base_input(required=["gcps"], properties={"gcps": _list_prop("gcps")}),
        base_output({"valid_gcps": _list_prop(), "rmse": _num_prop(),
                     "rejected": _list_prop()}),
        permissions=["qgis:gcp:write"],
        verification=["min_point_count", "residuals_checked"],
    )

    # ---- qgis.raster / qgis.vector / qgis.spatial ----
    # These are namespace markers. Individual raster/vector/spatial operations
    # are executed via qgis.algorithms.execute with dynamic algorithm discovery.
    # TODO: Implement dedicated tools when cluster handlers are wired to bridge.
    add(
        "qgis.raster.info", "qgis.raster",
        "Get raster layer information (bands, dimensions, CRS, extent).",
        base_input(required=["layer_id"], properties={"layer_id": _str_prop("Raster layer id")}),
        base_output({"bands": _int_prop(), "width": _int_prop(),
                     "height": _int_prop(), "crs": _str_prop(), "extent": _list_prop("extent", "number")}),
        permissions=["qgis:raster:read"],
    )

    # ---- qgis.raster (25 tools) ----
    add(
        "qgis.raster.calculator", "qgis.raster",
        "Raster calculator with expression (e.g., 'A * 2 + B').",
        base_input(required=["layers", "expression"], properties={
            "layers": _list_prop("Input raster layer ids (A, B, C...)", "string"),
            "expression": _str_prop("Expression using A, B, C... (e.g., 'A * 2 + B')"),
            "reference_layer": _str_prop("Optional reference layer for extent/CRS"),
            "cellsize": _num_prop("Output cell size (0 = use reference)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "bands_computed"],
    )
    add(
        "qgis.raster.reclassify", "qgis.raster",
        "Reclassify raster values by table or ranges.",
        base_input(required=["layer_id", "reclass_table"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "reclass_table": _list_prop("Reclass table: [[min, max, new_val], ...]", "array"),
            "nodata_for_missing": _bool_prop("NoData for missing values (default: true)"),
            "range_boundaries": _str_prop("Boundaries: min|max|min_max (default: min_max)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "values_reclassified"],
    )
    add(
        "qgis.raster.mosaic", "qgis.raster",
        "Mosaic/merge multiple raster layers into one.",
        base_input(required=["layer_ids"], properties={
            "layer_ids": _list_prop("List of raster layer ids to mosaic", "string"),
            "method": _str_prop("Overlap method: first|last|min|max|mean (default: first)"),
            "nodata_value": _num_prop("NoData value for output"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "layers_merged"],
    )
    add(
        "qgis.raster.clip", "qgis.raster",
        "Clip raster by mask layer (vector polygon).",
        base_input(required=["layer_id", "mask_layer_id"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "mask_layer_id": _str_prop("Mask vector layer id (polygon)"),
            "nodata_value": _num_prop("NoData value for clipped areas"),
            "keep_resolution": _bool_prop("Keep input resolution (default: true)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "raster_clipped"],
    )
    add(
        "qgis.raster.resample", "qgis.raster",
        "Resample raster to different resolution/CRS.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "target_resolution": _num_prop("Target resolution (cell size)"),
            "method": _str_prop("Resampling: nearest|bilinear|cubic|cubicspline|lanczos (default: bilinear)"),
            "target_crs": _str_prop("Optional target CRS"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "resolution_changed"],
    )
    add(
        "qgis.raster.convert", "qgis.raster",
        "Convert raster format (GeoTIFF, COG, etc.).",
        base_input(required=["layer_id", "format"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "format": _str_prop("Output format: GTiff|COG|AAIGrid|JPEG|PNG|etc"),
            "options": _list_prop("GDAL creation options (e.g., COMPRESS=DEFLATE)", "string"),
            "output_path": _str_prop("Output file path"),
        }),
        base_output({"output_path": _str_prop(), "format": _str_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "file_written", "format_valid"],
    )
    add(
        "qgis.raster.band_ops", "qgis.raster",
        "Band operations: extract, reorder, math between bands.",
        base_input(required=["layer_id", "operation"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "operation": _str_prop("Operation: extract|reorder|math|stack"),
            "bands": _list_prop("Band indices for operation", "integer"),
            "expression": _str_prop("Math expression for 'math' operation"),
            "other_layers": _list_prop("Other layer ids for stacking", "string"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "band_count": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "bands_processed"],
    )
    add(
        "qgis.raster.hillshade", "qgis.raster",
        "Generate hillshade from DEM.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input DEM raster layer id"),
            "z_factor": _num_prop("Vertical exaggeration factor (default: 1.0)"),
            "azimuth": _num_prop("Light azimuth in degrees (default: 315)"),
            "altitude": _num_prop("Light altitude in degrees (default: 45)"),
            "combined": _bool_prop("Combined shading (default: false)"),
            "multidirectional": _bool_prop("Multidirectional (default: false)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "hillshade_generated"],
    )
    add(
        "qgis.raster.slope", "qgis.raster",
        "Calculate slope from DEM (degrees or percent).",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input DEM raster layer id"),
            "z_factor": _num_prop("Vertical exaggeration factor (default: 1.0)"),
            "as_percent": _bool_prop("Output as percent instead of degrees (default: false)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "slope_computed"],
    )
    add(
        "qgis.raster.aspect", "qgis.raster",
        "Calculate aspect from DEM (direction of slope).",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input DEM raster layer id"),
            "z_factor": _num_prop("Vertical exaggeration factor (default: 1.0)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "aspect_computed"],
    )
    add(
        "qgis.raster.roughness", "qgis.raster",
        "Calculate terrain roughness index (TRI).",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input DEM raster layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "roughness_computed"],
    )
    add(
        "qgis.raster.tpi", "qgis.raster",
        "Calculate Topographic Position Index (TPI).",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input DEM raster layer id"),
            "radius": _int_prop("Neighborhood radius in cells (default: 1)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "tpi_computed"],
    )
    add(
        "qgis.raster.curvature", "qgis.raster",
        "Calculate curvature (profile, plan, total).",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input DEM raster layer id"),
            "z_factor": _num_prop("Vertical exaggeration factor (default: 1.0)"),
            "curvature_type": _str_prop("Type: profile|plan|total (default: total)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "curvature_computed"],
    )
    add(
        "qgis.raster.zonal_stats", "qgis.raster",
        "Calculate zonal statistics (mean, sum, count, min, max, std) for zones.",
        base_input(required=["raster_layer_id", "zone_layer_id"], properties={
            "raster_layer_id": _str_prop("Input raster layer id"),
            "zone_layer_id": _str_prop("Zone vector layer id (polygon)"),
            "zone_field": _str_prop("Zone field name (optional)"),
            "stats": _list_prop("Statistics: mean|sum|count|min|max|std|median|majority|minority", "string"),
            "output_layer": _str_prop("Optional output layer name (vector with stats)"),
        }),
        base_output({"output_layer_id": _str_prop(), "statistics": {"type": "object"}, "zone_count": _int_prop()}),
        permissions=["qgis:raster:read"],
        verification=["output_exists", "statistics_computed"],
    )
    add(
        "qgis.raster.zonal_histogram", "qgis.raster",
        "Calculate histogram of raster values per zone.",
        base_input(required=["raster_layer_id", "zone_layer_id"], properties={
            "raster_layer_id": _str_prop("Input raster layer id"),
            "zone_layer_id": _str_prop("Zone vector layer id (polygon)"),
            "zone_field": _str_prop("Zone field name (optional)"),
            "bin_width": _num_prop("Histogram bin width (default: 1)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "histograms": {"type": "object"}, "zone_count": _int_prop()}),
        permissions=["qgis:raster:read"],
        verification=["output_exists", "histograms_computed"],
    )
    add(
        "qgis.raster.proximity", "qgis.raster",
        "Calculate proximity (distance) to target values.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "target_values": _list_prop("Target pixel values to compute distance from", "number"),
            "max_distance": _num_prop("Maximum distance (default: 0 = unlimited)"),
            "units": _str_prop("Units: GEO|PIXEL (default: GEO)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "proximity_computed"],
    )
    add(
        "qgis.raster.sieve", "qgis.raster",
        "Remove small raster polygons (sieve filter).",
        base_input(required=["layer_id", "threshold"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "threshold": _int_prop("Minimum polygon size (pixels)"),
            "connectedness": _int_prop("Connectedness: 4|8 (default: 8)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "small_polygons_removed"],
    )
    add(
        "qgis.raster.polygonize", "qgis.raster",
        "Convert raster to vector polygons (raster to vector).",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "band": _int_prop("Band to polygonize (default: 1)"),
            "field_name": _str_prop("Field name for pixel values (default: DN)"),
            "eight_connected": _bool_prop("8-connected (default: false)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "polygons_created"],
    )
    add(
        "qgis.raster.fill_nodata", "qgis.raster",
        "Fill NoData areas by interpolation.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "max_distance": _num_prop("Maximum interpolation distance (default: 100)"),
            "iterations": _int_prop("Number of iterations (default: 0 = until filled)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "nodata_filled"],
    )
    add(
        "qgis.raster.warp", "qgis.raster",
        "Warp/reproject raster to new CRS/resolution.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "target_crs": _str_prop("Target CRS (e.g., EPSG:4326)"),
            "resampling": _str_prop("Resampling: nearest|bilinear|cubic|cubicspline|lanczos (default: bilinear)"),
            "target_resolution": _num_prop("Optional target resolution"),
            "target_extent": _list_prop("Optional target extent [xmin, ymin, xmax, ymax]", "number"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "crs": _str_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "crs_transformed"],
    )
    add(
        "qgis.raster.clip_extent", "qgis.raster",
        "Clip raster to extent [xmin, ymin, xmax, ymax].",
        base_input(required=["layer_id", "extent"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "extent": _list_prop("Extent [xmin, ymin, xmax, ymax]", "number"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "extent_clipped"],
    )
    add(
        "qgis.raster.translate", "qgis.raster",
        "Translate/convert raster with options (compression, tiles, etc.).",
        base_input(required=["layer_id", "output_path"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "output_path": _str_prop("Output file path"),
            "format": _str_prop("Output format (default: GTiff)"),
            "options": _list_prop("GDAL creation options", "string"),
            "band_list": _list_prop("Bands to copy (default: all)", "integer"),
            "scale_params": _list_prop("Scale params [[src_min, src_max, dst_min, dst_max]]", "array"),
        }),
        base_output({"output_path": _str_prop(), "width": _int_prop(), "height": _int_prop(), "band_count": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["file_exists", "output_valid", "format_valid"],
    )
    add(
        "qgis.raster.contour", "qgis.raster",
        "Generate contour lines from raster.",
        base_input(required=["layer_id", "interval"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "interval": _num_prop("Contour interval"),
            "offset": _num_prop("Contour offset (default: 0)"),
            "field_name": _str_prop("Attribute field name (default: ELEV)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "contours_generated"],
    )
    add(
        "qgis.raster.rgb_to_pct", "qgis.raster",
        "Convert RGB raster to paletted (color table).",
        base_input(required=["layer_id", "ncolors"], properties={
            "layer_id": _str_prop("Input RGB raster layer id"),
            "ncolors": _int_prop("Number of colors in palette (2-256)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "palette": _list_prop("palette", "integer")}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "palette_created"],
    )
    add(
        "qgis.raster.pct_to_rgb", "qgis.raster",
        "Convert paletted raster to RGB.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input paletted raster layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "band_count": _int_prop()}),
        permissions=["qgis:raster:write"],
        verification=["output_exists", "output_valid", "rgb_created"],
    )

    add(
        "qgis.vector.info", "qgis.vector",
        "Get vector layer information (feature count, fields, CRS, extent, geometry type).",
        base_input(required=["layer_id"], properties={"layer_id": _str_prop("Vector layer id")}),
        base_output({"feature_count": _int_prop(), "fields": _list_prop("field names"),
                     "crs": _str_prop(), "extent": _list_prop("extent", "number"),
                     "geometry_type": _str_prop()}),
        permissions=["qgis:vector:read"],
    )

    # ---- qgis.vector (25 tools) ----
    add(
        "qgis.vector.buffer", "qgis.vector",
        "Create buffer zones around features by distance.",
        base_input(required=["layer_id", "distance"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "distance": _num_prop("Buffer distance in layer units"),
            "segments": _int_prop("Number of segments for curves (default: 5)"),
            "end_cap_style": _str_prop("End cap style: round|flat|square (default: round)"),
            "join_style": _str_prop("Join style: round|miter|bevel (default: round)"),
            "miter_limit": _num_prop("Miter limit for miter joins (default: 2.0)"),
            "dissolve": _bool_prop("Dissolve result (default: false)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "geometry_type_preserved"],
    )
    add(
        "qgis.vector.clip", "qgis.vector",
        "Clip a vector layer by an overlay layer.",
        base_input(required=["layer_id", "overlay_layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "overlay_layer_id": _str_prop("Overlay (clip) layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "features_clipped"],
    )
    add(
        "qgis.vector.dissolve", "qgis.vector",
        "Dissolve features by attribute or dissolve all.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "field": _str_prop("Optional field to dissolve by (if omitted, dissolve all)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "features_dissolved"],
    )
    add(
        "qgis.vector.intersection", "qgis.vector",
        "Intersect two vector layers (overlay analysis).",
        base_input(required=["layer_id", "overlay_layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "overlay_layer_id": _str_prop("Overlay layer id"),
            "input_fields": _list_prop("Input fields to keep", "string"),
            "overlay_fields": _list_prop("Overlay fields to keep", "string"),
            "overlay_fields_prefix": _str_prop("Prefix for overlay fields"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "intersection_computed"],
    )
    add(
        "qgis.vector.union", "qgis.vector",
        "Union two vector layers (overlay analysis).",
        base_input(required=["layer_id", "overlay_layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "overlay_layer_id": _str_prop("Overlay layer id"),
            "overlay_fields_prefix": _str_prop("Prefix for overlay fields"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "union_computed"],
    )
    add(
        "qgis.vector.difference", "qgis.vector",
        "Difference between two vector layers (input - overlay).",
        base_input(required=["layer_id", "overlay_layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "overlay_layer_id": _str_prop("Overlay layer id to subtract"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "difference_computed"],
    )
    add(
        "qgis.vector.merge", "qgis.vector",
        "Merge multiple vector layers into one.",
        base_input(required=["layer_ids"], properties={
            "layer_ids": _list_prop("List of layer ids to merge", "string"),
            "crs": _str_prop("Optional target CRS (defaults to first layer CRS)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "layers_merged"],
    )
    add(
        "qgis.vector.repair", "qgis.vector",
        "Repair/fix invalid geometries in a vector layer.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "method": _str_prop("Repair method: structure|linework (default: linework)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop(), "fixed_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "geometries_fixed"],
    )
    add(
        "qgis.vector.split", "qgis.vector",
        "Split features by maximum distance or other criteria.",
        base_input(required=["layer_id", "max_length"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "max_length": _num_prop("Maximum segment length"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "features_split"],
    )
    add(
        "qgis.vector.centroids", "qgis.vector",
        "Calculate centroids of features.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "all_parts": _bool_prop("Centroid for each part of multipart (default: false)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "centroids_computed"],
    )
    add(
        "qgis.vector.convex_hull", "qgis.vector",
        "Generate convex hull(s) of features.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "per_feature": _bool_prop("Hull per feature vs single hull for all (default: false)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "hull_computed"],
    )
    add(
        "qgis.vector.bounds", "qgis.vector",
        "Generate bounding boxes of features.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "bounds_computed"],
    )
    add(
        "qgis.vector.envelope", "qgis.vector",
        "Generate envelope (rectangular bounds) of features.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "per_feature": _bool_prop("Envelope per feature vs single envelope (default: false)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "envelope_computed"],
    )
    add(
        "qgis.vector.simplify", "qgis.vector",
        "Simplify geometries by tolerance (Douglas-Peucker).",
        base_input(required=["layer_id", "tolerance"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "tolerance": _num_prop("Simplification tolerance in layer units"),
            "method": _str_prop("Method: douglas|visvalingam|snapping (default: douglas)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "geometries_simplified"],
    )
    add(
        "qgis.vector.smooth", "qgis.vector",
        "Smooth geometries by iterations and offset.",
        base_input(required=["layer_id", "iterations", "offset"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "iterations": _int_prop("Number of smoothing iterations"),
            "offset": _num_prop("Offset distance"),
            "max_angle": _num_prop("Maximum angle (degrees) for smoothing"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "geometries_smoothed"],
    )
    add(
        "qgis.vector.offset", "qgis.vector",
        "Offset line geometries by distance.",
        base_input(required=["layer_id", "distance"], properties={
            "layer_id": _str_prop("Input vector layer id (line geometry)"),
            "distance": _num_prop("Offset distance (positive = left, negative = right)"),
            "segments": _int_prop("Segments for curves (default: 8)"),
            "join_style": _str_prop("Join style: round|miter|bevel (default: round)"),
            "miter_limit": _num_prop("Miter limit (default: 2.0)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "offset_computed"],
    )
    add(
        "qgis.vector.polygonize", "qgis.vector",
        "Polygonize line geometries forming closed rings.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id (line geometry)"),
            "keep_fields": _bool_prop("Keep input fields (default: true)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "polygons_created"],
    )
    add(
        "qgis.vector.lines_to_polygons", "qgis.vector",
        "Convert lines to polygons by closing rings.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id (line geometry)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "polygons_created"],
    )
    add(
        "qgis.vector.polygons_to_lines", "qgis.vector",
        "Convert polygons to lines (boundaries).",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id (polygon geometry)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "lines_created"],
    )
    add(
        "qgis.vector.multipart_to_singlepart", "qgis.vector",
        "Convert multipart features to singlepart features.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "multipart_split"],
    )
    add(
        "qgis.vector.singlepart_to_multipart", "qgis.vector",
        "Convert singlepart features to multipart by attribute.",
        base_input(required=["layer_id", "field"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "field": _str_prop("Field to group by for multipart creation"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "multipart_created"],
    )
    add(
        "qgis.vector.extract_vertices", "qgis.vector",
        "Extract vertices from geometries as point features.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "vertices_extracted"],
    )
    add(
        "qgis.vector.add_geometry_attributes", "qgis.vector",
        "Add geometry attributes (area, length, perimeter, etc.) to features.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "calculate_area": _bool_prop("Calculate area (default: true)"),
            "calculate_length": _bool_prop("Calculate length (default: true)"),
            "calculate_perimeter": _bool_prop("Calculate perimeter (default: true)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop(), "fields_added": _list_prop("added field names", "string")}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "attributes_added"],
    )
    add(
        "qgis.vector.drop_m_z", "qgis.vector",
        "Drop M and/or Z values from geometries.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "drop_m": _bool_prop("Drop M values (default: true)"),
            "drop_z": _bool_prop("Drop Z values (default: true)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "m_z_dropped"],
    )
    add(
        "qgis.vector.set_m_z", "qgis.vector",
        "Set M and/or Z values on geometries from field or constant.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "m_field": _str_prop("Optional field for M values"),
            "z_field": _str_prop("Optional field for Z values"),
            "m_value": _num_prop("Constant M value if no field"),
            "z_value": _num_prop("Constant Z value if no field"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:vector:write"],
        verification=["output_exists", "output_valid", "m_z_set"],
    )

    add(
        "qgis.spatial.info", "qgis.spatial",
        "Get available spatial analysis algorithms and their parameters.",
        base_input(),
        base_output({"algorithms": _list_prop("spatial algorithms"), "count": _int_prop()}),
        permissions=["qgis:spatial:read"],
    )

    # ---- qgis.spatial (20 tools) ----
    add(
        "qgis.spatial.join_attributes_by_location", "qgis.spatial",
        "Join attributes from one layer to another by spatial relationship.",
        base_input(required=["input_layer", "join_layer"], properties={
            "input_layer": _str_prop("Input vector layer id"),
            "join_layer": _str_prop("Join vector layer id"),
            "predicate": _list_prop("Spatial predicates: intersects|contains|within|touches|overlaps|crosses", "string"),
            "join_fields": _list_prop("Fields to join (default: all)", "string"),
            "method": _str_prop("Join method: one-to-one|one-to-many (default: one-to-many)"),
            "discard_nonmatching": _bool_prop("Discard non-matching features (default: false)"),
            "prefix": _str_prop("Prefix for joined field names"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop(), "joined_fields": _list_prop("field names", "string")}),
        permissions=["qgis:spatial:write"],
        verification=["output_exists", "output_valid", "attributes_joined"],
    )
    add(
        "qgis.spatial.join_attributes_by_nearest", "qgis.spatial",
        "Join attributes by nearest feature distance.",
        base_input(required=["input_layer", "join_layer"], properties={
            "input_layer": _str_prop("Input vector layer id"),
            "join_layer": _str_prop("Join vector layer id"),
            "max_distance": _num_prop("Maximum search distance"),
            "k": _int_prop("Number of nearest neighbors (default: 1)"),
            "join_fields": _list_prop("Fields to join (default: all)", "string"),
            "prefix": _str_prop("Prefix for joined field names"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:spatial:write"],
        verification=["output_exists", "output_valid", "nearest_joined"],
    )
    add(
        "qgis.spatial.join_attributes_by_field_value", "qgis.spatial",
        "Join attributes by matching field values (non-spatial).",
        base_input(required=["input_layer", "join_layer", "input_field", "join_field"], properties={
            "input_layer": _str_prop("Input vector layer id"),
            "join_layer": _str_prop("Join vector layer id"),
            "input_field": _str_prop("Field in input layer"),
            "join_field": _str_prop("Field in join layer"),
            "join_fields": _list_prop("Fields to join (default: all)", "string"),
            "method": _str_prop("Join method: one-to-one|one-to-many (default: one-to-many)"),
            "discard_nonmatching": _bool_prop("Discard non-matching features (default: false)"),
            "prefix": _str_prop("Prefix for joined field names"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:spatial:write"],
        verification=["output_exists", "output_valid", "attributes_joined"],
    )
    add(
        "qgis.spatial.distance_matrix", "qgis.spatial",
        "Calculate distance matrix between points.",
        base_input(required=["input_layer", "target_layer"], properties={
            "input_layer": _str_prop("Input point layer id"),
            "target_layer": _str_prop("Target point layer id"),
            "unique_field": _str_prop("Unique ID field in input layer"),
            "target_field": _str_prop("Unique ID field in target layer"),
            "output_type": _str_prop("Output: matrix|list|summary (default: matrix)"),
            "nearest_only": _int_prop("Number of nearest features (0 = all)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "distances": {"type": "object"}}),
        permissions=["qgis:spatial:read"],
        verification=["output_exists", "distances_computed"],
    )
    add(
        "qgis.spatial.nearest_neighbor", "qgis.spatial",
        "Find k nearest neighbors for each feature.",
        base_input(required=["input_layer", "k"], properties={
            "input_layer": _str_prop("Input vector layer id"),
            "k": _int_prop("Number of nearest neighbors"),
            "target_layer": _str_prop("Optional target layer (default: same as input)"),
            "max_distance": _num_prop("Optional maximum distance"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:spatial:read"],
        verification=["output_exists", "neighbors_found"],
    )
    add(
        "qgis.spatial.point_distance", "qgis.spatial",
        "Calculate distance from points to nearest feature in another layer.",
        base_input(required=["points_layer", "target_layer"], properties={
            "points_layer": _str_prop("Input point layer id"),
            "target_layer": _str_prop("Target vector layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:spatial:read"],
        verification=["output_exists", "distances_computed"],
    )
    add(
        "qgis.spatial.intersection", "qgis.spatial",
        "Intersect two vector layers (overlay analysis).",
        base_input(required=["input_layer", "overlay_layer"], properties={
            "input_layer": _str_prop("Input vector layer id"),
            "overlay_layer": _str_prop("Overlay vector layer id"),
            "input_fields": _list_prop("Input fields to keep", "string"),
            "overlay_fields": _list_prop("Overlay fields to keep", "string"),
            "overlay_fields_prefix": _str_prop("Prefix for overlay fields"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:spatial:write"],
        verification=["output_exists", "output_valid", "intersection_computed"],
    )
    add(
        "qgis.spatial.union", "qgis.spatial",
        "Union two vector layers (overlay analysis).",
        base_input(required=["input_layer", "overlay_layer"], properties={
            "input_layer": _str_prop("Input vector layer id"),
            "overlay_layer": _str_prop("Overlay vector layer id"),
            "overlay_fields_prefix": _str_prop("Prefix for overlay fields"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:spatial:write"],
        verification=["output_exists", "output_valid", "union_computed"],
    )
    add(
        "qgis.spatial.difference", "qgis.spatial",
        "Difference between two vector layers (input - overlay).",
        base_input(required=["input_layer", "overlay_layer"], properties={
            "input_layer": _str_prop("Input vector layer id"),
            "overlay_layer": _str_prop("Overlay vector layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:spatial:write"],
        verification=["output_exists", "output_valid", "difference_computed"],
    )
    add(
        "qgis.spatial.symmetrical_difference", "qgis.spatial",
        "Symmetrical difference (XOR) between two layers.",
        base_input(required=["input_layer", "overlay_layer"], properties={
            "input_layer": _str_prop("Input vector layer id"),
            "overlay_layer": _str_prop("Overlay vector layer id"),
            "overlay_fields_prefix": _str_prop("Prefix for overlay fields"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:spatial:write"],
        verification=["output_exists", "output_valid", "symdiff_computed"],
    )
    add(
        "qgis.spatial.clip", "qgis.spatial",
        "Clip input layer by overlay layer.",
        base_input(required=["input_layer", "overlay_layer"], properties={
            "input_layer": _str_prop("Input vector layer id"),
            "overlay_layer": _str_prop("Overlay (clip) layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:spatial:write"],
        verification=["output_exists", "output_valid", "clip_computed"],
    )
    add(
        "qgis.spatial.count_points_in_polygon", "qgis.spatial",
        "Count points within polygons.",
        base_input(required=["polygons_layer", "points_layer"], properties={
            "polygons_layer": _str_prop("Polygon vector layer id"),
            "points_layer": _str_prop("Point vector layer id"),
            "weight_field": _str_prop("Optional weight field in points layer"),
            "class_field": _str_prop("Optional class field in points layer"),
            "output_field": _str_prop("Output field name for count (default: POINT_COUNT)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:spatial:write"],
        verification=["output_exists", "points_counted"],
    )
    add(
        "qgis.spatial.heatmap", "qgis.spatial",
        "Generate kernel density heatmap from points.",
        base_input(required=["points_layer"], properties={
            "points_layer": _str_prop("Input point layer id"),
            "radius": _num_prop("Search radius (map units)"),
            "pixels": _num_prop("Cell size for output raster"),
            "kernel": _str_prop("Kernel: quartic|triangular|uniform|triweight|epanechnikov (default: quartic)"),
            "weight_field": _str_prop("Optional weight field"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:spatial:write"],
        verification=["output_exists", "output_valid", "heatmap_generated"],
    )
    add(
        "qgis.spatial.kmeans_clustering", "qgis.spatial",
        "K-means clustering of point features.",
        base_input(required=["points_layer", "k"], properties={
            "points_layer": _str_prop("Input point layer id"),
            "k": _int_prop("Number of clusters"),
            "max_iterations": _int_prop("Max iterations (default: 100)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop(), "cluster_centers": _list_prop("cluster centers", "array")}),
        permissions=["qgis:spatial:write"],
        verification=["output_exists", "clusters_created"],
    )
    add(
        "qgis.spatial.dbscan_clustering", "qgis.spatial",
        "DBSCAN density-based clustering.",
        base_input(required=["points_layer", "eps", "min_points"], properties={
            "points_layer": _str_prop("Input point layer id"),
            "eps": _num_prop("Maximum distance between points in cluster"),
            "min_points": _int_prop("Minimum points to form cluster"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop(), "num_clusters": _int_prop()}),
        permissions=["qgis:spatial:write"],
        verification=["output_exists", "clusters_created"],
    )
    add(
        "qgis.spatial.idw_interpolation", "qgis.spatial",
        "Inverse Distance Weighted (IDW) interpolation.",
        base_input(required=["points_layer", "z_field"], properties={
            "points_layer": _str_prop("Input point layer id"),
            "z_field": _str_prop("Field with values to interpolate"),
            "distance_coeff": _num_prop("Distance coefficient (default: 2.0)"),
            "extent": _list_prop("Output extent [xmin, ymin, xmax, ymax]", "number"),
            "pixel_size": _num_prop("Output pixel size"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:spatial:write"],
        verification=["output_exists", "output_valid", "interpolation_computed"],
    )
    add(
        "qgis.spatial.tin_interpolation", "qgis.spatial",
        "TIN (Triangulated Irregular Network) interpolation.",
        base_input(required=["points_layer", "z_field"], properties={
            "points_layer": _str_prop("Input point layer id"),
            "z_field": _str_prop("Field with values to interpolate"),
            "extent": _list_prop("Output extent [xmin, ymin, xmax, ymax]", "number"),
            "pixel_size": _num_prop("Output pixel size"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:spatial:write"],
        verification=["output_exists", "output_valid", "interpolation_computed"],
    )
    add(
        "qgis.spatial.morans_i", "qgis.spatial",
        "Calculate Moran's I spatial autocorrelation.",
        base_input(required=["layer_id", "field"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "field": _str_prop("Field to analyze"),
            "weights_type": _str_prop("Spatial weights: queen|rook|knn|distance (default: queen)"),
            "k_neighbors": _int_prop("K for KNN weights (default: 5)"),
            "distance_threshold": _num_prop("Distance threshold for distance weights"),
        }),
        base_output({"morans_i": _num_prop(), "z_score": _num_prop(), "p_value": _num_prop(), "expected_i": _num_prop()}),
        permissions=["qgis:spatial:read"],
        verification=["statistics_computed"],
    )
    add(
        "qgis.spatial.getis_ord", "qgis.spatial",
        "Calculate Getis-Ord Gi* hot spot analysis.",
        base_input(required=["layer_id", "field"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "field": _str_prop("Field to analyze"),
            "weights_type": _str_prop("Spatial weights: queen|rook|knn|distance (default: queen)"),
            "k_neighbors": _int_prop("K for KNN weights (default: 5)"),
            "distance_threshold": _num_prop("Distance threshold for distance weights"),
        }),
        base_output({"hot_spots": _list_prop("hot spot features"), "cold_spots": _list_prop("cold spot features"), "gi_stats": _list_prop("Gi* values", "number")}),
        permissions=["qgis:spatial:read"],
        verification=["statistics_computed"],
    )
    add(
        "qgis.spatial.gearys_c", "qgis.spatial",
        "Calculate Geary's C spatial autocorrelation.",
        base_input(required=["layer_id", "field"], properties={
            "layer_id": _str_prop("Input vector layer id"),
            "field": _str_prop("Field to analyze"),
            "weights_type": _str_prop("Spatial weights: queen|rook|knn|distance (default: queen)"),
            "k_neighbors": _int_prop("K for KNN weights (default: 5)"),
            "distance_threshold": _num_prop("Distance threshold for distance weights"),
        }),
        base_output({"gearys_c": _num_prop(), "z_score": _num_prop(), "p_value": _num_prop(), "expected_c": _num_prop()}),
        permissions=["qgis:spatial:read"],
        verification=["statistics_computed"],
    )

    # ---- qgis.terrain (15 tools) ----
    add(
        "qgis.terrain.hillshade", "qgis.terrain",
        "Generate hillshade from DEM.",
        base_input(required=["dem_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "z_factor": _num_prop("Vertical exaggeration factor (default: 1.0)"),
            "azimuth": _num_prop("Light azimuth in degrees (default: 315)"),
            "altitude": _num_prop("Light altitude in degrees (default: 45)"),
            "combined": _bool_prop("Combined shading (default: false)"),
            "multidirectional": _bool_prop("Multidirectional (default: false)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:terrain:write"],
        verification=["output_exists", "output_valid", "hillshade_generated"],
    )
    add(
        "qgis.terrain.slope", "qgis.terrain",
        "Calculate slope from DEM (degrees or percent).",
        base_input(required=["dem_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "z_factor": _num_prop("Vertical exaggeration factor (default: 1.0)"),
            "as_percent": _bool_prop("Output as percent instead of degrees (default: false)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:terrain:write"],
        verification=["output_exists", "output_valid", "slope_computed"],
    )
    add(
        "qgis.terrain.aspect", "qgis.terrain",
        "Calculate aspect from DEM (direction of slope).",
        base_input(required=["dem_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "z_factor": _num_prop("Vertical exaggeration factor (default: 1.0)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:terrain:write"],
        verification=["output_exists", "output_valid", "aspect_computed"],
    )
    add(
        "qgis.terrain.ruggedness", "qgis.terrain",
        "Calculate terrain roughness index (TRI).",
        base_input(required=["dem_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:terrain:write"],
        verification=["output_exists", "output_valid", "roughness_computed"],
    )
    add(
        "qgis.terrain.tri", "qgis.terrain",
        "Calculate Terrain Ruggedness Index (TRI from Riley et al.).",
        base_input(required=["dem_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:terrain:write"],
        verification=["output_exists", "output_valid", "tri_computed"],
    )
    add(
        "qgis.terrain.tpi", "qgis.terrain",
        "Calculate Topographic Position Index (TPI).",
        base_input(required=["dem_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "radius": _int_prop("Neighborhood radius in cells (default: 1)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:terrain:write"],
        verification=["output_exists", "output_valid", "tpi_computed"],
    )
    add(
        "qgis.terrain.roughness", "qgis.terrain",
        "Calculate surface roughness (standard deviation of slope).",
        base_input(required=["dem_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:terrain:write"],
        verification=["output_exists", "output_valid", "roughness_computed"],
    )
    add(
        "qgis.terrain.contours", "qgis.terrain",
        "Generate contour lines from DEM.",
        base_input(required=["dem_layer", "interval"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "interval": _num_prop("Contour interval"),
            "offset": _num_prop("Contour offset (default: 0)"),
            "field_name": _str_prop("Attribute field name (default: ELEV)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:terrain:write"],
        verification=["output_exists", "output_valid", "contours_generated"],
    )
    add(
        "qgis.terrain.watershed", "qgis.terrain",
        "Calculate watershed basins from flow accumulation.",
        base_input(required=["dem_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "threshold": _num_prop("Flow accumulation threshold for stream initiation"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop(), "basin_count": _int_prop()}),
        permissions=["qgis:terrain:write"],
        verification=["output_exists", "output_valid", "watersheds_delineated"],
    )
    add(
        "qgis.terrain.flow_direction", "qgis.terrain",
        "Calculate flow direction from DEM (D8 or D-infinity).",
        base_input(required=["dem_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "method": _str_prop("Method: D8|Dinf|MFD (default: D8)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:terrain:write"],
        verification=["output_exists", "output_valid", "flow_direction_computed"],
    )
    add(
        "qgis.terrain.flow_accumulation", "qgis.terrain",
        "Calculate flow accumulation from DEM.",
        base_input(required=["dem_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "weight_layer": _str_prop("Optional weight raster layer"),
            "method": _str_prop("Method: D8|Dinf|MFD (default: D8)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:terrain:write"],
        verification=["output_exists", "output_valid", "flow_accumulation_computed"],
    )
    add(
        "qgis.terrain.stream_network", "qgis.terrain",
        "Extract stream network from flow accumulation.",
        base_input(required=["dem_layer", "threshold"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "threshold": _num_prop("Flow accumulation threshold"),
            "stream_order": _bool_prop("Calculate stream order (default: true)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop(), "stream_order_max": _int_prop()}),
        permissions=["qgis:terrain:write"],
        verification=["output_exists", "output_valid", "streams_extracted"],
    )
    add(
        "qgis.terrain.catchment", "qgis.terrain",
        "Calculate catchment area for outlet points.",
        base_input(required=["dem_layer", "outlet_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "outlet_layer": _str_prop("Outlet point layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:terrain:write"],
        verification=["output_exists", "output_valid", "catchments_delineated"],
    )
    add(
        "qgis.terrain.basin", "qgis.terrain",
        "Calculate sub-basin boundaries from stream network.",
        base_input(required=["dem_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "threshold": _num_prop("Flow accumulation threshold"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop(), "basin_count": _int_prop()}),
        permissions=["qgis:terrain:write"],
        verification=["output_exists", "output_valid", "basins_delineated"],
    )
    add(
        "qgis.terrain.depression_fill", "qgis.terrain",
        "Fill depressions (sinks) in DEM.",
        base_input(required=["dem_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "method": _str_prop("Method: PlanchonDarboux|WangLiu|Soille (default: PlanchonDarboux)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "filled_cells": _int_prop()}),
        permissions=["qgis:terrain:write"],
        verification=["output_exists", "output_valid", "depressions_filled"],
    )

    # ---- qgis.hydrology (12 tools) ----
    add(
        "qgis.hydrology.stream_order", "qgis.hydrology",
        "Calculate Strahler/Horton stream order from stream network.",
        base_input(required=["stream_layer"], properties={
            "stream_layer": _str_prop("Input stream network layer id"),
            "method": _str_prop("Method: strahler|horton|shreve|hack (default: strahler)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop(), "max_order": _int_prop()}),
        permissions=["qgis:hydrology:write"],
        verification=["output_exists", "output_valid", "orders_calculated"],
    )
    add(
        "qgis.hydrology.catchment_area", "qgis.hydrology",
        "Calculate catchment area and drainage basins.",
        base_input(required=["dem_layer", "outlet_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "outlet_layer": _str_prop("Outlet point layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop(), "total_area": _num_prop()}),
        permissions=["qgis:hydrology:write"],
        verification=["output_exists", "output_valid", "catchments_calculated"],
    )
    add(
        "qgis.hydrology.flood_mapping", "qgis.hydrology",
        "Generate flood risk mapping from DEM and hydrological parameters.",
        base_input(required=["dem_layer", "return_period"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "return_period": _int_prop("Return period in years (e.g., 10, 50, 100)"),
            "rainfall_depth": _num_prop("Rainfall depth (mm)"),
            "curve_number": _num_prop("SCS Curve Number (default: 75)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "flooded_area": _num_prop()}),
        permissions=["qgis:hydrology:write"],
        verification=["output_exists", "output_valid", "flood_map_generated"],
    )
    add(
        "qgis.hydrology.hec_ras_prep", "qgis.hydrology",
        "Prepare HEC-RAS input data from DEM and cross-sections.",
        base_input(required=["dem_layer", "cross_section_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "cross_section_layer": _str_prop("Cross-section line layer id"),
            "stream_layer": _str_prop("Stream centerline layer id"),
            "output_dir": _str_prop("Output directory for HEC-RAS files"),
        }),
        base_output({"output_dir": _str_prop(), "cross_sections": _int_prop(), "files_created": _list_prop("files", "string")}),
        permissions=["qgis:hydrology:write"],
        verification=["output_exists", "files_written", "hec_ras_format_valid"],
    )
    add(
        "qgis.hydrology.stream_length", "qgis.hydrology",
        "Calculate stream length and longitudinal profiles.",
        base_input(required=["stream_layer"], properties={
            "stream_layer": _str_prop("Input stream network layer id"),
            "dem_layer": _str_prop("Optional DEM for elevation profile"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "total_length": _num_prop(), "reach_count": _int_prop()}),
        permissions=["qgis:hydrology:write"],
        verification=["output_exists", "output_valid", "lengths_calculated"],
    )
    add(
        "qgis.hydrology.flow_length", "qgis.hydrology",
        "Calculate flow path length from each cell to outlet.",
        base_input(required=["dem_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:hydrology:write"],
        verification=["output_exists", "output_valid", "flow_lengths_computed"],
    )
    add(
        "qgis.hydrology.topographic_index", "qgis.hydrology",
        "Calculate Topographic Wetness Index (TWI) and related indices.",
        base_input(required=["dem_layer"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "indices": _list_prop("Indices: twi|spi|sti (default: all)", "string"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "indices_computed": _list_prop("indices", "string")}),
        permissions=["qgis:hydrology:write"],
        verification=["output_exists", "output_valid", "indices_computed"],
    )
    add(
        "qgis.hydrology.sed_transport", "qgis.hydrology",
        "Calculate sediment transport capacity and yield.",
        base_input(required=["dem_layer", "rainfall_erosivity", "soil_erodibility"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "rainfall_erosivity": _num_prop("R factor (rainfall erosivity)"),
            "soil_erodibility": _num_prop("K factor (soil erodibility)"),
            "cover_factor": _num_prop("C factor (cover management, default: 1.0)"),
            "practice_factor": _num_prop("P factor (support practice, default: 1.0)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "total_yield": _num_prop()}),
        permissions=["qgis:hydrology:write"],
        verification=["output_exists", "output_valid", "sediment_calculated"],
    )
    add(
        "qgis.hydrology.flood_extent", "qgis.hydrology",
        "Map flood extent for given return periods or water levels.",
        base_input(required=["dem_layer", "water_levels"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "water_levels": _list_prop("Water levels (m) or return periods", "number"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "flooded_areas": _list_prop("areas per level", "number")}),
        permissions=["qgis:hydrology:write"],
        verification=["output_exists", "output_valid", "extents_mapped"],
    )
    add(
        "qgis.hydrology.flood_depth", "qgis.hydrology",
        "Calculate flood depth and velocity rasters.",
        base_input(required=["dem_layer", "discharge", "manning_n"], properties={
            "dem_layer": _str_prop("Input DEM raster layer id"),
            "discharge": _num_prop("Discharge (m3/s)"),
            "manning_n": _num_prop("Manning's roughness coefficient"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "max_depth": _num_prop(), "max_velocity": _num_prop()}),
        permissions=["qgis:hydrology:write"],
        verification=["output_exists", "output_valid", "depth_velocity_computed"],
    )
    add(
        "qgis.hydrology.culvert", "qgis.hydrology",
        "Analyze culvert hydraulics and capacity.",
        base_input(required=["culvert_layer", "upstream_dem", "downstream_dem"], properties={
            "culvert_layer": _str_prop("Culvert line layer id"),
            "upstream_dem": _str_prop("Upstream DEM raster layer id"),
            "downstream_dem": _str_prop("Downstream DEM raster layer id"),
            "discharge": _num_prop("Design discharge (m3/s)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "capacity": _num_prop(), "headwater_depth": _num_prop(), "outlet_velocity": _num_prop()}),
        permissions=["qgis:hydrology:write"],
        verification=["output_exists", "hydraulics_computed"],
    )
    add(
        "qgis.hydrology.bridge", "qgis.hydrology",
        "Analyze bridge hydraulics, scour, and clearance.",
        base_input(required=["bridge_layer", "dem_layer", "discharge"], properties={
            "bridge_layer": _str_prop("Bridge line/polygon layer id"),
            "dem_layer": _str_prop("DEM raster layer id"),
            "discharge": _num_prop("Design discharge (m3/s)"),
            "return_period": _int_prop("Return period (years)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "water_surface_elevation": _num_prop(), "scour_depth": _num_prop(), "clearance": _num_prop()}),
        permissions=["qgis:hydrology:write"],
        verification=["output_exists", "hydraulics_computed"],
    )

    # ---- qgis.network (12 tools) ----
    add(
        "qgis.network.shortest_path", "qgis.network",
        "Calculate shortest path (point-to-point, layer-to-point, point-to-layer, layer-to-layer).",
        base_input(required=["network_layer", "start", "end"], properties={
            "network_layer": _str_prop("Network line layer id (with topology)"),
            "start": {"type": ["string", "object"], "description": "Start point: layer id or [x, y]"},
            "end": {"type": ["string", "object"], "description": "End point: layer id or [x, y]"},
            "cost_field": _str_prop("Cost field (default: length)"),
            "direction_field": _str_prop("Optional direction field for one-way streets"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "total_cost": _num_prop(), "path_length": _num_prop()}),
        permissions=["qgis:network:write"],
        verification=["output_exists", "output_valid", "path_found"],
    )
    add(
        "qgis.network.service_area", "qgis.network",
        "Calculate service area / isochrones from point or layer.",
        base_input(required=["network_layer", "center", "costs"], properties={
            "network_layer": _str_prop("Network line layer id"),
            "center": {"type": ["string", "object"], "description": "Center point: layer id or [x, y]"},
            "costs": _list_prop("Cost breaks (e.g., [5, 10, 15] minutes)", "number"),
            "cost_field": _str_prop("Cost field (default: time)"),
            "direction_field": _str_prop("Optional direction field"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop(), "cost_breaks": _list_prop("breaks", "number")}),
        permissions=["qgis:network:write"],
        verification=["output_exists", "output_valid", "service_area_computed"],
    )
    add(
        "qgis.network.od_matrix", "qgis.network",
        "Calculate Origin-Destination cost matrix between points.",
        base_input(required=["network_layer", "origins_layer", "destinations_layer"], properties={
            "network_layer": _str_prop("Network line layer id"),
            "origins_layer": _str_prop("Origin points layer id"),
            "destinations_layer": _str_prop("Destination points layer id"),
            "cost_field": _str_prop("Cost field (default: time)"),
            "cutoff": _num_prop("Optional cost cutoff"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "matrix": {"type": "object"}, "origin_count": _int_prop(), "dest_count": _int_prop()}),
        permissions=["qgis:network:write"],
        verification=["output_exists", "matrix_computed"],
    )
    add(
        "qgis.network.traveling_salesman", "qgis.network",
        "Solve Traveling Salesman Problem for network.",
        base_input(required=["network_layer", "stops_layer"], properties={
            "network_layer": _str_prop("Network line layer id"),
            "stops_layer": _str_prop("Stops point layer id"),
            "start_point": _str_prop("Optional start point layer id or [x, y]"),
            "end_point": _str_prop("Optional end point (default: return to start)"),
            "cost_field": _str_prop("Cost field (default: time)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "total_cost": _num_prop(), "stop_order": _list_prop("ordered stops", "string")}),
        permissions=["qgis:network:write"],
        verification=["output_exists", "output_valid", "route_optimized"],
    )
    add(
        "qgis.network.vehicle_routing", "qgis.network",
        "Solve Vehicle Routing Problem (VRP) with capacity constraints.",
        base_input(required=["network_layer", "depot_layer", "orders_layer", "vehicles_layer"], properties={
            "network_layer": _str_prop("Network line layer id"),
            "depot_layer": _str_prop("Depot point layer id"),
            "orders_layer": _str_prop("Orders point layer id"),
            "vehicles_layer": _str_prop("Vehicles layer id (capacity, max cost)"),
            "cost_field": _str_prop("Cost field (default: time)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "routes": _list_prop("routes"), "total_cost": _num_prop(), "orders_served": _int_prop()}),
        permissions=["qgis:network:write"],
        verification=["output_exists", "output_valid", "vrp_solved"],
    )
    add(
        "qgis.network.isochrone", "qgis.network",
        "Generate isochrone (time-based service area) polygons.",
        base_input(required=["network_layer", "center", "times"], properties={
            "network_layer": _str_prop("Network line layer id"),
            "center": {"type": ["string", "object"], "description": "Center point: layer id or [x, y]"},
            "times": _list_prop("Time breaks in minutes (e.g., [5, 10, 15])", "number"),
            "cost_field": _str_prop("Time cost field"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop(), "time_breaks": _list_prop("breaks", "number")}),
        permissions=["qgis:network:write"],
        verification=["output_exists", "output_valid", "isochrones_generated"],
    )
    add(
        "qgis.network.isodistance", "qgis.network",
        "Generate isodistance (distance-based service area) polygons.",
        base_input(required=["network_layer", "center", "distances"], properties={
            "network_layer": _str_prop("Network line layer id"),
            "center": {"type": ["string", "object"], "description": "Center point: layer id or [x, y]"},
            "distances": _list_prop("Distance breaks in map units (e.g., [1000, 2000, 5000])", "number"),
            "cost_field": _str_prop("Distance cost field (default: length)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "feature_count": _int_prop(), "distance_breaks": _list_prop("breaks", "number")}),
        permissions=["qgis:network:write"],
        verification=["output_exists", "output_valid", "isodistances_generated"],
    )
    add(
        "qgis.network.build", "qgis.network",
        "Build network topology from line layer (nodes, edges, connectivity).",
        base_input(required=["line_layer"], properties={
            "line_layer": _str_prop("Input line layer id"),
            "tolerance": _num_prop("Snapping tolerance (default: 0.1)"),
            "direction_field": _str_prop("Optional direction field"),
            "speed_field": _str_prop("Optional speed field for time cost"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "node_count": _int_prop(), "edge_count": _int_prop(), "connected": _bool_prop()}),
        permissions=["qgis:network:write"],
        verification=["output_exists", "topology_built", "connectivity_verified"],
    )
    add(
        "qgis.network.topology_check", "qgis.network",
        "Check network topology for errors (dangles, intersections, overshoots).",
        base_input(required=["network_layer"], properties={
            "network_layer": _str_prop("Network line layer id"),
            "check_dangles": _bool_prop("Check for dangles (default: true)"),
            "check_intersections": _bool_prop("Check for improper intersections (default: true)"),
            "check_overshoots": _bool_prop("Check for overshoots (default: true)"),
            "output_layer": _str_prop("Optional output layer name for errors"),
        }),
        base_output({"output_layer_id": _str_prop(), "dangles": _int_prop(), "intersections": _int_prop(), "overshoots": _int_prop(), "total_errors": _int_prop()}),
        permissions=["qgis:network:read"],
        verification=["checks_completed", "errors_reported"],
    )
    add(
        "qgis.network.turn_restriction", "qgis.network",
        "Add/manage turn restrictions on network edges.",
        base_input(required=["network_layer", "restrictions"], properties={
            "network_layer": _str_prop("Network line layer id"),
            "restrictions": _list_prop("Restrictions: [{from_edge, to_edge, via_node, type}]", "object"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "restriction_count": _int_prop()}),
        permissions=["qgis:network:write"],
        verification=["output_exists", "restrictions_applied"],
    )
    add(
        "qgis.network.elevation_profile", "qgis.network",
        "Extract elevation profile along network route.",
        base_input(required=["network_layer", "route_layer", "dem_layer"], properties={
            "network_layer": _str_prop("Network line layer id"),
            "route_layer": _str_prop("Route line layer id"),
            "dem_layer": _str_prop("DEM raster layer id"),
            "sample_distance": _num_prop("Sampling distance (default: 10)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "profile_points": _int_prop(), "elevation_gain": _num_prop(), "elevation_loss": _num_prop()}),
        permissions=["qgis:network:read"],
        verification=["output_exists", "profile_extracted"],
    )
    add(
        "qgis.network.route_report", "qgis.network",
        "Generate detailed route report (distance, time, turns, elevation).",
        base_input(required=["network_layer", "route_layer"], properties={
            "network_layer": _str_prop("Network line layer id"),
            "route_layer": _str_prop("Route line layer id"),
            "dem_layer": _str_prop("Optional DEM for elevation"),
            "speed_field": _str_prop("Optional speed field for time"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "total_distance": _num_prop(), "total_time": _num_prop(), "turn_count": _int_prop(), "elevation_profile": {"type": "object"}}),
        permissions=["qgis:network:read"],
        verification=["output_exists", "report_generated"],
    )

    # ---- qgis.remote_sensing (11 tools) ----
    add(
        "qgis.remote_sensing.satellite_import", "qgis.remote_sensing",
        "Import satellite imagery (GeoTIFF, SAFE, etc.) into QGIS.",
        base_input(required=["file_path"], properties={
            "file_path": _str_prop("Path to satellite imagery file or directory"),
            "provider": _str_prop("Provider: gdal|otb|sentinel|landsat (default: gdal)"),
            "band_selection": _list_prop("Bands to import (default: all)", "integer"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "band_count": _int_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:remote_sensing:write"],
        verification=["output_exists", "output_valid", "imagery_imported"],
    )
    add(
        "qgis.remote_sensing.band_combinations", "qgis.remote_sensing",
        "Create band combinations (RGB, false color, etc.) from multi-band imagery.",
        base_input(required=["layer_id", "bands"], properties={
            "layer_id": _str_prop("Input multi-band raster layer id"),
            "bands": _list_prop("Band indices for R, G, B (e.g., [4, 3, 2] for false color)", "integer"),
            "stretch": _str_prop("Stretch: none|minmax|stddev|histogram (default: minmax)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "band_count": _int_prop()}),
        permissions=["qgis:remote_sensing:write"],
        verification=["output_exists", "output_valid", "combination_created"],
    )
    add(
        "qgis.remote_sensing.spectral_indices", "qgis.remote_sensing",
        "Calculate spectral indices (NDVI, EVI, SAVI, NBR, MNDWI, etc.).",
        base_input(required=["layer_id", "index"], properties={
            "layer_id": _str_prop("Input multi-band raster layer id"),
            "index": _str_prop("Index: ndvi|evi|savi|nbr|mndwi|ndbi|bai|gci|msavi|arvi|si"),
            "red_band": _int_prop("Red band index (default: 3)"),
            "nir_band": _int_prop("NIR band index (default: 4)"),
            "blue_band": _int_prop("Blue band index (default: 1)"),
            "swir1_band": _int_prop("SWIR1 band index (default: 5)"),
            "swir2_band": _int_prop("SWIR2 band index (default: 6)"),
            "l_value": _num_prop("L factor for SAVI (default: 0.5)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "index": _str_prop()}),
        permissions=["qgis:remote_sensing:write"],
        verification=["output_exists", "output_valid", "index_calculated"],
    )
    add(
        "qgis.remote_sensing.pan_sharpening", "qgis.remote_sensing",
        "Pan-sharpen multispectral imagery using panchromatic band.",
        base_input(required=["ms_layer", "pan_layer"], properties={
            "ms_layer": _str_prop("Multispectral raster layer id"),
            "pan_layer": _str_prop("Panchromatic raster layer id"),
            "method": _str_prop("Method: brovey|ihs|pca|wavelet|bayes (default: brovey)"),
            "weights": _list_prop("Optional band weights for Brovey"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "band_count": _int_prop()}),
        permissions=["qgis:remote_sensing:write"],
        verification=["output_exists", "output_valid", "sharpened"],
    )
    add(
        "qgis.remote_sensing.atmospheric_correction", "qgis.remote_sensing",
        "Apply atmospheric correction (DOS, FLAASH, 6S, etc.).",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "method": _str_prop("Method: dos|flaash|6s|sen2cor|arci (default: dos)"),
            "sensor": _str_prop("Sensor type: sentinel2|landsat8|modis|planet|other"),
            "metadata_file": _str_prop("Optional metadata file path (MTL, XML)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:remote_sensing:write"],
        verification=["output_exists", "output_valid", "corrected"],
    )
    add(
        "qgis.remote_sensing.radiometric_correction", "qgis.remote_sensing",
        "Apply radiometric correction (calibration, normalization).",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "method": _str_prop("Method: calibration|normalization|relative|absolute"),
            "reference_layer": _str_prop("Optional reference layer for relative correction"),
            "gain_bias": _list_prop("Optional gain/bias per band", "number"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:remote_sensing:write"],
        verification=["output_exists", "output_valid", "radiometrically_corrected"],
    )
    add(
        "qgis.remote_sensing.geometric_correction", "qgis.remote_sensing",
        "Apply geometric correction (orthorectification, co-registration).",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "method": _str_prop("Method: orthorectification|coregistration|warp"),
            "dem_layer": _str_prop("DEM layer for orthorectification"),
            "gcp_layer": _str_prop("GCP vector layer for coregistration"),
            "target_crs": _str_prop("Target CRS (default: layer CRS)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "crs": _str_prop()}),
        permissions=["qgis:remote_sensing:write"],
        verification=["output_exists", "output_valid", "geometrically_corrected"],
    )
    add(
        "qgis.remote_sensing.image_preparation", "qgis.remote_sensing",
        "Prepare imagery: clip, reproject, resample, subset bands.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "operations": _list_prop("Operations: clip|reproject|resample|subset|mask", "string"),
            "clip_extent": _list_prop("Clip extent [xmin, ymin, xmax, ymax]", "number"),
            "target_crs": _str_prop("Target CRS for reprojection"),
            "target_resolution": _num_prop("Target resolution for resampling"),
            "bands_to_keep": _list_prop("Bands to keep (default: all)", "integer"),
            "mask_layer": _str_prop("Mask vector layer for clipping"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "band_count": _int_prop()}),
        permissions=["qgis:remote_sensing:write"],
        verification=["output_exists", "output_valid", "prepared"],
    )
    add(
        "qgis.remote_sensing.mosaic", "qgis.remote_sensing",
        "Mosaic multiple satellite scenes into single image.",
        base_input(required=["layer_ids"], properties={
            "layer_ids": _list_prop("List of raster layer ids to mosaic", "string"),
            "method": _str_prop("Overlap method: first|last|min|max|mean|blend (default: blend)"),
            "feathering": _num_prop("Feathering distance for blending (default: 100)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "band_count": _int_prop()}),
        permissions=["qgis:remote_sensing:write"],
        verification=["output_exists", "output_valid", "mosaicked"],
    )
    add(
        "qgis.remote_sensing.resampling", "qgis.remote_sensing",
        "Resample imagery to different resolution or projection.",
        base_input(required=["layer_id", "target_resolution"], properties={
            "layer_id": _str_prop("Input raster layer id"),
            "target_resolution": _num_prop("Target resolution (cell size)"),
            "method": _str_prop("Resampling: nearest|bilinear|cubic|cubicspline|lanczos (default: bilinear)"),
            "target_crs": _str_prop("Optional target CRS"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:remote_sensing:write"],
        verification=["output_exists", "output_valid", "resampled"],
    )
    add(
        "qgis.remote_sensing.vegetation_indices", "qgis.remote_sensing",
        "Calculate vegetation indices (NDVI, EVI, SAVI, ARVI, etc.).",
        base_input(required=["layer_id", "indices"], properties={
            "layer_id": _str_prop("Input multi-band raster layer id"),
            "indices": _list_prop("Indices: ndvi|evi|savi|arvi|gci|msavi|vari|gndvi|reip|ndre", "string"),
            "red_band": _int_prop("Red band index (default: 3)"),
            "nir_band": _int_prop("NIR band index (default: 4)"),
            "blue_band": _int_prop("Blue band index (default: 1)"),
            "green_band": _int_prop("Green band index (default: 2)"),
            "rededge_band": _int_prop("Red-edge band index (default: 5)"),
            "l_value": _num_prop("L factor for SAVI (default: 0.5)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "indices_computed": _list_prop("indices", "string")}),
        permissions=["qgis:remote_sensing:write"],
        verification=["output_exists", "output_valid", "indices_calculated"],
    )

    # ---- qgis.classification (13 tools) ----
    add(
        "qgis.classification.train_samples", "qgis.classification",
        "Generate training samples for supervised classification.",
        base_input(required=["layer_id", "class_layer", "num_samples"], properties={
            "layer_id": _str_prop("Input raster layer id (multiband)"),
            "class_layer": _str_prop("Vector layer with class polygons"),
            "class_field": _str_prop("Class field name in class layer"),
            "num_samples": _int_prop("Number of samples per class"),
            "sampling_method": _str_prop("Method: random|systematic|stratified (default: random)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "sample_count": _int_prop(), "class_distribution": {"type": "object"}}),
        permissions=["qgis:classification:write"],
        verification=["output_exists", "output_valid", "samples_generated"],
    )
    add(
        "qgis.classification.supervised_classify", "qgis.classification",
        "Perform supervised classification (RF, SVM, ML, etc.).",
        base_input(required=["layer_id", "training_layer", "algorithm"], properties={
            "layer_id": _str_prop("Input raster layer id (multiband)"),
            "training_layer": _str_prop("Training samples vector layer id"),
            "class_field": _str_prop("Class field name"),
            "algorithm": _str_prop("Algorithm: rf|svm|ml|knn|dt|nn (default: rf)"),
            "n_trees": _int_prop("Number of trees for RF (default: 100)"),
            "max_depth": _int_prop("Max tree depth (default: 20)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "class_count": _int_prop()}),
        permissions=["qgis:classification:write"],
        verification=["output_exists", "output_valid", "classified"],
    )
    add(
        "qgis.classification.unsupervised_classify", "qgis.classification",
        "Perform unsupervised classification (K-means, ISODATA).",
        base_input(required=["layer_id", "n_classes"], properties={
            "layer_id": _str_prop("Input raster layer id (multiband)"),
            "n_classes": _int_prop("Number of classes"),
            "algorithm": _str_prop("Algorithm: kmeans|isodata (default: kmeans)"),
            "max_iterations": _int_prop("Max iterations (default: 100)"),
            "convergence_threshold": _num_prop("Convergence threshold (default: 0.01)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "class_count": _int_prop()}),
        permissions=["qgis:classification:write"],
        verification=["output_exists", "output_valid", "classified"],
    )
    add(
        "qgis.classification.random_forest", "qgis.classification",
        "Random Forest classification with training and prediction.",
        base_input(required=["layer_id", "training_layer"], properties={
            "layer_id": _str_prop("Input raster layer id (multiband)"),
            "training_layer": _str_prop("Training samples vector layer id"),
            "class_field": _str_prop("Class field name"),
            "n_trees": _int_prop("Number of trees (default: 500)"),
            "max_depth": _int_prop("Max depth (default: 30)"),
            "min_samples_split": _int_prop("Min samples split (default: 2)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "variable_importance": _list_prop("importance", "number")}),
        permissions=["qgis:classification:write"],
        verification=["output_exists", "output_valid", "classified"],
    )
    add(
        "qgis.classification.svm", "qgis.classification",
        "Support Vector Machine classification.",
        base_input(required=["layer_id", "training_layer"], properties={
            "layer_id": _str_prop("Input raster layer id (multiband)"),
            "training_layer": _str_prop("Training samples vector layer id"),
            "class_field": _str_prop("Class field name"),
            "kernel": _str_prop("Kernel: rbf|linear|poly|sigmoid (default: rbf)"),
            "C": _num_prop("Regularization parameter (default: 1.0)"),
            "gamma": _num_prop("Kernel coefficient (default: scale)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "support_vectors": _int_prop()}),
        permissions=["qgis:classification:write"],
        verification=["output_exists", "output_valid", "classified"],
    )
    add(
        "qgis.classification.maximum_likelihood", "qgis.classification",
        "Maximum Likelihood classification.",
        base_input(required=["layer_id", "training_layer"], properties={
            "layer_id": _str_prop("Input raster layer id (multiband)"),
            "training_layer": _str_prop("Training samples vector layer id"),
            "class_field": _str_prop("Class field name"),
            "probability_threshold": _num_prop("Probability threshold (default: 0.0)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "rejected_pixels": _int_prop()}),
        permissions=["qgis:classification:write"],
        verification=["output_exists", "output_valid", "classified"],
    )
    add(
        "qgis.classification.knn", "qgis.classification",
        "K-Nearest Neighbors classification.",
        base_input(required=["layer_id", "training_layer", "k"], properties={
            "layer_id": _str_prop("Input raster layer id (multiband)"),
            "training_layer": _str_prop("Training samples vector layer id"),
            "class_field": _str_prop("Class field name"),
            "k": _int_prop("Number of neighbors (default: 5)"),
            "weight": _str_prop("Weight: uniform|distance (default: uniform)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:classification:write"],
        verification=["output_exists", "output_valid", "classified"],
    )
    add(
        "qgis.classification.decision_tree", "qgis.classification",
        "Decision Tree classification.",
        base_input(required=["layer_id", "training_layer"], properties={
            "layer_id": _str_prop("Input raster layer id (multiband)"),
            "training_layer": _str_prop("Training samples vector layer id"),
            "class_field": _str_prop("Class field name"),
            "max_depth": _int_prop("Max depth (default: 20)"),
            "min_samples_split": _int_prop("Min samples split (default: 2)"),
            "criterion": _str_prop("Criterion: gini|entropy (default: gini)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "tree_depth": _int_prop()}),
        permissions=["qgis:classification:write"],
        verification=["output_exists", "output_valid", "classified"],
    )
    add(
        "qgis.classification.neural_network", "qgis.classification",
        "Neural Network / MLP classification.",
        base_input(required=["layer_id", "training_layer"], properties={
            "layer_id": _str_prop("Input raster layer id (multiband)"),
            "training_layer": _str_prop("Training samples vector layer id"),
            "class_field": _str_prop("Class field name"),
            "hidden_layers": _list_prop("Hidden layer sizes (e.g., [100, 50])", "integer"),
            "max_iter": _int_prop("Max iterations (default: 200)"),
            "learning_rate": _num_prop("Learning rate (default: 0.001)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "loss_curve": _list_prop("loss", "number")}),
        permissions=["qgis:classification:write"],
        verification=["output_exists", "output_valid", "classified"],
    )
    add(
        "qgis.classification.accuracy_assessment", "qgis.classification",
        "Assess classification accuracy (confusion matrix, kappa, OA, PA, UA).",
        base_input(required=["classified_layer", "reference_layer"], properties={
            "classified_layer": _str_prop("Classified raster layer id"),
            "reference_layer": _str_prop("Reference (ground truth) vector layer id"),
            "class_field": _str_prop("Class field in reference layer"),
            "sample_method": _str_prop("Sampling: random|stratified|systematic (default: stratified)"),
            "num_samples": _int_prop("Number of validation samples"),
        }),
        base_output({"overall_accuracy": _num_prop(), "kappa": _num_prop(), "producer_accuracy": _list_prop("PA per class", "number"), "user_accuracy": _list_prop("UA per class", "number"), "f1_score": _list_prop("F1 per class", "number"), "confusion_matrix": {"type": "object"}}),
        permissions=["qgis:classification:read"],
        verification=["statistics_computed"],
    )
    add(
        "qgis.classification.confusion_matrix", "qgis.classification",
        "Generate confusion matrix from classified and reference data.",
        base_input(required=["classified_layer", "reference_layer"], properties={
            "classified_layer": _str_prop("Classified raster layer id"),
            "reference_layer": _str_prop("Reference (ground truth) vector layer id"),
            "class_field": _str_prop("Class field in reference layer"),
        }),
        base_output({"confusion_matrix": {"type": "object"}, "class_names": _list_prop("class names", "string")}),
        permissions=["qgis:classification:read"],
        verification=["matrix_computed"],
    )
    add(
        "qgis.classification.post_filter", "qgis.classification",
        "Post-classification filtering (majority filter, sieve).",
        base_input(required=["classified_layer"], properties={
            "classified_layer": _str_prop("Classified raster layer id"),
            "method": _str_prop("Method: majority|sieve|mode (default: majority)"),
            "kernel_size": _int_prop("Kernel size for majority filter (default: 3)"),
            "threshold": _int_prop("Minimum region size for sieve (default: 10)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "filtered": _bool_prop()}),
        permissions=["qgis:classification:write"],
        verification=["output_exists", "output_valid", "filtered"],
    )
    add(
        "qgis.classification.reclassify", "qgis.classification",
        "Reclassify thematic raster (merge/split classes).",
        base_input(required=["classified_layer", "reclass_map"], properties={
            "classified_layer": _str_prop("Classified raster layer id"),
            "reclass_map": _list_prop("Reclass mapping: [[old_val, new_val], ...]", "array"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "class_count": _int_prop()}),
        permissions=["qgis:classification:write"],
        verification=["output_exists", "output_valid", "reclassified"],
    )

    # ---- qgis.change_detection (15 tools) ----
    add(
        "qgis.change_detection.temporal_comparison", "qgis.change_detection",
        "Compare two temporal images (t1, t2) for changes.",
        base_input(required=["t1_layer", "t2_layer"], properties={
            "t1_layer": _str_prop("Time 1 raster layer id"),
            "t2_layer": _str_prop("Time 2 raster layer id"),
            "method": _str_prop("Method: difference|ratio|log_ratio|correlation|spectral_angle (default: difference)"),
            "threshold": _num_prop("Change threshold"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "change_pixels": _int_prop()}),
        permissions=["qgis:change_detection:write"],
        verification=["output_exists", "output_valid", "changes_detected"],
    )
    add(
        "qgis.change_detection.raster_difference", "qgis.change_detection",
        "Calculate raster difference (t2 - t1) or ratio (t2 / t1).",
        base_input(required=["t1_layer", "t2_layer"], properties={
            "t1_layer": _str_prop("Time 1 raster layer id"),
            "t2_layer": _str_prop("Time 2 raster layer id"),
            "operation": _str_prop("Operation: difference|ratio|log_ratio|normalized_difference (default: difference)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "min": _num_prop(), "max": _num_prop(), "mean": _num_prop(), "std": _num_prop()}),
        permissions=["qgis:change_detection:write"],
        verification=["output_exists", "output_valid", "difference_computed"],
    )
    add(
        "qgis.change_detection.landcover_change", "qgis.change_detection",
        "Detect land cover changes between two classified rasters.",
        base_input(required=["t1_classified", "t2_classified"], properties={
            "t1_classified": _str_prop("Time 1 classified raster layer id"),
            "t2_classified": _str_prop("Time 2 classified raster layer id"),
            "class_names": _list_prop("Class names for change matrix", "string"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "change_matrix": {"type": "object"}, "total_changes": _int_prop(), "gain_loss": {"type": "object"}}),
        permissions=["qgis:change_detection:write"],
        verification=["output_exists", "output_valid", "change_matrix_computed"],
    )
    add(
        "qgis.change_detection.change_report", "qgis.change_detection",
        "Generate change detection report with statistics and maps.",
        base_input(required=["change_layer"], properties={
            "change_layer": _str_prop("Change raster layer id"),
            "reference_layer": _str_prop("Optional reference vector layer for zonal stats"),
            "class_field": _str_prop("Class field in reference layer"),
            "report_format": _str_prop("Format: json|html|pdf (default: json)"),
        }),
        base_output({"report": {"type": "object"}, "summary": {"type": "object"}}),
        permissions=["qgis:change_detection:read"],
        verification=["report_generated"],
    )
    add(
        "qgis.change_detection.multitemporal_change", "qgis.change_detection",
        "Analyze changes across multiple time periods.",
        base_input(required=["layer_ids"], properties={
            "layer_ids": _list_prop("List of raster layer ids (chronological)", "string"),
            "method": _str_prop("Method: bfast|landtrendr|ccdc|trend|seasonal (default: trend)"),
            "dates": _list_prop("Acquisition dates (ISO format)", "string"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "breakpoints": _list_prop("breakpoints"), "trend": _list_prop("trend"), "magnitude": _list_prop("magnitude")}),
        permissions=["qgis:change_detection:write"],
        verification=["output_exists", "output_valid", "multitemporal_analyzed"],
    )
    add(
        "qgis.change_detection.image_ratio", "qgis.change_detection",
        "Calculate image ratio (t2 / t1) for change enhancement.",
        base_input(required=["t1_layer", "t2_layer"], properties={
            "t1_layer": _str_prop("Time 1 raster layer id"),
            "t2_layer": _str_prop("Time 2 raster layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:change_detection:write"],
        verification=["output_exists", "output_valid", "ratio_computed"],
    )
    add(
        "qgis.change_detection.image_difference", "qgis.change_detection",
        "Calculate image difference (t2 - t1) for change enhancement.",
        base_input(required=["t1_layer", "t2_layer"], properties={
            "t1_layer": _str_prop("Time 1 raster layer id"),
            "t2_layer": _str_prop("Time 2 raster layer id"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:change_detection:write"],
        verification=["output_exists", "output_valid", "difference_computed"],
    )
    add(
        "qgis.change_detection.ndvi_change", "qgis.change_detection",
        "Calculate NDVI change between two dates.",
        base_input(required=["t1_layer", "t2_layer"], properties={
            "t1_layer": _str_prop("Time 1 multi-band raster layer id"),
            "t2_layer": _str_prop("Time 2 multi-band raster layer id"),
            "red_band": _int_prop("Red band index (default: 3)"),
            "nir_band": _int_prop("NIR band index (default: 4)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop(), "ndvi_t1": _num_prop(), "ndvi_t2": _num_prop(), "ndvi_change": _num_prop()}),
        permissions=["qgis:change_detection:write"],
        verification=["output_exists", "output_valid", "ndvi_change_computed"],
    )
    add(
        "qgis.change_detection.urban_expansion", "qgis.change_detection",
        "Detect urban expansion from time series imagery.",
        base_input(required=["t1_layer", "t2_layer"], properties={
            "t1_layer": _str_prop("Time 1 raster layer id"),
            "t2_layer": _str_prop("Time 2 raster layer id"),
            "urban_threshold": _num_prop("Urban index threshold (default: 0.3)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "urban_area_t1": _num_prop(), "urban_area_t2": _num_prop(), "expansion_area": _num_prop()}),
        permissions=["qgis:change_detection:write"],
        verification=["output_exists", "output_valid", "expansion_detected"],
    )
    add(
        "qgis.change_detection.deforestation", "qgis.change_detection",
        "Detect deforestation from time series imagery.",
        base_input(required=["t1_layer", "t2_layer"], properties={
            "t1_layer": _str_prop("Time 1 multi-band raster layer id"),
            "t2_layer": _str_prop("Time 2 multi-band raster layer id"),
            "forest_threshold": _num_prop("NDVI threshold for forest (default: 0.6)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "forest_area_t1": _num_prop(), "forest_area_t2": _num_prop(), "deforested_area": _num_prop()}),
        permissions=["qgis:change_detection:write"],
        verification=["output_exists", "output_valid", "deforestation_detected"],
    )
    add(
        "qgis.change_detection.flood_mapping", "qgis.change_detection",
        "Map flood extent changes between dates.",
        base_input(required=["t1_layer", "t2_layer"], properties={
            "t1_layer": _str_prop("Time 1 raster layer id (pre-flood)"),
            "t2_layer": _str_prop("Time 2 raster layer id (during flood)"),
            "water_index": _str_prop("Water index: mndwi|ndwi|awi (default: mndwi)"),
            "threshold": _num_prop("Water threshold (default: 0)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "water_area_t1": _num_prop(), "water_area_t2": _num_prop(), "flooded_area": _num_prop()}),
        permissions=["qgis:change_detection:write"],
        verification=["output_exists", "output_valid", "flood_mapped"],
    )
    add(
        "qgis.change_detection.burned_area", "qgis.change_detection",
        "Map burned area from pre/post fire imagery.",
        base_input(required=["pre_fire_layer", "post_fire_layer"], properties={
            "pre_fire_layer": _str_prop("Pre-fire multi-band raster layer id"),
            "post_fire_layer": _str_prop("Post-fire multi-band raster layer id"),
            "index": _str_prop("Burn index: nbr|dbr|bai (default: nbr)"),
            "threshold": _num_prop("Burn threshold"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "burned_area": _num_prop(), "severity_classes": _list_prop("severity")}),
        permissions=["qgis:change_detection:write"],
        verification=["output_exists", "output_valid", "burned_area_mapped"],
    )
    add(
        "qgis.change_detection.trend_analysis", "qgis.change_detection",
        "Analyze temporal trends in time series imagery.",
        base_input(required=["layer_ids", "dates"], properties={
            "layer_ids": _list_prop("List of raster layer ids (chronological)", "string"),
            "dates": _list_prop("Acquisition dates (ISO format)", "string"),
            "method": _str_prop("Method: linear|mann_kendall|sen_slope|theil_sen (default: linear)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "slope": _num_prop(), "p_value": _num_prop(), "intercept": _num_prop(), "significant": _bool_prop()}),
        permissions=["qgis:change_detection:write"],
        verification=["output_exists", "output_valid", "trend_computed"],
    )
    add(
        "qgis.change_detection.time_series_analysis", "qgis.change_detection",
        "Time series analysis (smoothing, decomposition, forecasting).",
        base_input(required=["layer_ids", "dates"], properties={
            "layer_ids": _list_prop("List of raster layer ids (chronological)", "string"),
            "dates": _list_prop("Acquisition dates (ISO format)", "string"),
            "method": _str_prop("Method: smoothing|decomposition|forecasting|seasonal (default: smoothing)"),
            "window_size": _int_prop("Smoothing window size (default: 3)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "smoothed": _bool_prop(), "components": {"type": "object"}, "forecast": _list_prop("forecast", "number")}),
        permissions=["qgis:change_detection:write"],
        verification=["output_exists", "output_valid", "timeseries_analyzed"],
    )
    add(
        "qgis.change_detection.change_vector_analysis", "qgis.change_detection",
        "Change Vector Analysis (CVA) for multi-band change detection.",
        base_input(required=["t1_layer", "t2_layer"], properties={
            "t1_layer": _str_prop("Time 1 multi-band raster layer id"),
            "t2_layer": _str_prop("Time 2 multi-band raster layer id"),
            "bands": _list_prop("Bands to include in CVA", "integer"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"output_layer_id": _str_prop(), "magnitude": _num_prop(), "angle": _num_prop(), "change_classes": _list_prop("classes")}),
        permissions=["qgis:change_detection:write"],
        verification=["output_exists", "output_valid", "cva_computed"],
    )

    # ---- qgis.temporal (10 tools) ----
    add(
        "qgis.temporal.enable", "qgis.temporal",
        "Enable temporal control on layer.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Layer id to enable temporal control"),
            "start_field": _str_prop("Start datetime field name"),
            "end_field": _str_prop("End datetime field name (optional for instant)"),
            "mode": _str_prop("Mode: feature|fixed_range|animation (default: feature)"),
        }),
        base_output({"enabled": _bool_prop(), "layer_id": _str_prop()}),
        permissions=["qgis:temporal:write"],
        verification=["temporal_enabled"],
    )
    add(
        "qgis.temporal.filter", "qgis.temporal",
        "Apply temporal filter to layer.",
        base_input(required=["layer_id", "start_time", "end_time"], properties={
            "layer_id": _str_prop("Layer id with temporal control enabled"),
            "start_time": _str_prop("Filter start time (ISO format)"),
            "end_time": _str_prop("Filter end time (ISO format)"),
        }),
        base_output({"filtered": _bool_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:temporal:write"],
        verification=["filter_applied"],
    )
    add(
        "qgis.temporal.animate", "qgis.temporal",
        "Create temporal animation from time-enabled layers.",
        base_input(required=["layers", "start_time", "end_time"], properties={
            "layers": _list_prop("Layer ids with temporal control", "string"),
            "start_time": _str_prop("Animation start time (ISO format)"),
            "end_time": _str_prop("Animation end time (ISO format)"),
            "frame_duration": _int_prop("Frame duration in milliseconds (default: 500)"),
            "output_path": _str_prop("Optional output video path"),
        }),
        base_output({"animation_created": _bool_prop(), "frame_count": _int_prop(), "output_path": _str_prop()}),
        permissions=["qgis:temporal:write"],
        verification=["animation_created"],
    )
    add(
        "qgis.temporal.time_series", "qgis.temporal",
        "Extract time series data from temporal layers.",
        base_input(required=["layer_id", "point"], properties={
            "layer_id": _str_prop("Temporal raster layer id"),
            "point": _list_prop("Point coordinates [x, y]", "number"),
            "start_time": _str_prop("Optional start time (ISO format)"),
            "end_time": _str_prop("Optional end time (ISO format)"),
        }),
        base_output({"time_series": _list_prop("time-value pairs", "array"), "point": _list_prop("coordinates", "number")}),
        permissions=["qgis:temporal:read"],
        verification=["timeseries_extracted"],
    )
    add(
        "qgis.temporal.controller", "qgis.temporal",
        "Control temporal controller (play, pause, seek, speed).",
        base_input(required=["action"], properties={
            "action": _str_prop("Action: play|pause|stop|seek|set_speed"),
            "time": _str_prop("Time for seek action (ISO format)"),
            "speed": _num_prop("Playback speed (default: 1.0)"),
        }),
        base_output({"state": _str_prop(), "current_time": _str_prop(), "speed": _num_prop()}),
        permissions=["qgis:temporal:write"],
        verification=["controller_updated"],
    )
    add(
        "qgis.temporal.keyframe", "qgis.temporal",
        "Manage temporal keyframes for animation.",
        base_input(required=["action"], properties={
            "action": _str_prop("Action: add|remove|update|list"),
            "keyframe": {"type": "object", "description": "Keyframe: {time, camera, layers_visible}"},
        }),
        base_output({"keyframes": _list_prop("keyframes")}),
        permissions=["qgis:temporal:write"],
        verification=["keyframes_updated"],
    )
    add(
        "qgis.temporal.playback", "qgis.temporal",
        "Configure temporal playback settings.",
        base_input(properties={
            "loop": _bool_prop("Loop playback (default: true)"),
            "frame_rate": _int_prop("Frames per second (default: 10)"),
            "accumulate": _bool_prop("Accumulate features (default: false)"),
        }),
        base_output({"settings": {"type": "object"}}),
        permissions=["qgis:temporal:write"],
        verification=["playback_configured"],
    )
    add(
        "qgis.temporal.range", "qgis.temporal",
        "Set temporal range for project or layers.",
        base_input(required=["start_time", "end_time"], properties={
            "start_time": _str_prop("Range start time (ISO format)"),
            "end_time": _str_prop("Range end time (ISO format)"),
            "layer_ids": _list_prop("Optional layer ids (default: all temporal layers)", "string"),
        }),
        base_output({"range_set": _bool_prop(), "start_time": _str_prop(), "end_time": _str_prop()}),
        permissions=["qgis:temporal:write"],
        verification=["range_updated"],
    )
    add(
        "qgis.temporal.join", "qgis.temporal",
        "Join temporal attributes between layers.",
        base_input(required=["target_layer", "source_layer"], properties={
            "target_layer": _str_prop("Target layer id"),
            "source_layer": _str_prop("Source layer id with temporal attributes"),
            "time_tolerance": _str_prop("Time tolerance (e.g., 1 day, 1 hour)"),
            "prefix": _str_prop("Prefix for joined fields"),
        }),
        base_output({"joined": _bool_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:temporal:write"],
        verification=["temporal_join_completed"],
    )
    add(
        "qgis.temporal.timestamp", "qgis.temporal",
        "Add/extract timestamp from features.",
        base_input(required=["layer_id", "action"], properties={
            "layer_id": _str_prop("Layer id"),
            "action": _str_prop("Action: add|extract"),
            "timestamp_field": _str_prop("Field name for timestamp"),
            "timestamp_value": _str_prop("Timestamp value for add action (ISO format)"),
        }),
        base_output({"updated": _bool_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:temporal:write"],
        verification=["timestamp_updated"],
    )

    # ---- qgis.database (10 tools) ----
    add(
        "qgis.database.postgis_connect", "qgis.database",
        "Connect to PostGIS database.",
        base_input(required=["host", "database", "user", "password"], properties={
            "host": _str_prop("Database host"),
            "port": _int_prop("Database port (default: 5432)"),
            "database": _str_prop("Database name"),
            "user": _str_prop("Username"),
            "password": _str_prop("Password"),
            "ssl_mode": _str_prop("SSL mode: require|prefer|disable (default: prefer)"),
        }),
        base_output({"connected": _bool_prop(), "connection_id": _str_prop(), "version": _str_prop()}),
        permissions=["qgis:database:write"],
        verification=["connection_established"],
    )
    add(
        "qgis.database.geopackage_connect", "qgis.database",
        "Connect to GeoPackage database.",
        base_input(required=["path"], properties={
            "path": _str_prop("Path to GeoPackage file"),
            "readonly": _bool_prop("Open read-only (default: false)"),
        }),
        base_output({"connected": _bool_prop(), "table_count": _int_prop(), "tables": _list_prop("table names", "string")}),
        permissions=["qgis:database:read"],
        verification=["connection_established"],
    )
    add(
        "qgis.database.spatialite_connect", "qgis.database",
        "Connect to SpatiaLite database.",
        base_input(required=["path"], properties={
            "path": _str_prop("Path to SpatiaLite file"),
            "readonly": _bool_prop("Open read-only (default: false)"),
        }),
        base_output({"connected": _bool_prop(), "table_count": _int_prop(), "tables": _list_prop("table names", "string")}),
        permissions=["qgis:database:read"],
        verification=["connection_established"],
    )
    add(
        "qgis.database.virtual_layer", "qgis.database",
        "Create virtual layer from SQL query.",
        base_input(required=["query", "geometry_column"], properties={
            "query": _str_prop("SQL query"),
            "geometry_column": _str_prop("Geometry column name"),
            "geometry_type": _str_prop("Geometry type: Point|LineString|Polygon|Multi*"),
            "crs": _str_prop("CRS (e.g., EPSG:4326)"),
            "layer_name": _str_prop("Virtual layer name"),
        }),
        base_output({"layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:database:write"],
        verification=["virtual_layer_created"],
    )
    add(
        "qgis.database.spatial_sql", "qgis.database",
        "Execute spatial SQL query on database.",
        base_input(required=["connection_id", "query"], properties={
            "connection_id": _str_prop("Database connection id"),
            "query": _str_prop("Spatial SQL query"),
            "parameters": _list_prop("Query parameters", "object"),
        }),
        base_output({"result": {"type": "object"}, "row_count": _int_prop()}),
        permissions=["qgis:database:read"],
        verification=["query_executed"],
    )
    add(
        "qgis.database.db_import", "qgis.database",
        "Import layer into database.",
        base_input(required=["layer_id", "connection_id", "table_name"], properties={
            "layer_id": _str_prop("Layer id to import"),
            "connection_id": _str_prop("Database connection id"),
            "table_name": _str_prop("Target table name"),
            "overwrite": _bool_prop("Overwrite existing table (default: false)"),
            "spatial_index": _bool_prop("Create spatial index (default: true)"),
            "primary_key": _str_prop("Primary key field (optional)"),
        }),
        base_output({"imported": _bool_prop(), "table_name": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:database:write"],
        verification=["import_completed"],
    )
    add(
        "qgis.database.db_export", "qgis.database",
        "Export layer from database.",
        base_input(required=["connection_id", "table_name"], properties={
            "connection_id": _str_prop("Database connection id"),
            "table_name": _str_prop("Source table name"),
            "output_layer": _str_prop("Optional output layer name"),
            "where_clause": _str_prop("Optional WHERE clause"),
        }),
        base_output({"exported": _bool_prop(), "layer_id": _str_prop(), "feature_count": _int_prop()}),
        permissions=["qgis:database:read"],
        verification=["export_completed"],
    )
    add(
        "qgis.database.sql_builder", "qgis.database",
        "Build spatial SQL query visually.",
        base_input(required=["connection_id", "tables"], properties={
            "connection_id": _str_prop("Database connection id"),
            "tables": _list_prop("Table names to include", "string"),
            "operations": _list_prop("Operations: select|join|where|group|spatial", "string"),
            "output_format": _str_prop("Format: sql|geojson|layer (default: sql)"),
        }),
        base_output({"query": _str_prop(), "preview": _list_prop("preview rows", "object")}),
        permissions=["qgis:database:read"],
        verification=["query_built"],
    )
    add(
        "qgis.database.connection_test", "qgis.database",
        "Test database connection.",
        base_input(required=["connection_id"], properties={
            "connection_id": _str_prop("Database connection id"),
        }),
        base_output({"connected": _bool_prop(), "latency_ms": _int_prop(), "version": _str_prop()}),
        permissions=["qgis:database:read"],
        verification=["connection_tested"],
    )
    add(
        "qgis.database.schema_inspect", "qgis.database",
        "Inspect database schema (tables, columns, indexes, constraints).",
        base_input(required=["connection_id"], properties={
            "connection_id": _str_prop("Database connection id"),
            "schema": _str_prop("Schema name (default: public)"),
            "table": _str_prop("Optional specific table"),
        }),
        base_output({"tables": _list_prop("table schemas", "object"), "views": _list_prop("view schemas", "object")}),
        permissions=["qgis:database:read"],
        verification=["schema_inspected"],
    )

    # ---- qgis.web_gis (10 tools) ----
    add(
        "qgis.web_gis.wms_load", "qgis.web_gis",
        "Load WMS (Web Map Service) layer.",
        base_input(required=["url"], properties={
            "url": _str_prop("WMS service URL"),
            "layers": _list_prop("Layer names to load", "string"),
            "styles": _list_prop("Styles for each layer", "string"),
            "crs": _str_prop("CRS (default: EPSG:3857)"),
            "format": _str_prop("Image format (default: image/png)"),
            "transparent": _bool_prop("Transparent background (default: true)"),
            "layer_name": _str_prop("Optional layer name"),
        }),
        base_output({"layer_id": _str_prop(), "layer_count": _int_prop(), "crs": _str_prop()}),
        permissions=["qgis:web_gis:write"],
        verification=["layer_loaded"],
    )
    add(
        "qgis.web_gis.wfs_load", "qgis.web_gis",
        "Load WFS (Web Feature Service) layer.",
        base_input(required=["url", "typename"], properties={
            "url": _str_prop("WFS service URL"),
            "typename": _str_prop("Feature type name"),
            "crs": _str_prop("CRS (default: EPSG:4326)"),
            "max_features": _int_prop("Max features to load (default: 1000)"),
            "filter": _str_prop("Optional CQL filter"),
            "layer_name": _str_prop("Optional layer name"),
        }),
        base_output({"layer_id": _str_prop(), "feature_count": _int_prop(), "crs": _str_prop()}),
        permissions=["qgis:web_gis:write"],
        verification=["layer_loaded"],
    )
    add(
        "qgis.web_gis.wmts_load", "qgis.web_gis",
        "Load WMTS (Web Map Tile Service) layer.",
        base_input(required=["url", "layer"], properties={
            "url": _str_prop("WMTS service URL"),
            "layer": _str_prop("Layer identifier"),
            "style": _str_prop("Style identifier"),
            "tile_matrix_set": _str_prop("Tile matrix set"),
            "format": _str_prop("Image format (default: image/png)"),
            "layer_name": _str_prop("Optional layer name"),
        }),
        base_output({"layer_id": _str_prop(), "crs": _str_prop()}),
        permissions=["qgis:web_gis:write"],
        verification=["layer_loaded"],
    )
    add(
        "qgis.web_gis.xyz_tiles", "qgis.web_gis",
        "Load XYZ tile layer (OSM, Google, etc.).",
        base_input(required=["url"], properties={
            "url": _str_prop("XYZ tile URL template (e.g., https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png)"),
            "zmin": _int_prop("Minimum zoom (default: 0)"),
            "zmax": _int_prop("Maximum zoom (default: 19)"),
            "attribution": _str_prop("Attribution text"),
            "layer_name": _str_prop("Optional layer name"),
        }),
        base_output({"layer_id": _str_prop(), "zmin": _int_prop(), "zmax": _int_prop()}),
        permissions=["qgis:web_gis:write"],
        verification=["layer_loaded"],
    )
    add(
        "qgis.web_gis.ogc_api", "qgis.web_gis",
        "Load OGC API - Features layer.",
        base_input(required=["url", "collection"], properties={
            "url": _str_prop("OGC API - Features base URL"),
            "collection": _str_prop("Collection identifier"),
            "crs": _str_prop("CRS (default: EPSG:4326)"),
            "limit": _int_prop("Features per page (default: 100)"),
            "filter": _str_prop("Optional CQL filter"),
            "layer_name": _str_prop("Optional layer name"),
        }),
        base_output({"layer_id": _str_prop(), "feature_count": _int_prop(), "crs": _str_prop()}),
        permissions=["qgis:web_gis:write"],
        verification=["layer_loaded"],
    )
    add(
        "qgis.web_gis.server_publish", "qgis.web_gis",
        "Publish layer/project to QGIS Server.",
        base_input(required=["project_path", "server_url"], properties={
            "project_path": _str_prop("QGIS project file path"),
            "server_url": _str_prop("QGIS Server URL"),
            "service_name": _str_prop("Service name"),
            "layers": _list_prop("Layer ids to publish", "string"),
            "overwrite": _bool_prop("Overwrite existing (default: false)"),
        }),
        base_output({"published": _bool_prop(), "service_url": _str_prop(), "layers_published": _int_prop()}),
        permissions=["qgis:web_gis:write"],
        verification=["published"],
    )
    add(
        "qgis.web_gis.getcapabilities", "qgis.web_gis",
        "Get capabilities document from OGC service.",
        base_input(required=["url", "service"], properties={
            "url": _str_prop("Service URL"),
            "service": _str_prop("Service type: WMS|WFS|WMTS|WCS|OGC_API"),
            "version": _str_prop("Service version (default: latest)"),
        }),
        base_output({"capabilities": {"type": "object"}, "layers": _list_prop("available layers", "string")}),
        permissions=["qgis:web_gis:read"],
        verification=["capabilities_retrieved"],
    )
    add(
        "qgis.web_gis.getfeature", "qgis.web_gis",
        "Get features from WFS/OGC API service.",
        base_input(required=["url", "typename"], properties={
            "url": _str_prop("Service URL"),
            "typename": _str_prop("Feature type / collection name"),
            "filter": _str_prop("Optional CQL filter"),
            "max_features": _int_prop("Max features (default: 1000)"),
            "properties": _list_prop("Property names to return", "string"),
        }),
        base_output({"features": _list_prop("features", "object"), "count": _int_prop()}),
        permissions=["qgis:web_gis:read"],
        verification=["features_retrieved"],
    )
    add(
        "qgis.web_gis.getcoverage", "qgis.web_gis",
        "Get coverage from WCS service.",
        base_input(required=["url", "coverage"], properties={
            "url": _str_prop("WCS service URL"),
            "coverage": _str_prop("Coverage identifier"),
            "bbox": _list_prop("Bounding box [xmin, ymin, xmax, ymax]", "number"),
            "crs": _str_prop("CRS"),
            "format": _str_prop("Output format (default: GeoTIFF)"),
            "resolution": _list_prop("Resolution [x, y]", "number"),
        }),
        base_output({"coverage_layer_id": _str_prop(), "width": _int_prop(), "height": _int_prop()}),
        permissions=["qgis:web_gis:read"],
        verification=["coverage_retrieved"],
    )
    add(
        "qgis.web_gis.tile_cache", "qgis.web_gis",
        "Manage tile cache for web services.",
        base_input(required=["action"], properties={
            "action": _str_prop("Action: create|clear|stats|preload"),
            "layer_ids": _list_prop("Layer ids for cache operations", "string"),
            "bbox": _list_prop("Bounding box for preload", "number"),
            "zoom_levels": _list_prop("Zoom levels for preload", "integer"),
        }),
        base_output({"status": _str_prop(), "cache_size_mb": _num_prop(), "tiles_cached": _int_prop()}),
        permissions=["qgis:web_gis:write"],
        verification=["cache_managed"],
    )

    # ---- qgis.field_data (8 tools) ----
    add(
        "qgis.field_data.qfield_sync", "qgis.field_data",
        "Sync project with QField/QFieldCloud.",
        base_input(required=["project_path"], properties={
            "project_path": _str_prop("QGIS project file path"),
            "cloud_project_id": _str_prop("QFieldCloud project ID"),
            "direction": _str_prop("Direction: push|pull|both (default: both)"),
            "offline_editing": _bool_prop("Enable offline editing (default: true)"),
        }),
        base_output({"synced": _bool_prop(), "changes_pushed": _int_prop(), "changes_pulled": _int_prop()}),
        permissions=["qgis:field_data:write"],
        verification=["sync_completed"],
    )
    add(
        "qgis.field_data.mergin_sync", "qgis.field_data",
        "Sync project with Mergin Maps.",
        base_input(required=["project_path"], properties={
            "project_path": _str_prop("QGIS project file path"),
            "mergin_project": _str_prop("Mergin project name (namespace/project)"),
            "direction": _str_prop("Direction: push|pull|both (default: both)"),
        }),
        base_output({"synced": _bool_prop(), "changes_pushed": _int_prop(), "changes_pulled": _int_prop()}),
        permissions=["qgis:field_data:write"],
        verification=["sync_completed"],
    )
    add(
        "qgis.field_data.gps_track", "qgis.field_data",
        "Import GPS track as layer.",
        base_input(required=["file_path"], properties={
            "file_path": _str_prop("GPS file path (GPX, TCX, FIT, NMEA)"),
            "layer_name": _str_prop("Optional layer name"),
            "split_tracks": _bool_prop("Split into separate tracks (default: true)"),
            "elevation_mode": _str_prop("Elevation: gps|dem|none (default: gps)"),
        }),
        base_output({"layer_id": _str_prop(), "track_count": _int_prop(), "point_count": _int_prop()}),
        permissions=["qgis:field_data:write"],
        verification=["track_imported"],
    )
    add(
        "qgis.field_data.offline_package", "qgis.field_data",
        "Create offline editing package.",
        base_input(required=["project_path", "output_path"], properties={
            "project_path": _str_prop("QGIS project file path"),
            "output_path": _str_prop("Output package path (.qgs or directory)"),
            "area_of_interest": _list_prop("AOI extent [xmin, ymin, xmax, ymax]", "number"),
            "layers": _list_prop("Layer ids to include (default: all)", "string"),
            "include_rasters": _bool_prop("Include raster layers (default: true)"),
        }),
        base_output({"package_created": _bool_prop(), "output_path": _str_prop(), "size_mb": _num_prop()}),
        permissions=["qgis:field_data:write"],
        verification=["package_created"],
    )
    add(
        "qgis.field_data.feature_form", "qgis.field_data",
        "Configure feature form for field data collection.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Vector layer id"),
            "form_layout": _str_prop("Layout: dragdrop|autogenerated|ui_file (default: dragdrop)"),
            "fields_config": _list_prop("Field configuration: [{name, alias, widget, constraints}]", "object"),
            "relation_widgets": _list_prop("Relation widget config", "object"),
        }),
        base_output({"form_configured": _bool_prop(), "layer_id": _str_prop()}),
        permissions=["qgis:field_data:write"],
        verification=["form_configured"],
    )
    add(
        "qgis.field_data.attachment", "qgis.field_data",
        "Manage attachments (photos, docs) for features.",
        base_input(required=["layer_id", "action"], properties={
            "layer_id": _str_prop("Vector layer id"),
            "action": _str_prop("Action: add|remove|list|configure"),
            "feature_id": _int_prop("Feature id (for add/remove)"),
            "file_path": _str_prop("File path (for add)"),
            "attachment_type": _str_prop("Type: photo|document|audio|video"),
        }),
        base_output({"attachments": _list_prop("attachments"), "count": _int_prop()}),
        permissions=["qgis:field_data:write"],
        verification=["attachments_managed"],
    )
    add(
        "qgis.field_data.survey_design", "qgis.field_data",
        "Design survey/field data collection form.",
        base_input(required=["project_path", "survey_name"], properties={
            "project_path": _str_prop("QGIS project file path"),
            "survey_name": _str_prop("Survey name"),
            "layers": _list_prop("Layer configurations", "object"),
            "theme": _str_prop("UI theme: light|dark|auto (default: auto)"),
            "offline_capable": _bool_prop("Enable offline (default: true)"),
        }),
        base_output({"survey_created": _bool_prop(), "survey_name": _str_prop(), "layer_count": _int_prop()}),
        permissions=["qgis:field_data:write"],
        verification=["survey_created"],
    )
    add(
        "qgis.field_data.data_review", "qgis.field_data",
        "Review and validate collected field data.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Vector layer id with collected data"),
            "validation_rules": _list_prop("Validation rules", "object"),
            "auto_fix": _bool_prop("Auto-fix simple issues (default: false)"),
        }),
        base_output({"reviewed": _bool_prop(), "issues_found": _int_prop(), "issues_fixed": _int_prop(), "issues": _list_prop("issues", "object")}),
        permissions=["qgis:field_data:read"],
        verification=["data_reviewed"],
    )

    # ---- qgis.automation (10 tools) ----
    add(
        "qgis.automation.model_create", "qgis.automation",
        "Create Processing model (.model3) from parameters.",
        base_input(required=["model_name", "steps"], properties={
            "model_name": _str_prop("Model name"),
            "group": _str_prop("Model group"),
            "steps": _list_prop("Model steps: [{algorithm, parameters, dependencies}]", "object"),
            "inputs": _list_prop("Model inputs", "object"),
            "outputs": _list_prop("Model outputs", "object"),
        }),
        base_output({"model_created": _bool_prop(), "model_path": _str_prop(), "algorithm_id": _str_prop()}),
        permissions=["qgis:automation:write"],
        verification=["model_created"],
    )
    add(
        "qgis.automation.model_run", "qgis.automation",
        "Run Processing model with parameters.",
        base_input(required=["model_id", "parameters"], properties={
            "model_id": _str_prop("Model algorithm id"),
            "parameters": _list_prop("Model parameters", "object"),
            "context": _str_prop("Execution context: gui|batch|script (default: script)"),
        }),
        base_output({"outputs": {"type": "object"}, "execution_time_ms": _int_prop()}),
        permissions=["qgis:automation:write"],
        verification=["model_executed"],
    )
    add(
        "qgis.automation.model_export", "qgis.automation",
        "Export Processing model to file.",
        base_input(required=["model_id", "file_path"], properties={
            "model_id": _str_prop("Model algorithm id"),
            "file_path": _str_prop("Output file path (.model3)"),
        }),
        base_output({"exported": _bool_prop(), "file_path": _str_prop()}),
        permissions=["qgis:automation:read"],
        verification=["model_exported"],
    )
    add(
        "qgis.automation.model_import", "qgis.automation",
        "Import Processing model from file.",
        base_input(required=["file_path"], properties={
            "file_path": _str_prop("Model file path (.model3)"),
            "overwrite": _bool_prop("Overwrite existing (default: false)"),
        }),
        base_output({"imported": _bool_prop(), "model_id": _str_prop(), "model_name": _str_prop()}),
        permissions=["qgis:automation:write"],
        verification=["model_imported"],
    )
    add(
        "qgis.automation.batch_process", "qgis.automation",
        "Run batch processing for algorithm over multiple inputs.",
        base_input(required=["algorithm", "parameters_list"], properties={
            "algorithm": _str_prop("Algorithm id"),
            "parameters_list": _list_prop("List of parameter sets", "object"),
            "parallel": _bool_prop("Run in parallel (default: false)"),
            "max_concurrent": _int_prop("Max concurrent (default: 4)"),
        }),
        base_output({"completed": _int_prop(), "failed": _int_prop(), "results": _list_prop("results", "object")}),
        permissions=["qgis:automation:write"],
        verification=["batch_completed"],
    )
    add(
        "qgis.automation.batch_dialog", "qgis.automation",
        "Configure batch processing dialog.",
        base_input(required=["algorithm"], properties={
            "algorithm": _str_prop("Algorithm id"),
            "input_layers": _list_prop("Input layer ids for batch", "string"),
            "output_pattern": _str_prop("Output naming pattern"),
            "fixed_parameters": _list_prop("Fixed parameters for all runs", "object"),
        }),
        base_output({"configured": _bool_prop(), "run_count": _int_prop()}),
        permissions=["qgis:automation:write"],
        verification=["batch_configured"],
    )
    add(
        "qgis.automation.history", "qgis.automation",
        "Get processing history.",
        base_input(properties={
            "limit": _int_prop("Max history entries (default: 50)"),
            "algorithm": _str_prop("Filter by algorithm id"),
            "since": _str_prop("Filter since timestamp (ISO format)"),
        }),
        base_output({"history": _list_prop("history entries", "object"), "count": _int_prop()}),
        permissions=["qgis:automation:read"],
        verification=["history_retrieved"],
    )
    add(
        "qgis.automation.model_validate", "qgis.automation",
        "Validate Processing model for errors.",
        base_input(required=["model_id"], properties={
            "model_id": _str_prop("Model algorithm id"),
            "test_data": _list_prop("Optional test data paths", "string"),
        }),
        base_output({"valid": _bool_prop(), "errors": _list_prop("errors"), "warnings": _list_prop("warnings")}),
        permissions=["qgis:automation:read"],
        verification=["model_validated"],
    )
    add(
        "qgis.automation.model_document", "qgis.automation",
        "Generate documentation for Processing model.",
        base_input(required=["model_id"], properties={
            "model_id": _str_prop("Model algorithm id"),
            "format": _str_prop("Output format: markdown|html|pdf (default: markdown)"),
            "include_diagram": _bool_prop("Include flow diagram (default: true)"),
        }),
        base_output({"documentation": _str_prop(), "format": _str_prop()}),
        permissions=["qgis:automation:read"],
        verification=["documentation_generated"],
    )
    add(
        "qgis.automation.script_run", "qgis.automation",
        "Run PyQGIS script from file or string.",
        base_input(required=["script"], properties={
            "script": _str_prop("Script content or file path"),
            "parameters": _list_prop("Script parameters", "object"),
            "output_capture": _bool_prop("Capture output (default: true)"),
        }),
        base_output({"executed": _bool_prop(), "result": {"type": "object"}, "output": _str_prop(), "execution_time_ms": _int_prop()}),
        permissions=["qgis:automation:write"],
        verification=["script_executed"],
    )

    # ---- qgis.quality (15 tools) ----
    add(
        "qgis.quality.topology_check", "qgis.quality",
        "Check vector topology (dangles, intersections, gaps, overlaps).",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Vector layer id"),
            "checks": _list_prop("Checks: dangles|intersections|gaps|overlaps|duplicates|all (default: all)", "string"),
            "tolerance": _num_prop("Snapping tolerance (default: 0.001)"),
            "output_layer": _str_prop("Optional output layer for errors"),
        }),
        base_output({"errors_found": _int_prop(), "error_layer_id": _str_prop(), "error_types": _list_prop("error types", "string")}),
        permissions=["qgis:quality:read"],
        verification=["topology_checked"],
    )
    add(
        "qgis.quality.geometry_valid", "qgis.quality",
        "Validate geometry validity and fix errors.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Vector layer id"),
            "fix": _bool_prop("Auto-fix invalid geometries (default: true)"),
            "method": _str_prop("Fix method: buffer0|makevalid|structure|linework (default: makevalid)"),
            "output_layer": _str_prop("Optional output layer name"),
        }),
        base_output({"valid": _bool_prop(), "invalid_count": _int_prop(), "fixed_count": _int_prop(), "output_layer_id": _str_prop()}),
        permissions=["qgis:quality:write"],
        verification=["geometry_validated"],
    )
    add(
        "qgis.quality.duplicates", "qgis.quality",
        "Find duplicate features (geometry and/or attributes).",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Vector layer id"),
            "geometry_only": _bool_prop("Compare geometry only (default: false)"),
            "attributes": _list_prop("Attribute fields to compare (default: all)"),
            "output_layer": _str_prop("Optional output layer for duplicates"),
        }),
        base_output({"duplicates_found": _int_prop(), "duplicate_groups": _int_prop(), "output_layer_id": _str_prop()}),
        permissions=["qgis:quality:read"],
        verification=["duplicates_found"],
    )
    add(
        "qgis.quality.self_intersect", "qgis.quality",
        "Find self-intersections in polygons.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Polygon vector layer id"),
            "output_layer": _str_prop("Optional output layer for self-intersections"),
        }),
        base_output({"self_intersections": _int_prop(), "affected_features": _int_prop(), "output_layer_id": _str_prop()}),
        permissions=["qgis:quality:read"],
        verification=["self_intersections_found"],
    )
    add(
        "qgis.quality.gaps", "qgis.quality",
        "Find gaps between adjacent polygons.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Polygon vector layer id"),
            "tolerance": _num_prop("Gap tolerance (default: 0.001)"),
            "output_layer": _str_prop("Optional output layer for gaps"),
        }),
        base_output({"gaps_found": _int_prop(), "total_gap_area": _num_prop(), "output_layer_id": _str_prop()}),
        permissions=["qgis:quality:read"],
        verification=["gaps_found"],
    )
    add(
        "qgis.quality.overlaps", "qgis.quality",
        "Find overlaps between polygons.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Polygon vector layer id"),
            "output_layer": _str_prop("Optional output layer for overlaps"),
        }),
        base_output({"overlaps_found": _int_prop(), "total_overlap_area": _num_prop(), "output_layer_id": _str_prop()}),
        permissions=["qgis:quality:read"],
        verification=["overlaps_found"],
    )
    add(
        "qgis.quality.attr_rules", "qgis.quality",
        "Validate attribute rules (constraints, expressions).",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Vector layer id"),
            "rules": _list_prop("Rules: [{field, expression, message}]", "object"),
            "output_layer": _str_prop("Optional output layer for violations"),
        }),
        base_output({"violations": _int_prop(), "rule_results": _list_prop("rule results", "object"), "output_layer_id": _str_prop()}),
        permissions=["qgis:quality:read"],
        verification=["rules_validated"],
    )
    add(
        "qgis.quality.domain_check", "qgis.quality",
        "Check attribute values against domain/coded values.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Vector layer id"),
            "domains": _list_prop("Domain definitions: [{field, values: [...], description}]", "object"),
            "output_layer": _str_prop("Optional output layer for violations"),
        }),
        base_output({"violations": _int_prop(), "invalid_values": _list_prop("invalid values", "object"), "output_layer_id": _str_prop()}),
        permissions=["qgis:quality:read"],
        verification=["domains_checked"],
    )
    add(
        "qgis.quality.completeness", "qgis.quality",
        "Check data completeness (missing values, required fields).",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Vector layer id"),
            "required_fields": _list_prop("Required field names", "string"),
            "nullable_fields": _list_prop("Fields that can be null", "string"),
            "output_layer": _str_prop("Optional output layer for incomplete features"),
        }),
        base_output({"incomplete_features": _int_prop(), "missing_counts": _list_prop("per field", "integer"), "output_layer_id": _str_prop()}),
        permissions=["qgis:quality:read"],
        verification=["completeness_checked"],
    )
    add(
        "qgis.quality.consistency", "qgis.quality",
        "Check cross-layer consistency (referential integrity).",
        base_input(required=["layer_id", "reference_layer", "key_field", "ref_field"], properties={
            "layer_id": _str_prop("Layer to check"),
            "reference_layer": _str_prop("Reference layer"),
            "key_field": _str_prop("Key field in layer"),
            "ref_field": _str_prop("Reference field in reference layer"),
            "output_layer": _str_prop("Optional output layer for orphans"),
        }),
        base_output({"orphans": _int_prop(), "orphan_features": _list_prop("orphan fids", "integer"), "output_layer_id": _str_prop()}),
        permissions=["qgis:quality:read"],
        verification=["consistency_checked"],
    )
    add(
        "qgis.quality.accuracy", "qgis.quality",
        "Check positional accuracy against reference.",
        base_input(required=["layer_id", "reference_layer"], properties={
            "layer_id": _str_prop("Layer to check"),
            "reference_layer": _str_prop("Reference layer (higher accuracy)"),
            "match_field": _str_prop("Field to match features"),
            "tolerance": _num_prop("Positional tolerance (default: 1.0)"),
            "output_layer": _str_prop("Optional output layer for accuracy"),
        }),
        base_output({"mean_error": _num_prop(), "rmse": _num_prop(), "max_error": _num_prop(), "features_within_tolerance": _int_prop(), "output_layer_id": _str_prop()}),
        permissions=["qgis:quality:read"],
        verification=["accuracy_checked"],
    )
    add(
        "qgis.quality.precision", "qgis.quality",
        "Check coordinate precision and snapping.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Vector layer id"),
            "precision": _int_prop("Decimal places precision (default: 6)"),
            "snap_tolerance": _num_prop("Snapping tolerance (default: 0.0001)"),
            "output_layer": _str_prop("Optional output layer for snapped geometries"),
        }),
        base_output({"low_precision_features": _int_prop(), "snapped_features": _int_prop(), "output_layer_id": _str_prop()}),
        permissions=["qgis:quality:write"],
        verification=["precision_checked"],
    )
    add(
        "qgis.quality.lineage", "qgis.quality",
        "Track data lineage and provenance.",
        base_input(required=["layer_id"], properties={
            "layer_id": _str_prop("Layer id"),
            "action": _str_prop("Action: record|view|export"),
            "lineage_record": _list_prop("Lineage record: {source, process, timestamp, parameters}", "object"),
        }),
        base_output({"lineage": _list_prop("lineage records", "object"), "exported": _bool_prop()}),
        permissions=["qgis:quality:read"],
        verification=["lineage_tracked"],
    )
    add(
        "qgis.quality.metadata", "qgis.quality",
        "Validate and manage metadata (ISO 19115/19139).",
        base_input(required=["layer_id", "action"], properties={
            "layer_id": _str_prop("Layer id"),
            "action": _str_prop("Action: validate|create|edit|export|import"),
            "metadata_standard": _str_prop("Standard: iso19115|iso19139|fgdc|inspire (default: iso19115)"),
            "metadata_file": _str_prop("Metadata file path (for import/export)"),
        }),
        base_output({"valid": _bool_prop(), "metadata": {"type": "object"}, "errors": _list_prop("validation errors", "string")}),
        permissions=["qgis:quality:read"],
        verification=["metadata_validated"],
    )
    add(
        "qgis.quality.report", "qgis.quality",
        "Generate quality assurance report.",
        base_input(required=["layer_ids", "checks"], properties={
            "layer_ids": _list_prop("Layer ids to include in report", "string"),
            "checks": _list_prop("Checks to run: all|topology|geometry|attributes|completeness|consistency|accuracy|precision", "string"),
            "format": _str_prop("Report format: json|html|pdf (default: json)"),
            "output_path": _str_prop("Optional output file path"),
        }),
        base_output({"report": {"type": "object"}, "summary": {"type": "object"}, "output_path": _str_prop()}),
        permissions=["qgis:quality:read"],
        verification=["report_generated"],
    )

    # ---- qgis.database / qgis.layout / qgis.workflow ----
    add(
        "qgis.database.info", "qgis.database",
        "List available spatial database connections and tables.",
        base_input(),
        base_output({"connections": _list_prop("database connections"),
                     "tables": _list_prop("tables")}),
        permissions=["qgis:database:read"],
    )
    add(
        "qgis.layout.info", "qgis.layout",
        "List available print layouts and their export status.",
        base_input(),
        base_output({"layouts": _list_prop("layouts"), "count": _int_prop()}),
        permissions=["qgis:layout:read"],
    )
    add(
        "qgis.workflow.execute", "qgis.workflow",
        "Execute a saved GIS workflow by id.",
        base_input(required=["workflow_id"], properties={"workflow_id": _str_prop()}),
        base_output({"ok": _bool_prop("value"), "job_id": _str_prop()}),
        permissions=["qgis:workflow:execute"],
    )

    # ---- qgis.agents / qgis.skills / qgis.verify / qgis.jobs / qgis.history ----
    add(
        "qgis.agents.list", "qgis.agents",
        "List all available built-in and custom agents.",
        base_input(),
        base_output({"agents": _list_prop("agents"), "count": _int_prop()}),
        permissions=["qgis:agents:read"],
    )
    add(
        "qgis.skills.list", "qgis.skills",
        "List all available skills and their validation status.",
        base_input(),
        base_output({"skills": _list_prop("skills"), "count": _int_prop()}),
        permissions=["qgis:skills:read"],
    )
    add(
        "qgis.verify.status", "qgis.verify",
        "Get verification status of the last operation.",
        base_input(required=["request_id"], properties={"request_id": _str_prop()}),
        base_output({"verification_state": _str_prop(), "details": {"type": "object"}}),
        permissions=["qgis:verify:read"],
    )
    add(
        "qgis.jobs.cancel", "qgis.jobs",
        "Cancel a running job by id.",
        base_input(required=["job_id"], properties={"job_id": _str_prop()}),
        base_output({"cancelled": _bool_prop("value"), "job_id": _str_prop()}),
        permissions=["qgis:jobs:write"],
    )
    add(
        "qgis.history.inspect", "qgis.history",
        "Inspect job/task history and events.",
        base_input(properties={"limit": _int_prop("Max records")}),
        base_output({"jobs": _list_prop("jobs")}),
        permissions=["qgis:history:read"],
    )

    # ---- qgis.plugins ----
    add(
        "qgis.plugins.list", "qgis.plugins",
        "Inspect installed QGIS plugins.",
        base_input(),
        base_output({"plugins": _list_prop("plugins")}),
        permissions=["qgis:read"],
    )

    # ---- qgis.approval ----
    add(
        "qgis.approval.grant", "qgis.approval",
        "Grant approval for a pending tool execution.",
        base_input(required=["approval_id"], properties={
            "approval_id": _str_prop("Approval ID from APPROVAL_REQUIRED error"),
            "granted_by": _str_prop("Identity of grantor (default: user)"),
        }),
        base_output({"granted": _bool_prop("value"), "approval_id": _str_prop()}),
        permissions=["qgis:approval:write"],
    )
    add(
        "qgis.approval.deny", "qgis.approval",
        "Deny approval for a pending tool execution.",
        base_input(required=["approval_id"], properties={
            "approval_id": _str_prop("Approval ID from APPROVAL_REQUIRED error"),
            "denied_by": _str_prop("Identity of denier (default: user)"),
            "reason": _str_prop("Optional reason for denial"),
        }),
        base_output({"denied": _bool_prop("value"), "approval_id": _str_prop()}),
        permissions=["qgis:approval:write"],
    )
    add(
        "qgis.approval.list", "qgis.approval",
        "List all pending approval requests.",
        base_input(),
        base_output({"pending": _list_prop("pending approvals"), "count": _int_prop()}),
        permissions=["qgis:approval:read"],
    )

    return r
