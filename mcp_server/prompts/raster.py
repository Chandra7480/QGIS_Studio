"""Universal AI GIS Studio — Raster Analysis Prompts.

Prompt templates for common raster operations.
"""

from mcp_server.prompts.registry import PromptSpec, PromptArgument, PromptCategory


def register_raster_prompts(registry) -> None:
    """Register all raster analysis prompts."""

    # 1. Hillshade
    registry.register(PromptSpec(
        name="create_hillshade",
        description="Generate a hillshade (shaded relief) from a DEM raster.",
        category=PromptCategory.RASTER,
        arguments=[
            PromptArgument("dem_layer", "Input DEM raster layer (name or ID)"),
            PromptArgument("z_factor", "Vertical exaggeration factor", default=1.0, required=False),
            PromptArgument("azimuth", "Sun azimuth angle (degrees, 0-360)", default=315, required=False),
            PromptArgument("altitude", "Sun altitude angle (degrees, 0-90)", default=45, required=False),
            PromptArgument("output_name", "Name for output hillshade layer", default="Hillshade", required=False),
        ],
        template="""Create hillshade (shaded relief) from DEM in QGIS:

**DEM Layer:** {dem_layer}
**Z Factor:** {z_factor} (vertical exaggeration)
**Sun Azimuth:** {azimuth}° (0=North, 90=East, 180=South, 270=West)
**Sun Altitude:** {altitude}° (angle above horizon)
**Output Layer:** {output_name}

**Steps:**
1. Run "native:hillshade" algorithm:
   - INPUT: {dem_layer}
   - Z_FACTOR: {z_factor}
   - AZIMUTH: {azimuth}
   - ALTITUDE: {altitude}
   - OUTPUT: {output_name}
2. Result is a grayscale raster simulating 3D terrain illumination.
3. Use with "Multiply" blend mode over DEM for classic shaded relief map.

**QGIS Algorithm:** native:hillshade
**Use Case:** Terrain visualization, base maps, 3D effect""",
        tags=["hillshade", "shaded relief", "dem", "terrain", "native:hillshade"],
    ))

    # 2. Slope
    registry.register(PromptSpec(
        name="calculate_slope",
        description="Calculate slope (gradient) from a DEM raster.",
        category=PromptCategory.RASTER,
        arguments=[
            PromptArgument("dem_layer", "Input DEM raster layer (name or ID)"),
            PromptArgument("z_factor", "Vertical exaggeration factor", default=1.0, required=False),
            PromptArgument("output_name", "Name for output slope layer", default="Slope", required=False),
            PromptArgument("as_percent", "Output as percent instead of degrees", default=False, required=False),
        ],
        template="""Calculate slope from DEM in QGIS:

**DEM Layer:** {dem_layer}
**Z Factor:** {z_factor}
**Output as Percent:** {as_percent}
**Output Layer:** {output_name}

**Steps:**
1. Run "native:slope" algorithm:
   - INPUT: {dem_layer}
   - Z_FACTOR: {z_factor}
   - AS_PERCENT: {as_percent}
   - OUTPUT: {output_name}
2. Output: slope in degrees (default) or percent rise.
3. Style with color ramp (green=flat, red=steep) for visualization.

**QGIS Algorithm:** native:slope
**Use Case:** Terrain analysis, suitability modeling, erosion risk""",
        tags=["slope", "gradient", "dem", "terrain", "native:slope"],
    ))

    # 3. Aspect
    registry.register(PromptSpec(
        name="calculate_aspect",
        description="Calculate aspect (slope direction) from a DEM raster.",
        category=PromptCategory.RASTER,
        arguments=[
            PromptArgument("dem_layer", "Input DEM raster layer (name or ID)"),
            PromptArgument("z_factor", "Vertical exaggeration factor", default=1.0, required=False),
            PromptArgument("output_name", "Name for output aspect layer", default="Aspect", required=False),
        ],
        template="""Calculate aspect (slope direction) from DEM in QGIS:

**DEM Layer:** {dem_layer}
**Z Factor:** {z_factor}
**Output Layer:** {output_name}

**Steps:**
1. Run "native:aspect" algorithm:
   - INPUT: {dem_layer}
   - Z_FACTOR: {z_factor}
   - OUTPUT: {output_name}
2. Output: aspect in degrees (0=North, 90=East, 180=South, 270=West, -1=flat).
3. Style with circular color ramp for direction visualization.

**QGIS Algorithm:** native:aspect
**Use Case:** Solar potential, vegetation modeling, wind exposure""",
        tags=["aspect", "slope direction", "dem", "terrain", "native:aspect"],
    ))

    # 4. Reclassify Raster
    registry.register(PromptSpec(
        name="reclassify_raster",
        description="Reclassify raster values using a lookup table.",
        category=PromptCategory.RASTER,
        arguments=[
            PromptArgument("raster_layer", "Input raster layer (name or ID)"),
            PromptArgument("reclass_table", "Reclassification table (format: 'min max new_val; min max new_val')", required=True),
            PromptArgument("output_name", "Name for output layer", default="Reclassified", required=False),
            PromptArgument("nodata", "Value to use for NoData", default=-9999, required=False),
        ],
        template="""Reclassify raster values in QGIS:

**Input Raster:** {raster_layer}
**Reclass Table:** {reclass_table} (format: "min max new_val; min max new_val")
**NoData Value:** {nodata}
**Output Layer:** {output_name}

**Steps:**
1. Prepare reclassification table as semicolon-separated ranges:
   Example: "0 100 1; 100 200 2; 200 300 3"
2. Run "native:reclassifybytable" algorithm:
   - INPUT_RASTER: {raster_layer}
   - TABLE: {reclass_table}
   - NO_DATA: {nodata}
   - OUTPUT: {output_name}
3. Each input range maps to a new output value.

**QGIS Algorithm:** native:reclassifybytable
**Use Case:** Land cover simplification, suitability ranking, threshold mapping""",
        tags=["reclassify", "recode", "raster calculator", "native:reclassifybytable"],
    ))

    # 5. Clip Raster by Mask
    registry.register(PromptSpec(
        name="clip_raster",
        description="Clip a raster to a polygon mask layer.",
        category=PromptCategory.RASTER,
        arguments=[
            PromptArgument("raster_layer", "Input raster layer (name or ID)"),
            PromptArgument("mask_layer", "Polygon mask layer (name or ID)"),
            PromptArgument("output_name", "Name for output clipped raster", default="Clipped_Raster", required=False),
            PromptArgument("nodata", "NoData value for output", default=None, required=False),
            PromptArgument("crop_to_extent", "Crop to mask extent", default=True, required=False),
        ],
        template="""Clip raster to polygon mask in QGIS:

**Input Raster:** {raster_layer}
**Mask Layer:** {mask_layer} (polygon)
**Crop to Extent:** {crop_to_extent}
**NoData Value:** {nodata}
**Output Layer:** {output_name}

**Steps:**
1. Run "gdal:cliprasterbymasklayer" algorithm:
   - INPUT: {raster_layer}
   - MASK: {mask_layer}
   - CROP_TO_EXTENT: {crop_to_extent}
   - NODATA: {nodata}
   - OUTPUT: {output_name}
2. Raster is clipped to the exact polygon geometry.
3. Areas outside mask get NoData value.

**QGIS Algorithm:** gdal:cliprasterbymasklayer
**Use Case:** Extract study area, reduce file size, focus analysis""",
        tags=["clip", "mask", "extract", "gdal:cliprasterbymasklayer"],
    ))

    # 6. Raster Calculator
    registry.register(PromptSpec(
        name="raster_calculator",
        description="Perform mathematical operations on raster bands using expressions.",
        category=PromptCategory.RASTER,
        arguments=[
            PromptArgument("expression", "Raster calculator expression (e.g., 'A * 0.5 + B')", required=True),
            PromptArgument("layers", "Comma-separated layer references (A, B, C...)", required=True),
            PromptArgument("output_name", "Name for output raster", default="Calculated", required=False),
            PromptArgument("nodata", "NoData value for output", default=None, required=False),
        ],
        template="""Raster calculator expression in QGIS:

**Expression:** {expression}
**Layer References:** {layers} (e.g., "A=layer1, B=layer2")
**NoData Value:** {nodata}
**Output Layer:** {output_name}

**Steps:**
1. Define expression using layer references A, B, C...
   Examples:
   - NDVI: "(NIR - RED) / (NIR + RED)" where A=NIR, B=RED
   - EVI: "2.5 * (NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1)"
   - Sum: "A + B + C"
2. Run "native:rastercalculator" algorithm:
   - EXPRESSION: {expression}
   - LAYERS: {layers}
   - NODATA: {nodata}
   - OUTPUT: {output_name}

**QGIS Algorithm:** native:rastercalculator
**Use Case:** Spectral indices, band math, custom formulas, model outputs""",
        tags=["raster calculator", "band math", "expression", "ndvi", "native:rastercalculator"],
    ))

    # 7. Raster Statistics
    registry.register(PromptSpec(
        name="raster_statistics",
        description="Calculate basic statistics (min, max, mean, std) for a raster.",
        category=PromptCategory.RASTER,
        arguments=[
            PromptArgument("raster_layer", "Input raster layer (name or ID)"),
            PromptArgument("band", "Band number (1-based)", default=1, required=False),
            PromptArgument("output_name", "Optional output for stats table", default="", required=False),
        ],
        template="""Calculate raster statistics in QGIS:

**Raster Layer:** {raster_layer}
**Band:** {band}
**Output Stats Table:** {output_name} (optional)

**Steps:**
1. Run "native:rasterlayerstatistics" algorithm:
   - INPUT: {raster_layer}
   - BAND: {band}
   - OUTPUT: {output_name}
2. Output includes: min, max, mean, std dev, sum, count, range.
3. Use for data exploration, normalization params, threshold setting.

**QGIS Algorithm:** native:rasterlayerstatistics
**Use Case:** Data exploration, normalization, histogram analysis""",
        tags=["statistics", "histogram", "min max mean", "native:rasterlayerstatistics"],
    ))

    # 8. Merge Rasters
    registry.register(PromptSpec(
        name="merge_rasters",
        description="Mosaic multiple rasters into a single raster.",
        category=PromptCategory.RASTER,
        arguments=[
            PromptArgument("raster_layers", "Comma-separated list of raster layer names/IDs", required=True),
            PromptArgument("output_name", "Name for output merged raster", default="Merged", required=False),
            PromptArgument("nodata", "NoData value for output", default=None, required=False),
        ],
        template="""Merge multiple rasters into mosaic in QGIS:

**Input Rasters:** {raster_layers} (comma-separated)
**NoData Value:** {nodata}
**Output Layer:** {output_name}

**Steps:**
1. Run "gdal:merge" algorithm:
   - INPUT: [{raster_layers}]
   - NODATA_INPUT: {nodata}
   - NODATA_OUTPUT: {nodata}
   - OUTPUT: {output_name}
2. Rasters are combined; overlapping areas use first raster's values.
3. All input rasters should have same CRS and resolution.

**QGIS Algorithm:** gdal:merge
**Use Case:** Combine tiles, mosaic scenes, create seamless coverage""",
        tags=["merge", "mosaic", "combine", "gdal:merge"],
    ))

    # 9. Resample/Rescale Raster
    registry.register(PromptSpec(
        name="resample_raster",
        description="Resample raster to different resolution or extent.",
        category=PromptCategory.RASTER,
        arguments=[
            PromptArgument("raster_layer", "Input raster layer (name or ID)"),
            PromptArgument("target_resolution", "Target cell size (in layer CRS units)", required=True),
            PromptArgument("method", "Resampling method", default="bilinear", required=False, enum=["nearest", "bilinear", "cubic", "cubicspline", "lanczos", "average", "mode", "max", "min", "med", "q1", "q3"]),
            PromptArgument("output_name", "Name for output raster", default="Resampled", required=False),
        ],
        template="""Resample raster to new resolution in QGIS:

**Input Raster:** {raster_layer}
**Target Resolution:** {target_resolution} (CRS units)
**Resampling Method:** {method}
**Output Layer:** {output_name}

**Steps:**
1. Run "gdal:warpreproject" algorithm:
   - INPUT: {raster_layer}
   - TARGET_RESOLUTION: {target_resolution}
   - RESAMPLING: {method}
   - OUTPUT: {output_name}
2. Method guide:
   - nearest: categorical data (land cover)
   - bilinear: continuous data (DEM, temperature)
   - cubic/lanczos: high-quality continuous
   - average: downsampling continuous
3. CRS remains the same unless reprojection also needed.

**QGIS Algorithm:** gdal:warpreproject
**Use Case:** Match resolutions, reduce file size, prepare for analysis""",
        tags=["resample", "rescale", "resolution", "gdal:warpreproject"],
    ))

    # 10. Proximity (Distance) Raster
    registry.register(PromptSpec(
        name="proximity_raster",
        description="Create distance raster from vector features or raster values.",
        category=PromptCategory.RASTER,
        arguments=[
            PromptArgument("source_layer", "Source layer (vector or raster)"),
            PromptArgument("target_values", "Values to compute distance from (comma-separated)", default="", required=False),
            PromptArgument("max_distance", "Maximum distance to compute", default="", required=False),
            PromptArgument("output_name", "Name for output distance raster", default="Proximity", required=False),
            PromptArgument("units", "Distance units", default="GEO", required=False, enum=["GEO", "PIXEL"]),
        ],
        template="""Create proximity (distance) raster in QGIS:

**Source Layer:** {source_layer}
**Target Values:** {target_values} (empty = all non-zero/non-nodata)
**Max Distance:** {max_distance}
**Units:** {units} (GEO=CRS units, PIXEL=pixel count)
**Output Layer:** {output_name}

**Steps:**
1. Run "gdal:proximity" algorithm:
   - INPUT: {source_layer}
   - VALUES: {target_values}
   - MAX_DISTANCE: {max_distance}
   - UNITS: {units}
   - OUTPUT: {output_name}
2. Each output pixel = distance to nearest target feature/value.
3. Use for cost surfaces, buffer zones, accessibility analysis.

**QGIS Algorithm:** gdal:proximity
**Use Case:** Distance to roads, water, protected areas; cost surfaces""",
        tags=["proximity", "distance", "cost surface", "gdal:proximity"],
    ))