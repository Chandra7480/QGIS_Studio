"""Universal AI GIS Studio — Data Management Prompts.

Prompt templates for data loading, conversion, and management.
"""

from mcp_server.prompts.registry import PromptSpec, PromptArgument, PromptCategory


def register_data_prompts(registry) -> None:
    """Register all data management prompts."""

    # 1. Load Vector Layer
    registry.register(PromptSpec(
        name="load_vector_layer",
        description="Load a vector dataset (Shapefile, GeoPackage, GeoJSON, GPX, etc.) into QGIS.",
        category=PromptCategory.DATA,
        arguments=[
            PromptArgument("file_path", "Full path to vector file", required=True),
            PromptArgument("layer_name", "Custom layer name (default: filename)", default="", required=False),
            PromptArgument("encoding", "Character encoding", default="UTF-8", required=False, enum=["UTF-8", "ISO-8859-1", "Windows-1252", "System"]),
            PromptArgument("crs", "Force CRS (override file CRS)", default="", required=False),
        ],
        template="""Load vector layer in QGIS:

**File Path:** {file_path}
**Layer Name:** {layer_name} (auto from filename if empty)
**Encoding:** {encoding}
**Force CRS:** {crs} (empty = use file's CRS)

**Steps:**
1. Layer → Add Layer → Add Vector Layer
2. Source Type: File
3. Vector Dataset: {file_path}
4. Encoding: {encoding}
5. Add → Close
6. Optional: Right-click layer → Set CRS → {crs} (if forced)

**QGIS Tool:** "qgis.layers.load" (bridge tool)
**Supported:** Shapefile (.shp), GeoPackage (.gpkg), GeoJSON (.geojson), GPX, KML, DXF, CSV, etc.
**Use Case:** First step in any workflow - get data into project""",
        tags=["load", "vector", "shapefile", "geopackage", "geojson", "data"],
    ))

    # 2. Load Raster Layer
    registry.register(PromptSpec(
        name="load_raster_layer",
        description="Load a raster dataset (GeoTIFF, JPEG, PNG, ASCII Grid, etc.) into QGIS.",
        category=PromptCategory.DATA,
        arguments=[
            PromptArgument("file_path", "Full path to raster file", required=True),
            PromptArgument("layer_name", "Custom layer name (default: filename)", default="", required=False),
            PromptArgument("band", "Specific band to load (default: all)", default="", required=False),
            PromptArgument("crs", "Force CRS (override file CRS)", default="", required=False),
        ],
        template="""Load raster layer in QGIS:

**File Path:** {file_path}
**Layer Name:** {layer_name} (auto from filename if empty)
**Band:** {band} (empty = all bands)
**Force CRS:** {crs} (empty = use file's CRS)

**Steps:**
1. Layer → Add Layer → Add Raster Layer
2. Raster Dataset: {file_path}
3. Add → Close
4. Optional: Right-click layer → Set CRS → {crs} (if forced)
5. For multi-band: Right-click → Properties → Symbology → Set band rendering

**QGIS Tool:** "qgis.layers.load" (bridge tool)
**Supported:** GeoTIFF (.tif), JPEG (.jpg), PNG, ASCII Grid (.asc), DTED, ECW, JP2, etc.
**Use Case:** DEMs, satellite imagery, scanned maps, model outputs""",
        tags=["load", "raster", "geotiff", "dem", "imagery", "data"],
    ))

    # 3. Export Vector Layer
    registry.register(PromptSpec(
        name="export_vector_layer",
        description="Export a vector layer to various formats (Shapefile, GeoPackage, GeoJSON, CSV, etc.).",
        category=PromptCategory.DATA,
        arguments=[
            PromptArgument("layer_name", "Layer to export (name or ID)"),
            PromptArgument("output_path", "Full output file path"),
            PromptArgument("format", "Output format", default="ESRI Shapefile", required=False, enum=["ESRI Shapefile", "GeoPackage", "GeoJSON", "CSV", "KML", "GPX", "DXF", "MapInfo File"]),
            PromptArgument("crs", "Reproject to CRS on export", default="", required=False),
            PromptArgument("fields", "Fields to export (comma-separated, empty=all)", default="", required=False),
            PromptArgument("only_selected", "Export only selected features", default=False, required=False),
        ],
        template="""Export vector layer in QGIS:

**Layer:** {layer_name}
**Output:** {output_path}
**Format:** {format}
**Reproject CRS:** {crs} (empty = layer CRS)
**Fields:** {fields} (empty = all)
**Selected Only:** {only_selected}

**Steps:**
1. Right-click layer → Export → Save Features As
2. Format: {format}
3. File: {output_path}
4. CRS: {crs} (or layer CRS)
5. Fields: Select {fields} or all
6. Add "Only selected features" if {only_selected}
7. Encoding: UTF-8
8. OK

**QGIS Algorithm:** native:savefeatures (or gdal:convertformat)
**Use Case:** Data sharing, format conversion, subset extraction, archival""",
        tags=["export", "save as", "convert", "shapefile", "geopackage", "geojson", "data"],
    ))

    # 4. Export Raster Layer
    registry.register(PromptSpec(
        name="export_raster_layer",
        description="Export a raster layer to various formats with options.",
        category=PromptCategory.DATA,
        arguments=[
            PromptArgument("layer_name", "Raster layer to export (name or ID)"),
            PromptArgument("output_path", "Full output file path"),
            PromptArgument("format", "Output format", default="GTiff", required=False, enum=["GTiff", "AAIGrid", "JPEG", "PNG", "COG", "NetCDF", "ERDAS Imagine"]),
            PromptArgument("crs", "Reproject to CRS on export", default="", required=False),
            PromptArgument("resolution", "Output resolution (CRS units)", default="", required=False),
            PromptArgument("extent", "Output extent (xmin,ymin,xmax,ymax)", default="", required=False),
            PromptArgument("compression", "Compression (GTiff)", default="LZW", required=False, enum=["NONE", "LZW", "DEFLATE", "PACKBITS", "LERC"]),
        ],
        template="""Export raster layer in QGIS:

**Layer:** {layer_name}
**Output:** {output_path}
**Format:** {format}
**Reproject CRS:** {crs} (empty = layer CRS)
**Resolution:** {resolution} (empty = native)
**Extent:** {extent} (empty = full layer)
**Compression:** {compression}

**Steps:**
1. Right-click raster → Export → Save As
2. Format: {format}
3. File: {output_path}
4. CRS: {crs} (or layer CRS)
5. Resolution: {resolution}
6. Extent: {extent} or "Calculate from Layer"
7. Profile: {compression} (for GeoTIFF)
8. NoData: Use layer NoData
9. OK

**QGIS Algorithm:** gdal:translate
**Use Case:** Format conversion, compression, reprojection, tiling, COG creation""",
        tags=["export", "raster", "geotiff", "cog", "compression", "reproject", "data"],
    ))

    # 5. Reproject Layer
    registry.register(PromptSpec(
        name="reproject_layer",
        description="Reproject a vector or raster layer to a different CRS.",
        category=PromptCategory.DATA,
        arguments=[
            PromptArgument("layer_name", "Layer to reproject (name or ID)"),
            PromptArgument("target_crs", "Target CRS (e.g., EPSG:4326, EPSG:3857)", required=True),
            PromptArgument("output_name", "Name for reprojected layer", default="Reprojected", required=False),
            PromptArgument("operation", "Transform operation (optional, for datum shifts)", default="", required=False),
        ],
        template="""Reproject layer in QGIS:

**Layer:** {layer_name}
**Target CRS:** {target_crs}
**Output Layer:** {output_name}
**Transform Operation:** {operation} (auto if empty)

**Vector Steps:**
1. Run "native:reprojectlayer" algorithm:
   - INPUT: {layer_name}
   - TARGET_CRS: {target_crs}
   - OPERATION: {operation}
   - OUTPUT: {output_name}

**Raster Steps:**
1. Run "gdal:warpreproject" algorithm:
   - INPUT: {layer_name}
   - TARGET_CRS: {target_crs}
   - RESAMPLING: bilinear (continuous) / nearest (categorical)
   - OUTPUT: {output_name}

**Use Case:** Match project CRS, web mapping (EPSG:3857), GPS (EPSG:4326), analysis""",
        tags=["reproject", "transform", "crs", "warp", "data"],
    ))

    # 6. Join CSV to Vector
    registry.register(PromptSpec(
        name="join_csv",
        description="Join a CSV table to a vector layer by common field.",
        category=PromptCategory.DATA,
        arguments=[
            PromptArgument("vector_layer", "Target vector layer (name or ID)"),
            PromptArgument("csv_path", "Path to CSV file"),
            PromptArgument("vector_field", "Field in vector layer for join"),
            PromptArgument("csv_field", "Field in CSV for join"),
            PromptArgument("output_name", "Name for joined layer", default="Joined", required=False),
            PromptArgument("csv_encoding", "CSV encoding", default="UTF-8", required=False),
        ],
        template="""Join CSV to vector layer in QGIS:

**Vector Layer:** {vector_layer}
**CSV File:** {csv_path}
**Vector Join Field:** {vector_field}
**CSV Join Field:** {csv_field}
**Output Layer:** {output_name}
**CSV Encoding:** {csv_encoding}

**Steps:**
1. Layer → Add Layer → Add Delimited Text Layer
   - File: {csv_path}
   - Encoding: {csv_encoding}
   - CSV: Detected or Comma
   - Geometry: No geometry (attribute only)
   - Layer name: "csv_table"
2. Right-click {vector_layer} → Properties → Joins → Add Join
   - Join Layer: csv_table
   - Join Field: {csv_field}
   - Target Field: {vector_field}
   - Join Fields: Select desired or all
   - Custom prefix: "csv_"
3. Or use "native:joinattributestable" algorithm:
   - INPUT: {vector_layer}
   - FIELD: {vector_field}
   - INPUT_2: csv_table
   - FIELD_2: {csv_field}
   - OUTPUT: {output_name}

**Use Case:** Add census data, attributes from spreadsheet, lookup tables""",
        tags=["join", "csv", "attribute join", "table", "data"],
    ))

    # 7. Create Points from CSV/Table
    registry.register(PromptSpec(
        name="create_points_from_table",
        description="Create point layer from CSV with X/Y or Lat/Lon columns.",
        category=PromptCategory.DATA,
        arguments=[
            PromptArgument("csv_path", "Path to CSV file with coordinate columns"),
            PromptArgument("x_field", "X/Longitude column name", required=True),
            PromptArgument("y_field", "Y/Latitude column name", required=True),
            PromptArgument("crs", "CRS of coordinates", default="EPSG:4326", required=False),
            PromptArgument("layer_name", "Output layer name", default="Points_from_CSV", required=False),
            PromptArgument("encoding", "CSV encoding", default="UTF-8", required=False),
        ],
        template="""Create points from CSV coordinates in QGIS:

**CSV File:** {csv_path}
**X Field:** {x_field}
**Y Field:** {y_field}
**CRS:** {crs}
**Layer Name:** {layer_name}
**Encoding:** {encoding}

**Steps:**
1. Layer → Add Layer → Add Delimited Text Layer
2. File: {csv_path}
3. Encoding: {encoding}
4. Format: CSV (comma)
5. Geometry: Point coordinates
6. X field: {x_field}, Y field: {y_field}
7. CRS: {crs} (EPSG:4326 for lat/lon)
8. Add → Close
9. Optional: Export to GeoPackage/Shapefile for permanent storage

**Algorithm:** Native delimited text provider (not processing algorithm)
**Use Case:** GPS data, survey points, address geocoding results, sensor locations""",
        tags=["points", "csv", "coordinates", "geocode", "delimited text", "data"],
    ))

    # 8. Random Points in Extent
    registry.register(PromptSpec(
        name="random_points_extent",
        description="Generate random points within an extent or polygon layer.",
        category=PromptCategory.DATA,
        arguments=[
            PromptArgument("extent_layer", "Polygon layer or use canvas extent (name or 'canvas')"),
            PromptArgument("num_points", "Number of points to generate", required=True),
            PromptArgument("min_distance", "Minimum distance between points (CRS units)", default=0, required=False),
            PromptArgument("output_name", "Output layer name", default="Random_Points", required=False),
            PromptArgument("target_crs", "CRS for output (empty = extent layer CRS)", default="", required=False),
        ],
        template="""Generate random points in QGIS:

**Extent:** {extent_layer} (polygon layer or 'canvas')
**Number of Points:** {num_points}
**Min Distance:** {min_distance} (0 = no constraint)
**Output Layer:** {output_name}
**Target CRS:** {target_crs}

**Steps:**
1. Run "native:randompointsinextent" algorithm:
   - EXTENT: {extent_layer} (or use canvas extent)
   - POINTS_NUMBER: {num_points}
   - MIN_DISTANCE: {min_distance}
   - TARGET_CRS: {target_crs}
   - OUTPUT: {output_name}
2. For polygon-constrained: Use "native:randompointsinpolygons" instead:
   - POLYGONS: {extent_layer}
   - POINTS_NUMBER: {num_points}
   - MIN_DISTANCE: {min_distance}
   - OUTPUT: {output_name}

**Use Case:** Sampling design, simulation, null models, survey planning""",
        tags=["random", "sampling", "points", "simulation", "data"],
    ))

    # 9. Sample Raster Values at Points
    registry.register(PromptSpec(
        name="sample_raster_at_points",
        description="Extract raster values at point locations (add as attributes).",
        category=PromptCategory.DATA,
        arguments=[
            PromptArgument("point_layer", "Point layer to sample at"),
            PromptArgument("raster_layer", "Raster layer to sample"),
            PromptArgument("band", "Raster band to sample (1-based)", default=1, required=False),
            PromptArgument("field_prefix", "Prefix for new field names", default="sample_", required=False),
            PromptArgument("output_name", "Output layer name", default="Sampled_Points", required=False),
        ],
        template="""Sample raster values at points in QGIS:

**Point Layer:** {point_layer}
**Raster Layer:** {raster_layer}
**Band:** {band}
**Field Prefix:** {field_prefix}
**Output Layer:** {output_name}

**Steps:**
1. Run "native:rastersampling" algorithm:
   - INPUT: {point_layer}
   - RASTERCOPY: {raster_layer}
   - COLUMN_PREFIX: {field_prefix}
   - BAND: {band}
   - OUTPUT: {output_name}
2. Output: point layer with new field {field_prefix}{raster_layer_name}_band{band}
3. For multiple bands: repeat with different BAND values
4. Points outside raster extent get NULL

**Use Case:** Extract elevation at survey points, climate data at stations, validation""",
        tags=["sample", "extract", "raster", "points", "validation", "data"],
    ))

    # 10. Create Spatial Index
    registry.register(PromptSpec(
        name="create_spatial_index",
        description="Create or rebuild spatial index for a vector layer (improves performance).",
        category=PromptCategory.DATA,
        arguments=[
            PromptArgument("layer_name", "Vector layer to index"),
        ],
        template="""Create spatial index in QGIS:

**Layer:** {layer_name}

**Steps:**
1. Right-click {layer_name} → Properties → Source
2. Scroll to "Spatial Index" → Create Spatial Index
3. Or use "native:createspatialindex" algorithm:
   - INPUT: {layer_name}
2. Progress bar shows indexing status
3. Spatial index enables fast spatial queries, selections, joins

**Algorithm:** native:createspatialindex
**Use Case:** Large layers, before spatial joins, performance optimization""",
        tags=["spatial index", "performance", "optimization", "data"],
    ))