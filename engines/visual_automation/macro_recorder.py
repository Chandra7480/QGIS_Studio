"""Universal AI GIS Studio — Macro Recorder.

Records mouse/keyboard events with timestamps for playback automation.
Supports parameterization with template variables, loops, conditionals,
and JSON export/import.
"""

import json
import time
import threading
import uuid
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

from core.logging import get_logger
from core.emergency_stop import is_emergency_stop_active

logger = get_logger("uagis.macro_recorder")


class EventType(Enum):
    """Types of recordable events."""
    MOUSE_MOVE = "mouse_move"
    MOUSE_CLICK = "mouse_click"
    MOUSE_DRAG = "mouse_drag"
    MOUSE_SCROLL = "mouse_scroll"
    KEY_PRESS = "key_press"
    KEY_RELEASE = "key_release"
    KEY_TYPE = "key_type"
    HOTKEY = "hotkey"
    WAIT = "wait"
    CONDITION = "condition"
    LOOP_START = "loop_start"
    LOOP_END = "loop_end"
    COMMENT = "comment"


@dataclass
class MacroEvent:
    """A single recorded event."""
    type: str
    timestamp: float  # Relative to macro start
    data: Dict[str, Any] = field(default_factory=dict)
    comment: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "timestamp": self.timestamp,
            "data": self.data,
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "MacroEvent":
        return cls(
            type=d["type"],
            timestamp=d["timestamp"],
            data=d.get("data", {}),
            comment=d.get("comment", ""),
        )


@dataclass
class MacroTemplate:
    """Template variable for parameterization."""
    name: str
    default_value: Any = ""
    description: str = ""
    value_type: str = "string"  # string, int, float, bool, coordinate


@dataclass
class Macro:
    """A complete macro with events and metadata."""
    id: str
    name: str
    description: str = ""
    events: List[MacroEvent] = field(default_factory=list)
    templates: List[MacroTemplate] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "events": [e.to_dict() for e in self.events],
            "templates": [asdict(t) for t in self.templates],
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Macro":
        macro = cls(
            id=d["id"],
            name=d["name"],
            description=d.get("description", ""),
            events=[MacroEvent.from_dict(e) for e in d.get("events", [])],
            templates=[MacroTemplate(**t) for t in d.get("templates", [])],
            created_at=d.get("created_at", time.time()),
            modified_at=d.get("modified_at", time.time()),
            version=d.get("version", 1),
        )
        return macro

    def get_duration(self) -> float:
        """Get total macro duration in seconds."""
        if not self.events:
            return 0.0
        return self.events[-1].timestamp

    def add_template(self, name: str, default_value: Any = "",
                     description: str = "", value_type: str = "string"):
        """Add a template variable."""
        self.templates.append(MacroTemplate(
            name=name,
            default_value=default_value,
            description=description,
            value_type=value_type
        ))

    def apply_templates(self, values: Dict[str, Any]) -> "Macro":
        """Create a new macro with template values applied."""
        import copy
        new_macro = copy.deepcopy(self)
        new_macro.id = str(uuid.uuid4())[:8]
        new_macro.name = f"{self.name} (instantiated)"
        new_macro.modified_at = time.time()

        # Replace template placeholders in events
        for event in new_macro.events:
            event.data = self._apply_template_values(event.data, values)

        return new_macro

    def _apply_template_values(self, data: Any, values: Dict[str, Any]) -> Any:
        """Recursively apply template values to data."""
        if isinstance(data, str):
            # Replace {{template_name}} placeholders
            for name, value in values.items():
                placeholder = f"{{{{{name}}}}}"
                if placeholder in data:
                    data = data.replace(placeholder, str(value))
            return data
        elif isinstance(data, dict):
            return {k: self._apply_template_values(v, values) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._apply_template_values(item, values) for item in data]
        return data


