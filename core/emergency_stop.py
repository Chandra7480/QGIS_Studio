"""Universal AI GIS Studio — Global Emergency Stop System.

A singleton that coordinates emergency stop across all subsystems:
- JobManager: cancel_all_jobs()
- CursorController: stop()
- BridgeServer: stop()
- WorkflowEngine: cancel_all()
- ScreenCapture: stop_periodic()
- ScreenCaptureEngine: stop_periodic()
- MacroPlayer: stop()
- CursorController: emergency_stop()
- MouseKeyboardController: stop()

UI: Red button in toolbar + hotkey (Ctrl+Shift+X)
Audit log entry on activation.
"""

import logging
import threading
from typing import Callable, List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from core.logging import get_logger
from core.event_bus import EventBus

logger = get_logger("core.emergency_stop")


class EmergencyStopActiveError(Exception):
    """Raised when an operation is attempted while emergency stop is active."""
    pass


@dataclass
class EmergencyStopCallback:
    """Registered callback for emergency stop."""
    name: str
    callback: Callable[[], None]
    priority: int = 0  # Higher priority = called first
    description: str = ""


# Priority constants for consistent ordering
class EmergencyStopPriority:
    """Priority levels for emergency stop callbacks.
    Higher values execute first.
    """
    # Critical safety systems (highest)
    CURSOR_CONTROLLER = 100      # Stop AI cursor immediately
    MOUSE_KEYBOARD = 90          # Stop input injection
    SCREEN_CAPTURE = 80          # Stop periodic capture
    MACRO_PLAYER = 70            # Stop macro playback
    
    # Core execution systems
    JOB_MANAGER = 60             # Cancel all jobs
    WORKFLOW_ENGINE = 50         # Cancel workflow execution
    BRIDGE_EXECUTOR = 40         # Stop PyQGIS operations
    MCP_SERVER = 30              # Stop MCP tool execution
    
    # Agents (lower - they check is_emergency_stop_active() directly)
    AGENTS = 20                  # Agent execution checks
    
    # Default
    DEFAULT = 0


