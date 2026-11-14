# Universal AI GIS Studio — Complete Tool Reference

**Version:** 1.0.0  
**Generated from:** `mcp_server/registry.py` (single source of truth)  
**Total Tools:** 35 across 17 namespaces

---

## Table of Contents

1. [qgis.system](#qgissystem) — System diagnostics
2. [qgis.project](#qgisproject) — Project management
3. [qgis.layers](#qgislayers) — Layer operations
4. [qgis.canvas](#qgiscanvas) — Map canvas inspection
5. [qgis.screen](#qgisscreen) — Screen capture
6. [qgis.cursor](#qgiscursor) — AI cursor control
7. [qgis.keyboard](#qgiskeyboard) — Keyboard input
8. [qgis.mouse](#qgismouse) — Mouse control
9. [qgis.window / qgis.dialog](#qgiswindow--qgisdialog) — Window & dialog inspection
10. [qgis.algorithms](#qgisalgorithms) — Processing algorithms
11. [qgis.georeference / qgis.gcp](#qgisgeoreference--qgisgcp) — Georeferencing & GCPs
12. [qgis.raster / qgis.vector / qgis.spatial](#qgisraster--qgisvector--qgisspatial) — Data info
13. [qgis.database / qgis.layout / qgis.workflow](#qgisdatabase--qgislayout--qgisworkflow) — Advanced GIS
14. [qgis.agents / qgis.skills / qgis.verify / qgis.jobs / qgis.history](#qgisagents--qgisskills--qgisverify--qgisjobs--qgishistory) — Agents & monitoring
15. [qgis.plugins](#qgisplugins) — Plugin inspection
16. [Common Patterns](#common-patterns)
17. [Permission Model](#permission-model)

---

## qgis.system

### `qgis.system.inspect`

**Description:** Inspect the QGIS installation: version, GDAL version, Python version, bridge status.

**Permissions:** `qgis:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "qgis_version": {"type": "string", "description": "QGIS version"},
    "gdal_version": {"type": "string", "description": "GDAL version"},
    "python_version": {"type": "string", "description": "Python version"},
    "bridge_connected": {"type": "boolean", "description": "Whether the bridge is connected"}
  },
  "required": ["qgis_version", "gdal_version", "python_version", "bridge_connected"],
  "additionalProperties": false
}
```

**Example Response:**
```json
{
  "qgis_version": "4.2.3",
  "gdal_version": "3.13.3",
  "python_version": "3.12.15",
  "bridge_connected": true
}
```

**Verification Rules:** None (read-only)

---

### `qgis.system.health`

**Description:** Check health of the QGIS Bridge and active QGIS instance.

**Permissions:** `qgis:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "qgis_connected": {"type": "boolean", "description": "QGIS connection status"},
    "project_open": {"type": "boolean", "description": "Whether a project is open"},
    "layer_count": {"type": "integer", "description": "Number of loaded layers"},
    "main_thread": {"type": "boolean", "description": "Running on main thread"}
  },
  "required": ["qgis_connected", "project_open", "layer_count", "main_thread"],
  "additionalProperties": false
}
```

**Example Response:**
```json
{
  "qgis_connected": true,
  "project_open": true,
  "layer_count": 5,
  "main_thread": true
}
```

---

## qgis.project

### `qgis.project.open`

**Description:** Open a QGIS project file (.qgz/.qgs).

**Permissions:** `qgis:project:write`

**Requires Approval:** Yes

**Timeout:** 300 seconds

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "path": {"type": "string", "description": "Path to the project file"}
  },
  "required": ["path"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "project_file": {"type": "string"},
    "project_title": {"type": "string"},
    "crs": {"type": "string"},
    "layer_count": {"type": "integer"}
  },
  "required": ["project_file", "project_title", "crs", "layer_count"],
  "additionalProperties": false
}
```

**Verification Rules:** `file_exists`, `project_valid`

**Example:**
```json
{
  "path": "D:/projects/my_project.qgz"
}
```

---

### `qgis.project.save`

**Description:** Save the current QGIS project.

**Permissions:** `qgis:project:write`

**Requires Approval:** No

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "path": {"type": "string", "description": "Optional path to save to (save-as)"}
  },
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "saved": {"type": "boolean"},
    "project_file": {"type": "string"}
  },
  "required": ["saved", "project_file"],
  "additionalProperties": false
}
```

**Verification Rules:** `file_written`

---

### `qgis.project.inspect`

**Description:** Inspect the current QGIS project: metadata, CRS, layers.

**Permissions:** `qgis:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "project_file": {"type": "string"},
    "project_title": {"type": "string"},
    "crs": {"type": "string"},
    "layer_count": {"type": "integer"},
    "layers": {"type": "array", "description": "layers", "items": {"type": "object"}}
  },
  "required": ["project_file", "project_title", "crs", "layer_count", "layers"],
  "additionalProperties": false
}
```

---

## qgis.layers

### `qgis.layers.inspect`

**Description:** Inspect all loaded layers: id, name, type, validity, CRS, extent, fields.

**Permissions:** `qgis:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "layers": {"type": "array", "description": "layer list", "items": {"type": "object"}},
    "count": {"type": "integer"}
  },
  "required": ["layers", "count"],
  "additionalProperties": false
}
```

**Layer Object Properties:**
- `id`: Layer ID (string)
- `name`: Layer name (string)
- `type`: `vector` or `raster` (string)
- `valid`: Boolean
- `crs`: CRS authid (string, e.g., "EPSG:4326")
- `extent`: `[xmin, ymin, xmax, ymax]` (array of numbers)
- `feature_count`: Integer (vector only)
- `fields`: Array of field names (vector only)
- `geometry_type`: `Point`, `LineString`, `Polygon`, etc. (vector only)
- `band_count`: Integer (raster only)

---

### `qgis.layers.load`

**Description:** Load a GIS dataset (vector or raster) into the project.

**Permissions:** `qgis:layer:write`

**Requires Approval:** No

**Verification Rules:** `file_exists`, `layer_valid`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "path": {"type": "string", "description": "File path to load"},
    "layer_name": {"type": "string", "description": "Optional layer name"},
    "provider": {"type": "string", "description": "Provider hint: vector|raster"}
  },
  "required": ["path"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "id": {"type": "string"},
    "name": {"type": "string"},
    "type": {"type": "string"},
    "valid": {"type": "boolean"},
    "crs": {"type": "string"}
  },
  "required": ["id", "name", "type", "valid", "crs"],
  "additionalProperties": false
}
```

**Supported Formats:**
- Vector: `.gpkg`, `.shp`, `.geojson`, `.kml`, `.gml`, `.sqlite`, `.tab`
- Raster: `.tif`, `.tiff`, `.geotiff`, `.img`, `.asc`, `.grd`, `.nc`, `.hdf`

**Example:**
```json
{
  "path": "D:/data/parcels.gpkg",
  "layer_name": "Parcels 2024",
  "provider": "vector"
}
```

---

### `qgis.layers.remove`

**Description:** Remove a layer from the project by layer id.

**Permissions:** `qgis:layer:write`

**Requires Approval:** Yes (destructive)

**Verification Rules:** `layer_removed`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "layer_id": {"type": "string", "description": "Layer id to remove"}
  },
  "required": ["layer_id"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "removed": {"type": "boolean"},
    "id": {"type": "string"}
  },
  "required": ["removed", "id"],
  "additionalProperties": false
}
```

---

## qgis.canvas

### `qgis.canvas.inspect`

**Description:** Inspect the map canvas: extent, CRS, scale, rotation, visible layers.

**Permissions:** `qgis:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "extent": {"type": "array", "description": "canvas extent", "items": {"type": "number"}},
    "crs": {"type": "string"},
    "scale": {"type": "number"},
    "rotation": {"type": "number"},
    "layers": {"type": "array", "description": "layer ids", "items": {"type": "string"}}
  },
  "required": ["extent", "crs", "scale", "rotation", "layers"],
  "additionalProperties": false
}
```

---

## qgis.screen

### `qgis.screen.capture`

**Description:** Capture a screenshot of the QGIS map canvas. Returns PNG as base64.

**Permissions:** `qgis:screen:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "image_base64": {"type": "string", "description": "PNG base64"},
    "width": {"type": "integer"},
    "height": {"type": "integer"},
    "format": {"type": "string"}
  },
  "required": ["image_base64", "width", "height", "format"],
  "additionalProperties": false
}
```

**Note:** The base64 string can be saved as a PNG file:
```python
import base64
with open("screenshot.png", "wb") as f:
    f.write(base64.b64decode(result["image_base64"]))
```

---

## qgis.cursor

### `qgis.cursor.move`

**Description:** Move the AI cursor to a screen position.

**Permissions:** `qgis:cursor:write`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "x": {"type": "integer", "description": "Screen X"},
    "y": {"type": "integer", "description": "Screen Y"}
  },
  "required": ["x", "y"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "ok": {"type": "boolean", "description": "main thread"}
  },
  "required": ["ok"],
  "additionalProperties": false
}
```

---

### `qgis.cursor.click`

**Description:** Click at the current AI cursor position.

**Permissions:** `qgis:cursor:write`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "ok": {"type": "boolean", "description": "main thread"}
  },
  "required": ["ok"],
  "additionalProperties": false
}
```

---

### `qgis.cursor.drag`

**Description:** Drag from one screen position to another.

**Permissions:** `qgis:cursor:write`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "x1": {"type": "integer", "description": "Start X"},
    "y1": {"type": "integer", "description": "Start Y"},
    "x2": {"type": "integer", "description": "End X"},
    "y2": {"type": "integer", "description": "End Y"}
  },
  "required": ["x1", "y1", "x2", "y2"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "ok": {"type": "boolean", "description": "main thread"}
  },
  "required": ["ok"],
  "additionalProperties": false
}
```

---

## qgis.keyboard

### `qgis.keyboard.type`

**Description:** Type text into the focused QGIS control.

**Permissions:** `qgis:keyboard:write`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "text": {"type": "string", "description": "Text to type"}
  },
  "required": ["text"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "ok": {"type": "boolean", "description": "main thread"}
  },
  "required": ["ok"],
  "additionalProperties": false
}
```

---

### `qgis.keyboard.hotkey`

**Description:** Press a keyboard shortcut (comma-separated keys).

**Permissions:** `qgis:keyboard:write`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "keys": {"type": "string", "description": "Keys, e.g. ctrl,s"}
  },
  "required": ["keys"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "ok": {"type": "boolean", "description": "main thread"}
  },
  "required": ["ok"],
  "additionalProperties": false
}
```

**Examples:** `ctrl,s`, `ctrl+shift+n`, `f11`, `escape`

---

## qgis.mouse

### `qgis.mouse.scroll`

**Description:** Scroll the mouse wheel at the current position.

**Permissions:** `qgis:mouse:write`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "delta": {"type": "integer", "description": "Scroll delta"}
  },
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "ok": {"type": "boolean", "description": "main thread"}
  },
  "required": ["ok"],
  "additionalProperties": false
}
```

---

## qgis.window / qgis.dialog

### `qgis.window.inspect`

**Description:** Inspect the QGIS main window: title, size, state.

**Permissions:** `qgis:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "title": {"type": "string"},
    "size": {"type": "array", "description": "size", "items": {"type": "number"}}
  },
  "required": ["title", "size"],
  "additionalProperties": false
}
```

---

### `qgis.dialog.inspect`

**Description:** Inspect open QGIS dialogs.

**Permissions:** `qgis:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "dialogs": {"type": "array", "description": "open dialogs", "items": {"type": "object"}}
  },
  "required": ["dialogs"],
  "additionalProperties": false
}
```

**Dialog Object Properties:**
- `title`: Dialog window title
- `object_name`: Qt object name
- `geometry`: `[x, y, width, height]`
- `is_modal`: Boolean

---

## qgis.algorithms

### `qgis.algorithms.discover`

**Description:** Discover installed QGIS Processing algorithms (dynamic, version-aware).

**Permissions:** `qgis:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "algorithms": {"type": "array", "description": "algorithms", "items": {"type": "object"}},
    "count": {"type": "integer"}
  },
  "required": ["algorithms", "count"],
  "additionalProperties": false
}
```

**Algorithm Object Properties:**
- `id`: Algorithm ID (e.g., `native:buffer`)
- `name`: Display name
- `provider`: Provider name
- `description`: Short description
- `parameters`: Array of parameter definitions
- `outputs`: Array of output definitions

---

### `qgis.algorithms.execute`

**Description:** Execute a QGIS Processing algorithm by id with parameters.

**Permissions:** `qgis:algorithm:execute`

**Requires Approval:** No

**Verification Rules:** `output_exists`, `output_valid`

**Timeout:** 300 seconds (configurable per algorithm)

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "algorithm": {"type": "string", "description": "Algorithm id, e.g. native:buffer"},
    "parameters": {"type": "object", "description": "Algorithm parameters"}
  },
  "required": ["algorithm"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "outputs": {"type": "object"},
    "algorithm": {"type": "string"}
  },
  "required": ["outputs", "algorithm"],
  "additionalProperties": false
}
```

**Common Algorithms & Parameters:**

| Algorithm | Key Parameters |
|-----------|----------------|
| `native:buffer` | `INPUT`, `DISTANCE`, `SEGMENTS`, `END_CAP_STYLE`, `JOIN_STYLE`, `MITER_LIMIT`, `DISSOLVE`, `OUTPUT` |
| `native:clip` | `INPUT`, `OVERLAY`, `OUTPUT` |
| `native:dissolve` | `INPUT`, `FIELD`, `OUTPUT` |
| `native:reprojectlayer` | `INPUT`, `TARGET_CRS`, `OUTPUT` |
| `native:joinattributesbylocation` | `INPUT`, `JOIN`, `PREDICATE`, `JOIN_FIELDS`, `OUTPUT` |
| `qgis:rastercalculator` | `EXPRESSION`, `LAYERS`, `CELLSIZE`, `EXTENT`, `OUTPUT` |
| `gdal:warpreproject` | `INPUT`, `TARGET_CRS`, `RESAMPLING`, `OUTPUT` |
| `native:polygonize` | `INPUT`, `FIELD`, `OUTPUT` |
| `native:centroids` | `INPUT`, `ALL_PARTS`, `OUTPUT` |

**Example: Buffer**
```json
{
  "algorithm": "native:buffer",
  "parameters": {
    "INPUT": "parcels_abc123",
    "DISTANCE": 100,
    "SEGMENTS": 5,
    "END_CAP_STYLE": 0,
    "JOIN_STYLE": 0,
    "MITER_LIMIT": 2,
    "DISSOLVE": false,
    "OUTPUT": "memory:"
  }
}
```

**Example: Reproject**
```json
{
  "algorithm": "native:reprojectlayer",
  "parameters": {
    "INPUT": "layer_id",
    "TARGET_CRS": "EPSG:3857",
    "OUTPUT": "memory:"
  }
}
```

---

## qgis.georeference / qgis.gcp

### `qgis.georeference.analyze`

**Description:** Analyze an image for georeferencing: dimensions, quality, landmarks, rotation.

**Permissions:** `qgis:georeference:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "image_path": {"type": "string", "description": "Path to the scanned map image"}
  },
  "required": ["image_path"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "dimensions": {"type": "array", "description": "dimensions", "items": {"type": "number"}},
    "quality_score": {"type": "number"},
    "landmarks": {"type": "array", "description": "landmarks", "items": {"type": "object"}},
    "rotation": {"type": "number"}
  },
  "required": ["dimensions", "quality_score", "landmarks", "rotation"],
  "additionalProperties": false
}
```

---

### `qgis.gcp.generate`

**Description:** Generate candidate Ground Control Points from image + reference data.

**Permissions:** `qgis:gcp:write`

**Verification Rules:** `confidence_scored`, `outliers_rejected`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "image_path": {"type": "string"},
    "reference_source": {"type": "string", "description": "Reference raster or dataset"}
  },
  "required": ["image_path", "reference_source"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "gcps": {"type": "array", "description": "gcp candidates", "items": {"type": "object"}},
    "count": {"type": "integer"}
  },
  "required": ["gcps", "count"],
  "additionalProperties": false
}
```

**GCP Candidate Properties:**
- `pixel_x`, `pixel_y`: Source image coordinates
- `map_x`, `map_y`: Reference map coordinates (target CRS)
- `confidence`: 0.0–1.0
- `description`: Human-readable description
- `method`: Detection method (ORB, SIFT, template, manual)

---

### `qgis.gcp.validate`

**Description:** Validate candidate GCPs: duplicates, outliers, distribution, residuals.

**Permissions:** `qgis:gcp:write`

**Verification Rules:** `min_point_count`, `residuals_checked`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "gcps": {"type": "array", "description": "gcps", "items": {"type": "object"}}
  },
  "required": ["gcps"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "valid_gcps": {"type": "array", "items": {"type": "object"}},
    "rmse": {"type": "number"},
    "rejected": {"type": "array", "items": {"type": "object"}}
  },
  "required": ["valid_gcps", "rmse", "rejected"],
  "additionalProperties": false
}
```

---

## qgis.raster / qgis.vector / qgis.spatial

### `qgis.raster.info`

**Description:** Get raster layer information (bands, dimensions, CRS, extent).

**Permissions:** `qgis:raster:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "layer_id": {"type": "string", "description": "Raster layer id"}
  },
  "required": ["layer_id"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "bands": {"type": "integer"},
    "width": {"type": "integer"},
    "height": {"type": "integer"},
    "crs": {"type": "string"},
    "extent": {"type": "array", "description": "extent", "items": {"type": "number"}}
  },
  "required": ["bands", "width", "height", "crs", "extent"],
  "additionalProperties": false
}
```

---

### `qgis.vector.info`

**Description:** Get vector layer information (feature count, fields, CRS, extent, geometry type).

**Permissions:** `qgis:vector:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "layer_id": {"type": "string", "description": "Vector layer id"}
  },
  "required": ["layer_id"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "feature_count": {"type": "integer"},
    "fields": {"type": "array", "description": "field names", "items": {"type": "string"}},
    "crs": {"type": "string"},
    "extent": {"type": "array", "description": "extent", "items": {"type": "number"}},
    "geometry_type": {"type": "string"}
  },
  "required": ["feature_count", "fields", "crs", "extent", "geometry_type"],
  "additionalProperties": false
}
```

---

### `qgis.spatial.info`

**Description:** Get available spatial analysis algorithms and their parameters.

**Permissions:** `qgis:spatial:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "algorithms": {"type": "array", "description": "spatial algorithms", "items": {"type": "object"}},
    "count": {"type": "integer"}
  },
  "required": ["algorithms", "count"],
  "additionalProperties": false
}
```

---

## qgis.database / qgis.layout / qgis.workflow

### `qgis.database.info`

**Description:** List available spatial database connections and tables.

**Permissions:** `qgis:database:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "connections": {"type": "array", "description": "database connections", "items": {"type": "object"}},
    "tables": {"type": "array", "description": "tables", "items": {"type": "object"}}
  },
  "required": ["connections", "tables"],
  "additionalProperties": false
}
```

---

### `qgis.layout.info`

**Description:** List available print layouts and their export status.

**Permissions:** `qgis:layout:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "layouts": {"type": "array", "description": "layouts", "items": {"type": "object"}},
    "count": {"type": "integer"}
  },
  "required": ["layouts", "count"],
  "additionalProperties": false
}
```

---

### `qgis.workflow.execute`

**Description:** Execute a saved GIS workflow by id.

**Permissions:** `qgis:workflow:execute`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "workflow_id": {"type": "string"}
  },
  "required": ["workflow_id"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "ok": {"type": "boolean"},
    "job_id": {"type": "string"}
  },
  "required": ["ok", "job_id"],
  "additionalProperties": false
}
```