class MacroRecorder:
    """Records macro events from mouse/keyboard input."""

    def __init__(self):
        self._recording = False
        self._events: List[MacroEvent] = []
        self._start_time: float = 0
        self._lock = threading.RLock()
        self._current_macro: Optional[Macro] = None
        self._callbacks: List[Callable[[MacroEvent], None]] = []

    def start_recording(self, name: str = "Untitled Macro",
                        description: str = "") -> Macro:
        """Start recording a new macro."""
        with self._lock:
            if self._recording:
                raise RuntimeError("Already recording")

            self._recording = True
            self._events = []
            self._start_time = time.time()
            self._current_macro = Macro(
                id=str(uuid.uuid4())[:8],
                name=name,
                description=description,
            )
            logger.info("Started recording macro: %s", name)
            return self._current_macro

    def stop_recording(self) -> Optional[Macro]:
        """Stop recording and return the macro."""
        with self._lock:
            if not self._recording:
                return None

            self._recording = False
            if self._current_macro:
                self._current_macro.events = self._events.copy()
                self._current_macro.modified_at = time.time()
                macro = self._current_macro
                self._current_macro = None
                logger.info("Stopped recording macro: %s (%d events)", macro.name, len(macro.events))
                return macro
            return None

    def is_recording(self) -> bool:
        return self._recording

    def record_event(self, event_type: EventType, data: Dict[str, Any],
                     comment: str = "") -> None:
        """Record an event during recording."""
        with self._lock:
            if not self._recording:
                return

            timestamp = time.time() - self._start_time
            event = MacroEvent(
                type=event_type.value,
                timestamp=timestamp,
                data=data,
                comment=comment
            )
            self._events.append(event)

            # Notify callbacks
            for cb in self._callbacks:
                try:
                    cb(event)
                except Exception as exc:
                    logger.warning("Macro recorder callback failed: %s", exc)

    def register_callback(self, callback: Callable[[MacroEvent], None]) -> int:
        """Register a callback for real-time event monitoring."""
        callback_id = id(callback)
        self._callbacks.append(callback)
        return callback_id

    def unregister_callback(self, callback_id: int) -> bool:
        """Unregister a callback."""
        for i, cb in enumerate(self._callbacks):
            if id(cb) == callback_id:
                self._callbacks.pop(i)
                return True
        return False

    def get_current_events(self) -> List[MacroEvent]:
        """Get copy of current events (while recording)."""
        with self._lock:
            return self._events.copy()


