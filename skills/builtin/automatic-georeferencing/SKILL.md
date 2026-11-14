# Automatic Georeferencing Skill

## Overview

Analyzes a scanned map image, detects landmarks via OpenCV (ORB/SIFT), generates
candidate Ground Control Points (GCPs) matched to a reference raster, validates
them (duplicates, outliers, residuals), and executes the transformation via
QGIS/GDAL.

## Workflow

1. **Image Inspection** - Analyze dimensions, resolution, quality metrics
2. **Landmark Detection** - Find recognizable features (road intersections, river bends, bridges, buildings)
3. **Computer Vision** - ORB/SIFT feature detection, matching, RANSAC homography estimation
4. **Coordinate Identification** - Match source image pixels to reference raster coordinates via GDAL geotransform
5. **GCP Generation** - Create candidate GCPs with confidence scores
6. **GCP Validation** - Reject duplicates, low-confidence points, check spatial distribution
7. **Transformation** - Execute Helmert/Polynomial/Thin Plate Spline transformation via QGIS/GDAL
8. **Verification** - RMSE report, CRS check, extent validation

## Security Policy

- **No shell access** - Skill cannot execute shell commands
- **No network access** - Skill cannot make network requests
- **File access** - Read-only on declared input files only
- **Coordinate policy** - Coordinates are NEVER invented; they come from the reference raster via GDAL geotransform

## Operations

| Operation | Description | Required Params |
|-----------|-------------|-----------------|
| `inspect_image` | Inspect scanned map dimensions, quality, quality metrics | `image_path` |
| `detect_landmarks` | Detect landmarks via OpenCV ORB/SIFT + matching | `image_path`, optional `reference_image_path` |
| `generate_gcps` | Generate candidate GCPs matched to reference coordinates | `image_path`, `geotransform`, `crs` |
| `validate_gcps` | Validate GCPs: duplicates, outliers, distribution, RMSE | `gcps` (array) |
| `transform_with_qgis` | Execute georeferencing transformation via QGIS/GDAL | `image_path`, `output_path`, `gcps`, `method`, `target_crs` |

## Example Usage

```json
{
  "operation": "generate_gcps",
  "params": {
    "image_path": "/data/scanned_map.jpg",
    "geotransform": [0.0, 1.0, 0.0, 10.0, 0.0, -1.0],
    "crs": "EPSG:4326",
    "min_confidence": 0.5
  }
}
```

## Output Example

```json
{
  "gcps": [
    {
      "source_pixel_x": 150.5,
      "source_pixel_y": 200.3,
      "dest_map_x": 78.1234,
      "dest_map_y": 23.4567,
      "crs": "EPSG:4326",
      "confidence": 0.85,
      "landmark_description": "road intersection",
      "validation_status": "accepted"
    }
  ],
  "count": 5,
  "validation_report": {
    "accepted": 5,
    "rejected": 2,
    "rmse": 2.3,
    "min_points_met": true,
    "distribution_ok": true
  }
}
```

## Error Handling

- Returns `FAILED` if reference data is insufficient
- Returns `NEEDS_REVIEW` if RMSE exceeds threshold
- Returns `PARTIAL_SUCCESS` if some GCPs are valid but not optimal
- Never invents coordinates - requires trusted reference data