---

## qgis.agents / qgis.skills / qgis.verify / qgis.jobs / qgis.history

### `qgis.agents.list`

**Description:** List all available built-in and custom agents.

**Permissions:** `qgis:agents:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "agents": {"type": "array", "description": "agents", "items": {"type": "object"}},
    "count": {"type": "integer"}
  },
  "required": ["agents", "count"],
  "additionalProperties": false
}
```

---

### `qgis.skills.list`

**Description:** List all available skills and their validation status.

**Permissions:** `qgis:skills:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "skills": {"type": "array", "description": "skills", "items": {"type": "object"}},
    "count": {"type": "integer"}
  },
  "required": ["skills", "count"],
  "additionalProperties": false
}
```

---

### `qgis.verify.status`

**Description:** Get verification status of the last operation.

**Permissions:** `qgis:verify:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "request_id": {"type": "string"}
  },
  "required": ["request_id"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "verification_state": {"type": "string"},
    "details": {"type": "object"}
  },
  "required": ["verification_state", "details"],
  "additionalProperties": false
}
```

**Verification States:** `SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`, `NEEDS_REVIEW`, `CANCELLED`

---

### `qgis.jobs.cancel`

**Description:** Cancel a running job by id.

**Permissions:** `qgis:jobs:write`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "job_id": {"type": "string"}
  },
  "required": ["job_id"],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "cancelled": {"type": "boolean"},
    "job_id": {"type": "string"}
  },
  "required": ["cancelled", "job_id"],
  "additionalProperties": false
}
```

---

### `qgis.history.inspect`

**Description:** Inspect job/task history and events.

**Permissions:** `qgis:history:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {
    "limit": {"type": "integer", "description": "Max records"}
  },
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "jobs": {"type": "array", "description": "jobs", "items": {"type": "object"}}
  },
  "required": ["jobs"],
  "additionalProperties": false
}
```

---

## qgis.plugins

### `qgis.plugins.list`

**Description:** Inspect installed QGIS plugins.

**Permissions:** `qgis:read`

**Input Schema:**
```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

