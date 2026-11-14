"""Universal AI GIS Studio — Vector Analysis Prompts.

Prompt templates for common vector operations.
"""

from mcp_server.prompts.registry import PromptSpec, PromptArgument, PromptCategory


def register_vector_prompts(registry) -> None:
    """Register all vector analysis prompts."""

    # 1. Create Buffer
    registry.register(PromptSpec(
        name="create_buffer",
        description="Create a buffer zone around vector features.",
        category=PromptCategory.VECTOR,
        arguments=[
            PromptArgument("layer_name", "Name or ID of the input vector layer"),
            PromptArgument("distance", "Buffer distance in layer CRS units", required=True),
            PromptArgument("segments", "Number of segments to approximate curves", default=5, required=False),
            PromptArgument("dissolve", "Dissolve overlapping buffers into single features", default=False, required=False),
            PromptArgument("output_name", "Name for the output buffer layer", default="Buffered", required=False),
        ],
        template="""Create a buffer analysis in QGIS:

**Input Layer:** {layer_name}
**Buffer Distance:** {distance} (layer CRS units)
**Segments:** {segments} (curve approximation)
**Dissolve Result:** {dissolve}
**Output Layer Name:** {output_name}

**Steps:**
1. Load the input layer: {layer_name}
2. Run the "native:buffer" algorithm with:
   - INPUT: {layer_name}
   - DISTANCE: {distance}
   - SEGMENTS: {segments}
   - DISSOLVE: {dissolve}
   - OUTPUT: {output_name}
3. Verify the output layer has expected feature count and geometry.
4. Style the buffer layer with semi-transparent fill for visual clarity.

**QGIS Algorithm:** native:buffer
**Expected Output:** Polygon layer with buffered features""",
        tags=["buffer", "proximity", "polygon", "native:buffer"],
    ))

    # 2. Intersect Layers
    registry.register(PromptSpec(
        name="intersect_layers",
        description="Compute geometric intersection of two vector layers.",
        category=PromptCategory.VECTOR,
        arguments=[
            PromptArgument("layer_a", "First input vector layer (name or ID)"),
            PromptArgument("layer_b", "Second input vector layer (name or ID)"),
            PromptArgument("output_name", "Name for the output intersection layer", default="Intersection", required=False),
            PromptArgument("input_fields", "Fields to keep from first layer", default="all", required=False),
            PromptArgument("overlay_fields", "Fields to keep from second layer", default="all", required=False),
        ],
        template="""Perform vector intersection in QGIS:

**Layer A (Input):** {layer_a}
**Layer B (Overlay):** {layer_b}
**Output Layer:** {output_name}
**Keep Fields from A:** {input_fields}
**Keep Fields from B:** {overlay_fields}

**Steps:**
1. Ensure both layers are loaded and have valid geometries.
2. Run "native:intersection" algorithm:
   - INPUT: {layer_a}
   - OVERLAY: {layer_b}
   - INPUT_FIELDS: {input_fields}
   - OVERLAY_FIELDS: {overlay_fields}
   - OUTPUT: {output_name}
3. Verify output contains only overlapping areas.
4. Check attribute table for combined fields from both layers.

**QGIS Algorithm:** native:intersection
**Use Case:** Find overlapping areas, spatial joins, clipping""",
        tags=["intersect", "overlay", "spatial join", "native:intersection"],
    ))

    # 3. Clip Vector Layer
    registry.register(PromptSpec(
        name="clip_vector",
        description="Clip a vector layer using a polygon mask layer.",
        category=PromptCategory.VECTOR,
        arguments=[
            PromptArgument("input_layer", "Vector layer to clip (name or ID)"),
            PromptArgument("clip_layer", "Polygon layer to use as clipping mask (name or ID)"),
            PromptArgument("output_name", "Name for the clipped output layer", default="Clipped", required=False),
        ],
        template="""Clip a vector layer to a polygon boundary in QGIS:

**Input Layer:** {input_layer}
**Clip Mask Layer:** {clip_layer} (must be polygon)
**Output Layer:** {output_name}

**Steps:**
1. Verify {clip_layer} is a polygon layer with valid geometries.
2. Run "native:clip" algorithm:
   - INPUT: {input_layer}
   - OVERLAY: {clip_layer}
   - OUTPUT: {output_name}
3. Result contains only features from {input_layer} that fall within {clip_layer}.
4. Attributes from input layer are preserved.

**QGIS Algorithm:** native:clip
**Use Case:** Extract features within study area, administrative boundaries""",
        tags=["clip", "extract", "mask", "native:clip"],
    ))

    # 4. Dissolve Features
    registry.register(PromptSpec(
        name="dissolve_features",
        description="Dissolve (merge) features based on a common attribute.",
        category=PromptCategory.VECTOR,
        arguments=[
            PromptArgument("layer_name", "Input vector layer (name or ID)"),
            PromptArgument("field", "Field to dissolve by (features with same value merged)"),
            PromptArgument("output_name", "Name for the dissolved output layer", default="Dissolved", required=False),
        ],
        template="""Dissolve vector features by attribute in QGIS:

**Input Layer:** {layer_name}
**Dissolve Field:** {field}
**Output Layer:** {output_name}

**Steps:**
1. Check that {field} exists in {layer_name} attribute table.
2. Run "native:dissolve" algorithm:
   - INPUT: {layer_name}
   - FIELD: [{field}]
   - OUTPUT: {output_name}
3. Adjacent features with same {field} value are merged.
4. Non-spatial attributes: only {field} is kept (others dropped unless aggregated).

**QGIS Algorithm:** native:dissolve
**Use Case:** Merge polygons by category, simplify boundaries, aggregate regions""",
        tags=["dissolve", "merge", "aggregate", "native:dissolve"],
    ))

    # 5. Join Attributes by Location
    registry.register(PromptSpec(
        name="join_attributes_location",
        description="Spatial join: transfer attributes from one layer to another based on spatial relationship.",
        category=PromptCategory.VECTOR,
        arguments=[
            PromptArgument("target_layer", "Layer to receive attributes (name or ID)"),
            PromptArgument("join_layer", "Layer providing attributes (name or ID)"),
            PromptArgument("predicate", "Spatial predicate", default="intersects", required=False, enum=["intersects", "contains", "within", "touches", "crosses", "overlaps"]),
            PromptArgument("join_fields", "Fields to join from join layer (comma-separated, empty=all)", default="", required=False),
            PromptArgument("output_name", "Name for output layer", default="Joined", required=False),
            PromptArgument("summary", "Summary for multiple matches", default="take_first", required=False, enum=["take_first", "count", "sum", "mean", "min", "max"]),
        ],
        template="""Perform spatial join (Join Attributes by Location) in QGIS:

**Target Layer:** {target_layer} (receives attributes)
**Join Layer:** {join_layer} (provides attributes)
**Spatial Predicate:** {predicate}
**Join Fields:** {join_fields} (empty = all fields)
**Multiple Matches Summary:** {summary}
**Output Layer:** {output_name}

**Steps:**
1. Run "native:joinattributesbylocation" algorithm:
   - INPUT: {target_layer}
   - JOIN: {join_layer}
   - PREDICATE: [{predicate}]
   - JOIN_FIELDS: {join_fields}
   - SUMMARY: {summary}
   - OUTPUT: {output_name}
2. Each feature in target layer gets attributes from matching join layer features.
3. If multiple matches: {summary} determines how to handle.

**QGIS Algorithm:** native:joinattributesbylocation
**Use Case:** Add census data to points, zonal statistics prep, spatial enrichment""",
        tags=["spatial join", "join attributes", "enrichment", "native:joinattributesbylocation"],
    ))

    # 6. Centroids
    registry.register(PromptSpec(
        name="create_centroids",
        description="Generate point centroids from polygon or line features.",
        category=PromptCategory.VECTOR,
        arguments=[
            PromptArgument("layer_name", "Input polygon or line layer (name or ID)"),
            PromptArgument("output_name", "Name for centroid output layer", default="Centroids", required=False),
            PromptArgument("all_parts", "Create centroid for each part of multipart features", default=False, required=False),
        ],
        template="""Create centroids from polygons/lines in QGIS:

**Input Layer:** {layer_name} (polygon or line)
**Output Layer:** {output_name}
**All Parts:** {all_parts} (multipart features)

**Steps:**
1. Run "native:centroids" algorithm:
   - INPUT: {layer_name}
   - ALL_PARTS: {all_parts}
   - OUTPUT: {output_name}
2. Result is a point layer with one centroid per input feature (or per part).
3. All attributes from input layer are copied to centroid points.

**QGIS Algorithm:** native:centroids
**Use Case:** Label placement, point representation of areas, sampling points""",
        tags=["centroid", "point", "polygon", "native:centroids"],
    ))


    # 7. Voronoi Polygons
    registry.register(PromptSpec(
        name="voronoi_polygons",
        description="Create Voronoi (Thiessen) polygons from point features.",
        category=PromptCategory.VECTOR,
        arguments=[
            PromptArgument("layer_name", "Input point layer (name or ID)"),
            PromptArgument("buffer", "Buffer distance around extent (percentage)", default=0, required=False),
            PromptArgument("output_name", "Name for Voronoi output layer", default="Voronoi", required=False),
        ],
        template="""Create Voronoi (Thiessen) polygons in QGIS:

**Input Layer:** {layer_name} (points)
**Buffer %:** {buffer}
**Output Layer:** {output_name}

**Steps:**
1. Run "native:voronoipolygons" algorithm:
   - INPUT: {layer_name}
   - BUFFER: {buffer}
   - OUTPUT: {output_name}
2. Each point gets a polygon containing all locations closer to it than any other point.
3. Buffer extends the extent to avoid edge effects.

**QGIS Algorithm:** native:voronoipolygons
**Use Case:** Service areas, nearest neighbor analysis, spatial interpolation""",
        tags=["voronoi", "thiessen", "nearest neighbor", "native:voronoipolygons"],
    ))

    # 8. Difference (Erase)
    registry.register(PromptSpec(
        name="difference_layers",
        description="Extract parts of features from layer A that don't overlap with layer B (erase).",
        category=PromptCategory.VECTOR,
        arguments=[
            PromptArgument("input_layer", "Layer to erase from (name or ID)"),
            PromptArgument("overlay_layer", "Layer to erase with (name or ID)"),
            PromptArgument("output_name", "Name for output layer", default="Difference", required=False),
        ],
        template="""Erase/difference operation in QGIS:

**Input Layer:** {input_layer}
**Erase Layer:** {overlay_layer}
**Output Layer:** {output_name}

**Steps:**
1. Run "native:difference" algorithm:
   - INPUT: {input_layer}
   - OVERLAY: {overlay_layer}
   - OUTPUT: {output_name}
2. Result: portions of {input_layer} that do NOT overlap with {overlay_layer}.
3. Attributes from input layer are preserved.

**QGIS Algorithm:** native:difference
**Use Case:** Remove overlapping areas, create donut polygons, exclude zones""",
        tags=["difference", "erase", "subtract", "native:difference"],
    ))

    # 9. Symmetrical Difference
    registry.register(PromptSpec(
        name="symmetrical_difference",
        description="Extract non-overlapping portions of both layers (XOR operation).",
        category=PromptCategory.VECTOR,
        arguments=[
            PromptArgument("layer_a", "First layer (name or ID)"),
            PromptArgument("layer_b", "Second layer (name or ID)"),
            PromptArgument("output_name", "Name for output layer", default="SymDiff", required=False),
        ],
        template="""Symmetrical difference (XOR) in QGIS:

**Layer A:** {layer_a}
**Layer B:** {layer_b}
**Output Layer:** {output_name}

**Steps:**
1. Run "native:symmetricaldifference" algorithm:
   - INPUT: {layer_a}
   - OVERLAY: {layer_b}
   - OUTPUT: {output_name}
2. Result: areas in A or B but NOT in both (exclusive or).
3. Attributes from both layers are included with prefixes.

**QGIS Algorithm:** native:symmetricaldifference
**Use Case:** Change detection, boundary comparison, exclusive zones""",
        tags=["symmetrical difference", "xor", "exclusive", "native:symmetricaldifference"],
    ))

    # 10. Union
    registry.register(PromptSpec(
        name="union_layers",
        description="Union: combine all features from both layers, splitting at intersections.",
        category=PromptCategory.VECTOR,
        arguments=[
            PromptArgument("layer_a", "First layer (name or ID)"),
            PromptArgument("layer_b", "Second layer (name or ID)"),
            PromptArgument("output_name", "Name for output layer", default="Union", required=False),
            PromptArgument("overlay_fields", "Fields to keep from second layer", default="all", required=False),
        ],
        template="""Union of two vector layers in QGIS:

**Layer A:** {layer_a}
**Layer B:** {layer_b}
**Overlay Fields:** {overlay_fields}
**Output Layer:** {output_name}

**Steps:**
1. Run "native:union" algorithm:
   - INPUT: {layer_a}
   - OVERLAY: {layer_b}
   - OVERLAY_FIELDS: {overlay_fields}
   - OUTPUT: {output_name}
2. All features from both layers, split at every intersection.
3. Overlapping areas get attributes from BOTH layers.
4. Non-overlapping areas get attributes from source layer + nulls for other.

**QGIS Algorithm:** native:union
**Use Case:** Comprehensive overlay, land use + zoning, all combinations""",
        tags=["union", "overlay", "combine", "native:union"],
    ))