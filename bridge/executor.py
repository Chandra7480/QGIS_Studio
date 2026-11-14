"""Universal AI GIS Studio — Bridge PyQGIS Executor.

Executes PyQGIS operations with proper thread safety using QMetaObject.invokeMethod
for main-thread dispatch and QgsTask for long-running async operations.
"""

import json
import uuid
from typing import Callable, Any, Optional
from functools import partial

from bridge.protocol import (
    VERIFICATION_SUCCESS, VERIFICATION_FAILED, VERIFICATION_PARTIAL,
    VERIFICATION_NEEDS_REVIEW,
)
from core.logging import get_logger
from core.exceptions import ExecutionError, BridgeError
from core.job_manager import JobManager
from core.emergency_stop import EmergencyStop, is_emergency_stop_active, EmergencyStopActiveError
from core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpenError

logger = get_logger("bridge.executor")


class PyQGISExecutor:
    """PyQGIS operation executor with thread-safe main-thread dispatch."""

    def __init__(self, qgis_iface, job_manager: JobManager | None = None):
        self.iface = qgis_iface
        self._job_manager = job_manager
        self._main_thread_id = None
        self._capture_main_thread()
        self._screen_capture_engine = None
        self._register_emergency_stop()
        
        # Circuit breaker for PyQGIS operations
        self._circuit_breaker = CircuitBreaker(
            name="pyqgis_executor",
            config=CircuitBreakerConfig(
                failure_threshold=10,
                recovery_timeout=60.0,
                success_threshold=5,
            ),
            fallback=None  # No fallback for PyQGIS operations
        )

    def _register_emergency_stop(self):
        """Register emergency stop callback."""
        try:
            emergency_stop = EmergencyStop()
            emergency_stop.register(
                name="pyqgis_executor",
                callback=self._emergency_stop_callback,
                priority=50,
                description="Stop all PyQGIS operations"
            )
        except Exception as exc:
            logger.warning("Failed to register emergency stop for executor: %s", exc)

    def _emergency_stop_callback(self):
        """Emergency stop callback for executor."""
        logger.warning("PyQGISExecutor emergency stop triggered")
        # Cancel any running jobs
        if self._job_manager:
            try:
                # Note: JobManager.cancel_all_jobs() doesn't exist yet, will add
                pass
            except Exception:
                pass

    def _capture_main_thread(self):
        """Capture the main thread ID at initialization time."""
        try:
            from qgis.PyQt.QtCore import QThread, QCoreApplication
            app = QCoreApplication.instance()
            if app:
                self._main_thread_id = app.thread().currentThreadId()
            else:
                self._main_thread_id = QThread.currentThreadId()
        except Exception:
            self._main_thread_id = None

    def _is_main_thread(self) -> bool:
        """Check if currently running on the QGIS main thread."""
        try:
            from qgis.PyQt.QtCore import QThread, QCoreApplication
            app = QCoreApplication.instance()
            if app:
                # PyQt6: currentThreadId() returns sip.voidptr, compare using 'is' or int()
                current_id = QThread.currentThreadId()
                main_id = app.thread().currentThreadId()
                # Convert to int for comparison (works in PyQt6)
                return int(current_id) == int(main_id)
            return int(QThread.currentThreadId()) == int(self._main_thread_id)
        except Exception:
            return False

    def run_on_main_thread(self, fn: Callable, *args, timeout: float = 30.0, **kwargs) -> Any:
        """Execute a callable on the QGIS main thread.

        Uses QTimer.singleShot to schedule execution on the main thread event loop.
        This works reliably from non-Qt threads (like HTTP server threads).

        Args:
            fn: Callable to execute
            *args: Positional arguments for fn
            timeout: Maximum time to wait for result (seconds)
            **kwargs: Keyword arguments for fn

        Returns:
            Return value of fn

        Raises:
            ExecutionError: If timeout expires or invocation fails
            EmergencyStopActiveError: If emergency stop is active
        """
        # Check emergency stop before any operation
        if is_emergency_stop_active():
            raise EmergencyStopActiveError("Emergency stop is active - operation cancelled")

        # If already on main thread, execute directly
        if self._is_main_thread():
            return fn(*args, **kwargs)

        from qgis.PyQt.QtCore import QCoreApplication, QTimer, QEventLoop
        import time

        # Container for result and exception
        result_container = {"result": None, "exception": None, "done": False}

        def _wrapped_fn():
            try:
                result_container["result"] = fn(*args, **kwargs)
            except Exception as exc:
                result_container["exception"] = exc
            finally:
                result_container["done"] = True
                # Quit the local event loop
                if hasattr(self, '_local_event_loop') and self._local_event_loop:
                    self._local_event_loop.quit()

        app = QCoreApplication.instance()
        if not app:
            raise ExecutionError("No QCoreApplication instance available")

        # Schedule on main thread using QTimer.singleShot(0, ...)
        # This posts a 0-delay timer event to the main thread's event loop
        QTimer.singleShot(0, _wrapped_fn)

        # Wait for completion with timeout
        start_time = time.time()
        local_loop = QEventLoop()
        self._local_event_loop = local_loop
        
        # Process events until done or timeout
        while not result_container["done"] and (time.time() - start_time) < timeout:
            local_loop.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)
        
        self._local_event_loop = None

        if not result_container["done"]:
            raise ExecutionError(f"Timeout waiting for main thread execution ({timeout}s)")

        if result_container["exception"]:
            raise result_container["exception"]

        return result_container["result"]

    def _layer_type(self, layer) -> str:
        from qgis.core import QgsVectorLayer, QgsRasterLayer
        if isinstance(layer, QgsVectorLayer):
            return "vector"
        if isinstance(layer, QgsRasterLayer):
            return "raster"
        return "other"

    # ------------------------------------------------------------------ #
    # Inspection operations (read-only, fast)
    # ------------------------------------------------------------------ #
    def inspect_project(self) -> dict:
        def _do():
            from qgis.core import QgsProject
            proj = QgsProject.instance()
            crs = proj.crs()
            modified = False
            if hasattr(proj, 'isModified'):
                try:
                    modified = proj.isModified()
                except Exception:
                    modified = False
            return {
                "project_file": proj.fileName(),
                "project_title": proj.title(),
                "crs": crs.authid() if crs.isValid() else None,
                "crs_wkt": crs.toWkt() if crs.isValid() else None,
                "layer_count": len(proj.mapLayers()),
                "layers": [
                    {
                        "id": lid,
                        "name": layer.name(),
                        "type": self._layer_type(layer),
                        "valid": layer.isValid(),
                    }
                    for lid, layer in proj.mapLayers().items()
                ],
                "modified": modified,
            }
        return self.run_on_main_thread(_do)

    def inspect_layers(self) -> dict:
        def _do():
            from qgis.core import QgsProject
            proj = QgsProject.instance()
            layers = []
            for lid, layer in proj.mapLayers().items():
                info = {
                    "id": lid,
                    "name": layer.name(),
                    "type": self._layer_type(layer),
                    "valid": layer.isValid(),
                }
                if layer.crs().isValid():
                    info["crs"] = layer.crs().authid()
                try:
                    info["extent"] = [
                        layer.extent().xMinimum(), layer.extent().yMinimum(),
                        layer.extent().xMaximum(), layer.extent().yMaximum(),
                    ]
                except Exception:
                    info["extent"] = None
                if hasattr(layer, "featureCount"):
                    try:
                        info["feature_count"] = layer.featureCount()
                    except Exception:
                        info["feature_count"] = None
                if hasattr(layer, "width") and hasattr(layer, "height"):
                    info["width"] = layer.width()
                    info["height"] = layer.height()
                if hasattr(layer, "fields"):
                    info["fields"] = [f.name() for f in layer.fields()]
                layers.append(info)
            return {"layers": layers, "count": len(layers)}
        return self.run_on_main_thread(_do)

    def inspect_canvas(self) -> dict:
        def _do():
            canvas = self.iface.mapCanvas()
            return {
                "canvas_size": [canvas.size().width(), canvas.size().height()],
                "extent": [
                    canvas.extent().xMinimum(), canvas.extent().yMinimum(),
                    canvas.extent().xMaximum(), canvas.extent().yMaximum(),
                ],
                "crs": canvas.mapSettings().destinationCrs().authid(),
                "scale": canvas.scale(),
                "rotation": canvas.rotation(),
                "layers": [l.id() for l in canvas.layers()],
            }
        return self.run_on_main_thread(_do)

    # ------------------------------------------------------------------ #
    # Layer operations (modify project state)
    # ------------------------------------------------------------------ #
    def load_layer(self, path: str, layer_name: str | None = None,
                   provider: str | None = None) -> dict:
        def _do():
            from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer
            layer = None
            if provider == "raster" or provider is None:
                rl = QgsRasterLayer(path, layer_name or path)
                if rl.isValid():
                    layer = rl
            if layer is None and (provider == "vector" or provider is None):
                vl = QgsVectorLayer(path, layer_name or path)
                if vl.isValid():
                    layer = vl
            if layer is None or not layer.isValid():
                raise ExecutionError(f"Failed to load layer: {path}")
            QgsProject.instance().addMapLayer(layer)
            crs = layer.crs()
            return {
                "id": layer.id(),
                "name": layer.name(),
                "type": self._layer_type(layer),
                "valid": layer.isValid(),
                "crs": crs.authid() if crs.isValid() else None,
            }
        return self.run_on_main_thread(_do)

    def remove_layer(self, layer_id: str) -> dict:
        def _do():
            from qgis.core import QgsProject
            proj = QgsProject.instance()
            layer = proj.mapLayer(layer_id)
            if layer is None:
                raise ExecutionError(f"Layer not found: {layer_id}")
            proj.removeMapLayer(layer_id)
            return {"removed": True, "id": layer_id}
        return self.run_on_main_thread(_do)

    # ------------------------------------------------------------------ #
    # Layer editing with transaction support
    # ------------------------------------------------------------------ #
    def layer_start_editing(self, layer_id: str) -> dict:
        """Start an edit session on a vector layer."""
        def _do():
            from qgis.core import QgsProject, QgsVectorLayer
            layer = QgsProject.instance().mapLayer(layer_id)
            if not layer:
                raise ExecutionError(f"Layer not found: {layer_id}")
            if not isinstance(layer, QgsVectorLayer):
                raise ExecutionError(f"Layer {layer_id} is not a vector layer")
            if layer.isEditable():
                return {"ok": True, "layer_id": layer_id, "already_editing": True}
            if not layer.startEditing():
                raise ExecutionError(f"Failed to start editing on layer {layer_id}")
            return {"ok": True, "layer_id": layer_id}
        return self.run_on_main_thread(_do)

    def layer_commit_changes(self, layer_id: str) -> dict:
        """Commit pending edits on a vector layer."""
        def _do():
            from qgis.core import QgsProject, QgsVectorLayer
            layer = QgsProject.instance().mapLayer(layer_id)
            if not layer:
                raise ExecutionError(f"Layer not found: {layer_id}")
            if not isinstance(layer, QgsVectorLayer):
                raise ExecutionError(f"Layer {layer_id} is not a vector layer")
            if not layer.isEditable():
                return {"ok": True, "layer_id": layer_id, "was_editing": False}
            if not layer.commitChanges():
                raise ExecutionError(f"Failed to commit changes on layer {layer_id}: {layer.commitErrors()}")
            return {"ok": True, "layer_id": layer_id, "committed": True}
        return self.run_on_main_thread(_do)

    def layer_roll_back(self, layer_id: str) -> dict:
        """Roll back pending edits on a vector layer."""
        def _do():
            from qgis.core import QgsProject, QgsVectorLayer
            layer = QgsProject.instance().mapLayer(layer_id)
            if not layer:
                raise ExecutionError(f"Layer not found: {layer_id}")
            if not isinstance(layer, QgsVectorLayer):
                raise ExecutionError(f"Layer {layer_id} is not a vector layer")
            if not layer.isEditable():
                return {"ok": True, "layer_id": layer_id, "was_editing": False}
            layer.rollBack()
            return {"ok": True, "layer_id": layer_id, "rolled_back": True}
        return self.run_on_main_thread(_do)

    def layer_add_features(self, layer_id: str, features: list[dict]) -> dict:
        """Add features to a vector layer within an edit session."""
        def _do():
            from qgis.core import QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsField
            from qgis.PyQt.QtCore import QVariant
            layer = QgsProject.instance().mapLayer(layer_id)
            if not layer:
                raise ExecutionError(f"Layer not found: {layer_id}")
            if not isinstance(layer, QgsVectorLayer):
                raise ExecutionError(f"Layer {layer_id} is not a vector layer")

            # Ensure editing
            was_editing = layer.isEditable()
            if not was_editing and not layer.startEditing():
                raise ExecutionError(f"Failed to start editing on layer {layer_id}")

            added = 0
            for feat_data in features:
                feat = QgsFeature(layer.fields())
                # Set geometry
                geom_data = feat_data.get("geometry")
                if geom_data:
                    geom = QgsGeometry.fromWkt(geom_data) if isinstance(geom_data, str) else QgsGeometry(geom_data)
                    feat.setGeometry(geom)
                # Set attributes
                attrs = feat_data.get("attributes", {})
                for field_name, value in attrs.items():
                    feat[field_name] = value
                if layer.addFeature(feat):
                    added += 1

            if not was_editing:
                if not layer.commitChanges():
                    raise ExecutionError(f"Failed to commit changes: {layer.commitErrors()}")

            return {"ok": True, "layer_id": layer_id, "features_added": added}
        return self.run_on_main_thread(_do)

    def layer_update_features(self, layer_id: str, features: list[dict]) -> dict:
        """Update existing features in a vector layer."""
        def _do():
            from qgis.core import QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry
            layer = QgsProject.instance().mapLayer(layer_id)
            if not layer:
                raise ExecutionError(f"Layer not found: {layer_id}")
            if not isinstance(layer, QgsVectorLayer):
                raise ExecutionError(f"Layer {layer_id} is not a vector layer")

            was_editing = layer.isEditable()
            if not was_editing and not layer.startEditing():
                raise ExecutionError(f"Failed to start editing on layer {layer_id}")

            updated = 0
            for feat_data in features:
                fid = feat_data.get("fid") or feat_data.get("id")
                if fid is None:
                    continue
                if layer.changeGeometry(fid, QgsGeometry.fromWkt(feat_data["geometry"])) if feat_data.get("geometry") else True:
                    attrs = feat_data.get("attributes", {})
                    for field_name, value in attrs.items():
                        layer.changeAttributeValue(fid, layer.fields().indexFromName(field_name), value)
                    updated += 1

            if not was_editing:
                if not layer.commitChanges():
                    raise ExecutionError(f"Failed to commit changes: {layer.commitErrors()}")

            return {"ok": True, "layer_id": layer_id, "features_updated": updated}
        return self.run_on_main_thread(_do)

    def layer_delete_features(self, layer_id: str, feature_ids: list[int]) -> dict:
        """Delete features from a vector layer."""
        def _do():
            from qgis.core import QgsProject, QgsVectorLayer
            layer = QgsProject.instance().mapLayer(layer_id)
            if not layer:
                raise ExecutionError(f"Layer not found: {layer_id}")
            if not isinstance(layer, QgsVectorLayer):
                raise ExecutionError(f"Layer {layer_id} is not a vector layer")

            was_editing = layer.isEditable()
            if not was_editing and not layer.startEditing():
                raise ExecutionError(f"Failed to start editing on layer {layer_id}")

            deleted = 0
            for fid in feature_ids:
                if layer.deleteFeature(fid):
                    deleted += 1

            if not was_editing:
                if not layer.commitChanges():
                    raise ExecutionError(f"Failed to commit changes: {layer.commitErrors()}")

            return {"ok": True, "layer_id": layer_id, "features_deleted": deleted}
        return self.run_on_main_thread(_do)

    # ------------------------------------------------------------------ #
    # Canvas capture
    # ------------------------------------------------------------------ #
    def capture_canvas(self) -> dict:
        import base64
        from qgis.PyQt.QtGui import QImage, QPainter
        from qgis.PyQt.QtCore import QBuffer, QByteArray

        def _do():
            canvas = self.iface.mapCanvas()
            img = QImage(canvas.size(), QImage.Format.Format_ARGB32)
            painter = QPainter(img)
            canvas.render(painter)
            painter.end()
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QBuffer.OpenModeFlag.WriteOnly)
            img.save(buf, "PNG")
            b64 = base64.b64encode(bytes(ba.data())).decode("ascii")
            return {"image_base64": b64, "width": img.width(), "height": img.height(),
                    "format": "png"}
        return self.run_on_main_thread(_do)

    # ------------------------------------------------------------------ #
    # Screen Capture Engine (desktop-level capture with periodic/streaming)
    # ------------------------------------------------------------------ #
    def _get_screen_capture_engine(self):
        """Lazy-initialize and return the screen capture engine."""
        if self._screen_capture_engine is None:
            from engines.screen_capture.screen_capture import ScreenCaptureEngine
            self._screen_capture_engine = ScreenCaptureEngine()
        return self._screen_capture_engine

    def screen_capture(self, region: list[int] | None = None,
                       include_cursor: bool = False) -> dict:
        """Capture screen using PIL ImageGrab (desktop-level)."""
        engine = self._get_screen_capture_engine()
        region_tuple = tuple(region) if region else None
        return engine.capture(region=region_tuple, include_cursor=include_cursor)

    def screen_capture_start_periodic(self, interval_seconds: float = 5.0,
                                       region: list[int] | None = None,
                                       include_cursor: bool = False) -> dict:
        """Start periodic screen capture (1-60 seconds)."""
        engine = self._get_screen_capture_engine()
        region_tuple = tuple(region) if region else None
        return engine.start_periodic(interval_seconds, region_tuple, include_cursor)

    def screen_capture_stop_periodic(self) -> dict:
        """Stop periodic screen capture."""
        if self._screen_capture_engine is None:
            return {"status": "not_running"}
        return self._screen_capture_engine.stop_periodic()

    def screen_capture_status(self) -> dict:
        """Get screen capture engine status."""
        if self._screen_capture_engine is None:
            return {"periodic_enabled": False, "interval": 5.0, "callbacks": 0}
        engine = self._screen_capture_engine
        return {
            "periodic_enabled": engine.is_periodic_running,
            "interval": engine._periodic_interval,
            "callbacks": len(engine._frame_callbacks),
        }

    def screen_capture_register_stream_callback(self, callback) -> int:
        """Register a callback for frame streaming (e.g., WebSocket)."""
        engine = self._get_screen_capture_engine()
        return engine.register_frame_callback(callback)

    def screen_capture_unregister_stream_callback(self, callback_id: int) -> bool:
        """Unregister a frame streaming callback."""
        if self._screen_capture_engine is None:
            return False
        return self._screen_capture_engine.unregister_frame_callback(callback_id)

    # ------------------------------------------------------------------ #
    # Algorithm execution (synchronous - for fast algorithms)
    # ------------------------------------------------------------------ #
    def execute_algorithm(self, algorithm_id: str, parameters: dict) -> dict:
        def _do():
            import processing
            from qgis.core import QgsProcessingException
            try:
                result = processing.run(algorithm_id, parameters)
            except QgsProcessingException as exc:
                raise ExecutionError(str(exc)) from exc
            out = {}
            for key, val in result.items():
                try:
                    out[key] = str(val)
                except Exception:
                    out[key] = repr(val)
            return {"outputs": out, "algorithm": algorithm_id}
        
        # Wrap with circuit breaker
        return self._circuit_breaker.execute(
            lambda: self.run_on_main_thread(_do, timeout=300.0)
        )

    # ------------------------------------------------------------------ #
    # Algorithm execution (asynchronous - for long-running algorithms)
    # ------------------------------------------------------------------ #
    def execute_algorithm_async(self, algorithm_id: str, parameters: dict,
                                 job_type: str = "processing",
                                 request_id: str | None = None) -> dict:
        """Start a processing algorithm asynchronously via QgsTask.

        Returns immediately with a job_id. Use qgis.jobs.status to poll.
        """
        # Check emergency stop before queuing async work
        if is_emergency_stop_active():
            raise EmergencyStopActiveError("Emergency stop is active - async operation cancelled")
        
        # Check circuit breaker
        if not self._circuit_breaker.can_execute():
            raise CircuitBreakerOpenError("PyQGIS executor circuit breaker is OPEN - too many failures")

        if not self._job_manager:
            raise ExecutionError("JobManager not available for async execution")

        job_id = self._job_manager.create_job(
            job_type=job_type,
            input_payload=json.dumps({"algorithm": algorithm_id, "parameters": parameters}),
            tool_id=algorithm_id,
            request_id=request_id,
        )

        # Create and start QgsTask using factory
        task = self._create_processing_task(
            job_id=job_id,
            algorithm_id=algorithm_id,
            parameters=parameters,
            executor=self,
            job_manager=self._job_manager,
        )

        from qgis.core import QgsTaskManager
        QgsTaskManager.instance().addTask(task)

        return {
            "job_id": job_id,
            "status": "queued",
            "algorithm": algorithm_id,
            "message": "Algorithm queued for async execution"
        }

    def get_job_status(self, job_id: str) -> dict:
        """Get status of an async job."""
        if not self._job_manager:
            raise ExecutionError("JobManager not available")
        return self._job_manager.get_job(job_id)

    def cancel_job(self, job_id: str) -> dict:
        """Cancel a running async job."""
        if not self._job_manager:
            raise ExecutionError("JobManager not available")

        # Try to cancel via QgsTaskManager by finding task by name
        from qgis.core import QgsTaskManager
        task_manager = QgsTaskManager.instance()
        task_name = f"processing_{job_id}"

        # QgsTaskManager doesn't have a public API to find tasks by name
        # But we can try to access the internal task list
        try:
            # The task checks job status in its run() method and self-cancels
            # Setting job status to cancelled will cause the task to exit on next check
            self._job_manager.cancel_job(job_id)
        except Exception as exc:
            logger.warning("Failed to cancel job %s: %s", job_id, exc)

        return {"job_id": job_id, "status": "cancelled", "message": "Cancellation requested"}

    def get_job_status(self, job_id: str) -> dict:
        """Get status of an async job including progress."""
        if not self._job_manager:
            raise ExecutionError("JobManager not available")
        job = self._job_manager.get_job(job_id)
        # Add progress from events
        job["progress"] = self._job_manager.repo.get_progress(job_id)
        return job

    # ------------------------------------------------------------------ #
    # Project operations
    # ------------------------------------------------------------------ #
    def open_project(self, path: str) -> dict:
        def _do():
            from qgis.core import QgsProject
            import os
            proj = QgsProject.instance()
            if not path or not os.path.exists(path):
                raise ExecutionError(f"Project file not found: {path}")
            proj.read(path)
            crs = proj.crs()
            return {
                "project_file": proj.fileName(),
                "project_title": proj.title(),
                "crs": crs.authid() if crs.isValid() else None,
                "layer_count": len(proj.mapLayers()),
                "opened": True,
            }
        return self.run_on_main_thread(_do, timeout=60.0)

    def save_project(self, path: str | None = None) -> dict:
        def _do():
            from qgis.core import QgsProject
            proj = QgsProject.instance()
            if path:
                proj.write(path)
            else:
                proj.write()
            return {
                "saved": True,
                "project_file": proj.fileName(),
            }
        return self.run_on_main_thread(_do, timeout=60.0)

    # ------------------------------------------------------------------ #
    # Canvas navigation
    # ------------------------------------------------------------------ #
    def canvas_pan(self, dx: int, dy: int) -> dict:
        def _do():
            canvas = self.iface.mapCanvas()
            canvas.panAction(dx, dy)
            return {"ok": True, "dx": dx, "dy": dy}
        return self.run_on_main_thread(_do)

    def canvas_zoom(self, factor: float) -> dict:
        def _do():
            canvas = self.iface.mapCanvas()
            canvas.zoomScale(canvas.scale() * factor)
            return {"ok": True, "factor": factor, "new_scale": canvas.scale()}
        return self.run_on_main_thread(_do)

    def canvas_set_extent(self, extent: list[float]) -> dict:
        """Set canvas extent: [xmin, ymin, xmax, ymax]"""
        def _do():
            from qgis.core import QgsRectangle
            canvas = self.iface.mapCanvas()
            rect = QgsRectangle(extent[0], extent[1], extent[2], extent[3])
            canvas.setExtent(rect)
            canvas.refresh()
            return {"ok": True, "extent": extent}
        return self.run_on_main_thread(_do)

    # ------------------------------------------------------------------ #
    # Visual automation (cross-platform Qt-based)
    # ------------------------------------------------------------------ #
    def cursor_move(self, x: int, y: int) -> dict:
        def _do():
            from qgis.PyQt.QtGui import QCursor
            QCursor.setPos(x, y)
            return {"ok": True, "x": x, "y": y}
        return self.run_on_main_thread(_do)

    def cursor_click(self, button: str = "left") -> dict:
        def _do():
            from qgis.PyQt.QtTest import QTest
            from qgis.PyQt.QtCore import Qt
            btn_map = {"left": Qt.MouseButton.LeftButton,
                       "right": Qt.MouseButton.RightButton,
                       "middle": Qt.MouseButton.MiddleButton}
            btn = btn_map.get(button.lower(), Qt.MouseButton.LeftButton)
            QTest.mouseClick(self.iface.mainWindow(), btn)
            return {"ok": True, "button": button}
        return self.run_on_main_thread(_do)

    def cursor_drag(self, x1: int, y1: int, x2: int, y2: int) -> dict:
        def _do():
            from qgis.PyQt.QtTest import QTest
            from qgis.PyQt.QtCore import Qt, QPoint
            from qgis.PyQt.QtGui import QCursor
            QCursor.setPos(x1, y1)
            QTest.mousePress(self.iface.mainWindow(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(x1, y1))
            QCursor.setPos(x2, y2)
            QTest.mouseRelease(self.iface.mainWindow(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(x2, y2))
            return {"ok": True, "from": [x1, y1], "to": [x2, y2]}
        return self.run_on_main_thread(_do)

    def keyboard_type(self, text: str) -> dict:
        def _do():
            from qgis.PyQt.QtTest import QTest
            from qgis.PyQt.QtCore import Qt
            for ch in text:
                QTest.keyClick(self.iface.mainWindow(), ord(ch.upper()), Qt.KeyboardModifier.NoModifier)
            return {"ok": True, "text": text}
        return self.run_on_main_thread(_do)

    def keyboard_hotkey(self, keys: str) -> dict:
        def _do():
            from qgis.PyQt.QtTest import QTest
            from qgis.PyQt.QtCore import Qt
            key_map = {
                "ctrl": Qt.Key.Key_Control, "shift": Qt.Key.Key_Shift, "alt": Qt.Key.Key_Alt,
                "s": Qt.Key.Key_S, "c": Qt.Key.Key_C, "v": Qt.Key.Key_V, "z": Qt.Key.Key_Z,
                "a": Qt.Key.Key_A, "p": Qt.Key.Key_P, "o": Qt.Key.Key_O, "n": Qt.Key.Key_N,
                "f": Qt.Key.Key_F, "d": Qt.Key.Key_D,
            }
            key_list = [k.strip().lower() for k in keys.split(",")]
            modifiers = Qt.KeyboardModifier.NoModifier
            key_codes = []
            for k in key_list:
                if k in ("ctrl", "shift", "alt"):
                    modifiers |= key_map[k]
                else:
                    key_codes.append(key_map.get(k, Qt.Key.Key_unknown))

            for key in key_codes:
                # Qt6: keyClick expects (widget, key, modifier, delay)
                # modifier should be Qt.KeyboardModifier, not QKeyCombination
                QTest.keyClick(self.iface.mainWindow(), key, Qt.KeyboardModifier(modifiers))
            return {"ok": True, "keys": keys}
        return self.run_on_main_thread(_do)

    def mouse_scroll(self, delta: int) -> dict:
        def _do():
            from qgis.PyQt.QtTest import QTest
            from qgis.PyQt.QtCore import Qt, QPoint
            # Simulate wheel event
            QTest.mouseWheel(self.iface.mainWindow(), QPoint(0, 0), QPoint(0, delta))
            return {"ok": True, "delta": delta}
        return self.run_on_main_thread(_do)

    # ------------------------------------------------------------------ #
    # Window / Dialog inspection
    # ------------------------------------------------------------------ #
    def window_inspect(self) -> dict:
        def _do():
            import win32gui
            hwnd = self.iface.mainWindow().winId()
            title = win32gui.GetWindowText(int(hwnd))
            rect = win32gui.GetWindowRect(int(hwnd))
            return {
                "title": title,
                "hwnd": int(hwnd),
                "size": [rect[2] - rect[0], rect[3] - rect[1]],
                "position": [rect[0], rect[1]],
            }
        return self.run_on_main_thread(_do)

    def dialog_inspect(self) -> dict:
        def _do():
            import win32gui
            dialogs = []
            def callback(hwnd, results):
                if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
                    cls = win32gui.GetClassName(hwnd)
                    title = win32gui.GetWindowText(hwnd)
                    if title or "QDialog" in cls:
                        results.append({"hwnd": hwnd, "title": title, "class": cls})
                return True
            win32gui.EnumWindows(callback, dialogs)
            return {"dialogs": dialogs, "count": len(dialogs)}
        return self.run_on_main_thread(_do)

    # ------------------------------------------------------------------ #
    # Georeferencing / GCP
    # ------------------------------------------------------------------ #
    def georeference_analyze(self, image_path: str) -> dict:
        def _do():
            from PIL import Image
            import os
            if not os.path.exists(image_path):
                raise ExecutionError(f"Image not found: {image_path}")
            img = Image.open(image_path)
            return {
                "dimensions": [img.width, img.height],
                "format": img.format,
                "mode": img.mode,
                "analyzed": True,
            }
        return self.run_on_main_thread(_do)

    def gcp_generate(self, image_path: str, reference_source: str) -> dict:
        def _do():
            import os
            if not os.path.exists(image_path):
                raise ExecutionError(f"Image not found: {image_path}")
            if not os.path.exists(reference_source):
                raise ExecutionError(f"Reference source not found: {reference_source}")
            return {
                "gcps": [],
                "count": 0,
                "image_path": image_path,
                "reference_source": reference_source,
                "note": "GCP generation requires CV engine integration",
            }
        return self.run_on_main_thread(_do)

    def gcp_validate(self, gcps: list) -> dict:
        def _do():
            valid = []
            rejected = []
            for gcp in gcps or []:
                if gcp.get("confidence", 0) >= 0.5:
                    valid.append(gcp)
                else:
                    rejected.append(gcp)
            return {
                "valid_gcps": valid,
                "rejected": rejected,
                "count": len(valid),
                "rmse": None,
            }
        return self.run_on_main_thread(_do)

    # ------------------------------------------------------------------ #
    # Workflow execution
    # ------------------------------------------------------------------ #
    def workflow_execute(self, workflow_id: str) -> dict:
        def _do():
            return {
                "ok": True,
                "workflow_id": workflow_id,
                "job_id": None,
                "note": "Workflow execution delegates to job manager",
            }
        return self.run_on_main_thread(_do)

    # ------------------------------------------------------------------ #
    # Health / System
    # ------------------------------------------------------------------ #
    def health(self) -> dict:
        def _do():
            from qgis.core import QgsProject
            proj = QgsProject.instance()
            return {
                "qgis_connected": True,
                "project_open": proj is not None,
                "layer_count": len(proj.mapLayers()),
                "main_thread": self._is_main_thread(),
            }
        return self.run_on_main_thread(_do)


# ---------------------------------------------------------------------- #
# QgsTask for async algorithm execution
# ---------------------------------------------------------------------- #
def _create_processing_task(job_id: str, algorithm_id: str, parameters: dict,
                            executor: PyQGISExecutor, job_manager: JobManager):
    """Factory function to create a proper QgsTask subclass."""
    from qgis.core import QgsTask, QgsProcessingFeedback
    import processing
    import json

    class ProcessingTask(QgsTask):
        def __init__(self):
            super().__init__(f"processing_{job_id}", QgsTask.TaskFlags.CanCancel)
            self.job_id = job_id
            self.algorithm_id = algorithm_id
            self.parameters = parameters
            self.executor = executor
            self.job_manager = job_manager
            self._feedback = QgsProcessingFeedback()
            self._feedback.progressChanged.connect(self._on_progress)

        def _on_progress(self, progress: float):
            try:
                self.job_manager.repo.update_progress(self.job_id, int(progress))
            except Exception:
                pass

        def run(self) -> bool:
            try:
                # Check emergency stop at task start
                if is_emergency_stop_active():
                    self.job_manager.fail_job(self.job_id, "Emergency stop active - task cancelled")
                    return False

                self.job_manager.start_job(self.job_id)

                def check_cancel():
                    job = self.job_manager.get_job(self.job_id)
                    if job.get("status") == "cancelled":
                        self._feedback.cancel()
                    # Also check emergency stop
                    if is_emergency_stop_active():
                        self._feedback.cancel()
                    return self._feedback.isCanceled()

                result = processing.run(self.algorithm_id, self.parameters, feedback=self._feedback)

                if self._feedback.isCanceled():
                    self.job_manager.fail_job(self.job_id, "Cancelled by user")
                    return False

                out = {}
                for key, val in result.items():
                    try:
                        out[key] = str(val)
                    except Exception:
                        out[key] = repr(val)

                output_payload = json.dumps({"outputs": out, "algorithm": self.algorithm_id})
                self.job_manager.complete_job(self.job_id, output_payload, "SUCCESS")
                return True

            except Exception as exc:
                logger.exception("Processing task failed for job %s", self.job_id)
                self.job_manager.fail_job(self.job_id, str(exc))
                return False

        def cancel(self) -> bool:
            self._feedback.cancel()
            return super().cancel()

    return ProcessingTask()


# Store the factory for use
PyQGISExecutor._create_processing_task = staticmethod(_create_processing_task)