**Output Schema:**
```json
{
  "type": "object",
  "properties": {
    "plugins": {"type": "array", "description": "plugins", "items": {"type": "object"}}
  },
  "required": ["plugins"],
  "additionalProperties": false
}
```

**Plugin Object Properties:**
- `name`: Plugin name
- `version`: Plugin version
- `description`: Description
- `enabled`: Boolean
- `path`: Installation path
- `is_builtin`: Boolean

---

## Common Patterns

### Standard Response Format

All tools return a standardized response envelope:

```json
{
  "request_id": "req_abc123def",
  "tool": "qgis.layers.load",
  "status": "ok",
  "verification_state": "SUCCESS",
  "result": { ... },
  "job_id": "job_xyz789",
  "timestamp": "2026-11-12T08:00:00Z"
}
```

### Error Response Format

```json
{
  "request_id": "req_abc123def",
  "tool": "qgis.layers.load",
  "status": "error",
  "verification_state": "FAILED",
  "result": {},
  "error": {
    "code": "LAYER_INVALID",
    "message": "Failed to load layer: not a valid vector dataset",
    "context": {"path": "D:/data/bad_file.shp"}
  },
  "job_id": null,
  "timestamp": "2026-11-12T08:00:00Z"
}
```

### Common Error Codes

| Code | Meaning |
|------|---------|
| `VALIDATION_ERROR` | Input schema validation failed |
| `UNAUTHORIZED` | Missing or invalid auth token |
| `NOT_FOUND` | Tool or resource not found |
| `LAYER_INVALID` | Layer failed to load or is invalid |
| `ALGORITHM_ERROR` | Processing algorithm execution failed |
| `BRIDGE_ERROR` | Bridge communication failed |
| `TIMEOUT` | Operation exceeded timeout |
| `APPROVAL_REQUIRED` | Operation requires user approval |
| `PERMISSION_DENIED` | Insufficient permissions |

