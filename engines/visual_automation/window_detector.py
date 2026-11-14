"""Universal AI GIS Studio — QGIS Window Detection.

Uses Win32 API (win32gui) to find the QGIS Desktop window, enumerate
windows, and report window geometry. Defaults to controlling only the
authorized QGIS window.
"""

import logging
from typing import Optional, Dict, Any, List

import win32gui
import win32process
import win32api

logger = logging.getLogger("uagis.window_detector")


class WindowDetector:
    """Detects and inspects windows, with a focus on QGIS Desktop."""

    def __init__(self, authorized_window_title_substring: str = "QGIS"):
        self.authorized_substring = authorized_window_title_substring

    # ------------------------------------------------------------------ #
    # Enumeration
    # ------------------------------------------------------------------ #
    def list_windows(self) -> List[Dict[str, Any]]:
        """List all visible windows with title, handle, pid, rect."""
        windows = []

        def enum_cb(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                except Exception:
                    pid = None
                rect = win32gui.GetWindowRect(hwnd)  # (left, top, right, bottom)
                windows.append({
                    "hwnd": hwnd,
                    "title": title,
                    "pid": pid,
                    "left": rect[0], "top": rect[1],
                    "right": rect[2], "bottom": rect[3],
                    "width": rect[2] - rect[0],
                    "height": rect[3] - rect[1],
                })

        win32gui.EnumWindows(enum_cb, None)
        return windows

    def find_qgis_window(self) -> Optional[Dict[str, Any]]:
        """Find the QGIS Desktop window matching the authorized substring."""
        for w in self.list_windows():
            title = w["title"] or ""
            if self.authorized_substring.lower() in title.lower():
                return w
        return None

    def is_qgis_window(self, hwnd: int) -> bool:
        """Return True if the given window handle is the authorized QGIS window."""
        qgis = self.find_qgis_window()
        return qgis is not None and qgis["hwnd"] == hwnd

    def window_rect(self, hwnd: int) -> Optional[Dict[str, int]]:
        """Return the rect of a window."""
        try:
            rect = win32gui.GetWindowRect(hwnd)
            return {"left": rect[0], "top": rect[1],
                    "right": rect[2], "bottom": rect[3],
                    "width": rect[2] - rect[0], "height": rect[3] - rect[1]}
        except Exception as exc:
            logger.warning("window_rect failed for hwnd %s: %s", hwnd, exc)
            return None

    def bring_to_foreground(self, hwnd: int) -> bool:
        """Bring a window to the foreground (authorized QGIS window only)."""
        if not self.is_qgis_window(hwnd):
            logger.warning("Refusing to bring non-QGIS window %s to foreground", hwnd)
            return False
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE) if False else None
            win32gui.SetForegroundWindow(hwnd)
            return True
        except Exception as exc:
            logger.warning("SetForegroundWindow failed: %s", exc)
            return False


# imported lazily to avoid unused-import ordering issues
import win32con  # noqa: E402
