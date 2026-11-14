"""Universal AI GIS Studio — Remote Sensing Prompts.

Prompt templates for satellite imagery processing workflows.
"""

from mcp_server.prompts.registry import PromptSpec, PromptArgument, PromptCategory


def register_remote_sensing_prompts(registry) -> None:
    """Register all remote sensing prompts."""

    # 1. Calculate NDVI
    registry.register(PromptSpec(
        name="calculate_ndvi",
        description="Calculate Normalized Difference Vegetation Index from Sentinel-2 or Landsat.",
        category=PromptCategory.REMOTE_SENSING,
        arguments=[
            PromptArgument("nir_band", "NIR band layer (Sentinel-2: B8, Landsat 8/9: Band 5)", required=True),
            PromptArgument("red_band", "Red band layer (Sentinel-2: B4, Landsat 8/9: Band 4)", required=True),
            PromptArgument("output_name", "Output NDVI layer name", default="NDVI", required=False),
            PromptArgument("formula", "NDVI formula", default="(NIR - RED) / (NIR + RED)", required=False),
        ],
        template="""Calculate NDVI in QGIS:

**NIR Band:** {nir_band}
**Red Band:** {red_band}
**Formula:** {formula}
**Output:** {output_name}

**Steps:**
1. Ensure both bands are loaded and aligned (same extent, resolution, CRS).
2. Run "native:rastercalculator":
   - EXPRESSION: "{formula}" (replace NIR/RED with layer references)
   - LAYERS: A={nir_band}, B={red_band}
   - EXPRESSION: "(A - B) / (A + B)"
   - OUTPUT: {output_name}
2. Style: Singleband pseudocolor, color ramp: RdYlGn, min=-1, max=1
3. Values: -1 to 1 (vegetation: 0.2-0.8, water: <0, bare soil: 0.1-0.2)

**Sentinel-2 Bands:** B8 (NIR, 10m), B4 (Red, 10m)
**Landsat 8/9 Bands:** Band 5 (NIR), Band 4 (Red)
**Use Case:** Vegetation health, crop monitoring, biomass estimation""",
        tags=["ndvi", "vegetation index", "sentinel", "landsat", "raster calculator", "remote sensing"],
    ))

    # 2. Calculate EVI (Enhanced Vegetation Index)
    registry.register(PromptSpec(
        name="calculate_evi",
        description="Calculate Enhanced Vegetation Index (reduces soil/atmosphere effects).",
        category=PromptCategory.REMOTE_SENSING,
        arguments=[
            PromptArgument("nir_band", "NIR band layer"),
            PromptArgument("red_band", "Red band layer"),
            PromptArgument("blue_band", "Blue band layer (Sentinel-2: B2, Landsat: Band 2)"),
            PromptArgument("output_name", "Output EVI layer", default="EVI", required=False),
            PromptArgument("L", "Canopy background adjustment", default=1.0, required=False),
            PromptArgument("C1", "Coefficient for aerosol resistance", default=6.0, required=False),
            PromptArgument("C2", "Coefficient for aerosol resistance", default=7.5, required=False),
            PromptArgument("G", "Gain factor", default=2.5, required=False),
        ],
        template="""Calculate EVI (Enhanced Vegetation Index) in QGIS:

**NIR Band:** {nir_band}
**Red Band:** {red_band}
**Blue Band:** {blue_band}
**Output:** {output_name}

**Formula:** EVI = G * (NIR - RED) / (NIR + C1*RED - C2*BLUE + L)
**Parameters:** L={L}, C1={C1}, C2={C2}, G={G}

**Steps:**
1. Run "native:rastercalculator":
   - LAYERS: A={nir_band}, B={red_band}, C={blue_band}
   - EXPRESSION: "{G} * (A - B) / (A + {C1}*B - {C2}*C + {L})"
   - OUTPUT: {output_name}
2. Style: Pseudocolor, RdYlGn, range -1 to 1

**Advantage over NDVI:** Better in high biomass, reduces soil/atmosphere noise
**Use Case:** Dense forests, crops, MODIS-style vegetation monitoring""",
        tags=["evi", "enhanced vegetation index", "modis", "remote sensing"],
    ))

    # 3. Calculate Multiple Spectral Indices
    registry.register(PromptSpec(
        name="calculate_spectral_indices",
        description="Calculate multiple spectral indices (NDVI, NDBI, NDWI, MNDWI, BSI, SAVI) at once.",
        category=PromptCategory.REMOTE_SENSING,
        arguments=[
            PromptArgument("bands", "Dictionary of band layers: {nir:layer, red:layer, green:layer, swir1:layer, swir2:layer, blue:layer}", required=True),
            PromptArgument("indices", "Comma-separated indices to calculate", default="NDVI,NDBI,NDWI,MNDWI,BSI,SAVI", required=False),
            PromptArgument("output_prefix", "Prefix for output layers", default="", required=False),
        ],
        template="""Calculate multiple spectral indices in QGIS:

**Bands:** {bands}
**Indices:** {indices}
**Output Prefix:** {output_prefix}

**Common Formulas:**
- NDVI = (NIR - RED) / (NIR + RED)
- NDBI = (SWIR1 - NIR) / (SWIR1 + NIR)  [Built-up]
- NDWI = (GREEN - NIR) / (GREEN + NIR)  [Water]
- MNDWI = (GREEN - SWIR1) / (GREEN + SWIR1)  [Better water]
- BSI = ((SWIR1 + RED) - (NIR + BLUE)) / ((SWIR1 + RED) + (NIR + BLUE))  [Bare soil]
- SAVI = (1+L) * (NIR - RED) / (NIR + RED + L)  [Soil-adjusted, L=0.5]

**Steps:**
For each index, run "native:rastercalculator" with appropriate expression.
Use batch processing or model builder for automation.

**Sentinel-2 Bands:** B2(Blue), B3(Green), B4(Red), B8(NIR), B11(SWIR1), B12(SWIR2)
**Landsat 8/9:** B2(Blue), B3(Green), B4(Red), B5(NIR), B6(SWIR1), B7(SWIR2)

**Use Case:** Comprehensive land cover characterization, multi-index analysis""",
        tags=["spectral indices", "ndvi", "ndbi", "ndwi", "mndwi", "bsi", "savi", "batch", "remote sensing"],
    ))

    # 4. Supervised Classification (Random Forest)
    registry.register(PromptSpec(
        name="supervised_classification",
        description="Train and apply Random Forest classifier for land cover mapping.",
        category=PromptCategory.REMOTE_SENSING,
        arguments=[
            PromptArgument("training_data", "Vector layer with training polygons + class field"),
            PromptArgument("class_field", "Field in training data containing class labels"),
            PromptArgument("input_rasters", "Comma-separated raster bands/features for classification"),
            PromptArgument("output_name", "Output classification raster", default="Classification", required=False),
            PromptArgument("n_trees", "Number of trees", default=100, required=False),
            PromptArgument("max_depth", "Max tree depth (0=unlimited)", default=0, required=False),
        ],
        template="""Supervised Classification (Random Forest) in QGIS:

**Training Data:** {training_data} (polygons with class field)
**Class Field:** {class_field}
**Input Rasters:** {input_rasters} (bands, indices, textures)
**Output:** {output_name}
**Trees:** {n_trees}
**Max Depth:** {max_depth}

**Steps:**
1. Prepare training polygons: each polygon = sample area, {class_field} = class name/ID
2. Stack input rasters (bands + indices) as multiband raster or use "native:rasterlayeruniquevaluesreport"
3. Run classification via:
   - **Option A (OTB):** "otb:TrainRandomForestClassifier" + "otb:ImageClassifier"
   - **Option B (SAGA):** "saga:randomforestclassifier" + "saga:randomforestprediction"
   - **Option C (Python/sklearn):** Custom script via Processing
4. Output: classified raster with class values
5. Style: Paletted/Unique values with class colors

**Training Tips:** 50-100 samples per class, stratified, independent validation set
**Use Case:** Land cover mapping, crop typing, urban extent, forest classification""",
        tags=["classification", "random forest", "supervised", "land cover", "machine learning", "remote sensing"],
    ))

    # 5. Unsupervised Classification (K-Means)
    registry.register(PromptSpec(
        name="unsupervised_classification",
        description="K-Means unsupervised clustering on raster bands.",
        category=PromptCategory.REMOTE_SENSING,
        arguments=[
            PromptArgument("input_rasters", "Comma-separated input raster bands"),
            PromptArgument("n_classes", "Number of classes/clusters", default=10, required=False),
            PromptArgument("output_name", "Output classification raster", default="Unsupervised_Class", required=False),
            PromptArgument("max_iterations", "Max iterations", default=100, required=False),
        ],
        template="""Unsupervised Classification (K-Means) in QGIS:

**Input Rasters:** {input_rasters}
**Number of Classes:** {n_classes}
**Output:** {output_name}
**Max Iterations:** {max_iterations}

**Steps:**
1. Stack input rasters into multiband (or use each band as feature)
2. Run "saga:kmeansclustering" or "otb:KMeansClassification":
   - INPUT: {input_rasters}
   - NCLASSES: {n_classes}
   - MAX_ITERATIONS: {max_iterations}
   - OUTPUT: {output_name}
3. Result: raster with cluster IDs (0 to n_classes-1)
4. Interpret clusters: overlay with reference data, assign class labels
5. Optional: Reclassify cluster IDs to meaningful class names

**Use Case:** Exploratory analysis, no training data, pre-classification stratification""",
        tags=["unsupervised", "kmeans", "clustering", "classification", "remote sensing"],
    ))

    # 6. Change Detection (Image Differencing)
    registry.register(PromptSpec(
        name="change_detection_difference",
        description="Detect changes between two dates using image differencing.",
        category=PromptCategory.CHANGE_DETECTION,
        arguments=[
            PromptArgument("raster_t1", "Raster at time 1 (earlier)"),
            PromptArgument("raster_t2", "Raster at time 2 (later)"),
            PromptArgument("method", "Difference method", default="simple", required=False, enum=["simple", "ratio", "log_ratio", "cva"]),
            PromptArgument("threshold", "Change threshold (std deviations)", default=2.0, required=False),
            PromptArgument("output_name", "Output change layer", default="Change_Detection", required=False),
        ],
        template="""Change Detection (Image Differencing) in QGIS:

**Time 1 Raster:** {raster_t1}
**Time 2 Raster:** {raster_t2}
**Method:** {method}
**Threshold:** {threshold} std deviations
**Output:** {output_name}

**Methods:**
- Simple Difference: T2 - T1
- Ratio: T2 / T1
- Log Ratio: ln(T2 / T1)
- CVA (Change Vector Analysis): Multi-band magnitude + direction

**Steps:**
1. Ensure both rasters: same CRS, extent, resolution, radiometric calibration
2. Run "native:rastercalculator":
   - Simple: "B - A" (A=T1, B=T2)
   - Ratio: "B / A"
   - Log Ratio: "ln(B / A)"
3. Calculate statistics: mean, std of difference
4. Threshold: mean ± {threshold} * std
5. Reclassify: "No Change", "Increase", "Decrease"
6. Style: Diverging ramp (blue=decrease, white=no change, red=increase)

**Preprocessing:** Atmospheric correction, co-registration, radiometric normalization essential
**Use Case:** Deforestation, urban growth, flood mapping, crop harvest""",
        tags=["change detection", "image differencing", "time series", "deforestation", "urban growth", "remote sensing"],
    ))

    # 7. Change Detection (Post-Classification Comparison)
    registry.register(PromptSpec(
        name="change_detection_post_classification",
        description="Compare two classified rasters to detect land cover transitions.",
        category=PromptCategory.CHANGE_DETECTION,
        arguments=[
            PromptArgument("class_t1", "Classified raster at time 1"),
            PromptArgument("class_t2", "Classified raster at time 2"),
            PromptArgument("class_names", "Comma-separated class names (matching class values)"),
            PromptArgument("output_name", "Output change matrix layer", default="Change_Matrix", required=False),
            PromptArgument("output_table", "Output transition table (CSV)", default="", required=False),
        ],
        template="""Change Detection (Post-Classification Comparison) in QGIS:

**Classified T1:** {class_t1}
**Classified T2:** {class_t2}
**Class Names:** {class_names} (e.g., "Forest,Water,Urban,Agriculture,Bare")
**Output Raster:** {output_name}
**Output Table:** {output_table}

**Steps:**
1. Both classified rasters must use SAME class scheme/values
2. Run "saga:crossclassificationandtabulation" or "r.cross" (GRASS):
   - INPUT_A: {class_t1}
   - INPUT_B: {class_t2}
   - OUTPUT: {output_name}
3. Output raster: each pixel = transition code (e.g., 11=Forest→Forest, 12=Forest→Water)
4. Cross-tabulation table: rows=T1, cols=T2, values=pixel count/area
5. Calculate: net change, gross change, swap change per class
6. Style transition raster with qualitative color scheme

**Advantage:** Provides FROM-TO transitions, not just change/no-change
**Use Case:** Land cover change accounting, transition matrices, policy reporting""",
        tags=["change detection", "post-classification", "transition matrix", "land cover change", "remote sensing"],
    ))

    # 8. Cloud Masking (Sentinel-2 SCL Band)
    registry.register(PromptSpec(
        name="cloud_mask_sentinel2",
        description="Create cloud/cloud-shadow mask from Sentinel-2 Scene Classification Layer (SCL).",
        category=PromptCategory.REMOTE_SENSING,
        arguments=[
            PromptArgument("scl_band", "SCL band layer (band 10 in Sentinel-2 L2A)"),
            PromptArgument("cloud_classes", "SCL values to mask (comma-separated)", default="3,8,9,10,11", required=False),
            PromptArgument("dilate_pixels", "Dilate mask by N pixels", default=2, required=False),
            PromptArgument("output_name", "Output cloud mask", default="Cloud_Mask", required=False),
        ],
        template="""Cloud Mask from Sentinel-2 SCL in QGIS:

**SCL Band:** {scl_band}
**Mask Classes:** {cloud_classes} (3=cloud shadow, 8=cloud medium, 9=cloud high, 10=thin cirrus, 11=cloud)
**Dilate:** {dilate_pixels} pixels
**Output:** {output_name}

**SCL Values:**
- 0: No data
- 1: Saturated/defective
- 2: Dark area
- **3: Cloud shadows**
- 4: Vegetation
- 5: Bare soil
- 6: Water
- 7: Cloud low prob/unclassified
- **8: Cloud medium prob**
- **9: Cloud high prob**
- **10: Thin cirrus**
- **11: Snow/ice**

**Steps:**
1. Run "native:rastercalculator":
   - EXPRESSION: "(A=3) + (A=8) + (A=9) + (A=10) + (A=11)" (1=cloud, 0=clear)
   - LAYERS: A={scl_band}
   - OUTPUT: {output_name}_raw
2. Optional dilate: "gdal:proximity" + threshold or "native:buffer" on vectorized mask
3. Apply mask: Multiply original bands by (1 - mask) to set cloud pixels to NoData

**Use Case:** Preprocessing for time series, composites, classification""",
        tags=["cloud mask", "sentinel-2", "scl", "preprocessing", "remote sensing"],
    ))

    # 9. Cloud-Free Composite (Median/Max NDVI)
    registry.register(PromptSpec(
        name="cloud_free_composite",
        description="Create cloud-free composite from time series using median or max-NDVI.",
        category=PromptCategory.REMOTE_SENSING,
        arguments=[
            PromptArgument("raster_collection", "List of raster layers (same bands, different dates)"),
            PromptArgument("method", "Composite method", default="median", required=False, enum=["median", "max_ndvi", "min_ndvi", "recent"]),
            PromptArgument("output_name", "Output composite name", default="Composite", required=False),
            PromptArgument("ndvi_band_pair", "NIR,Red band names for max_ndvi", default="", required=False),
        ],
        template="""Cloud-Free Composite from Time Series in QGIS:

**Rasters:** {raster_collection} (same bands, multiple dates)
**Method:** {method}
**Output:** {output_name}
**NDVI Bands:** {ndvi_band_pair} (for max_ndvi)

**Methods:**
- Median: Per-pixel median across dates (robust to outliers)
- Max NDVI: Select pixel from date with highest NDVI (greenness)
- Min NDVI: Select pixel from date with lowest NDVI (senescence)
- Recent: Most recent clear observation

**Steps (QGIS native - limited):**
1. **For median:** Use "saga:rasterstatisticsforrasters" or Python/xarray
2. **For max_ndvi:** 
   - Calculate NDVI for each date
   - Use "saga:rastercalculator" with conditional logic
   - Or use Google Earth Engine / Python (recommended)

**Recommended:** Use Python with `odc-stac`, `xarray`, `planetary-computer` for large stacks:
```python
import xarray as xr
ds = xr.open_mfdataset(raster_paths)
composite = ds.median(dim='time')  # or ds.idxmax('ndvi')
```

**Use Case:** Annual/seasonal composites, cloud-prone regions, basemap creation""",
        tags=["composite", "median", "max ndvi", "time series", "cloud-free", "remote sensing"],
    ))

    # 10. Time Series Analysis (Phenology/Trends)
    registry.register(PromptSpec(
        name="time_series_analysis",
        description="Extract time series statistics and trends from raster stack.",
        category=PromptCategory.REMOTE_SENSING,
        arguments=[
            PromptArgument("raster_stack", "Multiband raster or list of rasters (time series)"),
            PromptArgument("dates", "Comma-separated dates for each band (YYYY-MM-DD)"),
            PromptArgument("aoi_layer", "Optional polygon AOI to extract statistics"),
            PromptArgument("output_prefix", "Prefix for output layers", default="TS_", required=False),
        ],
        template="""Time Series Analysis in QGIS:

**Raster Stack:** {raster_stack} (bands = time steps)
**Dates:** {dates} (YYYY-MM-DD per band)
**AOI:** {aoi_layer} (optional polygon)
**Output Prefix:** {output_prefix}

**Available Metrics (via SAGA/GRASS/Python):**
- Mean, Std, Min, Max per pixel across time
- Linear trend (Sen's slope, Mann-Kendall p-value)
- Phenology: SOS (start of season), EOS (end), Peak, Amplitude
- Breakpoint detection (BFAST, CCDC)
- Harmonic regression (Fourier)

**Steps (QGIS):**
1. **Basic stats:** "saga:rasterstatisticsforrasters" → mean, std, min, max
2. **Trends:** "r.series" (GRASS) with method=linear
3. **Phenology:** "r.green.biomass" or Python (scipy, phenopix)
4. **Breakpoints:** BFAST requires R/Python (bfast, pybfast)

**Recommended Python Stack:**
```python
import xarray as xr
from scipy import stats
# Mann-Kendall trend
# BFAST: from bfast import bfast
```

**Use Case:** Vegetation trends, degradation monitoring, crop calendars, climate impacts""",
        tags=["time series", "trend", "phenology", "mann-kendall", "sen's slope", "bfast", "remote sensing"],
    ))