#!/usr/bin/env python3
"""Generate synthetic test data for Universal AI GIS Studio integration tests.

Creates:
- sample.gpkg: Vector data (points, lines, polygons, multipolygons)
- dem.tif: Single-band DEM (Float32)
- rgb.tif: Three-band RGB (Byte)
- scan_map.tif: Unreferenced TIFF for georeferencing
- reference.tif: Copy of DEM for GCP reference

Usage:
    python scripts/generate_test_data.py [--output-dir DIR]
"""

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np
from osgeo import gdal, ogr, osr


def create_vector_gpkg(output_path: Path):
    """Create a GeoPackage with multiple geometry types."""
    print(f"Creating vector GeoPackage: {output_path}")

    driver = ogr.GetDriverByName("GPKG")
    if output_path.exists():
        driver.DeleteDataSource(str(output_path))

    ds = driver.CreateDataSource(str(output_path))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)  # WGS84

    # ============================================================
    # Points layer - 10 features
    # ============================================================
    lyr = ds.CreateLayer("points", srs, ogr.wkbPoint)
    lyr.CreateField(ogr.FieldDefn("name", ogr.OFTString))
    lyr.CreateField(ogr.FieldDefn("value", ogr.OFTInteger))
    lyr.CreateField(ogr.FieldDefn("category", ogr.OFTString))
    lyr.CreateField(ogr.FieldDefn("timestamp", ogr.OFTDateTime))

    categories = ["A", "B", "C", "D"]
    for i in range(10):
        f = ogr.Feature(lyr.GetLayerDefn())
        f.SetField("name", f"point_{i:02d}")
        f.SetField("value", i * 100)
        f.SetField("category", categories[i % len(categories)])
        f.SetField("timestamp", f"2024-01-{(i % 28) + 1:02d}T12:00:00")
        geom = ogr.Geometry(ogr.wkbPoint)
        # Spread across a region
        x = -74.0 + (i % 5) * 0.5
        y = 40.0 + (i // 5) * 0.5
        geom.AddPoint(x, y)
        f.SetGeometry(geom)
        lyr.CreateFeature(f)

    # ============================================================
    # Lines layer - 5 features
    # ============================================================
    lyr = ds.CreateLayer("lines", srs, ogr.wkbLineString)
    lyr.CreateField(ogr.FieldDefn("name", ogr.OFTString))
    lyr.CreateField(ogr.FieldDefn("length_km", ogr.OFTReal))
    lyr.CreateField(ogr.FieldDefn("type", ogr.OFTString))

    line_types = ["road", "river", "rail", "trail", "border"]
    for i in range(5):
        f = ogr.Feature(lyr.GetLayerDefn())
        f.SetField("name", f"{line_types[i]}_{i}")
        f.SetField("length_km", 50.0 + i * 25.5)
        f.SetField("type", line_types[i])
        geom = ogr.Geometry(ogr.wkbLineString)
        # Create curved lines
        for j in range(10):
            x = -74.0 + i * 0.3 + j * 0.1
            y = 40.0 + i * 0.2 + np.sin(j * 0.5) * 0.1
            geom.AddPoint(x, y)
        f.SetGeometry(geom)
        lyr.CreateFeature(f)

    # ============================================================
    # Polygons layer - 8 features
    # ============================================================
    lyr = ds.CreateLayer("polygons", srs, ogr.wkbPolygon)
    lyr.CreateField(ogr.FieldDefn("name", ogr.OFTString))
    lyr.CreateField(ogr.FieldDefn("area_km2", ogr.OFTReal))
    lyr.CreateField(ogr.FieldDefn("zone", ogr.OFTString))
    lyr.CreateField(ogr.FieldDefn("population", ogr.OFTInteger64))

    zones = ["residential", "commercial", "industrial", "park", "water", "agricultural", "forest", "urban"]
    for i in range(8):
        f = ogr.Feature(lyr.GetLayerDefn())
        f.SetField("name", f"{zones[i]}_zone_{i}")
        f.SetField("area_km2", 100.0 + i * 50.0)
        f.SetField("zone", zones[i])
        f.SetField("population", int(1000 + i * 5000))

        ring = ogr.Geometry(ogr.wkbLinearRing)
        # Create grid of polygons
        col = i % 4
        row = i // 4
        x0 = -74.5 + col * 0.5
        y0 = 39.5 + row * 0.5
        x1 = x0 + 0.45
        y1 = y0 + 0.45
        ring.AddPoint(x0, y0)
        ring.AddPoint(x1, y0)
        ring.AddPoint(x1, y1)
        ring.AddPoint(x0, y1)
        ring.AddPoint(x0, y0)
        geom = ogr.Geometry(ogr.wkbPolygon)
        geom.AddGeometry(ring)
        f.SetGeometry(geom)
        lyr.CreateFeature(f)

    # ============================================================
    # MultiPolygons layer - 3 features
    # ============================================================
    lyr = ds.CreateLayer("multipolygons", srs, ogr.wkbMultiPolygon)
    lyr.CreateField(ogr.FieldDefn("name", ogr.OFTString))
    lyr.CreateField(ogr.FieldDefn("part_count", ogr.OFTInteger))

    for i in range(3):
        f = ogr.Feature(lyr.GetLayerDefn())
        f.SetField("name", f"multi_region_{i}")
        f.SetField("part_count", 2 + i)
        multi = ogr.Geometry(ogr.wkbMultiPolygon)
        for part in range(2 + i):
            ring = ogr.Geometry(ogr.wkbLinearRing)
            px = -71.0 + i * 0.5 + part * 0.2
            py = 39.0 + i * 0.3
            ring.AddPoint(px, py)
            ring.AddPoint(px + 0.15, py)
            ring.AddPoint(px + 0.15, py + 0.15)
            ring.AddPoint(px, py + 0.15)
            ring.AddPoint(px, py)
            poly = ogr.Geometry(ogr.wkbPolygon)
            poly.AddGeometry(ring)
            multi.AddGeometry(poly)
        f.SetGeometry(multi)
        lyr.CreateFeature(f)

    ds = None
    print(f"  Created layers: points, lines, polygons, multipolygons")


def create_dem_tif(output_path: Path, width: int = 500, height: int = 500):
    """Create a synthetic DEM GeoTIFF."""
    print(f"Creating DEM GeoTIFF: {output_path} ({width}x{height})")

    driver = gdal.GetDriverByName("GTiff")
    if output_path.exists():
        driver.Delete(str(output_path))

    ds = driver.Create(str(output_path), width, height, 1, gdal.GDT_Float32)

    # GeoTransform: ~10km x 10km at 20m resolution
    # Top-left at UTM zone 18N (EPSG:32618) for more realistic DEM
    ds.SetGeoTransform([500000.0, 20.0, 0.0, 4500000.0, 0.0, -20.0])

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32618)  # WGS84 / UTM zone 18N
    ds.SetProjection(srs.ExportToWkt())

    band = ds.GetRasterBand(1)

    # Generate synthetic terrain: hills, valleys, noise
    y, x = np.mgrid[0:height, 0:width]
    xf = x / width
    yf = y / height

    # Multiple hill functions
    elevation = np.zeros((height, width), dtype=np.float32)

    # Hill 1
    cx, cy = 0.3, 0.7
    dist1 = np.sqrt((xf - cx)**2 + (yf - cy)**2)
    elevation += 300 * np.exp(-dist1 / 0.15)

    # Hill 2
    cx, cy = 0.7, 0.3
    dist2 = np.sqrt((xf - cx)**2 + (yf - cy)**2)
    elevation += 250 * np.exp(-dist2 / 0.12)

    # Ridge
    elevation += 100 * np.exp(-(yf - 0.5)**2 / 0.01)

    # Valley
    elevation -= 50 * np.exp(-(xf - 0.5)**2 / 0.02)

    # Base elevation
    elevation += 100

    # Add noise
    np.random.seed(42)
    elevation += np.random.normal(0, 5, (height, width)).astype(np.float32)

    # Clamp to reasonable range
    elevation = np.clip(elevation, 0, 600)

    band.WriteArray(elevation)
    band.SetNoDataValue(-9999.0)
    band.SetMetadataItem("STATISTICS_MINIMUM", str(float(elevation.min())))
    band.SetMetadataItem("STATISTICS_MAXIMUM", str(float(elevation.max())))
    band.SetMetadataItem("STATISTICS_MEAN", str(float(elevation.mean())))
    band.SetMetadataItem("STATISTICS_STDDEV", str(float(elevation.std())))

    # Build overviews
    ds.BuildOverviews("AVERAGE", [2, 4, 8, 16])

    ds.FlushCache()
    ds = None
    print(f"  Elevation range: {elevation.min():.1f} - {elevation.max():.1f} m")


