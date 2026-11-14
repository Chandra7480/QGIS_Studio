"""Universal AI GIS Studio — Terrain Analysis Prompts.

Prompt templates for terrain analysis and geomorphometry.
"""

from mcp_server.prompts.registry import PromptSpec, PromptArgument, PromptCategory


def register_terrain_prompts(registry) -> None:
    """Register all terrain analysis prompts."""

    # 1. Contours
    registry.register(PromptSpec(
        name="create_contours",
        description="Generate contour lines from a DEM at specified interval.",
        category=PromptCategory.TERRAIN,
        arguments=[
            PromptArgument("dem_layer", "Input DEM raster layer"),
            PromptArgument("interval", "Contour interval (DEM vertical units, typically meters)", required=True),
            PromptArgument("offset", "Contour offset from zero", default=0, required=False),
            PromptArgument("output_name", "Output contour layer name", default="Contours", required=False),
            PromptArgument("field_name", "Attribute field for elevation values", default="ELEV", required=False),
        ],
        template="""Generate Contours from DEM in QGIS:

**DEM Layer:** {dem_layer}
**Interval:** {interval} (meters)
**Offset:** {offset}
**Output:** {output_name}
**Elevation Field:** {field_name}

**Steps:**
1. Run "gdal:contour" algorithm:
   - INPUT: {dem_layer}
   - INTERVAL: {interval}
   - OFFSET: {offset}
   - FIELD_NAME: {field_name}
   - OUTPUT: {output_name}
2. Output: Line layer with {field_name} attribute
3. Style: Graduated or categorized by {field_name}
4. Labels: Show {field_name} with proper formatting

**Advanced (SAGA):**
- "saga:contourlines" - more options (smoothing, min/max length)
- "saga:contourlinesfrompoints" - from point elevation data

**Use Case:** Topographic maps, hypsometric analysis, elevation visualization""",
        tags=["contours", "dem", "topography", "elevation", "gdal:contour"],
    ))

    # 2. Topographic Position Index (TPI)
    registry.register(PromptSpec(
        name="calculate_tpi",
        description="Calculate Topographic Position Index (relative elevation vs neighborhood).",
        category=PromptCategory.TERRAIN,
        arguments=[
            PromptArgument("dem_layer", "Input DEM raster layer"),
            PromptArgument("radius", "Neighborhood radius (cells)", default=10, required=False),
            PromptArgument("output_name", "Output TPI layer", default="TPI", required=False),
            PromptArgument("normalize", "Normalize by local std deviation", default=False, required=False),
        ],
        template="""Calculate Topographic Position Index (TPI) in QGIS:

**DEM Layer:** {dem_layer}
**Radius:** {radius} cells
**Normalize:** {normalize}
**Output:** {output_name}

**TPI Formula:** TPI = elevation - mean(elevation in neighborhood)
- Positive: Ridge/peak (higher than surroundings)
- Negative: Valley (lower than surroundings)
- Near zero: Flat/slope (similar to surroundings)

**Steps:**
1. Run "saga:topographicpositionindex" algorithm:
   - DEM: {dem_layer}
   - RADIUS: {radius}
   - METHOD: 0 (Standard) or 1 (Standardized)
   - OUTPUT: {output_name}
2. If {normalize}: Standardized TPI = TPI / std_dev(neighborhood)
3. Style: Diverging ramp (red=ridges, blue=valleys, white=slopes)

**Interpretation:**
- TPI > 1 std: Ridge top
- TPI 0.5-1: Upper slope
- TPI -0.5 to 0.5: Mid slope/flat
- TPI -1 to -0.5: Lower slope
- TPI < -1: Valley bottom

**Use Case:** Landform classification, geomorphology, habitat modeling, soil mapping""",
        tags=["tpi", "topographic position", "landform", "geomorphology", "saga"],
    ))

    # 3. Terrain Ruggedness Index (TRI)
    registry.register(PromptSpec(
        name="calculate_tri",
        description="Calculate Terrain Ruggedness Index (elevation difference from neighbors).",
        category=PromptCategory.TERRAIN,
        arguments=[
            PromptArgument("dem_layer", "Input DEM raster layer"),
            PromptArgument("radius", "Neighborhood radius (cells)", default=1, required=False),
            PromptArgument("output_name", "Output TRI layer", default="TRI", required=False),
        ],
        template="""Calculate Terrain Ruggedness Index (TRI) in QGIS:

**DEM Layer:** {dem_layer}
**Radius:** {radius} cells
**Output:** {output_name}

**TRI Formula:** TRI = sqrt(sum((center - neighbor)²) / n)
Means: mean absolute difference between center cell and its neighbors
- Low TRI: Flat terrain
- High TRI: Rugged, complex terrain

**Steps:**
1. Run "saga:terrainruggednessindextri" algorithm:
   - DEM: {dem_layer}
   - RADIUS: {radius}
   - OUTPUT: {output_name}
2. Or "gdal:triterrainruggedness" for simpler 3x3 neighborhood
3. Style: Singleband pseudocolor, viridis ramp

**Related:** VRM (Vector Ruggedness Measure) - uses surface normals
**Use Case:** Wildlife habitat, vehicle mobility, erosion potential, geological mapping""",
        tags=["tri", "ruggedness", "terrain", "geomorphology", "saga"],
    ))

    # 4. Roughness
    registry.register(PromptSpec(
        name="calculate_roughness",
        description="Calculate surface roughness (max-min elevation in neighborhood).",
        category=PromptCategory.TERRAIN,
        arguments=[
            PromptArgument("dem_layer", "Input DEM raster layer"),
            PromptArgument("radius", "Neighborhood radius (cells)", default=1, required=False),
            PromptArgument("output_name", "Output roughness layer", default="Roughness", required=False),
        ],
        template="""Calculate Surface Roughness in QGIS:

**DEM Layer:** {dem_layer}
**Radius:** {radius} cells
**Output:** {output_name}

**Roughness Formula:** Roughness = max(elevation) - min(elevation) in neighborhood
Simpler than TRI, captures local relief.

**Steps:**
1. Run "saga:roughness" algorithm:
   - DEM: {dem_layer}
   - RADIUS: {radius}
   - OUTPUT: {output_name}
2. Or "gdal:roughness" for 3x3 window
3. Style: Pseudocolor, high values = rough terrain

**Use Case:** Landing site selection, rover navigation, soil erosion, terrain classification""",
        tags=["roughness", "local relief", "terrain", "saga"],
    ))

    # 5. Watershed Delineation
    registry.register(PromptSpec(
        name="delineate_watershed",
        description="Delineate watershed catchment area from DEM for a pour point.",
        category=PromptCategory.TERRAIN,
        arguments=[
            PromptArgument("dem_layer", "Input DEM raster (filled/sink-free)"),
            PromptArgument("pour_point", "Pour point (point layer or X,Y coordinates)"),
            PromptArgument("output_name", "Output watershed polygon", default="Watershed", required=False),
            PromptArgument("threshold", "Flow accumulation threshold for stream network", default=1000, required=False),
        ],
        template="""Delineate Watershed from DEM in QGIS:

**DEM Layer:** {dem_layer} (must be hydrologically corrected - filled sinks)
**Pour Point:** {pour_point} (point layer or "X,Y")
**Stream Threshold:** {threshold} cells
**Output:** {output_name}

**Complete Workflow (GRASS/SAGA):**

**Step 1: Fill Sinks**
- "saga:fillsinkswangliu" or "grass7:r.fill.dir"
- Input: {dem_layer} → Output: DEM_filled

**Step 2: Flow Direction**
- "grass7:r.watershed" or "saga:flowdirection"
- Input: DEM_filled → Flow direction raster

**Step 3: Flow Accumulation**
- "grass7:r.watershed" or "saga:flowaccumulation"
- Input: Flow direction → Accumulation raster

**Step 4: Stream Network**
- "grass7:r.stream.extract" or "saga:channelnetwork"
- Threshold: {threshold} → Stream raster

**Step 5: Watershed Basin**
- "grass7:r.water.outlet" or "saga:upslopearea"
- Pour point: {pour_point} → Watershed raster

**Step 6: Vectorize**
- "gdal:polygonize" or "native:polygonize"
- Raster to polygon: {output_name}

**Alternative (SAGA One-Step):**
"saga:watershedbasins" - computes all basins at once

**Use Case:** Hydrology, flood modeling, water resource management, erosion""",
        tags=["watershed", "catchment", "hydrology", "delineation", "grass", "saga"],
    ))

    # 6. Stream Network Extraction
    registry.register(PromptSpec(
        name="extract_streams",
        description="Extract stream network from DEM using flow accumulation threshold.",
        category=PromptCategory.TERRAIN,
        arguments=[
            PromptArgument("dem_layer", "Input DEM (filled)"),
            PromptArgument("threshold", "Flow accumulation threshold (cells)", default=1000, required=False),
            PromptArgument("output_name", "Output stream vector layer", default="Streams", required=False),
        ],
        template="""Extract Stream Network from DEM in QGIS:

**DEM Layer:** {dem_layer} (filled)
**Threshold:** {threshold} cells (contributing area)
**Output:** {output_name}

**Steps (GRASS r.watershed - Recommended):**
1. Run "grass7:r.watershed":
   - ELEVATION: {dem_layer}
   - THRESHOLD: {threshold}
   - DRAINAGE: Streams_raster
   - ACCUMULATION: Flow_accum
   - BASIN: Basins
2. Vectorize: "gdal:polygonize" or "native:polygonize"
   - INPUT: Streams_raster → {output_name}
3. Add Strahler order: "grass7:r.stream.order"

**Steps (SAGA):**
1. "saga:flowdirection" → Flow dir
2. "saga:flowaccumulation" → Accumulation
3. "saga:channelnetwork" → Threshold: {threshold} → Streams
4. "saga:channelnetworkvectors" → Vector output

**Threshold Guide:**
- 1000 cells (30m DEM) ≈ 0.9 km² ≈ small streams
- 10000 cells ≈ 9 km² ≈ major streams
- Adjust for DEM resolution and desired density

**Use Case:** Hydrography, drainage mapping, flood modeling, watershed analysis""",
        tags=["streams", "hydrography", "drainage", "flow accumulation", "grass", "saga"],
    ))

    # 7. Hypsometric Curve
    registry.register(PromptSpec(
        name="hypsometric_curve",
        description="Generate hypsometric curve (area-elevation distribution) for a DEM or watershed.",
        category=PromptCategory.TERRAIN,
        arguments=[
            PromptArgument("dem_layer", "Input DEM raster"),
            PromptArgument("zone_layer", "Optional zone polygon (watershed boundary)"),
            PromptArgument("output_table", "Output CSV with elevation/area data"),
            PromptArgument("num_bins", "Number of elevation bins", default=50, required=False),
        ],
        template="""Generate Hypsometric Curve in QGIS:

**DEM Layer:** {dem_layer}
**Zone Layer:** {zone_layer} (optional, for watershed-specific)
**Output Table:** {output_table}
**Bins:** {num_bins}

**Steps:**
1. **If zone provided:** Clip DEM to zone
   - "gdal:cliprasterbymasklayer" → DEM_clipped
2. **Histogram:** "native:rasterlayerhistogram"
   - INPUT: {dem_layer} (or DEM_clipped)
   - BINS: {num_bins}
   - OUTPUT: {output_table}
3. **Calculate Cumulative Area:**
   - Open CSV in spreadsheet
   - Area per bin = count * cell_area
   - Cumulative % area = cumsum(area) / total_area
   - Plot: Elevation (y) vs % Area (x)

**Hypsometric Integral (HI):**
HI = Area under curve / Total area
- HI > 0.5: Youthful, erosional landscape
- HI ≈ 0.5: Mature, equilibrium
- HI < 0.5: Old, depositional

**Use Case:** Geomorphology, landscape evolution, tectonic activity, drainage basin analysis""",
        tags=["hypsometric", "elevation distribution", "geomorphology", "landscape evolution"],
    ))

    # 8. Viewshed (also in analysis.py but terrain-specific)
    registry.register(PromptSpec(
        name="terrain_viewshed",
        description="Calculate visibility from observer points on terrain (DEM-based).",
        category=PromptCategory.TERRAIN,
        arguments=[
            PromptArgument("dem_layer", "Input DEM raster"),
            PromptArgument("observer_points", "Point layer with observer locations"),
            PromptArgument("observer_height", "Observer height above ground (m)", default=1.75, required=False),
            PromptArgument("target_height", "Target height above ground (m)", default=0, required=False),
            PromptArgument("max_distance", "Max visibility distance (m)", default="", required=False),
            PromptArgument("output_name", "Output viewshed raster", default="Viewshed", required=False),
        ],
        template="""Terrain Viewshed Analysis in QGIS:

**DEM Layer:** {dem_layer}
**Observer Points:** {observer_points}
**Observer Height:** {observer_height} m
**Target Height:** {target_height} m
**Max Distance:** {max_distance} m
**Output:** {output_name}

**Steps (Native QGIS 3.22+):**
1. Run "native:viewshed":
   - INPUT: {dem_layer}
   - OBSERVER_POINTS: {observer_points}
   - OBSERVER_HEIGHT: {observer_height}
   - TARGET_HEIGHT: {target_height}
   - MAX_DISTANCE: {max_distance}
   - OUTPUT: {output_name}

**Steps (GRASS - More Options):**
1. "grass7:r.viewshed":
   - INPUT: {dem_layer}
   - COORDINATES: X,Y of observer (or vector points)
   - OBSERVER_ELEVATION: {observer_height}
   - TARGET_ELEVATION: {target_height}
   - MAX_DISTANCE: {max_distance}
   - OUTPUT: {output_name}
   - Options: Curvature correction, Refraction coefficient

**Output Values:**
- 0: Not visible
- 1: Visible (or count of observers if multiple)
- NULL: Outside max distance

**Multi-Observer:** Each cell = count of observers that can see it
**Use Case:** Tower siting, scenic assessment, military, wind farms, communication""",
        tags=["viewshed", "visibility", "line of sight", "dem", "terrain"],
    ))

    # 9. Solar Radiation / Insolation
    registry.register(PromptSpec(
        name="solar_radiation",
        description="Calculate incoming solar radiation (insolation) on terrain.",
        category=PromptCategory.TERRAIN,
        arguments=[
            PromptArgument("dem_layer", "Input DEM raster"),
            PromptArgument("latitude", "Site latitude (decimal degrees)", required=True),
            PromptArgument("start_date", "Start date (YYYY-MM-DD)", default="2024-01-01", required=False),
            PromptArgument("end_date", "End date (YYYY-MM-DD)", default="2024-12-31", required=False),
            PromptArgument("time_step", "Time step (hours)", default=1, required=False),
            PromptArgument("output_name", "Output radiation raster", default="Solar_Radiation", required=False),
        ],
        template="""Calculate Solar Radiation (Insolation) in QGIS:

**DEM Layer:** {dem_layer}
**Latitude:** {latitude}
**Period:** {start_date} to {end_date}
**Time Step:** {time_step} hour(s)
**Output:** {output_name}

**Steps (GRASS r.sun):**
1. Run "grass7:r.sun" (daily) or "grass7:r.sun.hourly":
   - ELEVATION: {dem_layer}
   - LATITUDE: {latitude}
   - DAY: Day of year (1-365) or range
   - TIME_STEP: {time_step}
   - OUTPUT: {output_name}
   - Additional: Linke turbidity, albedo, diffuse proportion

**Steps (SAGA):**
1. "saga:insolation" - simpler interface
   - DEM: {dem_layer}
   - LATITUDE: {latitude}
   - PERIOD: {start_date} to {end_date}
   - OUTPUT: {output_name}

**Output:** Wh/m² (Watt-hours per square meter) for period
**Use Case:** Solar panel siting, agriculture, ecology, climate modeling, viticulture""",
        tags=["solar", "insolation", "radiation", "sun", "energy", "grass", "saga"],
    ))

    # 10. Landform Classification
    registry.register(PromptSpec(
        name="landform_classification",
        description="Classify terrain into landform units (peaks, ridges, slopes, valleys, pits).",
        category=PromptCategory.TERRAIN,
        arguments=[
            PromptArgument("dem_layer", "Input DEM raster"),
            PromptArgument("method", "Classification method", default="TPI", required=False, enum=["TPI", "Geomorphons", "PIPE", "Roughness"]),
            PromptArgument("output_name", "Output landform raster", default="Landforms", required=False),
        ],
        template="""Landform Classification in QGIS:

**DEM Layer:** {dem_layer}
**Method:** {method}
**Output:** {output_name}

**Methods:**

**1. TPI-based (SAGA: "saga:tpi_based_landform_classification")**
Classes: Peak, Ridge, Shoulder, Spur, Slope, Hollow, Valley, Pit
Uses TPI at multiple scales

**2. Geomorphons (GRASS: "grass7:r.geomorphon")**
10 classes: Flat, Peak, Ridge, Shoulder, Spur, Slope, Hollow, Footslope, Valley, Pit
Based on ternary pattern of visibility
- search: radius in cells
- skip: inner radius
- flat: flatness threshold

**3. PIPE (SAGA: "saga:pipe_landform_classification")**
Parameter-free, uses pattern recognition

**4. Roughness + Slope + TPI (Custom)**
Combine multiple indices with decision rules

**Recommended: Geomorphons (most robust)**
```bash
grass7:r.geomorphon elevation={dem_layer} forms={output_name} search=15 skip=0 flat=1
```

**Style:** Paletted/Unique values with 10-class color scheme
**Use Case:** Geomorphology, soil mapping, habitat classification, terrain analysis""",
        tags=["landform", "geomorphons", "classification", "terrain types", "grass", "saga"],
    ))