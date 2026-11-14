"""Real QGIS integration tests for Universal AI GIS Studio.

These tests run against a real QGIS 4.2.3 instance. They skip gracefully
if QGIS is not available (recorded as "skipped", not "passed").
"""

import os
import sys
import unittest

# Try to import QGIS — if not available, skip all tests
try:
    from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer
    from qgis.PyQt.QtWidgets import QApplication
    QGIS_AVAILABLE = True
except Exception:
    QGIS_AVAILABLE = False

from bridge.executor import PyQGISExecutor
from bridge.dispatcher import BridgeDispatcher


class QGISBridgeIntegrationTest(unittest.TestCase):
    """Integration tests that require a running QGIS instance."""

    @classmethod
    def setUpClass(cls):
        if not QGIS_AVAILABLE:
            raise unittest.SkipTest("QGIS not available in this environment")
        # QGIS app must already be running (started by QGIS plugin)
        cls.project = QgsProject.instance()
        cls.executor = PyQGISExecutor(None)  # iface not needed for read ops
        cls.dispatcher = BridgeDispatcher(cls.executor)

    @unittest.skipUnless(QGIS_AVAILABLE, "QGIS not available")
    def test_bridge_health(self):
        """Bridge health endpoint returns QGIS connected."""
        result = self.executor.health()
        self.assertTrue(result.get("qgis_connected"))
        self.assertIsInstance(result.get("layer_count"), int)

    @unittest.skipUnless(QGIS_AVAILABLE, "QGIS not available")
    def test_project_inspect(self):
        """Project inspection returns metadata."""
        result = self.executor.inspect_project()
        self.assertIn("layer_count", result)
        self.assertIn("crs", result)
        self.assertIn("project_title", result)

    @unittest.skipUnless(QGIS_AVAILABLE, "QGIS not available")
    def test_layers_inspect(self):
        """Layer inspection returns layer list."""
        result = self.executor.inspect_layers()
        self.assertIn("layers", result)
        self.assertIn("count", result)
        self.assertIsInstance(result["count"], int)

    @unittest.skipUnless(QGIS_AVAILABLE, "QGIS not available")
    def test_canvas_inspect(self):
        """Canvas inspection returns extent, CRS, scale."""
        result = self.executor.inspect_canvas()
        self.assertIn("extent", result)
        self.assertIn("crs", result)
        self.assertIn("scale", result)

    @unittest.skipUnless(QGIS_AVAILABLE, "QGIS not available")
    def test_screen_capture(self):
        """Screen capture returns valid PNG base64."""
        result = self.executor.capture_canvas()
        self.assertIn("image_base64", result)
        self.assertIn("width", result)
        self.assertIn("height", result)
        self.assertEqual(result.get("format"), "png")
        # Verify base64 decodes
        import base64
        decoded = base64.b64decode(result["image_base64"])
        self.assertGreater(len(decoded), 0)

    @unittest.skipUnless(QGIS_AVAILABLE, "QGIS not available")
    def test_load_and_remove_layer(self):
        """Load a real vector/raster layer, then remove it."""
        # Try to find a sample dataset
        test_paths = [
            "D:/1 2 3 QGIS/sample_data/test.shp",
            "D:/1 2 3 QGIS/sample_data/test.gpkg",
            "D:/1 2 3 QGIS/sample_data/test.tif",
        ]
        loaded = False
        for path in test_paths:
            if os.path.exists(path):
                result = self.executor.load_layer(path=path, layer_name="test_layer")
                self.assertTrue(result.get("valid"))
                self.assertIn("id", result)
                loaded = True
                # Remove the layer
                remove_result = self.executor.remove_layer(layer_id=result["id"])
                self.assertTrue(remove_result.get("removed"))
                break
        if not loaded:
            self.skipTest("No sample dataset found for layer load test")

    @unittest.skipUnless(QGIS_AVAILABLE, "QGIS not available")
    def test_algorithms_discover(self):
        """Algorithm discovery returns installed QGIS processing algorithms."""
        import processing
        from qgis.core import QgsApplication
        registry = QgsApplication.processingRegistry()
        algs = list(registry.algorithms())
        self.assertGreater(len(algs), 0)
        # Check that common algorithms exist
        alg_ids = [a.id() for a in algs]
        self.assertTrue(any("buffer" in aid for aid in alg_ids),
                        "native:buffer algorithm not found")

    @unittest.skipUnless(QGIS_AVAILABLE, "QGIS not available")
    def test_dispatcher_routes_tools(self):
        """Dispatcher routes known tools to executor."""
        # Test system.inspect
        from bridge.protocol import Request
        req = Request(request_id="test_1", tool="qgis.system.inspect", params={})
        resp = self.dispatcher.dispatch(req)
        self.assertEqual(resp.status, "ok")

    @unittest.skipUnless(QGIS_AVAILABLE, "QGIS not available")
    def test_dispatcher_unknown_tool(self):
        """Dispatcher returns error for unknown tools."""
        from bridge.protocol import Request
        req = Request(request_id="test_2", tool="qgis.nonexistent.tool", params={})
        resp = self.dispatcher.dispatch(req)
        self.assertEqual(resp.status, "error")


class QGISLayerLoadIntegrationTest(unittest.TestCase):
    """Test loading real GIS datasets into QGIS project."""

    @classmethod
    def setUpClass(cls):
        if not QGIS_AVAILABLE:
            raise unittest.SkipTest("QGIS not available in this environment")
        cls.project = QgsProject.instance()

    @unittest.skipUnless(QGIS_AVAILABLE, "QGIS not available")
    def test_load_geopackage(self):
        """Load a GeoPackage vector layer."""
        gpkg_paths = [
            "D:/1 2 3 QGIS/sample_data/test.gpkg",
        ]
        for path in gpkg_paths:
            if os.path.exists(path):
                layer = QgsVectorLayer(path, "test_gpkg", "ogr")
                self.assertTrue(layer.isValid())
                self.project.addMapLayer(layer)
                self.project.removeMapLayer(layer.id())
                return
        self.skipTest("No GeoPackage sample found")

    @unittest.skipUnless(QGIS_AVAILABLE, "QGIS not available")
    def test_load_geotiff(self):
        """Load a GeoTIFF raster layer."""
        tif_paths = [
            "D:/1 2 3 QGIS/sample_data/test.tif",
        ]
        for path in tif_paths:
            if os.path.exists(path):
                layer = QgsRasterLayer(path, "test_tif")
                self.assertTrue(layer.isValid())
                self.project.addMapLayer(layer)
                self.project.removeMapLayer(layer.id())
                return
        self.skipTest("No GeoTIFF sample found")


if __name__ == "__main__":
    unittest.main()