def create_rgb_tif(output_path: Path, width: int = 500, height: int = 500):
    """Create a synthetic RGB GeoTIFF."""
    print(f"Creating RGB GeoTIFF: {output_path} ({width}x{height})")

    driver = gdal.GetDriverByName("GTiff")
    if output_path.exists():
        driver.Delete(str(output_path))

    ds = driver.Create(str(output_path), width, height, 3, gdal.GDT_Byte)

    ds.SetGeoTransform([500000.0, 20.0, 0.0, 4500000.0, 0.0, -20.0])
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32618)
    ds.SetProjection(srs.ExportToWkt())

    y, x = np.mgrid[0:height, 0:width]
    xf = x / width
    yf = y / height

    # Band 1 (Red) - terrain-like pattern
    red = ((np.sin(xf * 10) * np.cos(yf * 10) + 1) * 127).astype(np.uint8)

    # Band 2 (Green) - vegetation-like pattern
    green = ((np.sin(xf * 5 + 1) * np.cos(yf * 5 + 1) + 1) * 100 + 50).astype(np.uint8)

    # Band 3 (Blue) - water-like pattern
    blue = ((np.sin((xf + yf) * 8) + 1) * 80 + 30).astype(np.uint8)

    for b, data in enumerate([red, green, blue], 1):
        band = ds.GetRasterBand(b)
        band.WriteArray(data)

    ds.FlushCache()
    ds = None
    print(f"  Created 3-band RGB")


