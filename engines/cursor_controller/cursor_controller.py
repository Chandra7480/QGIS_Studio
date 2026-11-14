"""Universal AI GIS Studio — AI Cursor Controller.

A visible, AI-controlled cursor drawn as an overlay, visually distinct
from the human cursor. Features smooth movement, target highlighting,
click/drag animation, action indicator, pause/resume, emergency stop,
position reporting, highlight radius, click ripple, and trail effects.

Runs as a PyQt6 transparent overlay on top of the authorized QGIS window.
"""

import logging
import math
import time
from typing import Optional, Tuple, List
from dataclasses import dataclass, field

from core.emergency_stop import is_emergency_stop_active

logger = logging.getLogger("uagis.cursor_controller")

try:
    from qgis.PyQt.QtWidgets import QWidget, QApplication
    from qgis.PyQt.QtCore import Qt, QPoint, QTimer, QPropertyAnimation, QEasingCurve, QRectF
    from qgis.PyQt.QtGui import QPainter, QColor, QPen, QBrush, QCursor, QPainterPath
    _QT_AVAILABLE = True
except Exception:  # pragma: no cover - Qt may not be available outside QGIS
    _QT_AVAILABLE = False


@dataclass
class TrailPoint:
    """A point in the cursor trail."""
    x: float
    y: float
    timestamp: float
    alpha: float = 1.0


