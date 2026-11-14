"""Universal AI GIS Studio — Spatial Analysis Prompts.

Prompt templates for advanced spatial analysis workflows.
"""

from mcp_server.prompts.registry import PromptSpec, PromptArgument, PromptCategory


def register_analysis_prompts(registry) -> None:
    """Register all spatial analysis prompts."""

    # 1. Hotspot Analysis (Getis-Ord Gi*)
    registry.register(PromptSpec(
        name="hotspot_analysis",
        description="Identify statistically significant hot spots and cold spots (Getis-Ord Gi*).",
        category=PromptCategory.ANALYSIS,
        arguments=[
            PromptArgument("input_layer", "Input point or polygon layer with analysis field"),
            PromptArgument("analysis_field", "Numeric field to analyze for clustering"),
            PromptArgument("distance_threshold", "Distance threshold for neighborhood (CRS units)", required=True),
            PromptArgument("output_name", "Name for output hotspot layer", default="Hotspots", required=False),
            PromptArgument("conceptualization", "Spatial relationship concept", default="FIXED_DISTANCE", required=False, enum=["FIXED_DISTANCE", "INVERSE_DISTANCE", "K_NEAREST_NEIGHBORS", "CONTIGUITY_EDGES", "CONTIGUITY_EDGES_CORNERS"]),
        ],
        template="""Hotspot Analysis (Getis-Ord Gi*) in QGIS:

**Input Layer:** {input_layer}
**Analysis Field:** {analysis_field}
**Distance Threshold:** {distance_threshold} (CRS units)
**Conceptualization:** {conceptualization}
**Output Layer:** {output_name}

**Steps:**
1. Ensure input layer has a numeric field for analysis.
2. Run "native:hotspotanalysis" algorithm (or use Processing toolbox):
   - INPUT: {input_layer}
   - FIELD: {analysis_field}
   - DISTANCE: {distance_threshold}
   - CONCEPTUALIZATION: {conceptualization}
   - OUTPUT: {output_name}
3. Output contains Gi* z-scores and p-values:
   - High positive z-score = Hot spot (cluster of high values)
   - Low negative z-score = Cold spot (cluster of low values)
   - Near zero = Random pattern
4. Style with diverging color ramp (red=hot, blue=cold).

**QGIS Algorithm:** native:hotspotanalysis
**Use Case:** Crime clusters, disease outbreaks, retail hotspots, pollution""",
        tags=["hotspot", "getis-ord", "clustering", "spatial statistics", "native:hotspotanalysis"],
    ))

    # 2. Viewshed Analysis
    registry.register(PromptSpec(
        name="viewshed_analysis",
        description="Calculate visible areas from observer points on a DEM.",
        category=PromptCategory.ANALYSIS,
        arguments=[
            PromptArgument("dem_layer", "Input DEM raster layer"),
            PromptArgument("observer_points", "Point layer with observer locations"),
            PromptArgument("observer_height", "Height of observer above ground (meters)", default=1.75, required=False),
            PromptArgument("target_height", "Height of target above ground (meters)", default=0, required=False),
            PromptArgument("max_distance", "Maximum visibility distance (meters)", default="", required=False),
            PromptArgument("output_name", "Name for output viewshed layer", default="Viewshed", required=False),
        ],
        template="""Viewshed (Visibility) Analysis in QGIS:

**DEM Layer:** {dem_layer}
**Observer Points:** {observer_points}
**Observer Height:** {observer_height} m
**Target Height:** {target_height} m
**Max Distance:** {max_distance} m
**Output Layer:** {output_name}

**Steps:**
1. Run "native:viewshed" algorithm (requires QGIS 3.22+):
   - INPUT: {dem_layer}
   - OBSERVER_POINTS: {observer_points}
   - OBSERVER_HEIGHT: {observer_height}
   - TARGET_HEIGHT: {target_height}
   - MAX_DISTANCE: {max_distance}
   - OUTPUT: {output_name}
2. Output: raster where 1=visible, 0=not visible (or cumulative count).
3. For multiple observers: each cell shows count of observers that can see it.
4. Consider Earth curvature and atmospheric refraction for long distances.

**QGIS Algorithm:** native:viewshed
**Use Case:** Tower placement, scenic viewpoints, military, wind farms""",
        tags=["viewshed", "visibility", "line of sight", "dem", "native:viewshed"],
    ))

    # 3. Cost Distance / Least Cost Path
    registry.register(PromptSpec(
        name="cost_distance",
        description="Calculate least-cost distance and paths from source across a cost surface.",
        category=PromptCategory.ANALYSIS,
        arguments=[
            PromptArgument("source_layer", "Source point/polygon layer"),
            PromptArgument("cost_raster", "Cost surface raster (friction/cost per unit distance)"),
            PromptArgument("max_distance", "Maximum cost distance to compute", default="", required=False),
            PromptArgument("output_distance", "Name for cost distance raster", default="Cost_Distance", required=False),
            PromptArgument("output_backlink", "Name for backlink raster (for path tracing)", default="Cost_Backlink", required=False),
        ],
        template="""Cost Distance / Least-Cost Path Analysis in QGIS:

**Source Layer:** {source_layer}
**Cost Raster:** {cost_raster} (higher = more difficult to traverse)
**Max Distance:** {max_distance}
**Output Distance:** {output_distance}
**Output Backlink:** {output_backlink}

**Steps:**
1. Prepare cost raster (e.g., slope, land cover friction, combined).
2. Run "grass7:r.cost" or "grass7:r.walk" for anisotropic cost:
   - INPUT: {cost_raster}
   - START_POINTS: {source_layer}
   - MAX_COST: {max_distance}
   - OUTPUT: {output_distance}
   - OUTPUT_BACKLINK: {output_backlink}
3. For least-cost PATH: use "grass7:r.drain" with backlink raster.
4. Result shows accumulated cost from source to every cell.

**QGIS Algorithms:** grass7:r.cost, grass7:r.walk, grass7:r.drain
**Use Case:** Wildlife corridors, pipeline routing, evacuation paths, hiking trails""",
        tags=["cost distance", "least cost path", "friction", "routing", "grass7:r.cost"],
    ))

    # 4. Zonal Statistics
    registry.register(PromptSpec(
        name="zonal_statistics",
        description="Calculate raster statistics for each zone in a vector layer.",
        category=PromptCategory.ANALYSIS,
        arguments=[
            PromptArgument("zone_layer", "Vector layer defining zones (polygons)"),
            PromptArgument("raster_layer", "Raster layer to calculate statistics from"),
            PromptArgument("zone_field", "Field in zone layer to identify zones (optional)", default="", required=False),
            PromptArgument("statistics", "Statistics to calculate", default="mean,count,sum,min,max,std", required=False),
            PromptArgument("output_prefix", "Prefix for output fields", default="zonal_", required=False),
            PromptArgument("output_name", "Name for output layer", default="Zonal_Stats", required=False),
        ],
        template="""Zonal Statistics in QGIS:

**Zone Layer:** {zone_layer} (polygons)
**Raster Layer:** {raster_layer}
**Zone ID Field:** {zone_field} (optional, uses FID if empty)
**Statistics:** {statistics} (comma-separated: mean,count,sum,min,max,std,median,majority,minority,variety,range)
**Output Prefix:** {output_prefix}
**Output Layer:** {output_name}

**Steps:**
1. Run "native:zonalstatisticsfb" algorithm:
   - INPUT: {zone_layer}
   - INPUT_RASTER: {raster_layer}
   - RASTER_BAND: 1
   - COLUMN_PREFIX: {output_prefix}
   - STATISTICS: [{statistics}]
   - OUTPUT: {output_name}
2. Selected statistics added as new fields to zone layer.
3. Use for: elevation stats per watershed, land cover per admin unit, etc.

**QGIS Algorithm:** native:zonalstatisticsfb
**Use Case:** Watershed analysis, administrative reporting, sampling design""",
        tags=["zonal statistics", "zonals", "raster stats", "native:zonalstatisticsfb"],
    ))

    # 5. Spatial Join (Join Attributes by Location - Summary)
    registry.register(PromptSpec(
        name="spatial_join_summary",
        description="Join attributes from one layer to another with summary statistics for multiple matches.",
        category=PromptCategory.ANALYSIS,
        arguments=[
            PromptArgument("target_layer", "Layer to receive joined attributes"),
            PromptArgument("join_layer", "Layer providing attributes to join"),
            PromptArgument("predicate", "Spatial relationship", default="intersects", required=False, enum=["intersects", "contains", "within", "touches", "crosses", "overlaps"]),
            PromptArgument("summary", "Summary for multiple matches", default="mean", required=False, enum=["count", "sum", "mean", "median", "std", "min", "max", "range", "majority", "minority", "variety"]),
            PromptArgument("join_fields", "Fields to join (comma-separated, empty=all)", default="", required=False),
            PromptArgument("output_name", "Name for output layer", default="Spatial_Join", required=False),
        ],
        template="""Spatial Join with Summary Statistics in QGIS:

**Target Layer:** {target_layer}
**Join Layer:** {join_layer}
**Predicate:** {predicate}
**Summary Method:** {summary}
**Join Fields:** {join_fields}
**Output Layer:** {output_name}

**Steps:**
1. Run "native:joinattributesbylocationsummary" algorithm:
   - INPUT: {target_layer}
   - JOIN: {join_layer}
   - PREDICATE: [{predicate}]
   - JOIN_FIELDS: {join_fields}
   - SUMMARIES: [{summary}]
   - OUTPUT: {output_name}
2. For each target feature, summarizes all matching join features.
3. Output fields prefixed with join layer name + summary method.

**QGIS Algorithm:** native:joinattributesbylocationsummary
**Use Case:** Points in polygons (count, mean), census in zones, facility access""",
        tags=["spatial join", "summary", "aggregate", "native:joinattributesbylocationsummary"],
    ))

    # 6. Nearest Neighbor Analysis
    registry.register(PromptSpec(
        name="nearest_neighbor",
        description="Find nearest features and distances between layers.",
        category=PromptCategory.ANALYSIS,
        arguments=[
            PromptArgument("input_layer", "Layer to find neighbors for"),
            PromptArgument("target_layer", "Layer to search for neighbors in"),
            PromptArgument("max_distance", "Maximum search distance", default="", required=False),
            PromptArgument("k_neighbors", "Number of nearest neighbors to find", default=1, required=False),
            PromptArgument("output_name", "Name for output layer", default="Nearest_Neighbor", required=False),
        ],
        template="""Nearest Neighbor Analysis in QGIS:

**Input Layer:** {input_layer}
**Target Layer:** {target_layer}
**Max Distance:** {max_distance}
**K Neighbors:** {k_neighbors}
**Output Layer:** {output_name}

**Steps:**
1. Run "native:joinbynearest" algorithm (QGIS 3.14+):
   - INPUT: {input_layer}
   - INPUT_2: {target_layer}
   - FIELDS_TO_COPY: [] (empty = all)
   - DISCARD_NONMATCHING: false
   - PREFIX: "nn_"
   - NEIGHBORS: {k_neighbors}
   - MAX_DISTANCE: {max_distance}
   - OUTPUT: {output_name}
2. Each input feature gets attributes of nearest target feature(s).
3. Distance field added: nn_distance.

**QGIS Algorithm:** native:joinbynearest
**Use Case:** Nearest facility, service area assignment, proximity analysis""",
        tags=["nearest neighbor", "distance", "join", "native:joinbynearest"],
    ))

    # 7. Cluster Analysis (DBSCAN)
    registry.register(PromptSpec(
        name="dbscan_clustering",
        description="Density-based clustering (DBSCAN) for point patterns.",
        category=PromptCategory.ANALYSIS,
        arguments=[
            PromptArgument("point_layer", "Input point layer"),
            PromptArgument("min_points", "Minimum points to form a cluster", default=5, required=False),
            PromptArgument("eps", "Maximum distance between points in cluster (CRS units)", required=True),
            PromptArgument("output_name", "Name for output clustered layer", default="DBSCAN_Clusters", required=False),
        ],
        template="""DBSCAN Clustering in QGIS:

**Point Layer:** {point_layer}
**Min Points:** {min_points}
**Epsilon (eps):** {eps} (CRS units)
**Output Layer:** {output_name}

**Steps:**
1. Run "native:dbscanclustering" algorithm:
   - INPUT: {point_layer}
   - MIN_SIZE: {min_points}
   - EPS: {eps}
   - OUTPUT: {output_name}
2. Output: points with CLUSTER_ID field (-1 = noise, 0+ = cluster ID).
3. DBSCAN finds arbitrarily-shaped clusters based on density.
4. Style by CLUSTER_ID for visualization.

**QGIS Algorithm:** native:dbscanclustering
**Use Case:** Event clustering, anomaly detection, pattern discovery""",
        tags=["dbscan", "clustering", "density", "points", "native:dbscanclustering"],
    ))

    # 8. K-Means Clustering (on attributes)
    registry.register(PromptSpec(
        name="kmeans_clustering",
        description="K-means clustering on attribute fields.",
        category=PromptCategory.ANALYSIS,
        arguments=[
            PromptArgument("layer", "Input vector layer"),
            PromptArgument("fields", "Comma-separated numeric fields to cluster on", required=True),
            PromptArgument("n_clusters", "Number of clusters (k)", default=5, required=False),
            PromptArgument("output_name", "Name for output layer", default="KMeans_Clusters", required=False),
        ],
        template="""K-Means Clustering on Attributes in QGIS:

**Layer:** {layer}
**Fields:** {fields} (comma-separated numeric fields)
**K Clusters:** {n_clusters}
**Output Layer:** {output_name}

**Steps:**
1. Run "native:kmeansclustering" algorithm:
   - INPUT: {layer}
   - FIELDS: [{fields}]
   - N_CLUSTERS: {n_clusters}
   - OUTPUT: {output_name}
2. Output: features with CLUSTER_ID field (0 to k-1).
3. Standardize fields first if different scales (use field calculator).
4. Use for: customer segmentation, land use classification, regionalization.

**QGIS Algorithm:** native:kmeansclustering
**Use Case:** Attribute-based grouping, regionalization, segmentation""",
        tags=["kmeans", "clustering", "attributes", "segmentation", "native:kmeansclustering"],
    ))

    # 9. Moran's I (Spatial Autocorrelation)
    registry.register(PromptSpec(
        name="morans_i",
        description="Calculate Global Moran's I for spatial autocorrelation.",
        category=PromptCategory.ANALYSIS,
        arguments=[
            PromptArgument("layer", "Input vector layer"),
            PromptArgument("field", "Numeric field to test"),
            PromptArgument("weights", "Spatial weights type", default="INVERSE_DISTANCE", required=False, enum=["INVERSE_DISTANCE", "FIXED_DISTANCE", "K_NEAREST_NEIGHBORS", "CONTIGUITY"]),
            PromptArgument("distance", "Distance threshold (for fixed distance)", default="", required=False),
        ],
        template="""Moran's I Spatial Autocorrelation in QGIS:

**Layer:** {layer}
**Field:** {field}
**Weights Type:** {weights}
**Distance Threshold:** {distance}

**Steps:**
1. Run "native:globalmoransI" algorithm:
   - INPUT: {layer}
   - FIELD: {field}
   - WEIGHTS: {weights}
   - DISTANCE: {distance}
2. Output: Moran's I index (-1 to +1), z-score, p-value.
   - I > 0: Positive autocorrelation (clustering)
   - I < 0: Negative autocorrelation (dispersion)
   - I ≈ 0: Random pattern
3. Significant p-value (<0.05) indicates non-random pattern.

**QGIS Algorithm:** native:globalmoransI
**Use Case:** Pattern validation, model residuals, disease clustering""",
        tags=["moran", "autocorrelation", "spatial statistics", "native:globalmoransI"],
    ))

    # 10. Geographically Weighted Regression (GWR)
    registry.register(PromptSpec(
        name="gwr",
        description="Geographically Weighted Regression for spatially varying relationships.",
        category=PromptCategory.ANALYSIS,
        arguments=[
            PromptArgument("layer", "Input vector layer with dependent & independent variables"),
            PromptArgument("dependent", "Dependent variable field"),
            PromptArgument("independents", "Comma-separated independent variable fields"),
            PromptArgument("bandwidth", "Kernel bandwidth (adaptive or fixed)", default="adaptive", required=False),
            PromptArgument("kernel", "Kernel function", default="gaussian", required=False, enum=["gaussian", "bisquare"]),
            PromptArgument("output_name", "Name for output layer", default="GWR_Results", required=False),
        ],
        template="""Geographically Weighted Regression (GWR) in QGIS:

**Layer:** {layer}
**Dependent Variable:** {dependent}
**Independent Variables:** {independents}
**Bandwidth:** {bandwidth}
**Kernel:** {kernel}
**Output Layer:** {output_name}

**Steps:**
1. Run "native:gwr" algorithm (requires QGIS 3.20+):
   - INPUT: {layer}
   - DEPENDENT: {dependent}
   - INDEPENDENTS: [{independents}]
   - BANDWIDTH: {bandwidth}
   - KERNEL: {kernel}
   - OUTPUT: {output_name}
2. Output: local coefficients for each independent variable per feature.
3. Also provides: local R², residuals, standard errors.
4. Map coefficients to see spatial non-stationarity.

**QGIS Algorithm:** native:gwr
**Use Case:** House price drivers, environmental determinants, spatially varying relationships""",
        tags=["gwr", "regression", "spatially varying", "native:gwr"],
    ))