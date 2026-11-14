"""Universal AI GIS Studio — Live Screen Capture Engine.

Captures screenshots of the QGIS Desktop interface using PIL ImageGrab.
Multi-monitor aware, resolution-detecting, on-demand and periodic frames.
WebSocket streaming support for real-time screen sharing.

Pixel coordinates are SCREEN coordinates (not geographic map coordinates).
Use the QGIS Bridge canvas APIs to convert between screen and map coordinates.
"""

import base64
import io
import logging
import threading
import time
from typing import Optional, Tuple, Dict, Any, Callable, List

from PIL import ImageGrab, Image

from core.emergency_stop import is_emergency_stop_active

logger = logging.getLogger("uagis.screen_capture")


class ScreenCaptureEngine:
    """Captures screenshots of the desktop / QGIS window with periodic and streaming support."""

    def __init__(self):
        self._last_frame: Optional[Image.Image] = None
        self._periodic_interval = 5.0  # seconds
        self._periodic_enabled = False
        self._periodic_thread: Optional[threading.Thread] = None
        self._periodic_stop_event = threading.Event()
        self._frame_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._callbacks_lock = threading.RLock()

    # ------------------------------------------------------------------ #
    # Screen info
    # ------------------------------------------------------------------ #
    def screen_size(self) -> Tuple[int, int]:
        """Return the primary screen resolution (width, height) in pixels."""
        img = ImageGrab.grab()
        return img.size  # (width, height)

    def all_monitors(self) -> list[Dict[str, Any]]:
        """Return info for each monitor (best-effort via ImageGrab)."""
        # ImageGrab.grab(all_screens=True) gives the virtual screen.
        try:
            img = ImageGrab.grab(all_screens=True)
            return [{"index": 0, "width": img.size[0], "height": img.size[1],
                     "left": 0, "top": 0, "primary": True}]
        except Exception as exc:
            logger.warning("all_monitors failed: %s", exc)
            w, h = self.screen_size()
            return [{"index": 0, "width": w, "height": h, "left": 0, "top": 0,
                     "primary": True}]

    # ------------------------------------------------------------------ #
    # Capture
    # ------------------------------------------------------------------ #
    def capture(self, region: Optional[Tuple[int, int, int, int]] = None,
                include_cursor: bool = False) -> Dict[str, Any]:
        """Capture a screenshot.

        Args:
            region: (left, top, right, bottom) screen pixels, or None for full screen.
            include_cursor: whether to include the mouse cursor (best-effort).

        Returns:
            dict with image_base64 (PNG), width, height, format, region.
        """
        try:
            if region:
                img = ImageGrab.grab(bbox=region, include_layered=include_cursor,
                                     all_screens=False)
            else:
                img = ImageGrab.grab(include_layered=include_cursor,
                                     all_screens=False)
        except TypeError:
            # Older Pillow without include_layered/all_screens
            img = ImageGrab.grab(bbox=region)

        self._last_frame = img
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        result = {
            "image_base64": b64,
            "width": img.size[0],
            "height": img.size[1],
            "format": "png",
            "region": region,
            "timestamp": time.time(),
        }
        # Notify callbacks
        self._notify_callbacks(result)
        return result

    def capture_to_file(self, path: str,
                        region: Optional[Tuple[int, int, int, int]] = None) -> str:
        """Capture and save to a file. Returns the path."""
        result = self.capture(region=region)
        img = Image.open(io.BytesIO(base64.b64decode(result["image_base64"])))
        img.save(path)
        return path

    # ------------------------------------------------------------------ #
    # Periodic Capture
    # ------------------------------------------------------------------ #
    def start_periodic(self, interval_seconds: float = 5.0,
                       region: Optional[Tuple[int, int, int, int]] = None,
                       include_cursor: bool = False) -> Dict[str, Any]:
        """Start periodic screen capture.

        Args:
            interval_seconds: Capture interval (1-60 seconds)
            region: Screen region to capture
            include_cursor: Include mouse cursor

        Returns:
            Status dict
        """
        if self._periodic_enabled:
            return {"status": "already_running", "interval": self._periodic_interval}

        # Clamp interval
        interval_seconds = max(1.0, min(60.0, interval_seconds))
        self._periodic_interval = interval_seconds
        self._periodic_region = region
        self._periodic_include_cursor = include_cursor
        self._periodic_stop_event.clear()

        self._periodic_thread = threading.Thread(
            target=self._periodic_capture_loop,
            daemon=True,
            name="uagis-screen-capture-periodic"
        )
        self._periodic_thread.start()
        self._periodic_enabled = True

        logger.info("Started periodic screen capture: interval=%.1fs", interval_seconds)
        return {"status": "started", "interval": interval_seconds}

    def stop_periodic(self) -> Dict[str, Any]:
        """Stop periodic screen capture."""
        if not self._periodic_enabled:
            return {"status": "not_running"}

        self._periodic_stop_event.set()
        if self._periodic_thread:
            self._periodic_thread.join(timeout=2.0)
        self._periodic_enabled = False
        self._periodic_thread = None

        logger.info("Stopped periodic screen capture")
        return {"status": "stopped"}

    def _periodic_capture_loop(self) -> None:
        """Background thread for periodic capture."""
        while not self._periodic_stop_event.is_set():
            # Check emergency stop
            if is_emergency_stop_active():
                logger.warning("Periodic capture loop stopped: emergency stop active")
                self._periodic_enabled = False
                break

            try:
                self.capture(
                    region=getattr(self, '_periodic_region', None),
                    include_cursor=getattr(self, '_periodic_include_cursor', False)
                )
            except Exception as exc:
                logger.error("Periodic capture failed: %s", exc)

            # Wait for interval or stop signal
            self._periodic_stop_event.wait(self._periodic_interval)

    # ------------------------------------------------------------------ #
    # Frame Callbacks (for WebSocket streaming)
    # ------------------------------------------------------------------ #
    def register_frame_callback(self, callback: Callable[[Dict[str, Any]], None]) -> int:
        """Register a callback to receive each captured frame.

        Returns:
            Callback ID for unregistering
        """
        with self._callbacks_lock:
            callback_id = id(callback)
            self._frame_callbacks.append(callback)
            return callback_id

    def unregister_frame_callback(self, callback_id: int) -> bool:
        """Unregister a frame callback by ID."""
        with self._callbacks_lock:
            for i, cb in enumerate(self._frame_callbacks):
                if id(cb) == callback_id:
                    self._frame_callbacks.pop(i)
                    return True
            return False

    def _notify_callbacks(self, frame: Dict[str, Any]) -> None:
        """Notify all registered callbacks of a new frame."""
        with self._callbacks_lock:
            callbacks = list(self._frame_callbacks)

        for cb in callbacks:
            try:
                cb(frame)
            except Exception as exc:
                logger.warning("Frame callback failed: %s", exc)

    # ------------------------------------------------------------------ #
    # WebSocket Streaming Support
    # ------------------------------------------------------------------ #
    def get_stream_config(self) -> Dict[str, Any]:
        """Get configuration for WebSocket streaming."""
        return {
            "interval": self._periodic_interval,
            "enabled": self._periodic_enabled,
            "callbacks_registered": len(self._frame_callbacks),
        }

    @property
    def last_frame(self) -> Optional[Image.Image]:
        return self._last_frame

    @property
    def is_periodic_running(self) -> bool:
        return self._periodic_enabled