def create_unreferenced_tif(output_path: Path, width: int = 400, height: int = 400):
    """Create an unreferenced TIFF for georeferencing tests."""
    print(f"Creating unreferenced TIFF: {output_path} ({width}x{height})")

    driver = gdal.GetDriverByName("GTiff")
    if output_path.exists():
        driver.Delete(str(output_path))

    ds = driver.Create(str(output_path), width, height, 3, gdal.GDT_Byte)
    # NO geotransform, NO projection - this is intentional for georeferencing tests

    y, x = np.mgrid[0:height, 0:width]
    xf = x / width
    yf = y / height

    # Create distinct patterns for feature matching
    # Red: vertical grid lines
    red = np.zeros((height, width), dtype=np.uint8)
    for i in range(0, width, 40):
        red[:, max(0, i-1):min(width, i+2)] = 255

    # Green: horizontal grid lines
    green = np.zeros((height, width), dtype=np.uint8)
    for i in range(0, height, 40):
        green[max(0, i-1):min(height, i+2), :] = 255

    # Blue: diagonal features + some noise
    blue = ((np.sin((xf + yf) * 20) + 1) * 100).astype(np.uint8)
    np.random.seed(123)
    noise = np.random.randint(0, 30, (height, width), dtype=np.uint8)
    blue = np.clip(blue.astype(np.int16) + noise.astype(np.int16), 0, 255).astype(np.uint8)

    for b, data in enumerate([red, green, blue], 1):
        band = ds.GetRasterBand(b)
        band.WriteArray(data)

    ds.FlushCache()
    ds = None
    print(f"  Created unreferenced scan with grid patterns")


def main():
    parser = argparse.ArgumentParser(description="Generate test data for UAGIS integration tests")
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=Path("tests/fixtures/data"),
        help="Output directory for test data"
    )
    parser.add_argument(
        "--clean", "-c",
        action="store_true",
        help="Remove existing files before generating"
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.clean:
        for f in output_dir.glob("*"):
            if f.is_file():
                f.unlink()
            else:
                shutil.rmtree(f, ignore_errors=True)

    print(f"Generating test data in: {output_dir}")
    print("=" * 60)

    # Generate all test files
    create_vector_gpkg(output_dir / "sample.gpkg")
    create_dem_tif(output_dir / "dem.tif")
    create_rgb_tif(output_dir / "rgb.tif")
    create_unreferenced_tif(output_dir / "scan_map.tif")

    # Copy DEM as reference for georeferencing
    ref_path = output_dir / "reference.tif"
    shutil.copy(output_dir / "dem.tif", ref_path)
    print(f"Copied DEM as reference: {ref_path}")

    print("=" * 60)
    print("Test data generation complete!")
    print(f"Files created in {output_dir}:")
    for f in sorted(output_dir.glob("*")):
        print(f"  {f.name} ({f.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()