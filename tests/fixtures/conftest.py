"""Pytest fixtures for QGIS integration tests.

Provides:
- qgis_app: Headless QgsApplication lifecycle
- clean_project: Fresh QgsProject per test
- sample_vector_layer: Loaded vector layer (points, lines, polygons)
- sample_raster_layer: Loaded raster layer (DEM)
- sample_project: QGIS project with layers
- temp_dir: Temporary directory for test outputs
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Generator

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Try to import QGIS - tests will skip if not available
try:
    from qgis.core import (
        QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer,
        QgsCoordinateReferenceSystem, QgsVectorFileWriter, QgsRasterFileWriter,
        QgsWkbTypes, QgsField, QgsFeature, QgsGeometry, QgsPointXY
    )
    from qgis.PyQt.QtCore import QVariant
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

# Skip all fixtures if QGIS not available
pytestmark = pytest.mark.skipif(not QGIS_AVAILABLE, reason="QGIS not available")


@pytest.fixture(scope="session")
def qgis_app() -> Generator[QgsApplication, None, None]:
    """Session-scoped headless QgsApplication."""
    # Set up QGIS prefix path if needed (for Windows/CI)
    qgis_prefix = os.environ.get("QGIS_PREFIX_PATH")
    if qgis_prefix:
        QgsApplication.setPrefixPath(qgis_prefix, True)

    app = QgsApplication([], False)
    app.initQgis()

    yield app

    app.exitQgis()


@pytest.fixture(scope="function")
def clean_project(qgis_app) -> Generator[QgsProject, None, None]:
    """Fresh QgsProject for each test."""
    project = QgsProject.instance()
    project.clear()
    project.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
    yield project
    project.clear()


@pytest.fixture(scope="session")
def temp_dir() -> Generator[Path, None, None]:
    """Temporary directory for test outputs."""
    tmp = Path(tempfile.mkdtemp(prefix="uagis_test_"))
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="session")
def test_data_dir(temp_dir) -> Path:
    """Directory for test data (generated once per session)."""
    data_dir = temp_dir / "test_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture(scope="session")
def sample_vector_gpkg(test_data_dir) -> Path:
    """Generate a GeoPackage with point, line, and polygon layers."""
    gpkg_path = test_data_dir / "sample.gpkg"
    if gpkg_path.exists():
        return gpkg_path

    # Create using ogr
    from osgeo import ogr, osr

    driver = ogr.GetDriverByName("GPKG")
    ds = driver.CreateDataSource(str(gpkg_path))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)

    # Points layer
    lyr = ds.CreateLayer("points", srs, ogr.wkbPoint)
    lyr.CreateField(ogr.FieldDefn("name", ogr.OFTString))
    lyr.CreateField(ogr.FieldDefn("value", ogr.OFTInteger))
    lyr.CreateField(ogr.FieldDefn("category", ogr.OFTString))
    for i, (x, y) in enumerate([(-74.0, 40.0), (-73.5, 40.5), (-73.0, 41.0), (-72.5, 41.5), (-72.0, 42.0)]):
        f = ogr.Feature(lyr.GetLayerDefn())
        f.SetField("name", f"point_{i}")
        f.SetField("value", i * 10)
        f.SetField("category", "A" if i % 2 == 0 else "B")
        geom = ogr.Geometry(ogr.wkbPoint)
        geom.AddPoint(x, y)
        f.SetGeometry(geom)
        lyr.CreateFeature(f)

    # Lines layer
    lyr = ds.CreateLayer("lines", srs, ogr.wkbLineString)
    lyr.CreateField(ogr.FieldDefn("name", ogr.OFTString))
    lyr.CreateField(ogr.FieldDefn("length_km", ogr.OFTReal))
    f = ogr.Feature(lyr.GetLayerDefn())
    f.SetField("name", "route_1")
    f.SetField("length_km", 125.5)
    geom = ogr.Geometry(ogr.wkbLineString)
    geom.AddPoint(-74.0, 40.0)
    geom.AddPoint(-73.5, 40.5)
    geom.AddPoint(-73.0, 41.0)
    geom.AddPoint(-72.5, 41.5)
    geom.AddPoint(-72.0, 42.0)
    f.SetGeometry(geom)
    lyr.CreateFeature(f)

    # Polygons layer
    lyr = ds.CreateLayer("polygons", srs, ogr.wkbPolygon)
    lyr.CreateField(ogr.FieldDefn("name", ogr.OFTString))
    lyr.CreateField(ogr.FieldDefn("area_km2", ogr.OFTReal))
    lyr.CreateField(ogr.FieldDefn("zone", ogr.OFTString))
    f = ogr.Feature(lyr.GetLayerDefn())
    f.SetField("name", "zone_1")
    f.SetField("area_km2", 2500.0)
    f.SetField("zone", "residential")
    ring = ogr.Geometry(ogr.wkbLinearRing)
    ring.AddPoint(-74.5, 39.5)
    ring.AddPoint(-72.5, 39.5)
    ring.AddPoint(-72.5, 42.5)
    ring.AddPoint(-74.5, 42.5)
    ring.AddPoint(-74.5, 39.5)
    geom = ogr.Geometry(ogr.wkbPolygon)
    geom.AddGeometry(ring)
    f.SetGeometry(geom)
    lyr.CreateFeature(f)

    # MultiPolygon layer
    lyr = ds.CreateLayer("multipolygons", srs, ogr.wkbMultiPolygon)
    lyr.CreateField(ogr.FieldDefn("name", ogr.OFTString))
    f = ogr.Feature(lyr.GetLayerDefn())
    f.SetField("name", "multi_1")
    multi = ogr.Geometry(ogr.wkbMultiPolygon)
    for x_offset in [0, 0.5]:
        ring = ogr.Geometry(ogr.wkbLinearRing)
        ring.AddPoint(-71.5 + x_offset, 39.5)
        ring.AddPoint(-71.0 + x_offset, 39.5)
        ring.AddPoint(-71.0 + x_offset, 40.0)
        ring.AddPoint(-71.5 + x_offset, 40.0)
        ring.AddPoint(-71.5 + x_offset, 39.5)
        poly = ogr.Geometry(ogr.wkbPolygon)
        poly.AddGeometry(ring)
        multi.AddGeometry(poly)
    f.SetGeometry(multi)
    lyr.CreateFeature(f)

    ds = None
    return gpkg_path


@pytest.fixture(scope="session")
def sample_raster_tif(test_data_dir) -> Path:
    """Generate a synthetic DEM GeoTIFF."""
    tif_path = test_data_dir / "dem.tif"
    if tif_path.exists():
        return tif_path

    from osgeo import gdal, osr
    import numpy as np

    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(str(tif_path), 200, 200, 1, gdal.GDT_Float32)

    # GeoTransform: top-left at (-75, 43), pixel size 0.05 deg
    ds.SetGeoTransform([-75.0, 0.05, 0.0, 43.0, 0.0, -0.05])

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    ds.SetProjection(srs.ExportToWkt())

    band = ds.GetRasterBand(1)
    # Synthetic elevation: hill + noise
    y, x = np.mgrid[0:200, 0:200]
    center_x, center_y = 100, 100
    dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
    elevation = 1000 * np.exp(-dist / 50) + np.random.rand(200, 200) * 50
    band.WriteArray(elevation.astype(np.float32))
    band.SetNoDataValue(-9999.0)
    band.SetMetadataItem("STATISTICS_MINIMUM", str(float(elevation.min())))
    band.SetMetadataItem("STATISTICS_MAXIMUM", str(float(elevation.max())))

    ds.FlushCache()
    ds = None
    return tif_path


@pytest.fixture(scope="session")
def sample_rgb_tif(test_data_dir) -> Path:
    """Generate a synthetic RGB GeoTIFF."""
    tif_path = test_data_dir / "rgb.tif"
    if tif_path.exists():
        return tif_path

    from osgeo import gdal, osr
    import numpy as np

    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(str(tif_path), 200, 200, 3, gdal.GDT_Byte)

    ds.SetGeoTransform([-75.0, 0.05, 0.0, 43.0, 0.0, -0.05])
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    ds.SetProjection(srs.ExportToWkt())

    # Create RGB bands with gradients
    for b in range(3):
        band = ds.GetRasterBand(b + 1)
        y, x = np.mgrid[0:200, 0:200]
        if b == 0:  # Red - horizontal gradient
            data = (x / 200 * 255).astype(np.uint8)
        elif b == 1:  # Green - vertical gradient
            data = (y / 200 * 255).astype(np.uint8)
        else:  # Blue - diagonal
            data = ((x + y) / 400 * 255).astype(np.uint8)
        band.WriteArray(data)

    ds.FlushCache()
    ds = None
    return tif_path


@pytest.fixture(scope="session")
def sample_unreferenced_tif(test_data_dir) -> Path:
    """Generate an unreferenced TIFF for georeferencing tests."""
    tif_path = test_data_dir / "scan_map.tif"
    if tif_path.exists():
        return tif_path

    from osgeo import gdal
    import numpy as np

    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(str(tif_path), 300, 300, 3, gdal.GDT_Byte)
    # No geotransform, no projection - unreferenced

    for b in range(3):
        band = ds.GetRasterBand(b + 1)
        # Simple pattern for feature detection
        y, x = np.mgrid[0:300, 0:300]
        if b == 0:
            data = ((x // 20) % 2 * 255).astype(np.uint8)  # Vertical stripes
        elif b == 1:
            data = ((y // 20) % 2 * 255).astype(np.uint8)  # Horizontal stripes
        else:
            data = (((x + y) // 20) % 2 * 255).astype(np.uint8)  # Checkerboard
        band.WriteArray(data)

    ds.FlushCache()
    ds = None
    return tif_path


@pytest.fixture(scope="session")
def sample_reference_tif(test_data_dir, sample_raster_tif) -> Path:
    """Copy DEM as reference for georeferencing."""
    ref_path = test_data_dir / "reference.tif"
    if ref_path.exists():
        return ref_path
    shutil.copy(sample_raster_tif, ref_path)
    return ref_path


@pytest.fixture(scope="function")
def sample_vector_layer(clean_project, sample_vector_gpkg) -> QgsVectorLayer:
    """Load vector layer into project."""
    layer = QgsVectorLayer(f"{sample_vector_gpkg}|layername=points", "test_points", "ogr")
    assert layer.isValid(), f"Failed to load vector layer: {layer.error().message()}"
    clean_project.addMapLayer(layer)
    yield layer
    clean_project.removeMapLayer(layer.id())


@pytest.fixture(scope="function")
def sample_line_layer(clean_project, sample_vector_gpkg) -> QgsVectorLayer:
    """Load line layer into project."""
    layer = QgsVectorLayer(f"{sample_vector_gpkg}|layername=lines", "test_lines", "ogr")
    assert layer.isValid(), f"Failed to load line layer: {layer.error().message()}"
    clean_project.addMapLayer(layer)
    yield layer
    clean_project.removeMapLayer(layer.id())


@pytest.fixture(scope="function")
def sample_polygon_layer(clean_project, sample_vector_gpkg) -> QgsVectorLayer:
    """Load polygon layer into project."""
    layer = QgsVectorLayer(f"{sample_vector_gpkg}|layername=polygons", "test_polygons", "ogr")
    assert layer.isValid(), f"Failed to load polygon layer: {layer.error().message()}"
    clean_project.addMapLayer(layer)
    yield layer
    clean_project.removeMapLayer(layer.id())


@pytest.fixture(scope="function")
def sample_raster_layer(clean_project, sample_raster_tif) -> QgsRasterLayer:
    """Load raster layer into project."""
    layer = QgsRasterLayer(str(sample_raster_tif), "test_dem")
    assert layer.isValid(), f"Failed to load raster layer: {layer.error().message()}"
    clean_project.addMapLayer(layer)
    yield layer
    clean_project.removeMapLayer(layer.id())


@pytest.fixture(scope="function")
def sample_rgb_layer(clean_project, sample_rgb_tif) -> QgsRasterLayer:
    """Load RGB raster layer into project."""
    layer = QgsRasterLayer(str(sample_rgb_tif), "test_rgb")
    assert layer.isValid(), f"Failed to load RGB layer: {layer.error().message()}"
    clean_project.addMapLayer(layer)
    yield layer
    clean_project.removeMapLayer(layer.id())


@pytest.fixture(scope="function")
def sample_project(clean_project, sample_vector_gpkg, sample_raster_tif) -> QgsProject:
    """Project with vector and raster layers loaded."""
    # Add vector
    v_layer = QgsVectorLayer(f"{sample_vector_gpkg}|layername=polygons", "polygons", "ogr")
    assert v_layer.isValid()
    clean_project.addMapLayer(v_layer)

    # Add raster
    r_layer = QgsRasterLayer(str(sample_raster_tif), "dem")
    assert r_layer.isValid()
    clean_project.addMapLayer(r_layer)

    # Set project CRS
    clean_project.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

    yield clean_project


@pytest.fixture(scope="function")
def bridge_executor():
    """Bridge executor for dispatcher tests."""
    from bridge.executor import PyQGISExecutor
    return PyQGISExecutor(None)


@pytest.fixture(scope="function")
def bridge_dispatcher(bridge_executor):
    """Bridge dispatcher for tool routing tests."""
    from bridge.dispatcher import BridgeDispatcher
    return BridgeDispatcher(bridge_executor)


@pytest.fixture(scope="function")
def mcp_registry():
    """MCP tool registry."""
    from mcp_server.registry import build_registry
    return build_registry()


# Helper fixtures for visual regression
@pytest.fixture(scope="session")
def visual_baselines_dir() -> Path:
    """Directory for visual regression baselines."""
    base = Path(__file__).parent.parent / "visual_baselines"
    base.mkdir(parents=True, exist_ok=True)
    return base


@pytest.fixture
def update_baselines() -> bool:
    """Check if UPDATE_BASELINES env var is set."""
    return os.environ.get("UPDATE_BASELINES", "0") == "1"