---

## Permission Model

Permissions are hierarchical and checked at the bridge:

```
qgis:read                          # All read operations
qgis:project:write                 # Project open/save
qgis:layer:write                   # Load/remove layers
qgis:algorithm:execute             # Run processing algorithms
qgis:screen:read                   # Screenshots
qgis:cursor:write                  # AI cursor move/click/drag
qgis:keyboard:write                # Type/hotkeys
qgis:mouse:write                   # Mouse scroll
qgis:georeference:read             # Image analysis
qgis:gcp:write                     # GCP generate/validate
qgis:raster:read                   # Raster info
qgis:vector:read                   # Vector info
qgis:spatial:read                  # Spatial algorithms list
qgis:database:read                 # Database connections
qgis:layout:read                   # Layout list
qgis:workflow:execute              # Workflow execution
qgis:agents:read                   # Agent listing
qgis:skills:read                   # Skills listing
qgis:verify:read                   # Verification status
qgis:jobs:write                    # Job cancellation
qgis:history:read                  # History inspection
qgis:plugins:read                  # Plugin list (uses qgis:read)
```

**Approval-Required Operations:**
- `qgis.project.open` (loads new project, may lose unsaved work)
- `qgis.layers.remove` (destructive)
- Any operation with `require_approval: true` in registry

---

## Tool Discovery

List all available tools programmatically:

```python
# Via MCP client
tools = await client.list_tools()
for tool in tools:
    print(f"{tool.name}: {tool.description}")
    print(f"  Input: {json.dumps(tool.inputSchema, indent=2)}")
```

Or via HTTP:
```bash
curl -X POST http://127.0.0.1:8766/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

---

*Generated from `mcp_server/registry.py` — the single source of truth for all MCP tools.*