class MacroPlayer:
    """Plays back recorded macros with parameterization support."""

    def __init__(self, executor=None):
        self.executor = executor  # Bridge executor or similar
        self._playing = False
        self._paused = False
        self._stop_requested = False
        self._current_macro: Optional[Macro] = None
        self._playback_thread: Optional[threading.Thread] = None
        self._event_index = 0
        self._loop_stack: List[Dict[str, Any]] = []
        self._variables: Dict[str, Any] = {}
        self._playback_speed = 1.0
        self._callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

    def register_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> int:
        """Register callback for playback events (event_type, event_data)."""
        callback_id = id(callback)
        self._callbacks.append(callback)
        return callback_id

    def unregister_callback(self, callback_id: int) -> bool:
        for i, cb in enumerate(self._callbacks):
            if id(cb) == callback_id:
                self._callbacks.pop(i)
                return True
        return False

    def _notify_callbacks(self, event_type: str, data: Dict[str, Any]):
        for cb in self._callbacks:
            try:
                cb(event_type, data)
            except Exception as exc:
                logger.warning("Playback callback failed: %s", exc)

    def play(self, macro: Macro, variables: Dict[str, Any] = None,
             speed: float = 1.0) -> Dict[str, Any]:
        """Play a macro with optional variable substitution."""
        if self._playing:
            return {"status": "already_playing"}

        # Apply templates if variables provided
        if variables:
            macro = macro.apply_templates(variables)

        self._current_macro = macro
        self._variables = variables or {}
        self._playback_speed = max(0.1, min(10.0, speed))
        self._playing = True
        self._paused = False
        self._stop_requested = False
        self._event_index = 0
        self._loop_stack = []

        self._playback_thread = threading.Thread(
            target=self._playback_loop,
            daemon=True,
            name="uagis-macro-playback"
        )
        self._playback_thread.start()

        logger.info("Started playback of macro: %s", macro.name)
        return {"status": "started", "macro_id": macro.id}

    def pause(self):
        """Pause playback."""
        self._paused = True
        logger.info("Macro playback paused")

    def resume(self):
        """Resume playback."""
        self._paused = False
        logger.info("Macro playback resumed")

    def stop(self):
        """Stop playback."""
        self._stop_requested = True
        self._playing = False
        if self._playback_thread:
            self._playback_thread.join(timeout=2.0)
        logger.info("Macro playback stopped")

    def is_playing(self) -> bool:
        return self._playing

    def get_progress(self) -> Dict[str, Any]:
        """Get current playback progress."""
        if not self._current_macro:
            return {"playing": False, "progress": 0.0}

        total = len(self._current_macro.events)
        current = self._event_index
        return {
            "playing": self._playing,
            "paused": self._paused,
            "progress": current / total if total > 0 else 1.0,
            "current_event": current,
            "total_events": total,
            "macro_name": self._current_macro.name,
        }

    def _playback_loop(self):
        """Main playback loop."""
        macro = self._current_macro
        events = macro.events

        last_timestamp = 0.0

        while self._event_index < len(events) and not self._stop_requested:
            # Check emergency stop
            if is_emergency_stop_active():
                logger.warning("Macro playback stopped: emergency stop active")
                self._stop_requested = True
                self._playing = False
                self._notify_callbacks("playback_complete", {
                    "macro_id": macro.id,
                    "completed": False,
                    "reason": "emergency_stop",
                })
                break

            if self._paused:
                time.sleep(0.1)
                continue

            event = events[self._event_index]

            # Calculate delay from last event
            delay = (event.timestamp - last_timestamp) / self._playback_speed
            if delay > 0:
                time.sleep(delay)

            if self._stop_requested:
                break

            # Execute event
            self._execute_event(event)
            self._notify_callbacks("event_executed", {
                "index": self._event_index,
                "event": event.to_dict(),
            })

            last_timestamp = event.timestamp
            self._event_index += 1

        self._playing = False
        logger.info("Playback finished: %s", macro.name)

    def _execute_event(self, event: MacroEvent):
        """Execute a single event."""
        if not self.executor:
            logger.debug("No executor, simulating event: %s", event.type)
            return

        event_type = event.type
        data = event.data

        try:
            if event_type == EventType.MOUSE_MOVE.value:
                self.executor.cursor_move(data.get("x", 0), data.get("y", 0))
            elif event_type == EventType.MOUSE_CLICK.value:
                self.executor.cursor_click(data.get("button", "left"))
            elif event_type == EventType.MOUSE_DRAG.value:
                self.executor.cursor_drag(
                    data.get("x1", 0), data.get("y1", 0),
                    data.get("x2", 0), data.get("y2", 0)
                )
            elif event_type == EventType.MOUSE_SCROLL.value:
                self.executor.mouse_scroll(data.get("delta", 0))
            elif event_type == EventType.KEY_TYPE.value:
                self.executor.keyboard_type(data.get("text", ""))
            elif event_type == EventType.HOTKEY.value:
                self.executor.keyboard_hotkey(data.get("keys", ""))
            elif event_type == EventType.WAIT.value:
                time.sleep(data.get("duration", 0))
            elif event_type == EventType.COMMENT.value:
                logger.info("Macro comment: %s", data.get("text", ""))
            elif event_type == EventType.LOOP_START.value:
                self._handle_loop_start(event)
            elif event_type == EventType.LOOP_END.value:
                self._handle_loop_end(event)
            elif event_type == EventType.CONDITION.value:
                self._handle_condition(event)
        except Exception as exc:
            logger.error("Failed to execute event %s: %s", event_type, exc)
            self._notify_callbacks("event_error", {
                "index": self._event_index,
                "event": event.to_dict(),
                "error": str(exc),
            })

    def _handle_loop_start(self, event: MacroEvent):
        """Handle loop start event."""
        count = event.data.get("count", 1)
        self._loop_stack.append({
            "start_index": self._event_index,
            "count": count,
            "iteration": 0,
        })

    def _handle_loop_end(self, event: MacroEvent):
        """Handle loop end event."""
        if not self._loop_stack:
            return

        loop = self._loop_stack[-1]
        loop["iteration"] += 1

        if loop["iteration"] < loop["count"]:
            # Jump back to after loop start
            self._event_index = loop["start_index"]
        else:
            # Loop complete, pop stack
            self._loop_stack.pop()

    def _handle_condition(self, event: MacroEvent):
        """Handle conditional event."""
        condition = event.data.get("condition", "")
        if not condition:
            return

        # Simple condition evaluation - can be extended
        # For now, just log
        logger.info("Condition check: %s", condition)