class EmergencyStop:
    """Global Emergency Stop Singleton.

    Coordinates immediate cessation of all automated operations.
    Thread-safe. Can be triggered from any thread.
    """

    _instance: Optional["EmergencyStop"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._callbacks: List[EmergencyStopCallback] = []
        self._callbacks_lock = threading.RLock()
        self._triggered = False
        self._trigger_time: Optional[datetime] = None
        self._trigger_reason: str = ""
        self._triggered_by: str = "unknown"
        self._audit_logger = None
        self._event_bus = EventBus()

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #
    def register(self, name: str, callback: Callable[[], None],
                 priority: int = 0, description: str = "") -> None:
        """Register a callback to be called on emergency stop.

        Args:
            name: Unique identifier for this callback (e.g., "job_manager", "cursor_controller")
            callback: Callable that takes no arguments and performs the stop action
            priority: Higher values called first (default 0)
            description: Human-readable description of what this callback stops
        """
        with self._callbacks_lock:
            # Remove existing callback with same name
            self._callbacks = [c for c in self._callbacks if c.name != name]
            self._callbacks.append(EmergencyStopCallback(
                name=name,
                callback=callback,
                priority=priority,
                description=description
            ))
            # Sort by priority (highest first)
            self._callbacks.sort(key=lambda c: -c.priority)
            logger.info("Registered emergency stop callback: %s (priority=%d)", name, priority)

    def unregister(self, name: str) -> bool:
        """Unregister a callback by name. Returns True if found and removed."""
        with self._callbacks_lock:
            for i, cb in enumerate(self._callbacks):
                if cb.name == name:
                    self._callbacks.pop(i)
                    logger.info("Unregistered emergency stop callback: %s", name)
                    return True
            return False

    def get_registered(self) -> List[Dict[str, Any]]:
        """Get list of registered callbacks for debugging/UI."""
        with self._callbacks_lock:
            return [
                {"name": c.name, "priority": c.priority, "description": c.description}
                for c in self._callbacks
            ]

    # ------------------------------------------------------------------ #
    # Trigger
    # ------------------------------------------------------------------ #
    def trigger(self, reason: str = "Manual emergency stop", triggered_by: str = "user") -> Dict[str, Any]:
        """Trigger emergency stop. Calls all registered callbacks.

        Args:
            reason: Human-readable reason for the stop
            triggered_by: Identifier of what triggered it (e.g., "user", "hotkey", "watchdog")

        Returns:
            Dict with results of each callback execution
        """
        if self._triggered:
            logger.warning("Emergency stop already triggered, ignoring duplicate")
            return {"already_triggered": True, "trigger_time": self._trigger_time.isoformat() if self._trigger_time else None}

        logger.critical("EMERGENCY STOP TRIGGERED: %s (by %s)", reason, triggered_by)

        self._triggered = True
        self._trigger_time = datetime.utcnow()
        self._trigger_reason = reason
        self._triggered_by = triggered_by

        results = {}
        errors = []

        # Execute callbacks in priority order
        with self._callbacks_lock:
            callbacks = list(self._callbacks)

        for cb in callbacks:
            try:
                logger.info("Executing emergency stop callback: %s", cb.name)
                cb.callback()
                results[cb.name] = {"status": "ok", "description": cb.description}
            except Exception as exc:
                logger.exception("Emergency stop callback %s failed: %s", cb.name, exc)
                results[cb.name] = {"status": "error", "error": str(exc), "description": cb.description}
                errors.append(cb.name)

        # Audit log
        self._log_audit(reason, triggered_by, results, errors)

        # Publish EventBus event
        self._event_bus.publish("emergency_stop.triggered", {
            "reason": reason,
            "triggered_by": triggered_by,
            "trigger_time": self._trigger_time.isoformat(),
            "callbacks_executed": len(results),
            "callbacks_failed": len(errors),
            "errors": errors,
        })

        return {
            "triggered": True,
            "trigger_time": self._trigger_time.isoformat(),
            "reason": reason,
            "triggered_by": triggered_by,
            "callbacks_executed": len(results),
            "callbacks_failed": len(errors),
            "results": results,
        }

    def _log_audit(self, reason: str, triggered_by: str, results: dict, errors: list) -> None:
        """Log emergency stop activation to audit trail."""
        try:
            from database.repositories.audit_repository import AuditRepository
            from database.db import Database
            from core.config import Config

            # Try to get database connection - this is best effort
            # In practice, the plugin should set the audit logger
            if self._audit_logger:
                self._audit_logger.log(
                    actor="emergency_stop",
                    action="trigger",
                    target="all_systems",
                    outcome="success" if not errors else "partial_failure",
                    details={
                        "reason": reason,
                        "triggered_by": triggered_by,
                        "callbacks": results,
                        "errors": errors,
                    }
                )
        except Exception as exc:
            logger.debug("Could not write audit log for emergency stop: %s", exc)

    def set_audit_logger(self, audit_logger) -> None:
        """Set the audit logger for emergency stop events."""
        self._audit_logger = audit_logger

    # ------------------------------------------------------------------ #
    # Status / Reset
    # ------------------------------------------------------------------ #
    def is_triggered(self) -> bool:
        """Check if emergency stop has been triggered."""
        return self._triggered

    def assert_not_active(self) -> None:
        """Raise an exception if emergency stop is active.
        
        Use this in long-running operations to fail fast when emergency stop is triggered.
        """
        if self._triggered:
            raise EmergencyStopActiveError(
                f"Emergency stop active: {self._trigger_reason} (triggered by {self._triggered_by})"
            )

    def status(self) -> Dict[str, Any]:
        """Get current emergency stop status."""
        return {
            "triggered": self._triggered,
            "trigger_time": self._trigger_time.isoformat() if self._trigger_time else None,
            "reason": self._trigger_reason,
            "triggered_by": self._triggered_by,
            "registered_callbacks": len(self._callbacks),
            "callbacks": self.get_registered(),
        }

    def reset(self) -> Dict[str, Any]:
        """Reset emergency stop state (after human confirmation).

        Returns:
            Dict with reset status
        """
        if not self._triggered:
            return {"reset": True, "already_reset": True}

        logger.info("Emergency stop reset by user")
        previous_state = self.status()

        self._triggered = False
        self._trigger_time = None
        self._trigger_reason = ""
        self._triggered_by = ""

        # Log reset to audit
        try:
            if self._audit_logger:
                self._audit_logger.log(
                    actor="emergency_stop",
                    action="reset",
                    target="all_systems",
                    outcome="success",
                    details={"previous_state": previous_state}
                )
        except Exception:
            pass

        return {"reset": True, "previous_state": previous_state}


# ---------------------------------------------------------------------- #
# Convenience functions
# ---------------------------------------------------------------------- #
def emergency_stop() -> EmergencyStop:
    """Get the global EmergencyStop singleton instance."""
    return EmergencyStop()


def trigger_emergency_stop(reason: str = "Manual emergency stop", triggered_by: str = "user") -> Dict[str, Any]:
    """Convenience function to trigger emergency stop."""
    return emergency_stop().trigger(reason, triggered_by)


def reset_emergency_stop() -> Dict[str, Any]:
    """Convenience function to reset emergency stop."""
    return emergency_stop().reset()


def is_emergency_stop_active() -> bool:
    """Check if emergency stop is currently active."""
    return emergency_stop().is_triggered()