class AICursorOverlay(QWidget if _QT_AVAILABLE else object):
    """Transparent overlay widget that renders the AI cursor with visual effects."""

    def __init__(self, parent=None):
        if not _QT_AVAILABLE:
            raise RuntimeError("PyQt6 is required for AICursorOverlay")
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.Tool |
                            Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._pos = QPoint(0, 0)
        self._target = QPoint(0, 0)
        self._active = False
        self._paused = False
        self._emergency_stopped = False
        self._action = "idle"  # idle, move, click, drag, typing
        self._action_timer = QTimer(self)
        self._action_timer.setSingleShot(True)
        self._action_timer.timeout.connect(self._clear_action)
        self._anim = QPropertyAnimation(self, b"cursorPos", self)
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # cursorPos property for animation
        self._cursor_pos = QPoint(0, 0)

        # Visual effects configuration
        self._highlight_radius = 20
        self._show_highlight = True
        self._show_ripple = True
        self._show_trail = True
        self._trail_points: List[TrailPoint] = []
        self._trail_max_length = 30
        self._trail_fade_time = 1.0  # seconds
        self._ripple_radius = 0
        self._ripple_max_radius = 40
        self._ripple_active = False
        self._ripple_timer = QTimer(self)
        self._ripple_timer.setSingleShot(True)
        self._ripple_timer.timeout.connect(self._animate_ripple)

        # Update timer for trail/ripple animation
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(16)  # ~60 FPS
        self._update_timer.timeout.connect(self._update_effects)
        self._update_timer.start()

    def _get_cursor_pos(self):
        return self._cursor_pos

    def _set_cursor_pos(self, p: QPoint):
        self._cursor_pos = p
        # Add to trail
        if self._show_trail:
            self._trail_points.append(TrailPoint(
                x=p.x(), y=p.y(), timestamp=time.time()
            ))
            # Limit trail length
            if len(self._trail_points) > self._trail_max_length:
                self._trail_points.pop(0)
        self.update()

    cursorPos = property(_get_cursor_pos, _set_cursor_pos)

    # ------------------------------------------------------------------ #
    # Control API
    # ------------------------------------------------------------------ #
    def move_to(self, x: int, y: int, smooth: bool = True) -> None:
        if self._emergency_stopped:
            return
        self._active = True
        self._action = "move"
        self._target = QPoint(x, y)
        self._action_timer.start(1200)
        if smooth and _QT_AVAILABLE:
            self._anim.setStartValue(self._cursor_pos)
            self._anim.setEndValue(QPoint(x, y))
            self._anim.start()
        else:
            self._cursor_pos = QPoint(x, y)
            self.update()
        logger.debug("AI cursor move to (%d, %d)", x, y)

    def click(self, x: int, y: int, button: str = "left") -> None:
        if self._emergency_stopped:
            return
        self.move_to(x, y, smooth=True)
        self._action = f"click:{button}"
        self._action_timer.start(1200)
        # Trigger ripple effect
        if self._show_ripple:
            self._trigger_ripple()
        self.update()
        logger.debug("AI cursor click %s at (%d, %d)", button, x, y)

    def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        if self._emergency_stopped:
            return
        self._action = "drag"
        self._target = QPoint(x2, y2)
        self._action_timer.start(1500)
        self.update()
        logger.debug("AI cursor drag (%d,%d)->(%d,%d)", x1, y1, x2, y2)

    def pause(self) -> None:
        self._paused = True
        logger.info("AI cursor paused")

    def resume(self) -> None:
        self._paused = False
        logger.info("AI cursor resumed")

    def emergency_stop(self) -> None:
        self._emergency_stopped = True
        self._active = False
        self._action = "idle"
        self._action_timer.stop()
        self._anim.stop()
        self._ripple_timer.stop()
        self._ripple_active = False
        self._ripple_radius = 0
        self._trail_points.clear()
        self.update()
        logger.warning("AI cursor emergency stop activated")

    def release_emergency_stop(self) -> None:
        self._emergency_stopped = False
        logger.info("AI cursor emergency stop released")

    def position(self) -> Tuple[int, int]:
        return (self._cursor_pos.x(), self._cursor_pos.y())

    def is_active(self) -> bool:
        return self._active and not self._paused and not self._emergency_stopped

    def status(self) -> dict:
        return {
            "position": self.position(),
            "active": self.is_active(),
            "paused": self._paused,
            "emergency_stopped": self._emergency_stopped,
            "action": self._action,
        }

    # ------------------------------------------------------------------ #
    # Visual Effects Configuration
    # ------------------------------------------------------------------ #
    def set_highlight_radius(self, radius: int) -> None:
        """Set the target highlight radius."""
        self._highlight_radius = max(5, min(100, radius))
        self.update()

    def set_show_highlight(self, show: bool) -> None:
        self._show_highlight = show
        self.update()

    def set_show_ripple(self, show: bool) -> None:
        self._show_ripple = show

    def set_show_trail(self, show: bool) -> None:
        self._show_trail = show
        if not show:
            self._trail_points.clear()
        self.update()

    def set_trail_max_length(self, length: int) -> None:
        self._trail_max_length = max(5, min(100, length))
        if len(self._trail_points) > self._trail_max_length:
            self._trail_points = self._trail_points[-self._trail_max_length:]

    def _clear_action(self):
        self._action = "idle"
        self.update()

    def _trigger_ripple(self):
        """Trigger click ripple animation."""
        self._ripple_active = True
        self._ripple_radius = 0
        self._ripple_timer.start(16)  # ~60 FPS animation

    def _animate_ripple(self):
        """Animate ripple expansion."""
        if not self._ripple_active:
            return
        self._ripple_radius += 4
        if self._ripple_radius >= self._ripple_max_radius:
            self._ripple_active = False
            self._ripple_radius = 0
        else:
            self._ripple_timer.start(16)
        self.update()

    def _update_effects(self):
        """Update trail fade and other time-based effects."""
        if not self._show_trail:
            return
        now = time.time()
        # Fade trail points
        self._trail_points = [
            TrailPoint(p.x, p.y, p.timestamp, max(0.0, 1.0 - (now - p.timestamp) / self._trail_fade_time))
            for p in self._trail_points
            if now - p.timestamp < self._trail_fade_time
        ]
        if self._trail_points:
            self.update()

    # ------------------------------------------------------------------ #
    # Painting
    # ------------------------------------------------------------------ #
    def paintEvent(self, event):  # noqa: N802
        if not _QT_AVAILABLE:
            return
        from qgis.PyQt.QtGui import QPainter, QColor, QPen, QBrush
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self._cursor_pos.x(), self._cursor_pos.y()

        # Draw trail
        if self._show_trail and self._trail_points:
            for i, point in enumerate(self._trail_points):
                if point.alpha <= 0:
                    continue
                # Trail gets smaller and more transparent towards the end
                size = max(2, int(10 * point.alpha * (i + 1) / len(self._trail_points)))
                alpha = int(180 * point.alpha * (i + 1) / len(self._trail_points))
                p.setPen(QPen(QColor(0, 255, 255, alpha), 2))
                p.setBrush(QBrush(QColor(0, 255, 255, alpha // 3)))
                p.drawEllipse(int(point.x) - size // 2, int(point.y) - size // 2, size, size)

        # Target highlight (when moving to a target)
        if self._active and self._action != "idle" and self._show_highlight:
            p.setPen(QPen(QColor(0, 120, 255, 180), 3))
            p.setBrush(QBrush(QColor(0, 120, 255, 40)))
            r = self._highlight_radius
            p.drawEllipse(self._target.x() - r, self._target.y() - r, r * 2, r * 2)
            # Crosshair at target
            p.setPen(QPen(QColor(0, 120, 255, 200), 2))
            tx, ty = self._target.x(), self._target.y()
            p.drawLine(tx - r, ty, tx + r, ty)
            p.drawLine(tx, ty - r, tx, ty + r)

        # Click ripple
        if self._ripple_active and self._show_ripple:
            alpha = int(200 * (1.0 - self._ripple_radius / self._ripple_max_radius))
            p.setPen(QPen(QColor(255, 255, 0, alpha), 3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(cx - self._ripple_radius, cy - self._ripple_radius,
                          self._ripple_radius * 2, self._ripple_radius * 2)

        # AI cursor body (distinct from human cursor: cyan ring + yellow dot)
        p.setPen(QPen(QColor(0, 255, 255), 3))
        p.setBrush(QBrush(QColor(0, 255, 255, 60)))
        p.drawEllipse(cx - 10, cy - 10, 20, 20)
        p.setBrush(QBrush(QColor(255, 255, 0)))
        p.drawEllipse(cx - 3, cy - 3, 6, 6)

        # Action indicator text
        if self._action != "idle":
            p.setPen(QPen(QColor(0, 120, 255), 2))
            p.drawText(cx + 12, cy - 10, self._action.upper())

        p.end()


class AICursorController:
    """Manages the AI cursor overlay and its state."""

    def __init__(self):
        self._overlay: Optional[AICursorOverlay] = None
        self._app: Optional[QApplication] = None
        self._register_emergency_stop()

    def _register_emergency_stop(self):
        """Register emergency stop callback."""
        try:
            from core.emergency_stop import EmergencyStop
            emergency_stop = EmergencyStop()
            emergency_stop.register(
                name="cursor_controller",
                callback=self._emergency_stop_callback,
                priority=80,
                description="Stop AI cursor overlay and animations"
            )
        except Exception as exc:
            logger.warning("Failed to register emergency stop for cursor controller: %s", exc)

    def _emergency_stop_callback(self):
        """Emergency stop callback for cursor controller."""
        logger.warning("CursorController emergency stop triggered")
        if self._overlay:
            self._overlay.emergency_stop()

    def ensure_overlay(self) -> AICursorOverlay:
        if not _QT_AVAILABLE:
            raise RuntimeError("PyQt6 not available; cannot create AI cursor overlay")
        if self._overlay is None:
            self._app = QApplication.instance() or QApplication([])
            self._overlay = AICursorOverlay()
            self._overlay.show()
        return self._overlay

    def move_to(self, x: int, y: int, smooth: bool = True):
        # Check global emergency stop
        if is_emergency_stop_active():
            logger.warning("Cursor move blocked: emergency stop active")
            return
        ov = self.ensure_overlay()
        if not ov._paused and not ov._emergency_stopped:
            ov.move_to(x, y, smooth=smooth)

    def click(self, x: int, y: int, button: str = "left"):
        # Check global emergency stop
        if is_emergency_stop_active():
            logger.warning("Cursor click blocked: emergency stop active")
            return
        ov = self.ensure_overlay()
        ov.click(x, y, button=button)

    def drag(self, x1: int, y1: int, x2: int, y2: int):
        # Check global emergency stop
        if is_emergency_stop_active():
            logger.warning("Cursor drag blocked: emergency stop active")
            return
        ov = self.ensure_overlay()
        ov.drag(x1, y1, x2, y2)

    def pause(self):
        ov = self.ensure_overlay()
        ov.pause()

    def resume(self):
        ov = self.ensure_overlay()
        ov.resume()

    def emergency_stop(self):
        ov = self.ensure_overlay()
        ov.emergency_stop()

    def release_emergency_stop(self):
        ov = self.ensure_overlay()
        ov.release_emergency_stop()

    def position(self) -> Tuple[int, int]:
        if self._overlay is None:
            return (0, 0)
        return self._overlay.position()

    def status(self) -> dict:
        if self._overlay is None:
            return {"position": (0, 0), "active": False, "paused": False,
                    "emergency_stopped": False, "action": "idle", "available": _QT_AVAILABLE}
        st = self._overlay.status()
        st["available"] = _QT_AVAILABLE
        return st

    # Visual effects configuration
    def set_highlight_radius(self, radius: int):
        """Set the target highlight radius."""
        if self._overlay:
            self._overlay.set_highlight_radius(radius)

    def set_show_highlight(self, show: bool):
        if self._overlay:
            self._overlay.set_show_highlight(show)

    def set_show_ripple(self, show: bool):
        if self._overlay:
            self._overlay.set_show_ripple(show)

    def set_show_trail(self, show: bool):
        if self._overlay:
            self._overlay.set_show_trail(show)

    def set_trail_max_length(self, length: int):
        if self._overlay:
            self._overlay.set_trail_max_length(length)


def cursor_controller() -> AICursorController:
    return AICursorController()


if __name__ == "__main__":  # pragma: no cover
    import sys
    app = QApplication(sys.argv)
    c = AICursorController()
    c.move_to(400, 300)
    c.click(400, 300)
    sys.exit(app.exec())