class MacroManager:
    """Manages macro storage, import/export."""

    def __init__(self, storage_dir: str = None):
        if storage_dir is None:
            from core.config import default_data_dir
            storage_dir = str(Path(default_data_dir()) / "macros")
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._macros: Dict[str, Macro] = {}
        self._load_all()

    def _load_all(self):
        """Load all macros from storage."""
        for file_path in self.storage_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                macro = Macro.from_dict(data)
                self._macros[macro.id] = macro
            except Exception as exc:
                logger.warning("Failed to load macro from %s: %s", file_path, exc)

    def save_macro(self, macro: Macro) -> str:
        """Save macro to file."""
        macro.modified_at = time.time()
        file_path = self.storage_dir / f"{macro.id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(macro.to_dict(), f, indent=2)
        self._macros[macro.id] = macro
        logger.info("Saved macro: %s", macro.name)
        return macro.id

    def load_macro(self, macro_id: str) -> Optional[Macro]:
        """Load macro by ID."""
        return self._macros.get(macro_id)

    def delete_macro(self, macro_id: str) -> bool:
        """Delete macro."""
        if macro_id in self._macros:
            file_path = self.storage_dir / f"{macro_id}.json"
            try:
                file_path.unlink(missing_ok=True)
                del self._macros[macro_id]
                return True
            except Exception as exc:
                logger.error("Failed to delete macro %s: %s", macro_id, exc)
        return False

    def list_macros(self) -> List[Dict[str, Any]]:
        """List all macros."""
        return [
            {
                "id": m.id,
                "name": m.name,
                "description": m.description,
                "event_count": len(m.events),
                "duration": m.get_duration(),
                "created_at": m.created_at,
                "modified_at": m.modified_at,
            }
            for m in self._macros.values()
        ]

    def export_macro(self, macro_id: str, export_path: str) -> bool:
        """Export macro to a specific path."""
        macro = self._macros.get(macro_id)
        if not macro:
            return False
        try:
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(macro.to_dict(), f, indent=2)
            return True
        except Exception as exc:
            logger.error("Failed to export macro: %s", exc)
            return False

    def import_macro(self, import_path: str) -> Optional[Macro]:
        """Import macro from file."""
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            macro = Macro.from_dict(data)
            # Generate new ID to avoid conflicts
            macro.id = str(uuid.uuid4())[:8]
            macro.name = f"{macro.name} (imported)"
            self.save_macro(macro)
            return macro
        except Exception as exc:
            logger.error("Failed to import macro: %s", exc)
            return None


# Convenience functions
def create_recorder() -> MacroRecorder:
    return MacroRecorder()


def create_player(executor=None) -> MacroPlayer:
    return MacroPlayer(executor)


def create_manager(storage_dir: str = None) -> MacroManager:
    return MacroManager(storage_dir)


if __name__ == "__main__":  # pragma: no cover
    # Demo
    recorder = create_recorder()
    macro = recorder.start_recording("Test Macro", "Demo recording")

    # Simulate recording some events
    recorder.record_event(EventType.MOUSE_MOVE, {"x": 100, "y": 100})
    time.sleep(0.1)
    recorder.record_event(EventType.MOUSE_CLICK, {"button": "left"})
    time.sleep(0.1)
    recorder.record_event(EventType.KEY_TYPE, {"text": "Hello"})
    time.sleep(0.1)
    recorder.record_event(EventType.MOUSE_MOVE, {"x": 200, "y": 200})

    macro = recorder.stop_recording()
    print(f"Recorded macro: {macro.name}, {len(macro.events)} events, {macro.get_duration():.2f}s")

    # Save and load
    manager = create_manager()
    manager.save_macro(macro)

    macros = manager.list_macros()
    print(f"Stored macros: {len(macros)}")

    # Play back
    player = create_player()
    player.play(macro, speed=2.0)
    while player.is_playing():
        time.sleep(0.1)
        prog = player.get_progress()
        print(f"Progress: {prog['progress']*100:.0f}%")
    print("Playback complete")