"""Universal AI GIS Studio — TCP Socket Server (nkarasiak pattern).

Non-blocking TCP socket driven by QTimer inside QGIS's event loop.
Length-prefixed framing, optional token auth, command registry with validation.
"""

import contextlib
import copy
import inspect
import itertools
import json
import math
import os
import secrets
import socket
import traceback
from collections import deque
from typing import ClassVar

from qgis.core import QgsApplication, QgsMessageLog, QgsProject
from qgis.PyQt.QtCore import QObject, QTimer

from bridge.registry import COMMANDS, command
from bridge.wire import (
    HEADER_STRUCT,
    MAX_MESSAGE_SIZE,
    RECV_CHUNK_SIZE,
    OutboundBuffer,
    OutboundOverflow,
    frame,
    BATCH_BLOCKED_COMMANDS,
    UNRECORDED_COMMANDS,
)
from core.logging import get_logger

logger = get_logger("uagis.socket_server")


def _json_safe(value):
    """Replace non-finite floats with None for valid JSON."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


# Compound Mode: 27 grouped commands with action parameter
# Format: {group_name: [(action_name, original_cmd_type), ...]}
COMPOUND_COMMANDS = {
    "system": [
        ("ping", "ping"),
        ("diagnose", "diagnose"),
        ("get_qgis_info", "get_qgis_info"),
        ("get_message_log", "get_message_log"),
    ],
    "project": [
        ("load_project", "load_project"),
        ("create_new_project", "create_new_project"),
        ("save_project", "save_project"),
        ("get_project_info", "get_project_info"),
        ("set_project_crs", "set_project_crs"),
    ],
    "layer": [
        ("get_layers", "get_layers"),
        ("add_vector_layer", "add_vector_layer"),
        ("add_raster_layer", "add_raster_layer"),
        ("remove_layer", "remove_layer"),
        ("find_layer", "find_layer"),
        ("create_memory_layer", "create_memory_layer"),
        ("set_layer_visibility", "set_layer_visibility"),
        ("zoom_to_layer", "zoom_to_layer"),
        ("get_layer_extent", "get_layer_extent"),
        ("set_layer_property", "set_layer_property"),
        ("get_layer_crs", "get_layer_crs"),
        ("set_layer_crs", "set_layer_crs"),
        ("get_active_layer", "get_active_layer"),
        ("set_active_layer", "set_active_layer"),
        ("add_table_join", "add_table_join"),
        ("export_layer", "export_layer"),
    ],
    "features": [
        ("get_layer_features", "get_layer_features"),
        ("add_features", "add_features"),
        ("update_features", "update_features"),
        ("update_feature_geometry", "update_feature_geometry"),
        ("delete_features", "delete_features"),
        ("select_features", "select_features"),
        ("get_selection", "get_selection"),
        ("clear_selection", "clear_selection"),
        ("get_field_statistics", "get_field_statistics"),
        ("get_unique_values", "get_unique_values"),
    ],
    "selection": [
        ("select_features", "select_features"),
        ("get_selection", "get_selection"),
        ("clear_selection", "clear_selection"),
    ],
    "style": [
        ("set_layer_style", "set_layer_style"),
        ("set_raster_style", "set_raster_style"),
        ("apply_style_qml", "apply_style_qml"),
        ("save_style_qml", "save_style_qml"),
        ("get_layer_labeling", "get_layer_labeling"),
        ("set_layer_labeling", "set_layer_labeling"),
    ],
    "canvas": [
        ("get_canvas_screenshot", "get_canvas_screenshot"),
        ("get_canvas_extent", "get_canvas_extent"),
        ("set_canvas_extent", "set_canvas_extent"),
        ("get_canvas_scale", "get_canvas_scale"),
        ("set_canvas_scale", "set_canvas_scale"),
    ],
    "render": [
        ("render_map", "render_map"),
        ("get_3d_screenshot", "get_3d_screenshot"),
    ],
    "processing": [
        ("execute_processing", "execute_processing"),
        ("execute_processing_batch", "execute_processing_batch"),
        ("list_processing_algorithms", "list_processing_algorithms"),
        ("get_algorithm_help", "get_algorithm_help"),
        ("get_processing_providers", "get_processing_providers"),
        ("create_processing_model", "create_processing_model"),
        ("list_processing_models", "list_processing_models"),
        ("run_model", "run_model"),
        ("start_processing_job", "start_processing_job"),
        ("get_processing_job", "get_processing_job"),
        ("cancel_processing_job", "cancel_processing_job"),
    ],
    "code": [
        ("execute_code", "execute_code"),
        ("batch_commands", "batch"),
        ("validate_expression", "validate_expression"),
    ],
    "batch": [
        ("batch_commands", "batch"),
    ],
    "layer_tree": [
        ("get_layer_tree", "get_layer_tree"),
        ("create_layer_group", "create_layer_group"),
        ("move_layer_to_group", "move_layer_to_group"),
        ("duplicate_layer", "duplicate_layer"),
        ("set_layer_order", "set_layer_order"),
    ],
    "plugins": [
        ("list_plugins", "list_plugins"),
        ("get_plugin_info", "get_plugin_info"),
        ("reload_plugin", "reload_plugin"),
    ],
    "variables": [
        ("get_project_variables", "get_project_variables"),
        ("set_project_variable", "set_project_variable"),
    ],
    "settings": [
        ("get_setting", "get_setting"),
        ("set_setting", "set_setting"),
    ],
    "expression": [
        ("evaluate_expression", "evaluate_expression"),
    ],
    "query": [
        ("execute_sql", "execute_sql"),
        ("identify_features", "identify_features"),
    ],
    "transform": [
        ("transform_coordinates", "transform_coordinates"),
    ],
}

# Build reverse mapping: original_cmd -> (group, action)
_COMPOUND_REVERSE_MAP = {}
for group, actions in COMPOUND_COMMANDS.items():
    for action, cmd in actions:
        _COMPOUND_REVERSE_MAP[cmd] = (group, action)


class SocketServer(
    QObject,
):
    """TCP Socket Server: accepts commands, dispatches them, frames replies.
    
    Non-blocking sockets driven by QTimer inside QGIS's event loop.
    No thread touches PyQGIS API (not thread-safe).
    Supports two tool modes:
    - granular: all individual commands (default, ~125 tools)
    - compound: 27 grouped tools with action parameter
    """

    LOG_TAG: ClassVar[str] = "UAGIS"

    MAX_CLIENTS: ClassVar[int] = 10
    MAX_TRACKED_VERSIONS: ClassVar[int] = 10
    MAX_AUTH_FAILURES: ClassVar[int] = 5
    MAX_JOURNAL: ClassVar[int] = 1000

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9876,
        iface=None,
        on_clients_changed=None,
    ):
        super().__init__()
        self.host = host
        self.port = port
        self.iface = iface
        self.on_clients_changed = on_clients_changed
        self.client_versions = set()
        self.client_fixes = {}
        self._signatures = {}
        
        # Tool mode: "granular" (default) or "compound"
        self.tool_mode = os.environ.get("QGIS_MCP_TOOL_MODE", "granular").lower()
        if self.tool_mode not in ("granular", "compound"):
            self.tool_mode = "granular"
        
        self.running = False
        self.socket = None
        self.clients: dict[socket.socket, bytearray] = {}
        self.outbound: dict[socket.socket, OutboundBuffer] = {}
        self._auth_failures: dict[socket.socket, int] = {}
        self.timer = None
        self._message_log = deque(maxlen=1000)
        self.start_error = None
        self._in_dispatch = False
        self._jobs = {}
        self._job_ids = itertools.count(1)
        self._journal = deque(maxlen=self.MAX_JOURNAL)
        self._journal_seq = itertools.count(1)
        self._journal_truncated = False
        self._checkpoints = {}
        self._checkpoint_ids = itertools.count(1)
        self._checkpoint_dir = None

    def _notify_clients_changed(self):
        if self.on_clients_changed:
            with contextlib.suppress(Exception):
                self.on_clients_changed(len(self.clients))

    _FIX_COMMANDS: ClassVar[dict] = {
        "uvx": "uv cache clean uagis-mcp",
        "source": 'uv --directory "{root}" sync',
    }
    _PATH_REJECTED: ClassVar[frozenset] = frozenset("\"'`$;&|<>\n\r")

    _LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})

    @staticmethod
    def _clean_announced(raw, limit):
        if not isinstance(raw, str):
            return ""
        return " ".join(raw.split())[:limit]

    def _fix_command(self, kind, raw_root):
        template = self._FIX_COMMANDS.get(kind)
        if template is None:
            return ""
        if "{root}" not in template:
            return template
        root = self._clean_announced(raw_root, 256)
        if not root or self._PATH_REJECTED & set(root):
            return ""
        return template.format(root=root)

    def _record_client_version(self, raw, kind=None, raw_root=None):
        version = self._clean_announced(raw, 64)
        if not version or version in self.client_versions:
            return
        if len(self.client_versions) >= self.MAX_TRACKED_VERSIONS:
            return
        self.client_versions.add(version)
        fix = self._fix_command(kind, raw_root)
        if fix:
            self.client_fixes[version] = fix

        mine = "1.0.0"
        if version == mine:
            QgsMessageLog.logMessage(f"MCP server {version} connected", self.LOG_TAG, 0)
            return
        message = (
            f"MCP server {version} connected, but this plugin is {mine}. "
            "Not fatal: tools added since the older half was built will be "
            "missing or refused."
        )
        if fix:
            message += f" To match them, run: {fix} (then restart your MCP client)."
        QgsMessageLog.logMessage(message, self.LOG_TAG, 1)

    def start(self):
        self.running = True
        self.start_error = None

        is_loopback = str(self.host).lower() in self._LOOPBACK_HOSTS
        has_token = bool(os.environ.get("QGIS_MCP_TOKEN", "").strip())
        if not is_loopback and not has_token:
            self.start_error = (
                f"Refusing to bind {self.host}: a non-loopback address exposes "
                "arbitrary code execution to the network. Set QGIS_MCP_TOKEN "
                "(in QGIS and in the MCP server) to enable this, or bind localhost."
            )
            QgsMessageLog.logMessage(self.start_error, self.LOG_TAG, 2)
            self.running = False
            return False

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.socket.setblocking(False)

            self.timer = QTimer()
            self.timer.timeout.connect(self.process_server)
            self.timer.start(25)  # 25ms interval

            msg_log = QgsApplication.messageLog()
            if hasattr(msg_log, "messageReceivedWithFormat"):
                msg_log.messageReceivedWithFormat.connect(self._capture_message)
            else:
                msg_log.messageReceived.connect(self._capture_message)
            QgsMessageLog.logMessage(
                f"UAGIS Socket Server started on {self.host}:{self.port}", self.LOG_TAG, 0
            )
            auth_on = bool(os.environ.get("QGIS_MCP_TOKEN", "").strip())
            QgsMessageLog.logMessage(
                f"Token authentication {'ENABLED' if auth_on else 'disabled (open)'}",
                self.LOG_TAG,
                0 if auth_on else 1,
            )
            return True
        except Exception as e:
            self.start_error = str(e)
            if isinstance(e, OSError) and e.errno in (98, 48):  # ADDR_IN_USE
                self.start_error = (
                    f"Port {self.port} is already in use. Pick a different port."
                )
            QgsMessageLog.logMessage(f"Failed to start server: {e!s}", self.LOG_TAG, 2)
            self.stop()
            return False

    def stop(self):
        self.running = False

        with contextlib.suppress(Exception):
            msg_log = QgsApplication.messageLog()
            if hasattr(msg_log, "messageReceivedWithFormat"):
                msg_log.messageReceivedWithFormat.disconnect(self._capture_message)
            else:
                msg_log.messageReceived.disconnect(self._capture_message)

        if self.timer:
            self.timer.stop()
            self.timer = None

        if self.socket:
            self.socket.close()
        for client_sock in list(self.clients):
            with contextlib.suppress(Exception):
                client_sock.close()
        self.clients.clear()
        self.outbound.clear()
        self._auth_failures.clear()
        self._notify_clients_changed()
        if self._checkpoint_dir:
            import shutil
            shutil.rmtree(self._checkpoint_dir, ignore_errors=True)
            self._checkpoint_dir = None
            self._checkpoints.clear()

        self.socket = None
        QgsMessageLog.logMessage("UAGIS Socket Server stopped", self.LOG_TAG, 0)

    def _disconnect_client(self, client_sock, message="Client disconnected", level=0):
        with contextlib.suppress(Exception):
            client_sock.close()
        self.clients.pop(client_sock, None)
        self.outbound.pop(client_sock, None)
        self._auth_failures.pop(client_sock, None)
        QgsMessageLog.logMessage(f"{message} ({len(self.clients)} active)", self.LOG_TAG, level)
        self._notify_clients_changed()

    def _send_response(self, client_sock, response):
        try:
            payload = json.dumps(_json_safe(response))
        except (TypeError, ValueError) as e:
            QgsMessageLog.logMessage(
                f"Response not JSON serializable: {e!s}", self.LOG_TAG, 2
            )
            payload = json.dumps(
                {
                    "status": "error",
                    "message": f"Response not JSON serializable: {e!s}",
                    "internal": True,
                }
            )
        resp_bytes = payload.encode("utf-8")
        buf = self.outbound.setdefault(client_sock, OutboundBuffer())
        buf.append(frame(resp_bytes))
        if buf.flush(client_sock):
            self.outbound.pop(client_sock, None)

    def _flush_outbound(self):
        for client_sock, buf in list(self.outbound.items()):
            try:
                if buf.flush(client_sock):
                    self.outbound.pop(client_sock, None)
            except Exception as e:
                self._disconnect_client(client_sock, f"Error writing: {e!s}", 1)

    def _read_frames(self, client_sock, data):
        buf = self.clients[client_sock]
        buf.extend(data)
        if len(buf) > 10 * 1024 * 1024:  # 10 MB
            raise ValueError("Buffer exceeded 10 MB limit")
        start = 0
        try:
            while len(buf) - start >= 4:
                msg_len = HEADER_STRUCT.unpack_from(buf, start)[0]
                if msg_len > 10 * 1024 * 1024:
                    raise ValueError(f"Message too large: {msg_len} bytes")
                body = start + 4
                msg_end = body + msg_len
                if len(buf) < msg_end:
                    break
                yield bytes(buf[body:msg_end])
                start = msg_end
        finally:
            del buf[:start]

    def _handle_request(self, client_sock, msg_bytes):
        try:
            request = json.loads(msg_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            QgsMessageLog.logMessage(f"Malformed request: {e!s}", self.LOG_TAG, 1)
            self._send_response(client_sock, {"status": "error", "message": f"Invalid JSON: {e!s}"})
            return True

        self._in_dispatch = True
        try:
            response = self.execute_command(request)
        finally:
            self._in_dispatch = False

        if response.get("message") == "Authentication failed: missing or invalid token":
            failures = self._auth_failures.get(client_sock, 0) + 1
            self._auth_failures[client_sock] = failures
            if failures >= 5:
                self._disconnect_client(client_sock, "Too many auth failures", 1)
                return False
        else:
            self._auth_failures.pop(client_sock, None)
        self._send_response(client_sock, response)
        return True

    def process_server(self):
        if not self.running:
            return
        if self._in_dispatch:
            return

        try:
            self._flush_outbound()

            if self.socket:
                while len(self.clients) < self.MAX_CLIENTS:
                    try:
                        client_sock, address = self.socket.accept()
                        client_sock.setblocking(False)
                        self.clients[client_sock] = bytearray()
                        QgsMessageLog.logMessage(
                            f"Connected: {address} ({len(self.clients)} active)",
                            self.LOG_TAG, 0,
                        )
                        self._notify_clients_changed()
                    except BlockingIOError:
                        break
                    except Exception as e:
                        QgsMessageLog.logMessage(f"Accept error: {e!s}", self.LOG_TAG, 1)
                        break

            for client_sock in list(self.clients):
                try:
                    data = client_sock.recv(65536)
                    if data:
                        for msg_bytes in self._read_frames(client_sock, data):
                            if not self._handle_request(client_sock, msg_bytes):
                                break
                    else:
                        self._disconnect_client(client_sock)
                except BlockingIOError:
                    pass
                except Exception as e:
                    self._disconnect_client(client_sock, f"Client error: {e!s}", 1)

        except Exception as e:
            QgsMessageLog.logMessage(f"Server error: {e!s}", self.LOG_TAG, 2)

    def execute_command(self, command):
        if not isinstance(command, dict):
            return {"status": "error", "message": "Invalid command: expected an object"}

        expected_token = os.environ.get("QGIS_MCP_TOKEN", "").strip()
        if expected_token:
            provided_token = str(command.get("token") or "")
            if not secrets.compare_digest(
                provided_token.encode("utf-8"), expected_token.encode("utf-8")
            ):
                QgsMessageLog.logMessage("Rejected: invalid token", self.LOG_TAG, 1)
                return {"status": "error", "message": "Authentication failed: missing or invalid token"}

        self._record_client_version(
            command.get("client_version"),
            command.get("client_install"),
            command.get("client_root"),
        )
        return self._dispatch(command)

    def _signature(self, cmd_type, handler):
        entry = self._signatures.get(cmd_type)
        if entry is None:
            signature = inspect.signature(handler)
            kinds = [p.kind for p in signature.parameters.values()]
            accepted = None
            if inspect.Parameter.VAR_KEYWORD in kinds:
                accepted = frozenset(
                    name
                    for name, p in signature.parameters.items()
                    if p.kind not in (p.VAR_KEYWORD, p.VAR_POSITIONAL)
                )
            entry = (signature, accepted)
            self._signatures[cmd_type] = entry
        return entry

    def _dispatch(self, command):
        try:
            cmd_type = command.get("type")
            params = command.get("params", {})

            if not isinstance(cmd_type, str) or cmd_type not in COMMANDS:
                QgsMessageLog.logMessage(f"Unknown command: {cmd_type}", self.LOG_TAG, 1)
                return {"status": "error", "message": f"Unknown command: {cmd_type}"}
            if not isinstance(params, dict):
                return {"status": "error", "message": "Invalid params: expected an object"}

            # In compound mode, only allow compound command and system commands
            if self.tool_mode == "compound":
                allowed_in_compound = {"compound", "get_compound_groups", "ping", "diagnose", "get_qgis_info", "get_message_log"}
                if cmd_type not in allowed_in_compound:
                    QgsMessageLog.logMessage(f"Command {cmd_type} not allowed in compound mode", self.LOG_TAG, 1)
                    return {"status": "error", "message": f"Command {cmd_type} not available in compound mode. Use 'compound' command with action parameter."}

            handler = getattr(self, cmd_type)

            signature, accepted = self._signature(cmd_type, handler)
            try:
                signature.bind(**params)
            except TypeError as exc:
                message = f"{cmd_type}: {exc}"
                QgsMessageLog.logMessage(f"Bad params: {message}", self.LOG_TAG, 1)
                return {"status": "error", "message": message}

            if accepted is not None:
                unknown = sorted(set(params) - accepted)
                if unknown:
                    message = (
                        f"{cmd_type}: unexpected parameter(s) {', '.join(unknown)}. "
                        f"Accepted: {', '.join(sorted(accepted)) or 'none'}"
                    )
                    QgsMessageLog.logMessage(f"Bad params: {message}", self.LOG_TAG, 1)
                    return {"status": "error", "message": message}

            record = cmd_type not in UNRECORDED_COMMANDS
            if record:
                recorded = copy.deepcopy(params)
                layers_before = set(QgsProject.instance().mapLayers())
                mark = self._journal[-1]["seq"] if self._journal else 0

            try:
                QgsMessageLog.logMessage(f"Executing: {cmd_type}", self.LOG_TAG, 0)
                result = handler(**params)
                if record and not (isinstance(result, dict) and result.get("executed") is False):
                    for entry in reversed(self._journal):
                        if entry["seq"] <= mark:
                            break
                        layers_before.update(lid for lid, _ in entry["creates"])
                    self._record(cmd_type, recorded, self._layers_added_since(layers_before))
                return {"status": "success", "result": result}
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Error in {cmd_type}: {e!r}\n{traceback.format_exc()}",
                    self.LOG_TAG, 2,
                )
                return {"status": "error", "message": str(e), "internal": True}

        except Exception as e:
            QgsMessageLog.logMessage(f"Dispatch error: {e!r}\n{traceback.format_exc()}", self.LOG_TAG, 2)
            return {"status": "error", "message": str(e), "internal": True}

    def _record(self, cmd_type, params, creates=()):
        if len(self._journal) == self._journal.maxlen:
            self._journal_truncated = True
        self._journal.append(
            {
                "seq": next(self._journal_seq),
                "command": cmd_type,
                "params": params,
                "creates": list(creates),
            }
        )

    @staticmethod
    def _layers_added_since(before):
        project = QgsProject.instance()
        return [
            (lid, layer.name()) for lid, layer in project.mapLayers().items() if lid not in before
        ]

    # --- Core Commands ---
    
    @command
    def ping(self, **kwargs):
        """Test connection."""
        return {"pong": True}

    @command
    def diagnose(self, **kwargs):
        """Run diagnostic checks."""
        return {
            "qgis_connected": self.iface is not None,
            "server_running": self.running,
            "port": self.port,
            "clients": len(self.clients),
            "plugin_version": "1.0.0",
        }

    @command
    def get_project_info(self, **kwargs):
        """Get current QGIS project information."""
        project = QgsProject.instance()
        return {
            "project_file": project.fileName(),
            "title": project.title(),
            "crs": project.crs().authid() if project.crs().isValid() else None,
            "layer_count": len(project.mapLayers()),
        }

    @command
    def load_project(self, path: str, **kwargs):
        """Load a QGIS project file."""
        project = QgsProject.instance()
        ok = project.read(path)
        return {"status": "success" if ok else "error", "path": path}

    @command
    def create_new_project(self, **kwargs):
        """Create a new QGIS project."""
        project = QgsProject.instance()
        project.clear()
        return {"status": "success", "message": "New project created"}

    @command
    def save_project(self, path: str = "", **kwargs):
        """Save current QGIS project."""
        project = QgsProject.instance()
        if path:
            ok = project.write(path)
        else:
            ok = project.write()
        return {"status": "success" if ok else "error"}

    @command
    def get_layers(self, **kwargs):
        """List all layers in current project."""
        project = QgsProject.instance()
        layers = []
        for lid, layer in project.mapLayers().items():
            layers.append({
                "id": lid,
                "name": layer.name(),
                "type": layer.type(),
                "crs": layer.crs().authid() if layer.crs().isValid() else None,
                "visible": True,
            })
        return {"layers": layers, "count": len(layers)}

    @command
    def add_vector_layer(self, path: str, name: str = "", provider: str = "ogr", **kwargs):
        """Add a vector layer to the project."""
        if not name:
            name = os.path.basename(path)
        layer = self.iface.addVectorLayer(path, name, provider)
        if not layer:
            raise Exception(f"Failed to load layer: {path}")
        return {"id": layer.id(), "name": layer.name()}

    @command
    def add_raster_layer(self, path: str, name: str = "", **kwargs):
        """Add a raster layer to the project."""
        if not name:
            name = os.path.basename(path)
        from qgis.core import QgsRasterLayer
        layer = QgsRasterLayer(path, name)
        if not layer.isValid():
            raise Exception(f"Failed to load raster: {path}")
        QgsProject.instance().addMapLayer(layer)
        return {"id": layer.id(), "name": layer.name()}

    @command
    def remove_layer(self, layer_id: str, **kwargs):
        """Remove a layer from the project."""
        project = QgsProject.instance()
        layer = project.mapLayer(layer_id)
        if not layer:
            raise Exception(f"Layer not found: {layer_id}")
        project.removeMapLayer(layer_id)
        return {"status": "success", "layer_id": layer_id}

    @command
    def get_layer_features(self, layer_id: str, limit: int = 100, **kwargs):
        """Get features from a layer."""
        project = QgsProject.instance()
        layer = project.mapLayer(layer_id)
        if not layer:
            raise Exception(f"Layer not found: {layer_id}")
        
        features = []
        for i, feat in enumerate(layer.getFeatures()):
            if i >= limit:
                break
            features.append({
                "id": feat.id(),
                "geometry": feat.geometry().asWkt() if feat.geometry() else None,
                "attributes": feat.attributes(),
            })
        return {"features": features, "count": len(features)}

    @command
    def add_features(self, layer_id: str, features: list, **kwargs):
        """Add features to a layer."""
        project = QgsProject.instance()
        layer = project.mapLayer(layer_id)
        if not layer:
            raise Exception(f"Layer not found: {layer_id}")
        
        if not layer.startEditing():
            raise Exception("Cannot start editing")
        
        added = []
        for feat_data in features:
            feat = layer.fields().createFeature()
            if "geometry" in feat_data:
                from qgis.core import QgsGeometry
                feat.setGeometry(QgsGeometry.fromWkt(feat_data["geometry"]))
            if "attributes" in feat_data:
                feat.setAttributes(feat_data["attributes"])
            if layer.addFeature(feat):
                added.append(feat.id())
        
        layer.commitChanges()
        return {"added": len(added), "feature_ids": added}

    @command
    def execute_processing(self, algorithm: str, parameters: dict = None, **kwargs):
        """Run a QGIS processing algorithm."""
        if parameters is None:
            parameters = {}
        import processing
        result = processing.run(algorithm, parameters)
        return result

    @command
    def execute_sql(self, connection: str, sql: str, **kwargs):
        """Execute SQL on a database connection."""
        from qgis.core import QgsDataSourceUri
        uri = QgsDataSourceUri(connection)
        # This is a simplified implementation
        return {"status": "executed", "connection": connection, "sql": sql}

    @command
    def render_map(self, width: int = 800, height: int = 600, **kwargs):
        """Render the map canvas to an image."""
        from qgis.PyQt.QtGui import QImage
        canvas = self.iface.mapCanvas()
        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(Qt.white)
        painter = QPainter(image)
        canvas.render(painter)
        painter.end()
        
        # Convert to base64
        import base64
        from qgis.PyQt.QtCore import QByteArray, QBuffer, QIODevice
        ba = QByteArray()
        buffer = QBuffer(ba)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        b64 = base64.b64encode(ba.data()).decode()
        return {"image_base64": b64, "width": width, "height": height}

    @command
    def execute_code(self, code: str, **kwargs):
        """Execute arbitrary PyQGIS code (dangerous!)."""
        # Create a restricted namespace
        namespace = {
            "iface": self.iface,
            "qgis": __import__("qgis"),
            "QgsProject": QgsProject,
        }
        try:
            exec(code, namespace)
            return {"executed": True, "result": "Code executed successfully"}
        except Exception as e:
            return {"executed": False, "error": str(e)}

    @command
    def batch(self, commands, **kwargs):
        if not isinstance(commands, list):
            raise Exception("commands must be a list")
        results = []
        for cmd in commands:
            if not isinstance(cmd, dict):
                results.append({"status": "error", "message": "Batch entry must be an object"})
                continue
            cmd_type = cmd.get("type")
            if cmd_type in BATCH_BLOCKED_COMMANDS:
                QgsMessageLog.logMessage(f"Refused {cmd_type!r} in batch", self.LOG_TAG, 1)
                results.append(
                    {
                        "status": "error",
                        "message": f"Command {cmd_type!r} not allowed in batch",
                    }
                )
                continue
            results.append(self._dispatch({"type": cmd_type, "params": cmd.get("params", {})}))
        return results

    @command
    def compound(self, action: str, params: dict = None, **kwargs):
        """
        Compound mode command - executes a grouped action.
        
        Args:
            action: The action name (e.g., "load_project", "get_layers")
            params: Parameters for the action
            
        Returns:
            Result of the sub-action
        """
        if params is None:
            params = {}
            
        if self.tool_mode != "compound":
            return {"status": "error", "message": "Compound mode not enabled. Set QGIS_MCP_TOOL_MODE=compound"}
        
        # Find the original command for this action
        for group, actions in COMPOUND_COMMANDS.items():
            for action_name, cmd_type in actions:
                if action_name == action:
                    return self._dispatch({"type": cmd_type, "params": params})
        
        return {"status": "error", "message": f"Unknown compound action: {action}"}

    @command
    def get_compound_groups(self, **kwargs):
        """Get list of available compound groups and their actions."""
        if self.tool_mode != "compound":
            return {"status": "error", "message": "Compound mode not enabled"}
        
        return {
            "groups": {
                group: [action for action, _ in actions]
                for group, actions in COMPOUND_COMMANDS.items()
            }
        }