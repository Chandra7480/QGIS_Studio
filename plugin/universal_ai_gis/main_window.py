"""Universal AI GIS Studio — Main plugin window (dock widget content).

Functional PyQt6 UI panels for Universal AI GIS Studio. Uses QGIS Bridge
via HTTP client to execute real GIS operations.
"""

import json
import threading
import time
import os
import sys
from typing import Optional, List, Dict, Any
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QLabel,
    QStackedWidget, QSplitter, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QFormLayout,
    QGroupBox, QSpinBox, QCheckBox, QHeaderView, QMessageBox,
    QToolBar, QSlider, QDoubleSpinBox, QComboBox, QProgressBar,
    QFrame, QSizePolicy, QTabWidget, QDialog, QDialogButtonBox,
    QFileDialog, QColorDialog, QScrollArea, QListWidget, QListWidgetItem,
    QApplication, QStyle
)
from qgis.PyQt.QtCore import Qt, QTimer, QUrl, pyqtSignal, QObject, QSysInfo, QEvent, QRect
from qgis.PyQt.QtGui import QShortcut
from qgis.PyQt.QtGui import QPixmap, QImage, QKeySequence, QIcon, QFont, QColor, QTextCursor, QTextCharFormat, QSyntaxHighlighter, QTextDocument
from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice, QEventLoop, QRegularExpression
from qgis.PyQt.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

import base64
import uuid
import re
from datetime import datetime

# Optional websockets import for WebSocket client
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

# LLM Providers integration
try:
    from integrations.llm_providers import (
        get_provider, list_providers, get_provider_metadata,
        LLMProvider, LLMMessage, LLMTool, LLMResponse, LLMToolCall,
        LLMProviderConfig, LLMProviderError
    )
    LLM_PROVIDERS_AVAILABLE = True
except ImportError:
    LLM_PROVIDERS_AVAILABLE = False

# Optional websockets import for WebSocket client
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


class BridgeClient(QObject):
    """HTTP client for communicating with the QGIS Bridge server."""

    response_received = pyqtSignal(str, dict)  # request_id, response
    error_occurred = pyqtSignal(str, str)  # request_id, error_message

    def __init__(self, base_url: str = "http://127.0.0.1:8765", auth_token: str = ""):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.manager = QNetworkAccessManager(self)
        self.manager.finished.connect(self._on_reply_finished)
        self._pending_requests = {}

    def set_base_url(self, url: str):
        self.base_url = url.rstrip("/")

    def set_auth_token(self, token: str):
        self.auth_token = token

    def dispatch(self, tool: str, params: dict = None, timeout: int = 300,
                 require_approval: bool = False) -> str:
        """Send a dispatch request to the bridge. Returns request_id."""
        request_id = str(uuid.uuid4())[:8]
        payload = {
            "request_id": request_id,
            "tool": tool,
            "params": params or {},
            "timeout_seconds": timeout,
            "require_approval": require_approval,
        }

        url = QUrl(f"{self.base_url}/dispatch")
        request = QNetworkRequest(url)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        if self.auth_token:
            request.setRawHeader(b"Authorization", f"Bearer {self.auth_token}".encode())

        self._pending_requests[request_id] = time.time()
        self.manager.post(request, json.dumps(payload).encode("utf-8"))
        return request_id

    def _on_reply_finished(self, reply: QNetworkReply):
        request_id = None
        try:
            data = reply.readAll().data().decode("utf-8")
            response = json.loads(data)
            request_id = response.get("request_id", "unknown")
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.error_occurred.emit(request_id, f"HTTP {reply.error()}: {reply.errorString()}")
            else:
                self.response_received.emit(request_id, response)
        except Exception as exc:
            if request_id:
                self.error_occurred.emit(request_id, str(exc))
        finally:
            if request_id and request_id in self._pending_requests:
                del self._pending_requests[request_id]
            reply.deleteLater()

    def health_check(self) -> bool:
        """Quick health check - synchronous."""
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.base_url}/health", method="GET")
            if self.auth_token:
                req.add_header("Authorization", f"Bearer {self.auth_token}")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False


class WebSocketClient(QObject):
    """WebSocket client for real-time screen streaming."""

    frame_received = pyqtSignal(dict)
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, ws_url: str = "ws://127.0.0.1:8767"):
        super().__init__()
        self.ws_url = ws_url
        self._ws = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def connect(self):
        """Connect to WebSocket server."""
        if not WEBSOCKETS_AVAILABLE:
            self.error_occurred.emit("websockets library not available. Install with: pip install websockets")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="uagis-ws-client")
        self._thread.start()

    def disconnect(self):
        """Disconnect from WebSocket server."""
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass

    def send_config(self, config: dict):
        """Send configuration to server."""
        if self._ws:
            try:
                import json
                self._ws.send(json.dumps({"type": "config", "config": config}))
            except Exception as exc:
                self.error_occurred.emit(str(exc))

    def _run(self):
        """Run WebSocket client in thread."""
        try:
            import websockets
            import asyncio
            asyncio.run(self._async_run())
        except ImportError:
            self.error_occurred.emit("websockets library not available")
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    async def _async_run(self):
        """Async WebSocket loop."""
        try:
            import websockets
            async with websockets.connect(self.ws_url) as ws:
                self._ws = ws
                self.connected.emit()
                # Send ping to keep alive
                ping_task = asyncio.create_task(self._ping_loop(ws))
                try:
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            if data.get("type") == "frame":
                                self.frame_received.emit(data.get("data", {}))
                            elif data.get("type") == "pong":
                                pass  # Keep alive
                            elif data.get("type") == "config_ack":
                                pass  # Config acknowledged
                        except json.JSONDecodeError:
                            pass
                finally:
                    ping_task.cancel()
        except Exception as exc:
            self.error_occurred.emit(str(exc))
        finally:
            self.disconnected.emit()
            self._ws = None

    async def _ping_loop(self, ws):
        """Send periodic pings."""
        try:
            while True:
                await asyncio.sleep(10)
                await ws.send(json.dumps({"type": "ping"}))
        except asyncio.CancelledError:
            pass
        except Exception:
            pass


class MCPServerDialog(QDialog):
    """Dialog for adding/editing MCP server configuration."""

    def __init__(self, parent=None, config: dict = None):
        super().__init__(parent)
        self.setWindowTitle("MCP Server Configuration")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._config = config or {}
        self._build_ui()
        self._load_config()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("My MCP Server")
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # Transport type
        transport_layout = QHBoxLayout()
        transport_layout.addWidget(QLabel("Transport:"))
        self.transport_combo = QComboBox()
        self.transport_combo.addItems(["stdio (Local Command)", "http (Remote HTTP)"])
        self.transport_combo.currentIndexChanged.connect(self._on_transport_changed)
        transport_layout.addWidget(self.transport_combo)
        layout.addLayout(transport_layout)

        # Stacked widget for transport-specific fields
        self.transport_stack = QStackedWidget()
        layout.addWidget(self.transport_stack)

        # --- stdio page ---
        stdio_page = QWidget()
        stdio_layout = QFormLayout(stdio_page)
        stdio_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        stdio_layout.setHorizontalSpacing(16)
        stdio_layout.setVerticalSpacing(10)

        self.stdio_command = QLineEdit()
        self.stdio_command.setPlaceholderText("e.g., python, node, npx, /path/to/executable")
        stdio_layout.addRow("Command:", self.stdio_command)

        self.stdio_args = QLineEdit()
        self.stdio_args.setPlaceholderText("Arguments (space-separated, e.g., -m mcp_server)")
        stdio_layout.addRow("Arguments:", self.stdio_args)

        self.stdio_env = QLineEdit()
        self.stdio_env.setPlaceholderText("Environment variables (KEY=VALUE,KEY=VALUE)")
        stdio_layout.addRow("Environment:", self.stdio_env)

        stdio_info = QLabel(
            "Example stdio servers:\n"
            "• Command: npx, Args: -y @modelcontextprotocol/server-filesystem /path/to/dir\n"
            "• Command: python, Args: -m mcp_server_sqlite --db-path ./data.db\n"
            "• Command: uvx, Args: mcp-server-git --repository /path/to/repo"
        )
        stdio_info.setWordWrap(True)
        stdio_info.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 8px; background-color: #f8f9fa; border-radius: 4px;")
        stdio_layout.addRow("", stdio_info)

        self.transport_stack.addWidget(stdio_page)

        # --- HTTP page ---
        http_page = QWidget()
        http_layout = QFormLayout(http_page)
        http_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        http_layout.setHorizontalSpacing(16)
        http_layout.setVerticalSpacing(10)

        self.http_url = QLineEdit()
        self.http_url.setPlaceholderText("https://api.example.com/mcp")
        http_layout.addRow("URL:", self.http_url)

        self.http_headers = QTextEdit()
        self.http_headers.setPlaceholderText(
            "{\n"
            '  "Authorization": "Bearer your-token",\n'
            '  "X-Custom-Header": "value"\n'
            "}"
        )
        self.http_headers.setFont(QFont("Consolas", 10))
        self.http_headers.setMaximumHeight(120)
        self.http_headers.setStyleSheet("border: 1px solid #bdc3c7; border-radius: 4px; padding: 8px;")
        http_layout.addRow("Headers (JSON):", self.http_headers)

        http_info = QLabel(
            "Enter the HTTP endpoint URL and any required headers as JSON. "
            "The server must implement the MCP protocol over HTTP/SSE."
        )
        http_info.setWordWrap(True)
        http_info.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 8px; background-color: #f8f9fa; border-radius: 4px;")
        http_layout.addRow("", http_info)

        self.transport_stack.addWidget(http_page)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Save")
        layout.addWidget(button_box)

    def _on_transport_changed(self, index: int):
        self.transport_stack.setCurrentIndex(index)

    def _load_config(self):
        if not self._config:
            return

        self.name_edit.setText(self._config.get("name", ""))

        transport = self._config.get("transport", "stdio")
        if transport == "stdio":
            self.transport_combo.setCurrentIndex(0)
            self.stdio_command.setText(self._config.get("command", ""))
            args = self._config.get("args", [])
            self.stdio_args.setText(" ".join(args) if isinstance(args, list) else str(args))
            env = self._config.get("env", {})
            if isinstance(env, dict):
                self.stdio_env.setText(",".join(f"{k}={v}" for k, v in env.items()))
        else:
            self.transport_combo.setCurrentIndex(1)
            self.http_url.setText(self._config.get("url", ""))
            headers = self._config.get("headers", {})
            import json
            self.http_headers.setPlainText(json.dumps(headers, indent=2))

        self._on_transport_changed(self.transport_combo.currentIndex())

    def _on_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Please enter a server name.")
            return

        transport_index = self.transport_combo.currentIndex()
        if transport_index == 0:  # stdio
            command = self.stdio_command.text().strip()
            if not command:
                QMessageBox.warning(self, "Validation Error", "Please enter a command for stdio transport.")
                return
            args_text = self.stdio_args.text().strip()
            args = args_text.split() if args_text else []
            env_text = self.stdio_env.text().strip()
            env = {}
            if env_text:
                for pair in env_text.split(","):
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        env[k.strip()] = v.strip()
            self._config = {
                "name": name,
                "transport": "stdio",
                "command": command,
                "args": args,
                "env": env
            }
        else:  # HTTP
            url = self.http_url.text().strip()
            if not url:
                QMessageBox.warning(self, "Validation Error", "Please enter a URL for HTTP transport.")
                return
            headers_text = self.http_headers.toPlainText().strip()
            headers = {}
            if headers_text:
                import json
                try:
                    headers = json.loads(headers_text)
                    if not isinstance(headers, dict):
                        raise ValueError("Headers must be a JSON object")
                except json.JSONDecodeError as exc:
                    QMessageBox.warning(self, "Invalid JSON", f"Headers JSON is invalid:\n{exc}")
                    return
            self._config = {
                "name": name,
                "transport": "http",
                "url": url,
                "headers": headers
            }

        self.accept()

    def get_config(self) -> dict:
        return self._config


class UniversalAIGISMainWindow(QWidget):
    def __init__(self, iface, parent=None, config=None):
        super().__init__(parent)
        self.iface = iface
        self.config = config
        self.bridge_client = BridgeClient()
        self.ws_client = WebSocketClient()
        self._ws_connected = False
        self._periodic_capture_active = False
        self._setup_shortcuts()
        self._build_ui()
        self._connect_signals()

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Emergency Stop: Ctrl+Shift+X
        self.emergency_shortcut = QShortcut(QKeySequence("Ctrl+Shift+X"), self)
        self.emergency_shortcut.activated.connect(self._trigger_emergency_stop)

    def _connect_signals(self):
        """Connect bridge client signals."""
        self.bridge_client.response_received.connect(self._on_bridge_response)
        self.bridge_client.error_occurred.connect(self._on_bridge_error)
        self.ws_client.frame_received.connect(self._on_ws_frame)
        self.ws_client.connected.connect(self._on_ws_connected)
        self.ws_client.disconnected.connect(self._on_ws_disconnected)
        self.ws_client.error_occurred.connect(self._on_ws_error)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Toolbar with Emergency Stop
        self.toolbar = self._build_toolbar()
        outer.addWidget(self.toolbar)

        # Main content area
        content = QHBoxLayout()
        content.setContentsMargins(4, 4, 4, 4)
        content.setSpacing(4)

        # Left: section navigator
        self.nav = QTreeWidget()
        self.nav.setHeaderHidden(True)
        self.nav.setMaximumWidth(240)
        sections = [
            "Dashboard", "AI Chat", "Live Screen", "AI Cursor",
            "AI Connections", "API Providers", "MCP Manager", "Agent Manager",
            "Skill Manager", "GIS Clusters", "Georeferencing", "GCP Intelligence",
            "Workflow Builder", "Algorithm Discovery", "Data Manager",
            "Quality Control", "Task History", "Security", "Settings",
            "Macro & Visual Verification",
        ]
        for s in sections:
            QTreeWidgetItem(self.nav, [s])

        # Right: stacked content (functional panels per section)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._panel_dashboard())
        self.stack.addWidget(self._panel_ai_chat())
        self.stack.addWidget(self._panel_live_screen())
        self.stack.addWidget(self._panel_ai_cursor())
        self.stack.addWidget(self._panel_ai_connections())
        self.stack.addWidget(self._panel_api_providers())
        self.stack.addWidget(self._panel_mcp_manager())
        self.stack.addWidget(self._panel_agent_manager())
        self.stack.addWidget(self._panel_skill_manager())
        self.stack.addWidget(self._panel_gis_clusters())
        self.stack.addWidget(self._panel_georeferencing())
        self.stack.addWidget(self._panel_gcp_intelligence())
        self.stack.addWidget(self._panel_workflow_builder())
        self.stack.addWidget(self._panel_algorithm_discovery())
        self.stack.addWidget(self._panel_data_manager())
        self.stack.addWidget(self._panel_quality_control())
        self.stack.addWidget(self._panel_task_history())
        self.stack.addWidget(self._panel_security())
        self.stack.addWidget(self._panel_settings())
        self.stack.addWidget(self._panel_macro_verification())

        self.nav.currentItemChanged.connect(self._on_nav)

        splitter = QSplitter()
        splitter.addWidget(self.nav)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(1, 1)

        content.addWidget(splitter)
        outer.addLayout(content)

        self.nav.setCurrentItem(self.nav.topLevelItem(0))

    def _build_toolbar(self) -> QToolBar:
        """Build main toolbar with emergency stop button."""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(toolbar.iconSize())

        # Emergency Stop Button
        self.btn_emergency_stop = QPushButton("🛑 EMERGENCY STOP")
        self.btn_emergency_stop.setToolTip("Emergency Stop (Ctrl+Shift+X) - Stops all automation immediately")
        self.btn_emergency_stop.setMinimumHeight(36)
        self.btn_emergency_stop.setStyleSheet("""
            QPushButton {
                background-color: #ff4444;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border: 2px solid #cc0000;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #ff6666;
            }
            QPushButton:pressed {
                background-color: #cc0000;
            }
            QPushButton:disabled {
                background-color: #888888;
                color: #cccccc;
            }
        """)
        self.btn_emergency_stop.clicked.connect(self._trigger_emergency_stop)
        toolbar.addWidget(self.btn_emergency_stop)

        toolbar.addSeparator()

        # Bridge status indicator
        self.bridge_status_label = QLabel("● Bridge: Disconnected")
        self.bridge_status_label.setStyleSheet("color: #ff4444; font-weight: bold; padding: 4px;")
        toolbar.addWidget(self.bridge_status_label)

        toolbar.addSeparator()

        # Emergency stop status
        self.emergency_status_label = QLabel("")
        self.emergency_status_label.setStyleSheet("color: #ff4444; font-weight: bold; padding: 4px;")
        toolbar.addWidget(self.emergency_status_label)

        toolbar.addSeparator()

        # Version info display
        self.version_label = QLabel("v1.0.0")
        self.version_label.setStyleSheet("color: #7f8c8d; font-family: Consolas; font-size: 11px; padding: 4px 8px; background-color: #f8f9fa; border-radius: 3px;")
        self.version_label.setToolTip("Click to view detailed version information")
        self.version_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version_label.mousePressEvent = lambda e: self.nav.setCurrentItem(self.nav.topLevelItem(17)) if self.nav.topLevelItemCount() > 17 else None
        toolbar.addWidget(self.version_label)

        toolbar.addStretch()

        # Settings button
        btn_settings = QPushButton("⚙ Settings")
        btn_settings.clicked.connect(lambda: self.nav.setCurrentItem(self.nav.topLevelItem(17)))
        toolbar.addWidget(btn_settings)

        return toolbar

    def _on_nav(self, current, previous):
        if current is None:
            return
        idx = self.nav.indexOfTopLevelItem(current)
        self.stack.setCurrentIndex(idx)

    # ------------------------------------------------------------------ #
    # Panel builders
    # ------------------------------------------------------------------ #
    def _label_panel(self, title, note):
        w = QWidget()
        layout = QVBoxLayout(w)
        label = QLabel(f"{title}\n\n{note}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        return w

    def _panel_dashboard(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Universal AI GIS Studio — Dashboard"))

        # Status group
        status_group = QGroupBox("System Status")
        status_layout = QFormLayout()
        self.dashboard_bridge_status = QLabel("Checking...")
        self.dashboard_emergency_status = QLabel("Normal")
        self.dashboard_jobs_status = QLabel("0 active")
        self.dashboard_status = QLabel("Ready")  # General status label
        status_layout.addRow("Bridge:", self.dashboard_bridge_status)
        status_layout.addRow("Emergency Stop:", self.dashboard_emergency_status)
        status_layout.addRow("Active Jobs:", self.dashboard_jobs_status)
        status_layout.addRow("Status:", self.dashboard_status)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # Quick actions
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QVBoxLayout()
        btn_refresh = QPushButton("🔄 Refresh Status")
        btn_refresh.clicked.connect(self._refresh_status)
        actions_layout.addWidget(btn_refresh)

        btn_test_bridge = QPushButton("🔗 Test Bridge Connection")
        btn_test_bridge.clicked.connect(self._test_bridge_connection)
        actions_layout.addWidget(btn_test_bridge)

        btn_emergency_test = QPushButton("🧪 Test Emergency Stop")
        btn_emergency_test.clicked.connect(self._test_emergency_stop)
        actions_layout.addWidget(btn_emergency_test)

        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)

        layout.addStretch()
        return w

    def _panel_ai_chat(self):
        """Build professional AI Chat panel with streaming, markdown, code highlighting, tool calls."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(toolbar.iconSize())

        # New chat button
        btn_new_chat = QPushButton("➕ New Chat")
        btn_new_chat.setToolTip("Start a new conversation (Ctrl+N)")
        btn_new_chat.clicked.connect(self._chat_new_conversation)
        toolbar.addWidget(btn_new_chat)

        # Model selector
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Model:"))
        self.chat_model_combo = QComboBox()
        self.chat_model_combo.setMinimumWidth(200)
        self.chat_model_combo.setToolTip("Select LLM model")
        self.chat_model_combo.currentIndexChanged.connect(self._chat_model_changed)
        toolbar.addWidget(self.chat_model_combo)

        # Temperature slider
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Temp:"))
        self.chat_temperature = QDoubleSpinBox()
        self.chat_temperature.setRange(0.0, 2.0)
        self.chat_temperature.setValue(0.7)
        self.chat_temperature.setSingleStep(0.1)
        self.chat_temperature.setMaximumWidth(80)
        self.chat_temperature.setToolTip("Temperature (creativity)")
        toolbar.addWidget(self.chat_temperature)

        # Context attachment
        toolbar.addSeparator()
        self.chat_attach_context = QPushButton("📎 Attach Context")
        self.chat_attach_context.setToolTip("Attach project layers, selection, etc.")
        self.chat_attach_context.setCheckable(True)
        self.chat_attach_context.clicked.connect(self._chat_toggle_context)
        toolbar.addWidget(self.chat_attach_context)

        # Context indicator
        self.chat_context_label = QLabel("No context attached")
        self.chat_context_label.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 2px 8px;")
        toolbar.addWidget(self.chat_context_label)

        toolbar.addStretch()

        # Token usage
        self.chat_token_label = QLabel("Tokens: 0/0")
        self.chat_token_label.setStyleSheet("color: #7f8c8d; font-family: Consolas; font-size: 11px; padding: 2px 8px; background-color: #f8f9fa; border-radius: 3px;")
        toolbar.addWidget(self.chat_token_label)

        # Export conversation
        btn_export = QPushButton("📤 Export")
        btn_export.setToolTip("Export conversation (Ctrl+E)")
        btn_export.clicked.connect(self._chat_export_conversation)
        toolbar.addWidget(btn_export)

        # Settings
        btn_chat_settings = QPushButton("⚙️")
        btn_chat_settings.setToolTip("Chat Settings")
        btn_chat_settings.setMaximumWidth(32)
        btn_chat_settings.clicked.connect(self._chat_show_settings)
        toolbar.addWidget(btn_chat_settings)

        layout.addWidget(toolbar)

        # Chat messages area (scrollable)
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chat_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #ffffff;
            }
            QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #bdc3c7;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #95a5a6;
            }
        """)

        self.chat_messages_widget = QWidget()
        self.chat_messages_layout = QVBoxLayout(self.chat_messages_widget)
        self.chat_messages_layout.setSpacing(12)
        self.chat_messages_layout.setContentsMargins(16, 16, 16, 16)
        self.chat_messages_layout.addStretch()

        self.chat_scroll.setWidget(self.chat_messages_widget)
        layout.addWidget(self.chat_scroll, 1)

        # Input area
        input_frame = QFrame()
        input_frame.setFrameShape(QFrame.Shape.StyledPanel)
        input_frame.setStyleSheet("""
            QFrame {
                background-color: #fafafa;
                border-top: 1px solid #e0e0e0;
            }
        """)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 8, 12, 12)
        input_layout.setSpacing(8)

        # Input text area with send button
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.chat_input = QTextEdit()
        self.chat_input.setPlaceholderText("Ask me anything about GIS... (Enter to send, Shift+Enter for new line)")
        self.chat_input.setMaximumHeight(120)
        self.chat_input.setMinimumHeight(50)
        self.chat_input.setFont(QFont("Segoe UI", 10))
        self.chat_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d0d0d0;
                border-radius: 8px;
                padding: 10px;
                background-color: white;
            }
            QTextEdit:focus {
                border-color: #3498db;
            }
        """)
        self.chat_input.installEventFilter(self)
        input_row.addWidget(self.chat_input, 1)

        # Send button column
        send_col = QVBoxLayout()
        send_col.setSpacing(4)

        self.chat_send_btn = QPushButton("➤ Send")
        self.chat_send_btn.setMinimumHeight(44)
        self.chat_send_btn.setMinimumWidth(80)
        self.chat_send_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #5dade2; }
            QPushButton:pressed { background-color: #2980b9; }
            QPushButton:disabled { background-color: #bdc3c7; color: #95a5a6; }
        """)
        self.chat_send_btn.clicked.connect(self._chat_send_message)
        send_col.addWidget(self.chat_send_btn)

        # Stop button (shown during streaming)
        self.chat_stop_btn = QPushButton("⏹ Stop")
        self.chat_stop_btn.setMinimumHeight(32)
        self.chat_stop_btn.setMinimumWidth(80)
        self.chat_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover { background-color: #ec7063; }
            QPushButton:pressed { background-color: #c0392b; }
        """)
        self.chat_stop_btn.clicked.connect(self._chat_stop_generation)
        self.chat_stop_btn.hide()
        send_col.addWidget(self.chat_stop_btn)

        input_row.addLayout(send_col)
        input_layout.addLayout(input_row)

        # Quick actions row
        quick_row = QHBoxLayout()
        quick_row.setSpacing(8)

        self.chat_system_prompt_btn = QPushButton("📝 System Prompt")
        self.chat_system_prompt_btn.setToolTip("Edit system prompt")
        self.chat_system_prompt_btn.clicked.connect(self._chat_edit_system_prompt)
        quick_row.addWidget(self.chat_system_prompt_btn)

        self.chat_clear_btn = QPushButton("🗑️ Clear")
        self.chat_clear_btn.setToolTip("Clear conversation (Ctrl+L)")
        self.chat_clear_btn.clicked.connect(self._chat_clear_conversation)
        quick_row.addWidget(self.chat_clear_btn)

        self.chat_save_btn = QPushButton("💾 Save")
        self.chat_save_btn.setToolTip("Save conversation (Ctrl+S)")
        self.chat_save_btn.clicked.connect(self._chat_save_conversation)
        quick_row.addWidget(self.chat_save_btn)

        self.chat_load_btn = QPushButton("📂 Load")
        self.chat_load_btn.setToolTip("Load conversation (Ctrl+O)")
        self.chat_load_btn.clicked.connect(self._chat_load_conversation)
        quick_row.addWidget(self.chat_load_btn)

        quick_row.addStretch()

        # Shortcuts hint
        shortcuts_label = QLabel("Enter: Send | Shift+Enter: New Line | Ctrl+N: New Chat | Ctrl+E: Export | Ctrl+L: Clear")
        shortcuts_label.setStyleSheet("color: #95a5a6; font-size: 10px;")
        quick_row.addWidget(shortcuts_label)

        input_layout.addLayout(quick_row)

        layout.addWidget(input_frame)

        # Initialize chat state
        self._chat_conversations = []
        self._chat_current_conversation = -1
        self._chat_messages = []
        self._chat_streaming = False
        self._chat_current_response = ""
        self._chat_current_message_widget = None
        self._chat_attached_context = {}
        self._chat_mcp_tools = []

        # Load models for combo
        QTimer.singleShot(100, self._chat_populate_models)

        # Load default conversation
        QTimer.singleShot(200, self._chat_load_default_conversation)

        # Fetch MCP tools
        QTimer.singleShot(500, self._chat_fetch_mcp_tools)

        return w

    def _panel_live_screen(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        # Header with connection status
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Live Screen — Desktop Capture & Streaming"))

        self.screen_ws_status = QLabel("WebSocket: Disconnected")
        self.screen_ws_status.setStyleSheet("color: #ff4444;")
        header_layout.addWidget(self.screen_ws_status)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Screen display
        self.screen_label = QLabel("No screenshot captured yet.")
        self.screen_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.screen_label.setMinimumSize(400, 300)
        self.screen_label.setStyleSheet("border: 1px solid gray; background-color: #1a1a1a; color: #888;")
        layout.addWidget(self.screen_label, 1)

        # Controls
        controls_group = QGroupBox("Capture Controls")
        controls_layout = QVBoxLayout()

        # Single capture
        single_row = QHBoxLayout()
        btn_capture = QPushButton("📸 Capture Once")
        btn_capture.clicked.connect(self._capture_screen_once)
        single_row.addWidget(btn_capture)
        single_row.addStretch()
        controls_layout.addLayout(single_row)

        # Periodic capture
        periodic_row = QHBoxLayout()
        periodic_row.addWidget(QLabel("Interval (s):"))
        self.screen_interval = QDoubleSpinBox()
        self.screen_interval.setRange(1.0, 60.0)
        self.screen_interval.setValue(5.0)
        self.screen_interval.setSingleStep(1.0)
        periodic_row.addWidget(self.screen_interval)

        periodic_row.addWidget(QLabel("Region:"))
        self.screen_region = QLineEdit()
        self.screen_region.setPlaceholderText("left,top,right,bottom (empty=full)")
        self.screen_region.setMaximumWidth(200)
        periodic_row.addWidget(self.screen_region)

        self.screen_include_cursor = QCheckBox("Include Cursor")
        periodic_row.addWidget(self.screen_include_cursor)

        periodic_row.addStretch()
        controls_layout.addLayout(periodic_row)

        # Periodic start/stop
        periodic_btn_row = QHBoxLayout()
        self.btn_start_periodic = QPushButton("▶ Start Periodic Capture")
        self.btn_start_periodic.clicked.connect(self._start_periodic_capture)
        periodic_btn_row.addWidget(self.btn_start_periodic)

        self.btn_stop_periodic = QPushButton("⏹ Stop Periodic Capture")
        self.btn_stop_periodic.clicked.connect(self._stop_periodic_capture)
        self.btn_stop_periodic.setEnabled(False)
        periodic_btn_row.addWidget(self.btn_stop_periodic)
        periodic_btn_row.addStretch()
        controls_layout.addLayout(periodic_btn_row)

        # WebSocket streaming
        ws_row = QHBoxLayout()
        self.btn_connect_ws = QPushButton("🔌 Connect WebSocket Stream")
        self.btn_connect_ws.clicked.connect(self._toggle_websocket)
        ws_row.addWidget(self.btn_connect_ws)

        self.btn_ws_config = QPushButton("📡 Send Config")
        self.btn_ws_config.clicked.connect(self._send_ws_config)
        self.btn_ws_config.setEnabled(False)
        ws_row.addWidget(self.btn_ws_config)
        ws_row.addStretch()
        controls_layout.addLayout(ws_row)

        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)

        # Status
        self.screen_status = QLabel("Ready")
        layout.addWidget(self.screen_status)

        return w

    def _panel_ai_cursor(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("AI Cursor — Visual Overlay Control"))

        # Position controls
        pos_group = QGroupBox("Position")
        pos_layout = QFormLayout()
        self.cursor_x = QSpinBox()
        self.cursor_x.setRange(0, 9999)
        self.cursor_x.setValue(400)
        self.cursor_y = QSpinBox()
        self.cursor_y.setRange(0, 9999)
        self.cursor_y.setValue(300)
        pos_layout.addRow("X:", self.cursor_x)
        pos_layout.addRow("Y:", self.cursor_y)
        pos_group.setLayout(pos_layout)
        layout.addWidget(pos_group)

        # Movement controls
        move_group = QGroupBox("Movement")
        move_layout = QVBoxLayout()

        btn_row1 = QHBoxLayout()
        btn_move = QPushButton("🎯 Move Cursor (Smooth)")
        btn_move.clicked.connect(self._cursor_move_smooth)
        btn_row1.addWidget(btn_move)

        btn_move_instant = QPushButton("⚡ Move Cursor (Instant)")
        btn_move_instant.clicked.connect(self._cursor_move_instant)
        btn_row1.addWidget(btn_move_instant)
        move_layout.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        btn_click = QPushButton("🖱 Click")
        btn_click.clicked.connect(self._cursor_click)
        btn_row2.addWidget(btn_click)

        btn_right_click = QPushButton("🖱 Right Click")
        btn_right_click.clicked.connect(lambda: self._cursor_click("right"))
        btn_row2.addWidget(btn_right_click)
        move_layout.addLayout(btn_row2)

        btn_drag = QPushButton("🖱 Drag")
        btn_drag.clicked.connect(self._cursor_drag)
        move_layout.addWidget(btn_drag)

        move_group.setLayout(move_layout)
        layout.addWidget(move_group)

        # Visual effects controls
        effects_group = QGroupBox("Visual Effects")
        effects_layout = QFormLayout()

        self.cursor_highlight_radius = QSpinBox()
        self.cursor_highlight_radius.setRange(5, 100)
        self.cursor_highlight_radius.setValue(20)
        self.cursor_highlight_radius.valueChanged.connect(self._on_highlight_radius_changed)
        effects_layout.addRow("Highlight Radius:", self.cursor_highlight_radius)

        self.cursor_show_highlight = QCheckBox("Show Target Highlight")
        self.cursor_show_highlight.setChecked(True)
        self.cursor_show_highlight.toggled.connect(self._on_show_highlight_changed)
        effects_layout.addRow("", self.cursor_show_highlight)

        self.cursor_show_ripple = QCheckBox("Show Click Ripple")
        self.cursor_show_ripple.setChecked(True)
        self.cursor_show_ripple.toggled.connect(self._on_show_ripple_changed)
        effects_layout.addRow("", self.cursor_show_ripple)

        self.cursor_show_trail = QCheckBox("Show Movement Trail")
        self.cursor_show_trail.setChecked(True)
        self.cursor_show_trail.toggled.connect(self._on_show_trail_changed)
        effects_layout.addRow("", self.cursor_show_trail)

        self.cursor_trail_length = QSpinBox()
        self.cursor_trail_length.setRange(5, 100)
        self.cursor_trail_length.setValue(30)
        self.cursor_trail_length.valueChanged.connect(self._on_trail_length_changed)
        effects_layout.addRow("Trail Length:", self.cursor_trail_length)

        effects_group.setLayout(effects_layout)
        layout.addWidget(effects_group)

        # Cursor state
        state_group = QGroupBox("Cursor State")
        state_layout = QFormLayout()
        self.cursor_status_pos = QLabel("(0, 0)")
        self.cursor_status_active = QLabel("Inactive")
        self.cursor_status_paused = QLabel("No")
        self.cursor_status_emergency = QLabel("Normal")
        state_layout.addRow("Position:", self.cursor_status_pos)
        state_layout.addRow("Active:", self.cursor_status_active)
        state_layout.addRow("Paused:", self.cursor_status_paused)
        state_layout.addRow("Emergency:", self.cursor_status_emergency)
        state_group.setLayout(state_layout)
        layout.addWidget(state_group)

        # Control buttons
        ctrl_group = QGroupBox("Controls")
        ctrl_layout = QVBoxLayout()
        btn_pause = QPushButton("⏸ Pause Cursor")
        btn_pause.clicked.connect(self._cursor_pause)
        ctrl_layout.addWidget(btn_pause)

        btn_resume = QPushButton("▶ Resume Cursor")
        btn_resume.clicked.connect(self._cursor_resume)
        ctrl_layout.addWidget(btn_resume)

        btn_emergency = QPushButton("🛑 Emergency Stop Cursor")
        btn_emergency.clicked.connect(self._cursor_emergency_stop)
        btn_emergency.setStyleSheet("background-color: #ff4444; color: white; font-weight: bold;")
        ctrl_layout.addWidget(btn_emergency)

        btn_release = QPushButton("✅ Release Emergency Stop")
        btn_release.clicked.connect(self._cursor_release_emergency)
        ctrl_layout.addWidget(btn_release)

        ctrl_group.setLayout(ctrl_layout)
        layout.addWidget(ctrl_group)

        layout.addStretch()
        return w

    def _panel_ai_connections(self):
        """Build comprehensive AI Host Connections panel."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(8)

        # Header
        header_label = QLabel("🔌 AI Host Connections")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; padding: 8px 0;")
        layout.addWidget(header_label)

        # Create tabbed interface for different connection types
        self.ai_connections_tabs = QTabWidget()
        self.ai_connections_tabs.setDocumentMode(True)
        layout.addWidget(self.ai_connections_tabs, 1)

        # --- Tab 1: OpenCode Harness ---
        self.ai_connections_tabs.addTab(self._build_opencode_tab(), "🔧 OpenCode Harness")

        # --- Tab 2: Codex ---
        self.ai_connections_tabs.addTab(self._build_codex_tab(), "📝 Codex")

        # --- Tab 3: MCP Servers ---
        self.ai_connections_tabs.addTab(self._build_mcp_servers_tab(), "🔗 MCP Servers")

        # --- Tab 4: Bridge Server ---
        self.ai_connections_tabs.addTab(self._build_bridge_tab(), "🌉 Bridge Server")

        # --- Tab 5: WebSocket Streaming ---
        self.ai_connections_tabs.addTab(self._build_websocket_tab(), "📡 WebSocket Stream")

        # --- Tab 6: LLM Models ---
        self.ai_connections_tabs.addTab(self._build_llm_models_tab(), "🤖 LLM Models")

        # --- Tab 7: Version Info ---
        self.ai_connections_tabs.addTab(self._build_version_info_tab(), "ℹ️ Version Info")

        # Global save/load buttons at bottom
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_save_all = QPushButton("💾 Save All Connections")
        btn_save_all.setMinimumHeight(36)
        btn_save_all.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
            }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:pressed { background-color: #1e8c49; }
        """)
        btn_save_all.clicked.connect(self._save_all_ai_connections)
        btn_layout.addWidget(btn_save_all)

        btn_load_all = QPushButton("📂 Load from Config")
        btn_load_all.setMinimumHeight(36)
        btn_load_all.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
            }
            QPushButton:hover { background-color: #5dade2; }
            QPushButton:pressed { background-color: #2980b9; }
        """)
        btn_load_all.clicked.connect(self._load_all_ai_connections)
        btn_layout.addWidget(btn_load_all)

        layout.addLayout(btn_layout)

        # Status label
        self.ai_connections_status = QLabel("Ready. Configure connections and click 'Save All Connections' to persist.")
        self.ai_connections_status.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 4px;")
        layout.addWidget(self.ai_connections_status)

        # Load initial config
        QTimer.singleShot(100, self._load_all_ai_connections)

        return w

    def _build_opencode_tab(self) -> QWidget:
        """Build OpenCode Harness configuration tab."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        # Enable checkbox
        self.opencode_enabled_cb = QCheckBox("Enable OpenCode Harness Integration")
        self.opencode_enabled_cb.setChecked(True)
        self.opencode_enabled_cb.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(self.opencode_enabled_cb)

        # Connection group
        conn_group = QGroupBox("Connection Settings")
        conn_group.setStyleSheet(self._groupbox_style())
        conn_layout = QFormLayout()
        conn_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        conn_layout.setFormAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        conn_layout.setHorizontalSpacing(16)
        conn_layout.setVerticalSpacing(10)

        self.opencode_host = QLineEdit("127.0.0.1")
        self.opencode_host.setPlaceholderText("Host address (e.g., 127.0.0.1)")
        self.opencode_host.setMinimumWidth(300)
        conn_layout.addRow("Host:", self.opencode_host)

        self.opencode_port = QSpinBox()
        self.opencode_port.setRange(1, 65535)
        self.opencode_port.setValue(8080)
        self.opencode_port.setMinimumWidth(150)
        conn_layout.addRow("Port:", self.opencode_port)

        self.opencode_api_key = QLineEdit()
        self.opencode_api_key.setPlaceholderText("API Key (optional)")
        self.opencode_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.opencode_api_key.setMinimumWidth(300)
        conn_layout.addRow("API Key:", self.opencode_api_key)

        # Show/hide API key toggle
        self.opencode_show_key = QCheckBox("Show API Key")
        self.opencode_show_key.toggled.connect(
            lambda checked: self.opencode_api_key.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        conn_layout.addRow("", self.opencode_show_key)

        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # Test connection button
        test_layout = QHBoxLayout()
        self.btn_test_opencode = QPushButton("🔍 Test OpenCode Connection")
        self.btn_test_opencode.setMinimumHeight(36)
        self.btn_test_opencode.setStyleSheet(self._primary_button_style())
        self.btn_test_opencode.clicked.connect(self._test_opencode_connection)
        test_layout.addWidget(self.btn_test_opencode)

        self.opencode_test_status = QLabel("")
        self.opencode_test_status.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        test_layout.addWidget(self.opencode_test_status)
        test_layout.addStretch()
        layout.addLayout(test_layout)

        # Info box
        info_group = QGroupBox("Information")
        info_group.setStyleSheet(self._groupbox_style())
        info_layout = QVBoxLayout()
        info_text = QLabel(
            "OpenCode Harness provides a local AI coding agent server. "
            "Configure the host and port where your OpenCode server is running. "
            "The default port is 8080. API key is optional for local development."
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        info_layout.addWidget(info_text)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        layout.addStretch()
        return w

    def _build_codex_tab(self) -> QWidget:
        """Build Codex configuration tab."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        # Enable checkbox
        self.codex_enabled_cb = QCheckBox("Enable Codex Integration")
        self.codex_enabled_cb.setChecked(True)
        self.codex_enabled_cb.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(self.codex_enabled_cb)

        # JSON Configuration group
        json_group = QGroupBox("Codex Configuration (JSON)")
        json_group.setStyleSheet(self._groupbox_style())
        json_layout = QVBoxLayout()

        self.codex_config_text = QTextEdit()
        self.codex_config_text.setPlaceholderText(
            "{\n"
            '  "model": "gpt-4",\n'
            '  "temperature": 0.7,\n'
            '  "max_tokens": 4096,\n'
            '  "api_base": "https://api.openai.com/v1",\n'
            '  "organization": "org-xxxxx",\n'
            '  "custom_headers": {}\n'
            "}"
        )
        self.codex_config_text.setFont(QFont("Consolas", 10))
        self.codex_config_text.setMinimumHeight(200)
        self.codex_config_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                background-color: #fdfdfd;
                padding: 8px;
            }
            QTextEdit:focus { border-color: #3498db; }
        """)
        json_layout.addWidget(self.codex_config_text)

        # Validate button
        btn_validate = QPushButton("✅ Validate JSON")
        btn_validate.setMinimumHeight(32)
        btn_validate.setStyleSheet(self._secondary_button_style())
        btn_validate.clicked.connect(self._validate_codex_json)
        json_layout.addWidget(btn_validate)

        self.codex_validate_status = QLabel("")
        self.codex_validate_status.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        json_layout.addWidget(self.codex_validate_status)

        json_group.setLayout(json_layout)
        layout.addWidget(json_group, 1)

        # Quick templates
        template_group = QGroupBox("Quick Templates")
        template_group.setStyleSheet(self._groupbox_style())
        template_layout = QHBoxLayout()

        btn_default = QPushButton("📄 Default OpenAI")
        btn_default.clicked.connect(lambda: self._load_codex_template("default"))
        template_layout.addWidget(btn_default)

        btn_azure = QPushButton("☁️ Azure OpenAI")
        btn_azure.clicked.connect(lambda: self._load_codex_template("azure"))
        template_layout.addWidget(btn_azure)

        btn_custom = QPushButton("🔧 Custom")
        btn_custom.clicked.connect(lambda: self._load_codex_template("custom"))
        template_layout.addWidget(btn_custom)

        template_layout.addStretch()
        template_group.setLayout(template_layout)
        layout.addWidget(template_group)

        layout.addStretch()
        return w

    def _build_mcp_servers_tab(self) -> QWidget:
        """Build MCP Servers management tab."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        # Header with add button
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("MCP Server Configuration"))
        header_layout.addStretch()

        self.btn_add_mcp = QPushButton("➕ Add MCP Server")
        self.btn_add_mcp.setMinimumHeight(32)
        self.btn_add_mcp.setStyleSheet(self._primary_button_style())
        self.btn_add_mcp.clicked.connect(self._add_mcp_server_dialog)
        header_layout.addWidget(self.btn_add_mcp)
        layout.addLayout(header_layout)

        # MCP servers table
        self.mcp_table = QTableWidget(0, 6)
        self.mcp_table.setHorizontalHeaderLabels(["Name", "Transport", "Command / URL", "Args / Headers", "Status", "Actions"])
        self.mcp_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.mcp_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.mcp_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.mcp_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.mcp_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.mcp_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.mcp_table.setAlternatingRowColors(True)
        self.mcp_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.mcp_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                gridline-color: #ecf0f1;
                background-color: white;
                alternate-background-color: #f8f9fa;
            }
            QHeaderView::section {
                background-color: #2c3e50;
                color: white;
                padding: 6px;
                border: none;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.mcp_table, 1)

        # Buttons row
        btn_layout = QHBoxLayout()
        self.btn_test_all_mcp = QPushButton("🔍 Test All Connections")
        self.btn_test_all_mcp.setStyleSheet(self._secondary_button_style())
        self.btn_test_all_mcp.clicked.connect(self._test_all_mcp_servers)
        btn_layout.addWidget(self.btn_test_all_mcp)

        self.btn_refresh_mcp = QPushButton("🔄 Refresh")
        self.btn_refresh_mcp.setStyleSheet(self._secondary_button_style())
        self.btn_refresh_mcp.clicked.connect(self._refresh_mcp_table)
        btn_layout.addWidget(self.btn_refresh_mcp)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Info
        info_label = QLabel(
            "MCP (Model Context Protocol) servers provide tools and resources to AI agents. "
            "Add stdio servers (local commands) or HTTP servers (remote endpoints). "
            "Each server can be tested individually or all at once."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 8px; background-color: #f8f9fa; border-radius: 4px;")
        layout.addWidget(info_label)

        return w

    def _build_bridge_tab(self) -> QWidget:
        """Build Bridge Server configuration tab."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        # Connection group
        conn_group = QGroupBox("Bridge HTTP Server")
        conn_group.setStyleSheet(self._groupbox_style())
        conn_layout = QFormLayout()
        conn_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        conn_layout.setFormAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        conn_layout.setHorizontalSpacing(16)
        conn_layout.setVerticalSpacing(10)

        self.bridge_host = QLineEdit("127.0.0.1")
        self.bridge_host.setPlaceholderText("Bridge server host")
        self.bridge_host.setMinimumWidth(300)
        conn_layout.addRow("Host:", self.bridge_host)

        self.bridge_port = QSpinBox()
        self.bridge_port.setRange(1, 65535)
        self.bridge_port.setValue(8765)
        self.bridge_port.setMinimumWidth(150)
        conn_layout.addRow("Port:", self.bridge_port)

        self.bridge_auth_token = QLineEdit()
        self.bridge_auth_token.setPlaceholderText("Authentication token (optional)")
        self.bridge_auth_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.bridge_auth_token.setMinimumWidth(300)
        conn_layout.addRow("Auth Token:", self.bridge_auth_token)

        self.bridge_show_token = QCheckBox("Show Token")
        self.bridge_show_token.toggled.connect(
            lambda checked: self.bridge_auth_token.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        conn_layout.addRow("", self.bridge_show_token)

        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # MCP Bridge settings
        mcp_group = QGroupBox("MCP Bridge Settings")
        mcp_group.setStyleSheet(self._groupbox_style())
        mcp_layout = QFormLayout()
        mcp_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        mcp_layout.setHorizontalSpacing(16)
        mcp_layout.setVerticalSpacing(10)

        self.mcp_stdio_enabled = QCheckBox("Enable MCP stdio transport")
        self.mcp_stdio_enabled.setChecked(True)
        mcp_layout.addRow("", self.mcp_stdio_enabled)

        self.mcp_http_enabled = QCheckBox("Enable MCP HTTP transport")
        self.mcp_http_enabled.setChecked(True)
        mcp_layout.addRow("", self.mcp_http_enabled)

        self.mcp_http_port = QSpinBox()
        self.mcp_http_port.setRange(1, 65535)
        self.mcp_http_port.setValue(8766)
        self.mcp_http_port.setMinimumWidth(150)
        mcp_layout.addRow("MCP HTTP Port:", self.mcp_http_port)

        mcp_group.setLayout(mcp_layout)
        layout.addWidget(mcp_group)

        # Test button
        test_layout = QHBoxLayout()
        self.btn_test_bridge = QPushButton("🔍 Test Bridge Connection")
        self.btn_test_bridge.setMinimumHeight(36)
        self.btn_test_bridge.setStyleSheet(self._primary_button_style())
        self.btn_test_bridge.clicked.connect(self._test_bridge_connection_from_ai_tab)
        test_layout.addWidget(self.btn_test_bridge)

        self.bridge_test_status = QLabel("")
        self.bridge_test_status.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        test_layout.addWidget(self.bridge_test_status)
        test_layout.addStretch()
        layout.addLayout(test_layout)

        layout.addStretch()
        return w

    def _build_websocket_tab(self) -> QWidget:
        """Build WebSocket Streaming configuration tab."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        # Enable checkbox
        self.ws_enabled_cb = QCheckBox("Enable WebSocket Streaming")
        self.ws_enabled_cb.setChecked(True)
        self.ws_enabled_cb.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(self.ws_enabled_cb)

        # Connection group
        conn_group = QGroupBox("WebSocket Server")
        conn_group.setStyleSheet(self._groupbox_style())
        conn_layout = QFormLayout()
        conn_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        conn_layout.setFormAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        conn_layout.setHorizontalSpacing(16)
        conn_layout.setVerticalSpacing(10)

        self.ws_host = QLineEdit("127.0.0.1")
        self.ws_host.setPlaceholderText("WebSocket server host")
        self.ws_host.setMinimumWidth(300)
        conn_layout.addRow("Host:", self.ws_host)

        self.ws_port = QSpinBox()
        self.ws_port.setRange(1, 65535)
        self.ws_port.setValue(8767)
        self.ws_port.setMinimumWidth(150)
        conn_layout.addRow("Port:", self.ws_port)

        self.ws_url_display = QLineEdit()
        self.ws_url_display.setReadOnly(True)
        self.ws_url_display.setStyleSheet("background-color: #f8f9fa; color: #2c3e50; font-family: Consolas;")
        self._update_ws_url_display()
        conn_layout.addRow("WebSocket URL:", self.ws_url_display)

        # Auto-update URL when host/port change
        self.ws_host.textChanged.connect(self._update_ws_url_display)
        self.ws_port.valueChanged.connect(self._update_ws_url_display)

        conn_group.setLayout(conn_layout)
        layout.addWidget(conn_group)

        # Streaming settings
        stream_group = QGroupBox("Streaming Settings")
        stream_group.setStyleSheet(self._groupbox_style())
        stream_layout = QFormLayout()
        stream_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        stream_layout.setHorizontalSpacing(16)
        stream_layout.setVerticalSpacing(10)

        self.ws_interval = QDoubleSpinBox()
        self.ws_interval.setRange(0.1, 60.0)
        self.ws_interval.setValue(1.0)
        self.ws_interval.setSingleStep(0.1)
        self.ws_interval.setSuffix(" s")
        stream_layout.addRow("Frame Interval:", self.ws_interval)

        self.ws_quality = QSpinBox()
        self.ws_quality.setRange(10, 100)
        self.ws_quality.setValue(85)
        self.ws_quality.setSuffix(" %")
        stream_layout.addRow("JPEG Quality:", self.ws_quality)

        self.ws_include_cursor = QCheckBox("Include Cursor in Stream")
        self.ws_include_cursor.setChecked(True)
        stream_layout.addRow("", self.ws_include_cursor)

        stream_group.setLayout(stream_layout)
        layout.addWidget(stream_group)

        # Test button
        test_layout = QHBoxLayout()
        self.btn_test_ws = QPushButton("🔍 Test WebSocket Connection")
        self.btn_test_ws.setMinimumHeight(36)
        self.btn_test_ws.setStyleSheet(self._primary_button_style())
        self.btn_test_ws.clicked.connect(self._test_websocket_connection)
        test_layout.addWidget(self.btn_test_ws)

        self.ws_test_status = QLabel("")
        self.ws_test_status.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        test_layout.addWidget(self.ws_test_status)
        test_layout.addStretch()
        layout.addLayout(test_layout)

        layout.addStretch()
        return w

    def _build_llm_models_tab(self) -> QWidget:
        """Build LLM Models configuration tab."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(12)

        # Header
        header_label = QLabel("🤖 LLM Model Configuration")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; padding: 8px 0;")
        layout.addWidget(header_label)

        # Provider selection
        provider_group = QGroupBox("Provider Selection")
        provider_group.setStyleSheet(self._groupbox_style())
        provider_layout = QFormLayout()
        provider_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        provider_layout.setHorizontalSpacing(16)
        provider_layout.setVerticalSpacing(10)

        self.llm_provider_combo = QComboBox()
        self.llm_provider_combo.setMinimumWidth(300)
        if LLM_PROVIDERS_AVAILABLE:
            for provider in list_providers():
                self.llm_provider_combo.addItem(f"{provider['name']} ({provider['id']})", provider['id'])
        else:
            self.llm_provider_combo.addItem("LLM Providers not available", "none")
        self.llm_provider_combo.currentIndexChanged.connect(self._on_llm_provider_changed)
        provider_layout.addRow("Provider:", self.llm_provider_combo)

        # Active provider indicator
        self.llm_active_provider_label = QLabel("Active: Not configured")
        self.llm_active_provider_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        provider_layout.addRow("", self.llm_active_provider_label)

        provider_group.setLayout(provider_layout)
        layout.addWidget(provider_group)

        # Provider configuration (stacked by provider)
        self.llm_config_stack = QStackedWidget()
        layout.addWidget(self.llm_config_stack, 1)

        # Create config pages for each provider
        self._llm_config_pages = {}
        if LLM_PROVIDERS_AVAILABLE:
            for provider in list_providers():
                page = self._create_llm_provider_config_page(provider)
                self._llm_config_pages[provider['id']] = page
                self.llm_config_stack.addWidget(page)
        else:
            # Placeholder page
            placeholder = QWidget()
            ph_layout = QVBoxLayout(placeholder)
            ph_layout.addWidget(QLabel("LLM Provider modules not available.\nPlease ensure integrations/llm_providers is installed."))
            ph_layout.addStretch()
            self.llm_config_stack.addWidget(placeholder)

        # Model presets
        preset_group = QGroupBox("Model Presets")
        preset_group.setStyleSheet(self._groupbox_style())
        preset_layout = QHBoxLayout()

        self.btn_save_preset = QPushButton("💾 Save as Preset")
        self.btn_save_preset.setMinimumHeight(32)
        self.btn_save_preset.setStyleSheet(self._primary_button_style())
        self.btn_save_preset.clicked.connect(self._save_llm_preset)
        preset_layout.addWidget(self.btn_save_preset)

        self.btn_load_preset = QPushButton("📂 Load Preset")
        self.btn_load_preset.setMinimumHeight(32)
        self.btn_load_preset.setStyleSheet(self._secondary_button_style())
        self.btn_load_preset.clicked.connect(self._load_llm_preset)
        preset_layout.addWidget(self.btn_load_preset)

        self.btn_delete_preset = QPushButton("🗑️ Delete Preset")
        self.btn_delete_preset.setMinimumHeight(32)
        self.btn_delete_preset.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold; border: none; border-radius: 4px; padding: 6px 16px;")
        self.btn_delete_preset.clicked.connect(self._delete_llm_preset)
        preset_layout.addWidget(self.btn_delete_preset)

        preset_layout.addStretch()
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        # Presets list
        self.llm_presets_combo = QComboBox()
        self.llm_presets_combo.setMinimumWidth(300)
        self.llm_presets_combo.setPlaceholderText("Select a preset...")
        preset_layout.addWidget(QLabel("Saved Presets:"))
        preset_layout.addWidget(self.llm_presets_combo)

        # Global parameters (apply to all providers)
        global_group = QGroupBox("Global Parameters")
        global_group.setStyleSheet(self._groupbox_style())
        global_layout = QFormLayout()
        global_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        global_layout.setHorizontalSpacing(16)
        global_layout.setVerticalSpacing(10)

        self.llm_global_system_prompt = QTextEdit()
        self.llm_global_system_prompt.setPlaceholderText("Default system prompt for all providers...")
        self.llm_global_system_prompt.setMaximumHeight(80)
        self.llm_global_system_prompt.setFont(QFont("Consolas", 10))
        global_layout.addRow("System Prompt:", self.llm_global_system_prompt)

        self.llm_global_temperature = QDoubleSpinBox()
        self.llm_global_temperature.setRange(0.0, 2.0)
        self.llm_global_temperature.setValue(0.7)
        self.llm_global_temperature.setSingleStep(0.1)
        global_layout.addRow("Default Temperature:", self.llm_global_temperature)

        self.llm_global_max_tokens = QSpinBox()
        self.llm_global_max_tokens.setRange(100, 128000)
        self.llm_global_max_tokens.setValue(4096)
        self.llm_global_max_tokens.setSingleStep(100)
        global_layout.addRow("Default Max Tokens:", self.llm_global_max_tokens)

        self.llm_global_top_p = QDoubleSpinBox()
        self.llm_global_top_p.setRange(0.0, 1.0)
        self.llm_global_top_p.setValue(1.0)
        self.llm_global_top_p.setSingleStep(0.05)
        global_layout.addRow("Default Top-p:", self.llm_global_top_p)

        self.llm_stream_responses = QCheckBox("Stream Responses")
        self.llm_stream_responses.setChecked(True)
        global_layout.addRow("", self.llm_stream_responses)

        self.llm_show_token_usage = QCheckBox("Show Token Usage")
        self.llm_show_token_usage.setChecked(True)
        global_layout.addRow("", self.llm_show_token_usage)

        global_group.setLayout(global_layout)
        layout.addWidget(global_group)

        # Test connection button
        test_layout = QHBoxLayout()
        self.btn_test_llm = QPushButton("🔍 Test Connection")
        self.btn_test_llm.setMinimumHeight(36)
        self.btn_test_llm.setStyleSheet(self._primary_button_style())
        self.btn_test_llm.clicked.connect(self._test_llm_connection)
        test_layout.addWidget(self.btn_test_llm)

        self.llm_test_status = QLabel("")
        self.llm_test_status.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        test_layout.addWidget(self.llm_test_status)
        test_layout.addStretch()
        layout.addLayout(test_layout)

        # Apply/Save button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_apply_llm = QPushButton("✅ Apply & Save Configuration")
        self.btn_apply_llm.setMinimumHeight(36)
        self.btn_apply_llm.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 4px;
                padding: 8px 24px;
            }
            QPushButton:hover { background-color: #2ecc71; }
            QPushButton:pressed { background-color: #1e8c49; }
        """)
        self.btn_apply_llm.clicked.connect(self._apply_llm_configuration)
        btn_layout.addWidget(self.btn_apply_llm)
        layout.addLayout(btn_layout)

        layout.addStretch()

        # Load saved configuration
        QTimer.singleShot(100, self._load_llm_configuration)

        return w

    def _create_llm_provider_config_page(self, provider_meta: dict) -> QWidget:
        """Create a configuration page for a specific provider."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        # API Key
        key_group = QGroupBox("Authentication")
        key_group.setStyleSheet(self._groupbox_style())
        key_layout = QFormLayout()
        key_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        key_layout.setHorizontalSpacing(16)
        key_layout.setVerticalSpacing(10)

        api_key_edit = QLineEdit()
        api_key_edit.setPlaceholderText("Enter API key...")
        api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        api_key_edit.setMinimumWidth(400)
        setattr(page, f"api_key_{provider_meta['id']}", api_key_edit)
        key_layout.addRow("API Key:", api_key_edit)

        show_key_cb = QCheckBox("Show API Key")
        show_key_cb.toggled.connect(
            lambda checked, edit=api_key_edit: edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        key_layout.addRow("", show_key_cb)

        if not provider_meta.get('requires_api_key', True):
            info_label = QLabel("⚠️ This provider may not require an API key (e.g., local Ollama)")
            info_label.setStyleSheet("color: #f39c12; font-size: 11px;")
            key_layout.addRow("", info_label)

        key_group.setLayout(key_layout)
        layout.addWidget(key_group)

        # Base URL override
        url_group = QGroupBox("Endpoint Configuration")
        url_group.setStyleSheet(self._groupbox_style())
        url_layout = QFormLayout()
        url_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        url_layout.setHorizontalSpacing(16)
        url_layout.setVerticalSpacing(10)

        base_url_edit = QLineEdit(provider_meta.get('default_base_url', ''))
        base_url_edit.setPlaceholderText("Base URL (optional override)")
        base_url_edit.setMinimumWidth(400)
        setattr(page, f"base_url_{provider_meta['id']}", base_url_edit)
        url_layout.addRow("Base URL:", base_url_edit)

        url_group.setLayout(url_layout)
        layout.addWidget(url_group)

        # Model selection
        model_group = QGroupBox("Model Selection")
        model_group.setStyleSheet(self._groupbox_style())
        model_layout = QFormLayout()
        model_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        model_layout.setHorizontalSpacing(16)
        model_layout.setVerticalSpacing(10)

        model_combo = QComboBox()
        model_combo.setMinimumWidth(400)
        model_combo.setEditable(True)
        model_combo.addItems(provider_meta.get('default_models', []))
        setattr(page, f"model_combo_{provider_meta['id']}", model_combo)
        model_layout.addRow("Model:", model_combo)

        # Fetch models button
        fetch_models_btn = QPushButton("🔄 Fetch Models from API")
        fetch_models_btn.setStyleSheet(self._secondary_button_style())
        fetch_models_btn.clicked.connect(
            lambda _, pid=provider_meta['id']: self._fetch_llm_models(pid)
        )
        model_layout.addRow("", fetch_models_btn)

        model_group.setLayout(model_layout)
        layout.addWidget(model_group)

        # Parameters
        param_group = QGroupBox("Model Parameters")
        param_group.setStyleSheet(self._groupbox_style())
        param_layout = QFormLayout()
        param_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        param_layout.setHorizontalSpacing(16)
        param_layout.setVerticalSpacing(10)

        temp_spin = QDoubleSpinBox()
        temp_spin.setRange(0.0, 2.0)
        temp_spin.setValue(0.7)
        temp_spin.setSingleStep(0.1)
        setattr(page, f"temperature_{provider_meta['id']}", temp_spin)
        param_layout.addRow("Temperature:", temp_spin)

        max_tokens_spin = QSpinBox()
        max_tokens_spin.setRange(100, 128000)
        max_tokens_spin.setValue(4096)
        max_tokens_spin.setSingleStep(100)
        setattr(page, f"max_tokens_{provider_meta['id']}", max_tokens_spin)
        param_layout.addRow("Max Tokens:", max_tokens_spin)

        top_p_spin = QDoubleSpinBox()
        top_p_spin.setRange(0.0, 1.0)
        top_p_spin.setValue(1.0)
        top_p_spin.setSingleStep(0.05)
        setattr(page, f"top_p_{provider_meta['id']}", top_p_spin)
        param_layout.addRow("Top-p:", top_p_spin)

        freq_penalty_spin = QDoubleSpinBox()
        freq_penalty_spin.setRange(-2.0, 2.0)
        freq_penalty_spin.setValue(0.0)
        freq_penalty_spin.setSingleStep(0.1)
        setattr(page, f"freq_penalty_{provider_meta['id']}", freq_penalty_spin)
        param_layout.addRow("Frequency Penalty:", freq_penalty_spin)

        pres_penalty_spin = QDoubleSpinBox()
        pres_penalty_spin.setRange(-2.0, 2.0)
        pres_penalty_spin.setValue(0.0)
        pres_penalty_spin.setSingleStep(0.1)
        setattr(page, f"pres_penalty_{provider_meta['id']}", pres_penalty_spin)
        param_layout.addRow("Presence Penalty:", pres_penalty_spin)

        param_group.setLayout(param_layout)
        layout.addWidget(param_group)

        # System prompt override
        system_group = QGroupBox("System Prompt (Optional Override)")
        system_group.setStyleSheet(self._groupbox_style())
        system_layout = QVBoxLayout()

        system_prompt_edit = QTextEdit()
        system_prompt_edit.setPlaceholderText("Override default system prompt for this provider...")
        system_prompt_edit.setMaximumHeight(80)
        system_prompt_edit.setFont(QFont("Consolas", 10))
        setattr(page, f"system_prompt_{provider_meta['id']}", system_prompt_edit)
        system_layout.addWidget(system_prompt_edit)

        system_group.setLayout(system_layout)
        layout.addWidget(system_group)

        layout.addStretch()
        return page

    def _build_version_info_tab(self) -> QWidget:
        """Build Version Information tab."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(16)

        # Title
        title = QLabel("📋 Version Control Information")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; padding: 8px 0;")
        layout.addWidget(title)

        # Version info group
        version_group = QGroupBox("Build Information")
        version_group.setStyleSheet(self._groupbox_style())
        version_layout = QFormLayout()
        version_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        version_layout.setHorizontalSpacing(16)
        version_layout.setVerticalSpacing(10)

        self.version_app_name = QLabel("Universal AI GIS Studio")
        self.version_app_name.setStyleSheet("font-weight: bold; color: #2c3e50;")
        version_layout.addRow("Application:", self.version_app_name)

        self.version_app_version = QLabel("1.0.0")
        self.version_app_version.setStyleSheet("font-family: Consolas; color: #2c3e50;")
        version_layout.addRow("Version:", self.version_app_version)

        self.version_git_hash = QLabel("Loading...")
        self.version_git_hash.setStyleSheet("font-family: Consolas; color: #34495e;")
        version_layout.addRow("Git Commit:", self.version_git_hash)

        self.version_git_branch = QLabel("Loading...")
        self.version_git_branch.setStyleSheet("font-family: Consolas; color: #34495e;")
        version_layout.addRow("Git Branch:", self.version_git_branch)

        self.version_git_tag = QLabel("Loading...")
        self.version_git_tag.setStyleSheet("font-family: Consolas; color: #34495e;")
        version_layout.addRow("Git Tag:", self.version_git_tag)

        self.version_build_date = QLabel("Loading...")
        self.version_build_date.setStyleSheet("font-family: Consolas; color: #34495e;")
        version_layout.addRow("Build Date:", self.version_build_date)

        self.version_build_number = QLabel("Loading...")
        self.version_build_number.setStyleSheet("font-family: Consolas; color: #34495e;")
        version_layout.addRow("Build Number:", self.version_build_number)

        self.version_qgis_version = QLabel("Loading...")
        self.version_qgis_version.setStyleSheet("font-family: Consolas; color: #34495e;")
        version_layout.addRow("QGIS Version:", self.version_qgis_version)

        self.version_python_version = QLabel("Loading...")
        self.version_python_version.setStyleSheet("font-family: Consolas; color: #34495e;")
        version_layout.addRow("Python Version:", self.version_python_version)

        self.version_pyqt_version = QLabel("Loading...")
        self.version_pyqt_version.setStyleSheet("font-family: Consolas; color: #34495e;")
        version_layout.addRow("PyQt Version:", self.version_pyqt_version)

        version_group.setLayout(version_layout)
        layout.addWidget(version_group)

        # Runtime info group
        runtime_group = QGroupBox("Runtime Information")
        runtime_group.setStyleSheet(self._groupbox_style())
        runtime_layout = QFormLayout()
        runtime_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        runtime_layout.setHorizontalSpacing(16)
        runtime_layout.setVerticalSpacing(10)

        self.runtime_os = QLabel("Loading...")
        self.runtime_os.setStyleSheet("font-family: Consolas; color: #34495e;")
        runtime_layout.addRow("Operating System:", self.runtime_os)

        self.runtime_platform = QLabel("Loading...")
        self.runtime_platform.setStyleSheet("font-family: Consolas; color: #34495e;")
        runtime_layout.addRow("Platform:", self.runtime_platform)

        self.runtime_arch = QLabel("Loading...")
        self.runtime_arch.setStyleSheet("font-family: Consolas; color: #34495e;")
        runtime_layout.addRow("Architecture:", self.runtime_arch)

        self.runtime_data_dir = QLabel("Loading...")
        self.runtime_data_dir.setStyleSheet("font-family: Consolas; color: #34495e;")
        runtime_layout.addRow("Data Directory:", self.runtime_data_dir)

        runtime_group.setLayout(runtime_layout)
        layout.addWidget(runtime_group)

        # Refresh button
        btn_refresh_version = QPushButton("🔄 Refresh Version Info")
        btn_refresh_version.setMinimumHeight(36)
        btn_refresh_version.setStyleSheet(self._primary_button_style())
        btn_refresh_version.clicked.connect(self._refresh_version_info)
        layout.addWidget(btn_refresh_version)

        layout.addStretch()

        # Load version info on creation
        QTimer.singleShot(50, self._refresh_version_info)

        return w

    # --- Styling helper methods ---
    def _groupbox_style(self) -> str:
        return """
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                left: 10px;
                background-color: white;
            }
        """

    def _primary_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
            }
            QPushButton:hover { background-color: #5dade2; }
            QPushButton:pressed { background-color: #2980b9; }
            QPushButton:disabled { background-color: #bdc3c7; color: #95a5a6; }
        """

    def _secondary_button_style(self) -> str:
        return """
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-weight: bold;
                font-size: 12px;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
            }
            QPushButton:hover { background-color: #bdc3c7; }
            QPushButton:pressed { background-color: #7f8c8d; }
            QPushButton:disabled { background-color: #ecf0f1; color: #bdc3c7; }
        """

    def _update_ws_url_display(self):
        """Update the WebSocket URL display field."""
        host = self.ws_host.text().strip() or "127.0.0.1"
        port = self.ws_port.value()
        protocol = "wss" if "https" in host else "ws"
        self.ws_url_display.setText(f"{protocol}://{host}:{port}")

    # --- OpenCode Actions ---
    def _test_opencode_connection(self):
        """Test OpenCode Harness connection."""
        host = self.opencode_host.text().strip()
        port = self.opencode_port.value()
        api_key = self.opencode_api_key.text().strip()

        self.btn_test_opencode.setEnabled(False)
        self.btn_test_opencode.setText("🔄 Testing...")
        self.opencode_test_status.setText("Testing connection...")
        self.opencode_test_status.setStyleSheet("color: #f39c12;")

        # Test via bridge (which can proxy to OpenCode)
        import urllib.request
        import json

        def test_in_thread():
            try:
                url = f"http://{host}:{port}/health"
                req = urllib.request.Request(url, method="GET")
                if api_key:
                    req.add_header("Authorization", f"Bearer {api_key}")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode())
                        return True, f"Connected! Server: {data.get('server', 'OpenCode')}"
                    else:
                        return False, f"HTTP {resp.status}: {resp.reason}"
            except Exception as exc:
                return False, str(exc)

        import threading
        def run_test():
            success, msg = test_in_thread()
            QTimer.singleShot(0, lambda: self._on_opencode_test_result(success, msg))

        threading.Thread(target=run_test, daemon=True).start()

    def _on_opencode_test_result(self, success: bool, message: str):
        self.btn_test_opencode.setEnabled(True)
        self.btn_test_opencode.setText("🔍 Test OpenCode Connection")
        if success:
            self.opencode_test_status.setText(f"✅ {message}")
            self.opencode_test_status.setStyleSheet("color: #27ae60; font-weight: bold;")
            QMessageBox.information(self, "OpenCode Connection", f"✅ Success!\n{message}")
        else:
            self.opencode_test_status.setText(f"❌ {message}")
            self.opencode_test_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
            QMessageBox.warning(self, "OpenCode Connection Failed", f"❌ Connection failed:\n{message}")

    # --- Codex Actions ---
    def _validate_codex_json(self):
        """Validate Codex JSON configuration."""
        text = self.codex_config_text.toPlainText().strip()
        if not text:
            self.codex_validate_status.setText("❌ Configuration is empty")
            self.codex_validate_status.setStyleSheet("color: #e74c3c;")
            return

        try:
            import json
            config = json.loads(text)
            self.codex_validate_status.setText("✅ Valid JSON configuration")
            self.codex_validate_status.setStyleSheet("color: #27ae60; font-weight: bold;")
            QMessageBox.information(self, "JSON Valid", "✅ Codex configuration is valid JSON.")
        except json.JSONDecodeError as exc:
            self.codex_validate_status.setText(f"❌ Invalid JSON: {exc.msg} at line {exc.lineno}, col {exc.colno}")
            self.codex_validate_status.setStyleSheet("color: #e74c3c;")
            QMessageBox.warning(self, "Invalid JSON", f"❌ JSON parse error:\n{exc.msg}\nLine {exc.lineno}, Column {exc.colno}")

    def _load_codex_template(self, template: str):
        """Load a Codex configuration template."""
        templates = {
            "default": {
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 4096,
                "api_base": "https://api.openai.com/v1",
                "organization": "",
                "custom_headers": {}
            },
            "azure": {
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 4096,
                "api_base": "https://your-resource.openai.azure.com/openai/deployments/your-deployment",
                "api_version": "2024-02-15-preview",
                "api_key": "",
                "organization": "",
                "custom_headers": {
                    "api-key": "your-azure-api-key"
                }
            },
            "custom": {
                "model": "custom-model",
                "temperature": 0.5,
                "max_tokens": 8192,
                "api_base": "http://localhost:11434/v1",
                "organization": "",
                "custom_headers": {}
            }
        }

        import json
        config = templates.get(template, templates["default"])
        self.codex_config_text.setPlainText(json.dumps(config, indent=2))
        self.codex_validate_status.setText(f"Loaded '{template}' template")
        self.codex_validate_status.setStyleSheet("color: #3498db;")

    # --- MCP Server Actions ---
    def _add_mcp_server_dialog(self):
        """Show dialog to add a new MCP server."""
        dialog = MCPServerDialog(self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            server_config = dialog.get_config()
            self._add_mcp_server_to_table(server_config)
            self._save_mcp_servers_to_config()

    def _add_mcp_server_to_table(self, config: dict):
        """Add an MCP server configuration to the table."""
        row = self.mcp_table.rowCount()
        self.mcp_table.insertRow(row)

        # Name
        self.mcp_table.setItem(row, 0, QTableWidgetItem(config.get("name", "")))

        # Transport
        transport = config.get("transport", "stdio")
        transport_item = QTableWidgetItem(transport.upper())
        transport_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if transport == "stdio":
            transport_item.setBackground(QColor("#e8f5e9"))
        else:
            transport_item.setBackground(QColor("#e3f2fd"))
        self.mcp_table.setItem(row, 1, transport_item)

        # Command / URL
        if transport == "stdio":
            cmd_display = config.get("command", "")
            if config.get("args"):
                cmd_display += " " + " ".join(config["args"])
        else:
            cmd_display = config.get("url", "")
        self.mcp_table.setItem(row, 2, QTableWidgetItem(cmd_display))

        # Args / Headers
        if transport == "stdio":
            args_display = " ".join(config.get("args", []))
        else:
            import json
            headers = config.get("headers", {})
            args_display = json.dumps(headers) if headers else "{}"
        self.mcp_table.setItem(row, 3, QTableWidgetItem(args_display))

        # Status
        status_item = QTableWidgetItem("⏸ Not Tested")
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mcp_table.setItem(row, 4, status_item)

        # Actions
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(4, 2, 4, 2)
        action_layout.setSpacing(4)

        btn_test = QPushButton("🔍")
        btn_test.setToolTip("Test this server")
        btn_test.setMaximumWidth(32)
        btn_test.clicked.connect(lambda _, r=row: self._test_mcp_server_row(r))
        action_layout.addWidget(btn_test)

        btn_edit = QPushButton("✏️")
        btn_edit.setToolTip("Edit this server")
        btn_edit.setMaximumWidth(32)
        btn_edit.clicked.connect(lambda _, r=row: self._edit_mcp_server_row(r))
        action_layout.addWidget(btn_edit)

        btn_remove = QPushButton("🗑️")
        btn_remove.setToolTip("Remove this server")
        btn_remove.setMaximumWidth(32)
        btn_remove.setStyleSheet("color: #e74c3c;")
        btn_remove.clicked.connect(lambda _, r=row: self._remove_mcp_server_row(r))
        action_layout.addWidget(btn_remove)

        self.mcp_table.setCellWidget(row, 5, action_widget)

        # Store full config in row's user data
        self.mcp_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, config)

    def _edit_mcp_server_row(self, row: int):
        """Edit an MCP server configuration."""
        item = self.mcp_table.item(row, 0)
        if not item:
            return
        config = item.data(Qt.ItemDataRole.UserRole)
        if not config:
            return

        dialog = MCPServerDialog(self, config)
        if dialog.exec() == dialog.DialogCode.Accepted:
            new_config = dialog.get_config()
            # Update table
            self.mcp_table.item(row, 0).setText(new_config.get("name", ""))
            transport = new_config.get("transport", "stdio")
            transport_item = self.mcp_table.item(row, 1)
            transport_item.setText(transport.upper())
            if transport == "stdio":
                transport_item.setBackground(QColor("#e8f5e9"))
            else:
                transport_item.setBackground(QColor("#e3f2fd"))

            if transport == "stdio":
                cmd_display = new_config.get("command", "")
                if new_config.get("args"):
                    cmd_display += " " + " ".join(new_config["args"])
            else:
                cmd_display = new_config.get("url", "")
            self.mcp_table.item(row, 2).setText(cmd_display)

            if transport == "stdio":
                args_display = " ".join(new_config.get("args", []))
            else:
                import json
                headers = new_config.get("headers", {})
                args_display = json.dumps(headers) if headers else "{}"
            self.mcp_table.item(row, 3).setText(args_display)

            self.mcp_table.item(row, 4).setText("⏸ Not Tested")
            self.mcp_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, new_config)

            self._save_mcp_servers_to_config()

    def _remove_mcp_server_row(self, row: int):
        """Remove an MCP server from the table."""
        reply = QMessageBox.question(
            self, "Remove MCP Server",
            f"Remove server '{self.mcp_table.item(row, 0).text()}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.mcp_table.removeRow(row)
            self._save_mcp_servers_to_config()

    def _test_mcp_server_row(self, row: int):
        """Test a specific MCP server."""
        item = self.mcp_table.item(row, 0)
        if not item:
            return
        config = item.data(Qt.ItemDataRole.UserRole)
        if not config:
            return

        status_item = self.mcp_table.item(row, 4)
        status_item.setText("🔄 Testing...")
        status_item.setForeground(QColor("#f39c12"))

        # Test via bridge
        self._send_bridge_request("qgis.mcp.test_server", {"server": config},
            callback=lambda r, row=row: self._on_mcp_test_result(r, row))

    def _on_mcp_test_result(self, response: dict, row: int):
        result = response.get("result", {})
        status_item = self.mcp_table.item(row, 4)
        if result.get("status") == "connected":
            status_item.setText("✅ Connected")
            status_item.setForeground(QColor("#27ae60"))
            status_item.setFont(QFont("", -1, QFont.Weight.Bold))
        else:
            status_item.setText(f"❌ Failed")
            status_item.setForeground(QColor("#e74c3c"))
            status_item.setFont(QFont("", -1, QFont.Weight.Bold))
            error = result.get("error", "Unknown error")
            QMessageBox.warning(self, "MCP Test Failed", f"Server test failed:\n{error}")

    def _test_all_mcp_servers(self):
        """Test all MCP servers in the table."""
        for row in range(self.mcp_table.rowCount()):
            self._test_mcp_server_row(row)

    def _refresh_mcp_table(self):
        """Refresh MCP table from config."""
        self.mcp_table.setRowCount(0)
        self._load_mcp_servers_from_config()

    def _load_mcp_servers_from_config(self):
        """Load MCP servers from config into table."""
        if not hasattr(self, 'config') or self.config is None:
            return
        mcp_servers_json = self.config.get("mcp_servers", "[]")
        try:
            import json
            servers = json.loads(mcp_servers_json)
            for server in servers:
                self._add_mcp_server_to_table(server)
        except json.JSONDecodeError:
            pass

    def _save_mcp_servers_to_config(self):
        """Save MCP servers from table to config."""
        if not hasattr(self, 'config') or self.config is None:
            return
        servers = []
        for row in range(self.mcp_table.rowCount()):
            item = self.mcp_table.item(row, 0)
            if item:
                config = item.data(Qt.ItemDataRole.UserRole)
                if config:
                    servers.append(config)
        import json
        self.config.set("mcp_servers", json.dumps(servers))
        self.ai_connections_status.setText(f"Saved {len(servers)} MCP server(s) to config")

    # --- Bridge Actions ---
    def _test_bridge_connection_from_ai_tab(self):
        """Test bridge connection from AI Connections tab."""
        host = self.bridge_host.text().strip()
        port = self.bridge_port.value()
        token = self.bridge_auth_token.text().strip()

        # Update bridge client
        self.bridge_client.set_base_url(f"http://{host}:{port}")
        self.bridge_client.set_auth_token(token)

        self.btn_test_bridge.setEnabled(False)
        self.btn_test_bridge.setText("🔄 Testing...")
        self.bridge_test_status.setText("Testing connection...")
        self.bridge_test_status.setStyleSheet("color: #f39c12;")

        connected = self.bridge_client.health_check()

        self.btn_test_bridge.setEnabled(True)
        self.btn_test_bridge.setText("🔍 Test Bridge Connection")

        if connected:
            self.bridge_test_status.setText("✅ Connected")
            self.bridge_test_status.setStyleSheet("color: #27ae60; font-weight: bold;")
            QMessageBox.information(self, "Bridge Connection", "✅ Bridge connection successful!")
        else:
            self.bridge_test_status.setText("❌ Failed")
            self.bridge_test_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
            QMessageBox.warning(self, "Bridge Connection Failed", "❌ Bridge connection failed. Check if bridge server is running.")

    # --- WebSocket Actions ---
    def _test_websocket_connection(self):
        """Test WebSocket connection."""
        host = self.ws_host.text().strip()
        port = self.ws_port.value()

        self.btn_test_ws.setEnabled(False)
        self.btn_test_ws.setText("🔄 Testing...")
        self.ws_test_status.setText("Testing WebSocket...")
        self.ws_test_status.setStyleSheet("color: #f39c12;")

        # Try HTTP health check on WebSocket port (bridge often shares port)
        import urllib.request
        def test_ws():
            try:
                url = f"http://{host}:{port}/health"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=3) as resp:
                    return resp.status == 200, f"HTTP health check OK (status {resp.status})"
            except Exception as exc:
                return False, str(exc)

        import threading
        def run_test():
            success, msg = test_ws()
            QTimer.singleShot(0, lambda: self._on_ws_test_result(success, msg))

        threading.Thread(target=run_test, daemon=True).start()

    def _on_ws_test_result(self, success: bool, message: str):
        self.btn_test_ws.setEnabled(True)
        self.btn_test_ws.setText("🔍 Test WebSocket Connection")
        if success:
            self.ws_test_status.setText(f"✅ {message}")
            self.ws_test_status.setStyleSheet("color: #27ae60; font-weight: bold;")
            QMessageBox.information(self, "WebSocket Test", f"✅ Health check passed!\n{message}")
        else:
            self.ws_test_status.setText(f"❌ {message}")
            self.ws_test_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
            QMessageBox.warning(self, "WebSocket Test Failed", f"❌ Health check failed:\n{message}\n\nNote: WebSocket server may not have HTTP health endpoint.")

    # --- Save/Load All ---
    def _save_all_ai_connections(self):
        """Save all AI connection settings to config."""
        if not hasattr(self, 'config') or self.config is None:
            QMessageBox.warning(self, "Config Error", "Configuration system not available.")
            return

        try:
            # OpenCode
            self.config.set("opencode_enabled", self.opencode_enabled_cb.isChecked())
            self.config.set("opencode_host", self.opencode_host.text().strip())
            self.config.set("opencode_port", self.opencode_port.value())
            self.config.set("opencode_api_key", self.opencode_api_key.text().strip())

            # Codex
            self.config.set("codex_enabled", self.codex_enabled_cb.isChecked())
            self.config.set("codex_config_json", self.codex_config_text.toPlainText().strip())

            # MCP Servers
            self._save_mcp_servers_to_config()

            # Bridge
            self.config.set("bridge_host", self.bridge_host.text().strip())
            self.config.set("bridge_port", self.bridge_port.value())
            self.config.set("bridge_auth_token", self.bridge_auth_token.text().strip())
            self.config.set("mcp_stdio_enabled", self.mcp_stdio_enabled.isChecked())
            self.config.set("mcp_http_enabled", self.mcp_http_enabled.isChecked())
            self.config.set("mcp_http_port", self.mcp_http_port.value())

            # WebSocket
            self.config.set("ws_enabled", self.ws_enabled_cb.isChecked())
            self.config.set("ws_host", self.ws_host.text().strip())
            self.config.set("ws_port", self.ws_port.value())

            # Update bridge client
            self.bridge_client.set_base_url(f"http://{self.bridge_host.text().strip()}:{self.bridge_port.value()}")
            self.bridge_client.set_auth_token(self.bridge_auth_token.text().strip())
            self.ws_client.ws_url = f"ws://{self.ws_host.text().strip()}:{self.ws_port.value()}"

            self.ai_connections_status.setText("✅ All connections saved successfully!")
            self.ai_connections_status.setStyleSheet("color: #27ae60; font-weight: bold;")
            QMessageBox.information(self, "Saved", "✅ All AI connection settings saved successfully!")

        except Exception as exc:
            self.ai_connections_status.setText(f"❌ Save failed: {exc}")
            self.ai_connections_status.setStyleSheet("color: #e74c3c;")
            QMessageBox.critical(self, "Save Failed", f"Failed to save settings:\n{exc}")

    def _load_all_ai_connections(self):
        """Load all AI connection settings from config."""
        if not hasattr(self, 'config') or self.config is None:
            return

        try:
            # OpenCode
            self.opencode_enabled_cb.setChecked(self.config.get("opencode_enabled", True))
            self.opencode_host.setText(self.config.get("opencode_host", "127.0.0.1"))
            self.opencode_port.setValue(self.config.get("opencode_port", 8080))
            self.opencode_api_key.setText(self.config.get("opencode_api_key", ""))

            # Codex
            self.codex_enabled_cb.setChecked(self.config.get("codex_enabled", True))
            self.codex_config_text.setPlainText(self.config.get("codex_config_json", "{}"))

            # MCP Servers
            self._load_mcp_servers_from_config()

            # Bridge
            self.bridge_host.setText(self.config.get("bridge_host", "127.0.0.1"))
            self.bridge_port.setValue(self.config.get("bridge_port", 8765))
            self.bridge_auth_token.setText(self.config.get("bridge_auth_token", ""))
            self.mcp_stdio_enabled.setChecked(self.config.get("mcp_stdio_enabled", True))
            self.mcp_http_enabled.setChecked(self.config.get("mcp_http_enabled", True))
            self.mcp_http_port.setValue(self.config.get("mcp_http_port", 8766))

            # WebSocket
            self.ws_enabled_cb.setChecked(self.config.get("ws_enabled", True))
            self.ws_host.setText(self.config.get("ws_host", "127.0.0.1"))
            self.ws_port.setValue(self.config.get("ws_port", 8767))
            self._update_ws_url_display()

            # Update bridge client
            self.bridge_client.set_base_url(f"http://{self.bridge_host.text()}:{self.bridge_port.value()}")
            self.bridge_client.set_auth_token(self.bridge_auth_token.text())
            self.ws_client.ws_url = f"ws://{self.ws_host.text()}:{self.ws_port.value()}"

            self.ai_connections_status.setText("✅ Configuration loaded from config system")
            self.ai_connections_status.setStyleSheet("color: #27ae60;")

        except Exception as exc:
            self.ai_connections_status.setText(f"❌ Load failed: {exc}")
            self.ai_connections_status.setStyleSheet("color: #e74c3c;")

    # --- LLM Models Actions ---
    def _on_llm_provider_changed(self, index: int):
        """Handle provider selection change."""
        if index >= 0:
            provider_id = self.llm_provider_combo.itemData(index)
            if provider_id and provider_id in self._llm_config_pages:
                self.llm_config_stack.setCurrentWidget(self._llm_config_pages[provider_id])
                self._update_active_provider_label(provider_id)

    def _update_active_provider_label(self, provider_id: str):
        """Update the active provider indicator."""
        if not hasattr(self, 'config') or self.config is None:
            return
        active = self.config.get("llm_active_provider", "")
        if active == provider_id:
            self.llm_active_provider_label.setText(f"Active: {provider_id} ✓")
            self.llm_active_provider_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.llm_active_provider_label.setText(f"Active: {active or 'None'} (click Apply to activate)")
            self.llm_active_provider_label.setStyleSheet("color: #f39c12; font-weight: bold;")

    def _get_current_provider_page(self):
        """Get the current provider config page widget."""
        return self.llm_config_stack.currentWidget()

    def _get_provider_config_from_page(self, page, provider_id: str) -> dict:
        """Extract configuration from a provider page."""
        return {
            "api_key": getattr(page, f"api_key_{provider_id}", QLineEdit()).text().strip(),
            "base_url": getattr(page, f"base_url_{provider_id}", QLineEdit()).text().strip(),
            "model": getattr(page, f"model_combo_{provider_id}", QComboBox()).currentText().strip(),
            "temperature": getattr(page, f"temperature_{provider_id}", QDoubleSpinBox()).value(),
            "max_tokens": getattr(page, f"max_tokens_{provider_id}", QSpinBox()).value(),
            "top_p": getattr(page, f"top_p_{provider_id}", QDoubleSpinBox()).value(),
            "frequency_penalty": getattr(page, f"freq_penalty_{provider_id}", QDoubleSpinBox()).value(),
            "presence_penalty": getattr(page, f"pres_penalty_{provider_id}", QDoubleSpinBox()).value(),
            "system_prompt": getattr(page, f"system_prompt_{provider_id}", QTextEdit()).toPlainText().strip(),
        }

    def _set_provider_config_on_page(self, page, provider_id: str, config: dict):
        """Set configuration on a provider page."""
        api_key_edit = getattr(page, f"api_key_{provider_id}", None)
        if api_key_edit:
            api_key_edit.setText(config.get("api_key", ""))

        base_url_edit = getattr(page, f"base_url_{provider_id}", None)
        if base_url_edit:
            base_url_edit.setText(config.get("base_url", ""))

        model_combo = getattr(page, f"model_combo_{provider_id}", None)
        if model_combo:
            model_text = config.get("model", "")
            if model_text:
                index = model_combo.findText(model_text)
                if index >= 0:
                    model_combo.setCurrentIndex(index)
                else:
                    model_combo.setEditText(model_text)

        for key in ["temperature", "max_tokens", "top_p", "frequency_penalty", "presence_penalty"]:
            widget = getattr(page, f"{key}_{provider_id}", None)
            if widget:
                if isinstance(widget, QDoubleSpinBox):
                    widget.setValue(config.get(key, widget.value()))
                elif isinstance(widget, QSpinBox):
                    widget.setValue(config.get(key, widget.value()))

        system_prompt_edit = getattr(page, f"system_prompt_{provider_id}", None)
        if system_prompt_edit:
            system_prompt_edit.setPlainText(config.get("system_prompt", ""))

    def _fetch_llm_models(self, provider_id: str):
        """Fetch available models from the provider API."""
        if not LLM_PROVIDERS_AVAILABLE:
            QMessageBox.warning(self, "Not Available", "LLM Provider modules not installed.")
            return

        page = self._llm_config_pages.get(provider_id)
        if not page:
            return

        api_key = getattr(page, f"api_key_{provider_id}", QLineEdit()).text().strip()
        base_url = getattr(page, f"base_url_{provider_id}", QLineEdit()).text().strip()

        # Create temporary provider to fetch models
        try:
            from integrations.llm_providers import get_provider, LLMProviderConfig
            config = LLMProviderConfig(api_key=api_key, base_url=base_url or None)
            provider = get_provider(provider_id, config=config)

            self.llm_test_status.setText("🔄 Fetching models...")
            self.llm_test_status.setStyleSheet("color: #f39c12;")

            def fetch_in_thread():
                try:
                    models = provider.list_models()
                    model_names = [m.get("id", "") for m in models if m.get("id")]
                    QTimer.singleShot(0, lambda: self._on_models_fetched(provider_id, model_names))
                except Exception as exc:
                    QTimer.singleShot(0, lambda: self._on_models_fetch_error(str(exc)))

            import threading
            threading.Thread(target=fetch_in_thread, daemon=True).start()

        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Failed to create provider: {exc}")

    def _on_models_fetched(self, provider_id: str, model_names: list):
        """Handle fetched models."""
        page = self._llm_config_pages.get(provider_id)
        if page:
            model_combo = getattr(page, f"model_combo_{provider_id}", None)
            if model_combo:
                current = model_combo.currentText()
                model_combo.clear()
                model_combo.addItems(model_names)
                # Restore selection if possible
                index = model_combo.findText(current)
                if index >= 0:
                    model_combo.setCurrentIndex(index)
                elif model_names:
                    model_combo.setCurrentIndex(0)

        self.llm_test_status.setText(f"✅ Fetched {len(model_names)} models")
        self.llm_test_status.setStyleSheet("color: #27ae60; font-weight: bold;")

    def _on_models_fetch_error(self, error: str):
        """Handle model fetch error."""
        self.llm_test_status.setText(f"❌ Fetch failed: {error}")
        self.llm_test_status.setStyleSheet("color: #e74c3c;")
        QMessageBox.warning(self, "Fetch Failed", f"Failed to fetch models:\n{error}")

    def _test_llm_connection(self):
        """Test the current LLM provider connection."""
        if not LLM_PROVIDERS_AVAILABLE:
            QMessageBox.warning(self, "Not Available", "LLM Provider modules not installed.")
            return

        current_index = self.llm_provider_combo.currentIndex()
        if current_index < 0:
            QMessageBox.warning(self, "No Provider", "Please select a provider first.")
            return

        provider_id = self.llm_provider_combo.itemData(current_index)
        page = self._llm_config_pages.get(provider_id)
        if not page:
            return

        config_data = self._get_provider_config_from_page(page, provider_id)
        api_key = config_data.get("api_key", "")
        base_url = config_data.get("base_url", "")
        model = config_data.get("model", "")

        if not api_key and provider_id != "custom":
            QMessageBox.warning(self, "Missing API Key", "Please enter an API key before testing.")
            return

        try:
            from integrations.llm_providers import get_provider, LLMProviderConfig
            config = LLMProviderConfig(
                api_key=api_key,
                base_url=base_url or None,
                model=model,
                temperature=config_data.get("temperature", 0.7),
                max_tokens=config_data.get("max_tokens", 100),
            )
            provider = get_provider(provider_id, config=config)

            self.btn_test_llm.setEnabled(False)
            self.btn_test_llm.setText("🔄 Testing...")
            self.llm_test_status.setText("Testing connection...")
            self.llm_test_status.setStyleSheet("color: #f39c12;")

            def test_in_thread():
                success, message = provider.validate_key()
                QTimer.singleShot(0, lambda: self._on_llm_test_result(success, message))

            import threading
            threading.Thread(target=test_in_thread, daemon=True).start()

        except Exception as exc:
            self.btn_test_llm.setEnabled(True)
            self.btn_test_llm.setText("🔍 Test Connection")
            self.llm_test_status.setText(f"❌ Error: {exc}")
            self.llm_test_status.setStyleSheet("color: #e74c3c;")
            QMessageBox.warning(self, "Test Failed", f"Failed to test connection:\n{exc}")

    def _on_llm_test_result(self, success: bool, message: str):
        """Handle LLM connection test result."""
        self.btn_test_llm.setEnabled(True)
        self.btn_test_llm.setText("🔍 Test Connection")
        if success:
            self.llm_test_status.setText(f"✅ {message}")
            self.llm_test_status.setStyleSheet("color: #27ae60; font-weight: bold;")
            QMessageBox.information(self, "Connection Test", f"✅ Success!\n{message}")
        else:
            self.llm_test_status.setText(f"❌ {message}")
            self.llm_test_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
            QMessageBox.warning(self, "Connection Failed", f"❌ Connection failed:\n{message}")

    def _apply_llm_configuration(self):
        """Apply and save the LLM configuration."""
        if not hasattr(self, 'config') or self.config is None:
            QMessageBox.warning(self, "Config Error", "Configuration system not available.")
            return

        try:
            # Get current provider
            current_index = self.llm_provider_combo.currentIndex()
            if current_index < 0:
                QMessageBox.warning(self, "No Provider", "Please select a provider first.")
                return

            provider_id = self.llm_provider_combo.itemData(current_index)
            page = self._llm_config_pages.get(provider_id)

            # Save provider-specific config
            if page:
                provider_config = self._get_provider_config_from_page(page, provider_id)

                # Save to config (store as JSON per provider)
                providers_json = self.config.get("llm_providers", "{}")
                import json
                providers = json.loads(providers_json) if providers_json else {}
                providers[provider_id] = provider_config
                self.config.set("llm_providers", json.dumps(providers))

            # Save active provider
            self.config.set("llm_active_provider", provider_id)

            # Save global parameters
            self.config.set("llm_default_system_prompt", self.llm_global_system_prompt.toPlainText().strip())
            self.config.set("llm_temperature", self.llm_global_temperature.value())
            self.config.set("llm_max_tokens", self.llm_global_max_tokens.value())
            self.config.set("llm_top_p", self.llm_global_top_p.value())
            self.config.set("llm_stream_responses", self.llm_stream_responses.isChecked())
            self.config.set("llm_show_token_usage", self.llm_show_token_usage.isChecked())

            # Update active provider label
            self._update_active_provider_label(provider_id)

            self.ai_connections_status.setText("✅ LLM configuration saved successfully!")
            self.ai_connections_status.setStyleSheet("color: #27ae60; font-weight: bold;")
            QMessageBox.information(self, "Saved", "✅ LLM configuration saved successfully!")

        except Exception as exc:
            self.ai_connections_status.setText(f"❌ Save failed: {exc}")
            self.ai_connections_status.setStyleSheet("color: #e74c3c;")
            QMessageBox.critical(self, "Save Failed", f"Failed to save LLM configuration:\n{exc}")

    def _load_llm_configuration(self):
        """Load LLM configuration from config."""
        if not hasattr(self, 'config') or self.config is None:
            return

        try:
            # Load provider configs
            providers_json = self.config.get("llm_providers", "{}")
            import json
            providers = json.loads(providers_json) if providers_json else {}

            # Load each provider's config
            for provider_id, config in providers.items():
                page = self._llm_config_pages.get(provider_id)
                if page:
                    self._set_provider_config_on_page(page, provider_id, config)

            # Load active provider
            active_provider = self.config.get("llm_active_provider", "openai")
            # Set combo to active provider
            for i in range(self.llm_provider_combo.count()):
                if self.llm_provider_combo.itemData(i) == active_provider:
                    self.llm_provider_combo.setCurrentIndex(i)
                    break

            self._update_active_provider_label(active_provider)

            # Load global parameters
            self.llm_global_system_prompt.setPlainText(self.config.get("llm_default_system_prompt", 
                "You are an expert GIS analyst and QGIS automation specialist. Help users with spatial analysis, mapping, geoprocessing, and GIS workflows using the available tools."))
            self.llm_global_temperature.setValue(self.config.get("llm_temperature", 0.7))
            self.llm_global_max_tokens.setValue(self.config.get("llm_max_tokens", 4096))
            self.llm_global_top_p.setValue(self.config.get("llm_top_p", 1.0))
            self.llm_stream_responses.setChecked(self.config.get("llm_stream_responses", True))
            self.llm_show_token_usage.setChecked(self.config.get("llm_show_token_usage", True))

            # Load presets
            self._load_llm_presets_list()

            self.ai_connections_status.setText("✅ LLM configuration loaded")
            self.ai_connections_status.setStyleSheet("color: #27ae60;")

        except Exception as exc:
            self.ai_connections_status.setText(f"❌ Load failed: {exc}")
            self.ai_connections_status.setStyleSheet("color: #e74c3c;")

    def _save_llm_preset(self):
        """Save current configuration as a preset."""
        if not hasattr(self, 'config') or self.config is None:
            return

        from qgis.PyQt.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return

        try:
            # Gather current configuration
            current_index = self.llm_provider_combo.currentIndex()
            if current_index < 0:
                return
            provider_id = self.llm_provider_combo.itemData(current_index)
            page = self._llm_config_pages.get(provider_id)

            preset = {
                "name": name.strip(),
                "provider_id": provider_id,
                "provider_config": self._get_provider_config_from_page(page, provider_id) if page else {},
                "global_system_prompt": self.llm_global_system_prompt.toPlainText().strip(),
                "temperature": self.llm_global_temperature.value(),
                "max_tokens": self.llm_global_max_tokens.value(),
                "top_p": self.llm_global_top_p.value(),
                "stream_responses": self.llm_stream_responses.isChecked(),
                "show_token_usage": self.llm_show_token_usage.isChecked(),
                "created_at": datetime.now().isoformat(),
            }

            presets_json = self.config.get("llm_model_presets", "{}")
            presets = json.loads(presets_json) if presets_json else {}
            presets[name.strip()] = preset
            self.config.set("llm_model_presets", json.dumps(presets))

            self._load_llm_presets_list()
            QMessageBox.information(self, "Saved", f"Preset '{name}' saved successfully!")

        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", f"Failed to save preset:\n{exc}")

    def _load_llm_presets_list(self):
        """Load presets into the combo box."""
        if not hasattr(self, 'config') or self.config is None:
            return

        try:
            presets_json = self.config.get("llm_model_presets", "{}")
            presets = json.loads(presets_json) if presets_json else {}

            self.llm_presets_combo.blockSignals(True)
            self.llm_presets_combo.clear()
            self.llm_presets_combo.addItem("Select a preset...", "")
            for name, preset in presets.items():
                self.llm_presets_combo.addItem(f"{name} ({preset.get('provider_id', '')})", name)
            self.llm_presets_combo.blockSignals(False)

            # Connect selection change
            try:
                self.llm_presets_combo.currentIndexChanged.disconnect()
            except:
                pass
            self.llm_presets_combo.currentIndexChanged.connect(self._on_llm_preset_selected)

        except Exception:
            pass

    def _on_llm_preset_selected(self, index: int):
        """Handle preset selection."""
        if index <= 0:
            return

        preset_name = self.llm_presets_combo.itemData(index)
        if not preset_name:
            return

        if not hasattr(self, 'config') or self.config is None:
            return

        try:
            presets_json = self.config.get("llm_model_presets", "{}")
            presets = json.loads(presets_json) if presets_json else {}
            preset = presets.get(preset_name)
            if not preset:
                return

            # Apply preset
            provider_id = preset.get("provider_id", "openai")
            # Set provider combo
            for i in range(self.llm_provider_combo.count()):
                if self.llm_provider_combo.itemData(i) == provider_id:
                    self.llm_provider_combo.setCurrentIndex(i)
                    break

            # Apply provider config
            page = self._llm_config_pages.get(provider_id)
            if page:
                provider_config = preset.get("provider_config", {})
                self._set_provider_config_on_page(page, provider_id, provider_config)

            # Apply global settings
            self.llm_global_system_prompt.setPlainText(preset.get("global_system_prompt", ""))
            self.llm_global_temperature.setValue(preset.get("temperature", 0.7))
            self.llm_global_max_tokens.setValue(preset.get("max_tokens", 4096))
            self.llm_global_top_p.setValue(preset.get("top_p", 1.0))
            self.llm_stream_responses.setChecked(preset.get("stream_responses", True))
            self.llm_show_token_usage.setChecked(preset.get("show_token_usage", True))

            QMessageBox.information(self, "Loaded", f"Preset '{preset_name}' loaded!")

        except Exception as exc:
            QMessageBox.warning(self, "Load Failed", f"Failed to load preset:\n{exc}")

    def _load_llm_preset(self):
        """Load a preset (triggered by button)."""
        # This just ensures the combo box is focused
        self.llm_presets_combo.showPopup()

    def _delete_llm_preset(self):
        """Delete selected preset."""
        index = self.llm_presets_combo.currentIndex()
        if index <= 0:
            QMessageBox.warning(self, "No Preset", "Please select a preset to delete.")
            return

        preset_name = self.llm_presets_combo.itemData(index)
        if not preset_name:
            return

        reply = QMessageBox.question(
            self, "Delete Preset",
            f"Delete preset '{preset_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if not hasattr(self, 'config') or self.config is None:
                return
            try:
                presets_json = self.config.get("llm_model_presets", "{}")
                presets = json.loads(presets_json) if presets_json else {}
                if preset_name in presets:
                    del presets[preset_name]
                    self.config.set("llm_model_presets", json.dumps(presets))
                    self._load_llm_presets_list()
                    QMessageBox.information(self, "Deleted", f"Preset '{preset_name}' deleted.")
            except Exception as exc:
                QMessageBox.warning(self, "Delete Failed", f"Failed to delete preset:\n{exc}")

    # --- Version Info Actions ---
    def _refresh_version_info(self):
        """Refresh version control information."""
        try:
            import subprocess
            import sys
            import platform
            from qgis.PyQt.QtCore import QSysInfo
            from qgis.core import Qgis

            # App version from config
            app_version = "1.0.0"
            git_hash = "unknown"
            if hasattr(self, 'config') and self.config:
                app_version = self.config.get("app_version", "1.0.0")
                self.version_app_version.setText(app_version)

            # Git info
            try:
                # Get git commit hash
                result = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    capture_output=True, text=True, timeout=3,
                    cwd=r"D:\1 2 3 QGIS\Universal-AI-GIS-Studio"
                )
                if result.returncode == 0:
                    git_hash = result.stdout.strip()
                    self.version_git_hash.setText(git_hash)
                else:
                    self.version_git_hash.setText("Not a git repo")

                # Get git branch
                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, text=True, timeout=3,
                    cwd=r"D:\1 2 3 QGIS\Universal-AI-GIS-Studio"
                )
                if result.returncode == 0:
                    self.version_git_branch.setText(result.stdout.strip())
                else:
                    self.version_git_branch.setText("Unknown")

                # Get latest tag
                result = subprocess.run(
                    ["git", "describe", "--tags", "--always"],
                    capture_output=True, text=True, timeout=3,
                    cwd=r"D:\1 2 3 QGIS\Universal-AI-GIS-Studio"
                )
                if result.returncode == 0:
                    self.version_git_tag.setText(result.stdout.strip())
                else:
                    self.version_git_tag.setText("No tags")

            except Exception:
                self.version_git_hash.setText("Git not available")
                self.version_git_branch.setText("Git not available")
                self.version_git_tag.setText("Git not available")

            # Build date from config or file
            if hasattr(self, 'config') and self.config:
                build_date = self.config.get("build_date", "")
                build_number = self.config.get("build_number", "")
                if build_date:
                    self.version_build_date.setText(build_date)
                else:
                    self.version_build_date.setText("Not set")
                if build_number:
                    self.version_build_number.setText(build_number)
                else:
                    self.version_build_number.setText("Not set")

            # QGIS version
            self.version_qgis_version.setText(f"{Qgis.QGIS_VERSION} ({Qgis.QGIS_RELEASE_NAME})")

            # Python version
            self.version_python_version.setText(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

            # PyQt version
            from qgis.PyQt.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
            self.version_pyqt_version.setText(f"Qt {QT_VERSION_STR}, PyQt {PYQT_VERSION_STR}")

            # Runtime info
            self.runtime_os.setText(f"{platform.system()} {platform.release()}")
            self.runtime_platform.setText(platform.platform())
            self.runtime_arch.setText(platform.machine())

            # Data directory
            from core.config import default_data_dir
            self.runtime_data_dir.setText(default_data_dir())

            # Update toolbar version label
            if hasattr(self, 'version_label'):
                self.version_label.setText(f"v{app_version} ({git_hash[:8] if git_hash != 'unknown' else 'dev'})")
                self.version_label.setToolTip(f"Version: {app_version}\nGit: {git_hash}\nClick for details")

        except Exception as exc:
            QMessageBox.warning(self, "Version Info", f"Failed to load version info: {exc}")

    def _panel_api_providers(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("API Providers — OpenAI, Gemini, Anthropic, OpenRouter"))
        form = QFormLayout()
        self.api_provider = QLineEdit()
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Provider:", self.api_provider)
        form.addRow("API Key:", self.api_key)
        layout.addLayout(form)
        btn = QPushButton("Save Provider")
        btn.clicked.connect(self._save_api_provider)
        layout.addWidget(btn)
        return w

    def _panel_mcp_manager(self):
        """MCP Manager panel - comprehensive MCP server management."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("MCP Manager — Manage external MCP servers and tool trust levels"))
        
        # Server list
        self.mcp_mgr_table = QTableWidget(0, 5)
        self.mcp_mgr_table.setHorizontalHeaderLabels(["Name", "Transport", "Command/URL", "Status", "Actions"])
        self.mcp_mgr_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.mcp_mgr_table)
        
        btn_row = QHBoxLayout()
        btn_add = QPushButton("➕ Add MCP Server")
        btn_add.clicked.connect(self._mcp_mgr_add_server)
        btn_row.addWidget(btn_add)
        
        btn_test_all = QPushButton("🔍 Test All")
        btn_test_all.clicked.connect(self._mcp_mgr_test_all)
        btn_row.addWidget(btn_test_all)
        
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self._mcp_mgr_refresh)
        btn_row.addWidget(btn_refresh)
        
        btn_row.addStretch()
        layout.addLayout(btn_row)
        
        # Load existing servers
        QTimer.singleShot(100, self._mcp_mgr_refresh)
        
        return w

    def _panel_agent_manager(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Agent Manager — 29 Built-in Agents"))
        
        # Filter
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self.agent_filter = QLineEdit()
        self.agent_filter.setPlaceholderText("Search agents...")
        self.agent_filter.textChanged.connect(self._filter_agents)
        filter_row.addWidget(self.agent_filter)
        filter_row.addStretch()
        layout.addLayout(filter_row)
        
        self.agent_table = QTableWidget(0, 4)
        self.agent_table.setHorizontalHeaderLabels(["Agent ID", "Name", "Category", "Action"])
        self.agent_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.agent_table)
        
        btn_refresh = QPushButton("Refresh Agents")
        btn_refresh.clicked.connect(self._refresh_agents)
        layout.addWidget(btn_refresh)
        
        return w

    def _panel_skill_manager(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Skill Manager — Import & Validate Skills"))
        
        # Skill list
        self.skill_table = QTableWidget(0, 4)
        self.skill_table.setHorizontalHeaderLabels(["Skill ID", "Name", "Version", "Actions"])
        self.skill_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.skill_table)
        
        btn_row = QHBoxLayout()
        btn_import = QPushButton("📥 Import Skill")
        btn_import.clicked.connect(self._import_skill)
        btn_row.addWidget(btn_import)
        
        btn_validate = QPushButton("✅ Validate All")
        btn_validate.clicked.connect(self._validate_skills)
        btn_row.addWidget(btn_validate)
        
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self._refresh_skills)
        btn_row.addWidget(btn_refresh)
        
        btn_row.addStretch()
        layout.addLayout(btn_row)
        
        return w

    def _filter_agents(self, text: str):
        """Filter agent table by search text."""
        for row in range(self.agent_table.rowCount()):
            match = False
            for col in range(self.agent_table.columnCount()):
                item = self.agent_table.item(row, col)
                if item and text.lower() in item.text().lower():
                    match = True
                    break
            self.agent_table.setRowHidden(row, not match)

    # ------------------------------------------------------------------ #
    # MCP Manager Handlers
    # ------------------------------------------------------------------ #
    def _mcp_mgr_add_server(self):
        """Add MCP server via dialog."""
        # Reuse the MCPServerDialog from AI Connections
        dialog = MCPServerDialog(self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            server_config = dialog.get_config()
            self._mcp_mgr_add_server_to_table(server_config)
            self._save_mcp_servers_to_config()

    def _mcp_mgr_add_server_to_table(self, config: dict):
        """Add an MCP server configuration to the table."""
        row = self.mcp_mgr_table.rowCount()
        self.mcp_mgr_table.insertRow(row)

        self.mcp_mgr_table.setItem(row, 0, QTableWidgetItem(config.get("name", "")))
        
        transport = config.get("transport", "stdio")
        transport_item = QTableWidgetItem(transport.upper())
        transport_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        if transport == "stdio":
            transport_item.setBackground(QColor("#e8f5e9"))
        else:
            transport_item.setBackground(QColor("#e3f2fd"))
        self.mcp_mgr_table.setItem(row, 1, transport_item)

        if transport == "stdio":
            cmd_display = config.get("command", "")
            if config.get("args"):
                cmd_display += " " + " ".join(config["args"])
        else:
            cmd_display = config.get("url", "")
        self.mcp_mgr_table.setItem(row, 2, QTableWidgetItem(cmd_display))

        status_item = QTableWidgetItem("⏸ Not Tested")
        status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mcp_mgr_table.setItem(row, 3, status_item)

        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(4, 2, 4, 2)
        action_layout.setSpacing(4)

        btn_test = QPushButton("🔍")
        btn_test.setToolTip("Test this server")
        btn_test.setMaximumWidth(32)
        btn_test.clicked.connect(lambda _, r=row: self._mcp_mgr_test_server_row(r))
        action_layout.addWidget(btn_test)

        btn_remove = QPushButton("🗑️")
        btn_remove.setToolTip("Remove this server")
        btn_remove.setMaximumWidth(32)
        btn_remove.setStyleSheet("color: #e74c3c;")
        btn_remove.clicked.connect(lambda _, r=row: self._mcp_mgr_remove_server_row(r))
        action_layout.addWidget(btn_remove)

        self.mcp_mgr_table.setCellWidget(row, 4, action_widget)
        self.mcp_mgr_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, config)

    def _mcp_mgr_test_server_row(self, row: int):
        """Test a specific MCP server."""
        item = self.mcp_mgr_table.item(row, 0)
        if not item:
            return
        config = item.data(Qt.ItemDataRole.UserRole)
        if not config:
            return

        status_item = self.mcp_mgr_table.item(row, 3)
        status_item.setText("🔄 Testing...")
        status_item.setForeground(QColor("#f39c12"))

        self._send_bridge_request("qgis.mcp.test_server", {"server": config},
            callback=lambda r, row=row: self._mcp_mgr_on_test_result(r, row))

    def _mcp_mgr_on_test_result(self, response: dict, row: int):
        result = response.get("result", {})
        status_item = self.mcp_mgr_table.item(row, 3)
        if result.get("status") == "connected":
            status_item.setText("✅ Connected")
            status_item.setForeground(QColor("#27ae60"))
            status_item.setFont(QFont("", -1, QFont.Weight.Bold))
        else:
            status_item.setText("❌ Failed")
            status_item.setForeground(QColor("#e74c3c"))
            status_item.setFont(QFont("", -1, QFont.Weight.Bold))
            error = result.get("error", "Unknown error")
            QMessageBox.warning(self, "MCP Test Failed", f"Server test failed:\n{error}")

    def _mcp_mgr_test_all(self):
        """Test all MCP servers in the table."""
        for row in range(self.mcp_mgr_table.rowCount()):
            self._mcp_mgr_test_server_row(row)

    def _mcp_mgr_remove_server_row(self, row: int):
        """Remove an MCP server from the table."""
        reply = QMessageBox.question(
            self, "Remove MCP Server",
            f"Remove server '{self.mcp_mgr_table.item(row, 0).text()}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.mcp_mgr_table.removeRow(row)
            self._save_mcp_servers_to_config()

    def _mcp_mgr_refresh(self):
        """Refresh MCP table from config."""
        self.mcp_mgr_table.setRowCount(0)
        self._load_mcp_servers_from_config()

    # ------------------------------------------------------------------ #
    # Skill Manager Handlers
    # ------------------------------------------------------------------ #
    def _refresh_skills(self):
        """Refresh skill list from bridge."""
        self._send_bridge_request("qgis.skills.list", {},
            callback=self._on_skills_list_response)

    def _on_skills_list_response(self, response: dict):
        result = response.get("result", {})
        skills = result.get("skills", [])
        self.skill_table.setRowCount(len(skills))
        for row, skill in enumerate(skills):
            self.skill_table.setItem(row, 0, QTableWidgetItem(skill.get("id", "")))
            self.skill_table.setItem(row, 1, QTableWidgetItem(skill.get("name", "")))
            self.skill_table.setItem(row, 2, QTableWidgetItem(skill.get("version", "")))
            btn = QPushButton("Run")
            btn.setMaximumWidth(60)
            btn.clicked.connect(lambda _, sid=skill.get("id"): self._run_skill(sid))
            self.skill_table.setCellWidget(row, 3, btn)

    def _run_skill(self, skill_id: str):
        self._send_bridge_request("qgis.skills.run", {"skill_id": skill_id},
            callback=lambda r: QMessageBox.information(self, "Skill Run", f"Skill {skill_id} started"))

    # ------------------------------------------------------------------ #
    # Task History Handlers
    # ------------------------------------------------------------------ #
    def _refresh_task_history(self):
        """Refresh task history."""
        self._send_bridge_request("qgis.jobs.history", {},
            callback=self._on_task_history_response)

    def _on_task_history_response(self, response: dict):
        result = response.get("result", {})
        jobs = result.get("jobs", [])
        text = f"Task History ({len(jobs)} jobs):\n\n"
        for job in jobs[:100]:
            text += f"[{job.get('created_at', '')}] {job.get('tool_id', '')} - {job.get('status', '')}\n"
        self.history_output.setText(text)

    # ------------------------------------------------------------------ #
    # Security Panel Handlers
    # ------------------------------------------------------------------ #
    def _refresh_security_audit(self):
        """Refresh security audit log."""
        self._send_bridge_request("qgis.security.audit_log", {},
            callback=self._on_security_audit_response)

    def _on_security_audit_response(self, response: dict):
        result = response.get("result", {})
        logs = result.get("logs", [])
        text = f"Security Audit Log ({len(logs)} entries):\n\n"
        for log in logs:
            text += f"[{log.get('timestamp', '')}] {log.get('event', '')}: {log.get('details', '')}\n"
        self.audit_output.setText(text)

    # ------------------------------------------------------------------ #
    # Settings Panel Handlers
    # ------------------------------------------------------------------ #
    def _load_settings(self):
        """Load settings into the settings panel."""
        if hasattr(self, 'config') and self.config:
            self.bridge_url.setText(self.config.get("bridge_host", "http://127.0.0.1:8765"))
            self.bridge_token.setText(self.config.get("bridge_auth_token", ""))
            ws_port = self.config.get("ws_port", 8767)
            ws_host = self.config.get("ws_host", "127.0.0.1")
            self.ws_url.setText(f"ws://{ws_host}:{ws_port}")
        btn_import = QPushButton("Import Skill")
        btn_import.clicked.connect(self._import_skill)
        layout.addWidget(btn_import)
        btn_validate = QPushButton("Validate Skills")
        btn_validate.clicked.connect(self._validate_skills)
        layout.addWidget(btn_validate)
        return w

    def _panel_gis_clusters(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("GIS Clusters — M01 to M25"))
        self.cluster_table = QTableWidget(0, 3)
        self.cluster_table.setHorizontalHeaderLabels(["Cluster ID", "Name", "Action"])
        self.cluster_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.cluster_table)
        btn_refresh = QPushButton("Refresh Clusters")
        btn_refresh.clicked.connect(self._refresh_clusters)
        layout.addWidget(btn_refresh)
        return w

    def _panel_georeferencing(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Georeferencing — Auto georeference scanned maps using CV and GCP"))
        
        # Image selection
        form = QFormLayout()
        self.georef_image = QLineEdit()
        self.georef_image.setPlaceholderText("Path to scanned map image")
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(lambda: self._browse_file(self.georef_image))
        file_layout = QHBoxLayout()
        file_layout.addWidget(self.georef_image)
        file_layout.addWidget(btn_browse)
        form.addRow("Image:", file_layout)
        
        self.georef_reference = QLineEdit()
        self.georef_reference.setPlaceholderText("Reference layer ID or WMS URL")
        form.addRow("Reference:", self.georef_reference)
        
        self.georef_gcp_method = QComboBox()
        self.georef_gcp_method.addItems(["Auto-detect", "Manual GCP", "CV Feature Matching"])
        form.addRow("GCP Method:", self.georef_gcp_method)
        
        layout.addLayout(form)
        
        btn_analyze = QPushButton("🔍 Analyze Image")
        btn_analyze.clicked.connect(self._georef_analyze)
        layout.addWidget(btn_analyze)
        
        btn_georef = QPushButton("🗺 Run Georeferencing")
        btn_georef.clicked.connect(self._georef_run)
        layout.addWidget(btn_georef)
        
        self.georef_output = QTextEdit()
        self.georef_output.setReadOnly(True)
        self.georef_output.setMaximumHeight(200)
        layout.addWidget(self.georef_output)
        
        return w

    def _panel_gcp_intelligence(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("GCP Intelligence — Generate, validate, and optimize Ground Control Points"))
        
        form = QFormLayout()
        self.gcp_image = QLineEdit()
        self.gcp_image.setPlaceholderText("Path to image for GCP generation")
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(lambda: self._browse_file(self.gcp_image))
        file_layout = QHBoxLayout()
        file_layout.addWidget(self.gcp_image)
        file_layout.addWidget(btn_browse)
        form.addRow("Image:", file_layout)
        
        self.gcp_reference = QLineEdit()
        self.gcp_reference.setPlaceholderText("Reference data source (layer, WMS, etc.)")
        form.addRow("Reference:", self.gcp_reference)
        
        self.gcp_count = QSpinBox()
        self.gcp_count.setRange(4, 100)
        self.gcp_count.setValue(10)
        form.addRow("Target GCP Count:", self.gcp_count)
        
        layout.addLayout(form)
        
        btn_generate = QPushButton("🎯 Generate GCPs")
        btn_generate.clicked.connect(self._gcp_generate)
        layout.addWidget(btn_generate)
        
        btn_validate = QPushButton("✅ Validate GCPs")
        btn_validate.clicked.connect(self._gcp_validate)
        layout.addWidget(btn_validate)
        
        btn_optimize = QPushButton("📐 Optimize GCPs (RMSE)")
        btn_optimize.clicked.connect(self._gcp_optimize)
        layout.addWidget(btn_optimize)
        
        self.gcp_output = QTextEdit()
        self.gcp_output.setReadOnly(True)
        self.gcp_output.setMaximumHeight(200)
        layout.addWidget(self.gcp_output)
        
        return w

    def _panel_workflow_builder(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Workflow Builder — Create and execute GIS workflows visually"))
        
        # Workflow name
        form = QFormLayout()
        self.workflow_name = QLineEdit()
        self.workflow_name.setPlaceholderText("My Workflow")
        form.addRow("Name:", self.workflow_name)
        
        self.workflow_desc = QLineEdit()
        self.workflow_desc.setPlaceholderText("Description...")
        form.addRow("Description:", self.workflow_desc)
        
        layout.addLayout(form)
        
        # Steps list
        self.workflow_steps = QTableWidget(0, 4)
        self.workflow_steps.setHorizontalHeaderLabels(["Step", "Tool", "Parameters", "Actions"])
        self.workflow_steps.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.workflow_steps)
        
        btn_row = QHBoxLayout()
        btn_add_step = QPushButton("➕ Add Step")
        btn_add_step.clicked.connect(self._workflow_add_step)
        btn_row.addWidget(btn_add_step)
        
        btn_remove_step = QPushButton("➖ Remove Step")
        btn_remove_step.clicked.connect(self._workflow_remove_step)
        btn_row.addWidget(btn_remove_step)
        
        btn_row.addStretch()
        layout.addLayout(btn_row)
        
        btn_run = QPushButton("▶ Run Workflow")
        btn_run.clicked.connect(self._workflow_run)
        layout.addWidget(btn_run)
        
        self.workflow_output = QTextEdit()
        self.workflow_output.setReadOnly(True)
        self.workflow_output.setMaximumHeight(150)
        layout.addWidget(self.workflow_output)
        
        return w

    def _panel_algorithm_discovery(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Algorithm Discovery — QGIS Processing Algorithms"))
        btn_discover = QPushButton("Discover Algorithms")
        btn_discover.clicked.connect(self._discover_algorithms)
        layout.addWidget(btn_discover)
        self.algo_output = QTextEdit()
        self.algo_output.setReadOnly(True)
        self.algo_output.setMaximumHeight(200)
        layout.addWidget(self.algo_output)
        return w

    def _panel_data_manager(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Data Manager — Load, inspect, and remove GIS data layers"))
        
        # Load layer
        form = QFormLayout()
        self.dm_layer_path = QLineEdit()
        self.dm_layer_path.setPlaceholderText("Path to layer file")
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(lambda: self._browse_file(self.dm_layer_path))
        file_layout = QHBoxLayout()
        file_layout.addWidget(self.dm_layer_path)
        file_layout.addWidget(btn_browse)
        form.addRow("File:", file_layout)
        
        self.dm_layer_name = QLineEdit()
        self.dm_layer_name.setPlaceholderText("Optional layer name")
        form.addRow("Name:", self.dm_layer_name)
        
        self.dm_provider = QComboBox()
        self.dm_provider.addItems(["Auto", "Vector", "Raster"])
        form.addRow("Provider:", self.dm_provider)
        
        layout.addLayout(form)
        
        btn_load = QPushButton("📥 Load Layer")
        btn_load.clicked.connect(self._dm_load_layer)
        layout.addWidget(btn_load)
        
        # Layer list
        layout.addWidget(QLabel("Loaded Layers:"))
        self.dm_layers = QTableWidget(0, 4)
        self.dm_layers.setHorizontalHeaderLabels(["ID", "Name", "Type", "Actions"])
        self.dm_layers.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.dm_layers)
        
        btn_refresh = QPushButton("🔄 Refresh Layers")
        btn_refresh.clicked.connect(self._dm_refresh_layers)
        layout.addWidget(btn_refresh)
        
        return w

    def _panel_quality_control(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Quality Control — Validate geometry, topology, and data quality"))
        
        # Layer selection
        form = QFormLayout()
        self.qc_layer = QComboBox()
        self.qc_layer.setEditable(True)
        form.addRow("Layer:", self.qc_layer)
        
        self.qc_checks = QComboBox()
        self.qc_checks.addItems([
            "All Checks",
            "Geometry Validity",
            "Topology (Gaps/Overlaps)",
            "Duplicate Geometries",
            "Self-Intersections",
            "Attribute Rules",
            "Completeness",
            "Consistency"
        ])
        form.addRow("Check Type:", self.qc_checks)
        
        layout.addLayout(form)
        
        btn_run = QPushButton("🔍 Run Quality Check")
        btn_run.clicked.connect(self._qc_run_check)
        layout.addWidget(btn_run)
        
        self.qc_output = QTextEdit()
        self.qc_output.setReadOnly(True)
        layout.addWidget(self.qc_output)
        
        return w

    def _panel_task_history(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Task History — Job Execution Log"))
        
        btn_refresh = QPushButton("🔄 Refresh History")
        btn_refresh.clicked.connect(self._refresh_task_history)
        layout.addWidget(btn_refresh)
        
        self.history_output = QTextEdit()
        self.history_output.setReadOnly(True)
        self.history_output.setFont(QFont("Consolas", 9))
        layout.addWidget(self.history_output)
        
        # Load on show
        QTimer.singleShot(100, self._refresh_task_history)
        
        return w

    def _panel_security(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Security — Permissions, Approvals, and Audit Logs"))
        
        btn_refresh_audit = QPushButton("🔄 Refresh Audit Log")
        btn_refresh_audit.clicked.connect(self._refresh_security_audit)
        layout.addWidget(btn_refresh_audit)
        
        self.audit_output = QTextEdit()
        self.audit_output.setReadOnly(True)
        self.audit_output.setFont(QFont("Consolas", 9))
        layout.addWidget(self.audit_output)
        
        # Load on show
        QTimer.singleShot(100, self._refresh_security_audit)
        
        return w

    def _panel_settings(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Settings — Bridge & Connection Configuration"))
        form = QFormLayout()

        # Default values
        bridge_host = "127.0.0.1"
        bridge_port = 8765
        bridge_token = ""
        ws_host = "127.0.0.1"
        ws_port = 8767

        if hasattr(self, 'config') and self.config:
            bridge_host = self.config.get("bridge_host", "127.0.0.1")
            bridge_port = self.config.get("bridge_port", 8765)
            bridge_token = self.config.get("bridge_auth_token", "")
            ws_host = self.config.get("ws_host", "127.0.0.1")
            ws_port = self.config.get("ws_port", 8767)

        self.settings_bridge_host = QLineEdit(bridge_host)
        self.settings_bridge_host.setPlaceholderText("Bridge server host")
        self.settings_bridge_host.setMinimumWidth(300)
        form.addRow("Bridge Host:", self.settings_bridge_host)

        self.settings_bridge_port = QSpinBox()
        self.settings_bridge_port.setRange(1, 65535)
        self.settings_bridge_port.setValue(bridge_port)
        self.settings_bridge_port.setMinimumWidth(150)
        form.addRow("Bridge Port:", self.settings_bridge_port)

        self.settings_bridge_token = QLineEdit(bridge_token)
        self.settings_bridge_token.setPlaceholderText("Authentication token (optional)")
        self.settings_bridge_token.setEchoMode(QLineEdit.EchoMode.Password)
        self.settings_bridge_token.setMinimumWidth(300)
        form.addRow("Auth Token:", self.settings_bridge_token)

        self.settings_bridge_show_token = QCheckBox("Show Token")
        self.settings_bridge_show_token.toggled.connect(
            lambda checked: self.settings_bridge_token.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        form.addRow("", self.settings_bridge_show_token)

        # WebSocket settings
        self.settings_ws_host = QLineEdit(ws_host)
        self.settings_ws_host.setPlaceholderText("WebSocket server host")
        self.settings_ws_host.setMinimumWidth(300)
        form.addRow("WebSocket Host:", self.settings_ws_host)

        self.settings_ws_port = QSpinBox()
        self.settings_ws_port.setRange(1, 65535)
        self.settings_ws_port.setValue(ws_port)
        self.settings_ws_port.setMinimumWidth(150)
        form.addRow("WebSocket Port:", self.settings_ws_port)

        layout.addLayout(form)
        btn = QPushButton("Save Settings")
        btn.clicked.connect(self._save_settings)
        layout.addWidget(btn)
        layout.addStretch()
        return w

    def _panel_macro_verification(self):
        """Macro Recorder & Visual Verification panel."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("Macro Recorder & Visual Verification"))

        # --- Macro Recorder Section ---
        macro_group = QGroupBox("🎬 Macro Recorder")
        macro_layout = QVBoxLayout()

        # Macro name and description
        form = QFormLayout()
        self.macro_name = QLineEdit()
        self.macro_name.setPlaceholderText("My Macro")
        self.macro_description = QLineEdit()
        self.macro_description.setPlaceholderText("Description...")
        form.addRow("Name:", self.macro_name)
        form.addRow("Description:", self.macro_description)
        macro_layout.addLayout(form)

        # Recording controls
        rec_controls = QHBoxLayout()
        self.btn_macro_record = QPushButton("⏺ Start Recording")
        self.btn_macro_record.clicked.connect(self._macro_start_recording)
        self.btn_macro_record.setStyleSheet("background-color: #ff4444; color: white; font-weight: bold;")
        rec_controls.addWidget(self.btn_macro_record)

        self.btn_macro_stop = QPushButton("⏹ Stop Recording")
        self.btn_macro_stop.clicked.connect(self._macro_stop_recording)
        self.btn_macro_stop.setEnabled(False)
        rec_controls.addWidget(self.btn_macro_stop)

        self.btn_macro_save = QPushButton("💾 Save Macro")
        self.btn_macro_save.clicked.connect(self._macro_save)
        rec_controls.addWidget(self.btn_macro_save)

        rec_controls.addStretch()
        macro_layout.addLayout(rec_controls)

        # Playback controls
        play_controls = QHBoxLayout()
        self.macro_speed = QDoubleSpinBox()
        self.macro_speed.setRange(0.1, 10.0)
        self.macro_speed.setValue(1.0)
        self.macro_speed.setSingleStep(0.1)
        play_controls.addWidget(QLabel("Speed:"))
        play_controls.addWidget(self.macro_speed)

        self.btn_macro_play = QPushButton("▶ Play Macro")
        self.btn_macro_play.clicked.connect(self._macro_play)
        play_controls.addWidget(self.btn_macro_play)

        self.btn_macro_pause = QPushButton("⏸ Pause")
        self.btn_macro_pause.clicked.connect(self._macro_pause)
        self.btn_macro_pause.setEnabled(False)
        play_controls.addWidget(self.btn_macro_pause)

        self.btn_macro_stop_play = QPushButton("⏹ Stop")
        self.btn_macro_stop_play.clicked.connect(self._macro_stop_play)
        self.btn_macro_stop_play.setEnabled(False)
        play_controls.addWidget(self.btn_macro_stop_play)

        play_controls.addStretch()
        macro_layout.addLayout(play_controls)

        # Template variables
        template_group = QGroupBox("Template Variables (for parameterization)")
        template_layout = QVBoxLayout()
        self.template_table = QTableWidget(0, 4)
        self.template_table.setHorizontalHeaderLabels(["Variable", "Default Value", "Type", "Description"])
        self.template_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        template_layout.addWidget(self.template_table)

        template_btns = QHBoxLayout()
        btn_add_template = QPushButton("➕ Add Variable")
        btn_add_template.clicked.connect(self._macro_add_template)
        template_btns.addWidget(btn_add_template)

        btn_remove_template = QPushButton("➖ Remove Selected")
        btn_remove_template.clicked.connect(self._macro_remove_template)
        template_btns.addWidget(btn_remove_template)
        template_btns.addStretch()
        template_layout.addLayout(template_btns)
        template_group.setLayout(template_layout)
        macro_layout.addWidget(template_group)

        # Macro list
        list_group = QGroupBox("Saved Macros")
        list_layout = QVBoxLayout()
        self.macro_list = QTableWidget(0, 5)
        self.macro_list.setHorizontalHeaderLabels(["ID", "Name", "Events", "Duration (s)", "Actions"])
        self.macro_list.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        list_layout.addWidget(self.macro_list)

        list_btns = QHBoxLayout()
        btn_refresh_macros = QPushButton("🔄 Refresh List")
        btn_refresh_macros.clicked.connect(self._macro_refresh_list)
        list_btns.addWidget(btn_refresh_macros)

        btn_import_macro = QPushButton("📥 Import")
        btn_import_macro.clicked.connect(self._macro_import)
        list_btns.addWidget(btn_import_macro)

        btn_export_macro = QPushButton("📤 Export")
        btn_export_macro.clicked.connect(self._macro_export)
        list_btns.addWidget(btn_export_macro)
        list_btns.addStretch()
        list_layout.addLayout(list_btns)
        list_group.setLayout(list_layout)
        macro_layout.addWidget(list_group)

        macro_group.setLayout(macro_layout)
        layout.addWidget(macro_group)

        # --- Visual Verification Section ---
        verify_group = QGroupBox("🔍 Visual Verification")
        verify_layout = QVBoxLayout()

        # Image comparison
        compare_form = QFormLayout()
        self.verify_ref_image = QLineEdit()
        self.verify_ref_image.setPlaceholderText("Path or base64 reference image")
        self.verify_test_image = QLineEdit()
        self.verify_test_image.setPlaceholderText("Path or base64 test image")
        compare_form.addRow("Reference:", self.verify_ref_image)
        compare_form.addRow("Test:", self.verify_test_image)

        self.verify_threshold = QDoubleSpinBox()
        self.verify_threshold.setRange(0.0, 1.0)
        self.verify_threshold.setValue(0.95)
        self.verify_threshold.setSingleStep(0.01)
        compare_form.addRow("SSIM Threshold:", self.verify_threshold)

        self.verify_ignore_regions = QLineEdit()
        self.verify_ignore_regions.setPlaceholderText("x,y,w,h;x,y,w,h (regions to ignore)")
        compare_form.addRow("Ignore Regions:", self.verify_ignore_regions)

        verify_layout.addLayout(compare_form)

        # Compare button
        btn_compare = QPushButton("🔍 Compare Images")
        btn_compare.clicked.connect(self._verify_compare)
        verify_layout.addWidget(btn_compare)

        # Results
        self.verify_result = QTextEdit()
        self.verify_result.setReadOnly(True)
        self.verify_result.setMaximumHeight(200)
        self.verify_result.setFont(QFont("Consolas", 9))
        verify_layout.addWidget(self.verify_result)

        # Diff image display
        self.verify_diff_label = QLabel("Diff image will appear here")
        self.verify_diff_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.verify_diff_label.setMinimumSize(400, 200)
        self.verify_diff_label.setStyleSheet("border: 1px solid gray; background-color: #1a1a1a; color: #888;")
        verify_layout.addWidget(self.verify_diff_label)

        verify_group.setLayout(verify_layout)
        layout.addWidget(verify_group)

        # Batch comparison
        batch_group = QGroupBox("📁 Batch Comparison")
        batch_layout = QVBoxLayout()
        batch_form = QFormLayout()
        self.batch_ref_dir = QLineEdit()
        self.batch_ref_dir.setPlaceholderText("Reference directory")
        self.batch_test_dir = QLineEdit()
        self.batch_test_dir.setPlaceholderText("Test directory")
        self.batch_pattern = QLineEdit("*.png")
        batch_form.addRow("Reference Dir:", self.batch_ref_dir)
        batch_form.addRow("Test Dir:", self.batch_test_dir)
        batch_form.addRow("Pattern:", self.batch_pattern)
        batch_layout.addLayout(batch_form)

        btn_batch_compare = QPushButton("📊 Run Batch Comparison")
        btn_batch_compare.clicked.connect(self._verify_batch_compare)
        batch_layout.addWidget(btn_batch_compare)

        self.batch_result = QTextEdit()
        self.batch_result.setReadOnly(True)
        self.batch_result.setMaximumHeight(150)
        self.batch_result.setFont(QFont("Consolas", 9))
        batch_layout.addWidget(self.batch_result)

        batch_group.setLayout(batch_layout)
        layout.addWidget(batch_group)

        layout.addStretch()
        return w

    # ------------------------------------------------------------------ #
    # Bridge Communication
    # ------------------------------------------------------------------ #
    def _send_bridge_request(self, tool: str, params: dict = None,
                              callback: callable = None, error_callback: callable = None) -> str:
        """Send a request to the bridge and handle response via callbacks."""
        request_id = self.bridge_client.dispatch(tool, params)

        # Store callbacks for this request
        if not hasattr(self, '_request_callbacks'):
            self._request_callbacks = {}
        self._request_callbacks[request_id] = {
            'callback': callback,
            'error_callback': error_callback,
            'tool': tool
        }
        return request_id

    def _on_bridge_response(self, request_id: str, response: dict):
        """Handle bridge response."""
        if hasattr(self, '_request_callbacks') and request_id in self._request_callbacks:
            cb_info = self._request_callbacks.pop(request_id)
            if cb_info['callback']:
                cb_info['callback'](response)
        else:
            # Default handling based on tool
            self._handle_default_response(request_id, response)

    def _on_bridge_error(self, request_id: str, error: str):
        """Handle bridge error."""
        if hasattr(self, '_request_callbacks') and request_id in self._request_callbacks:
            cb_info = self._request_callbacks.pop(request_id)
            if cb_info['error_callback']:
                cb_info['error_callback'](error)
            else:
                QMessageBox.warning(self, f"Bridge Error ({cb_info['tool']})", error)
        else:
            QMessageBox.warning(self, "Bridge Error", error)

    def _handle_default_response(self, request_id: str, response: dict):
        """Default response handler."""
        pass

    # ------------------------------------------------------------------ #
    # Dashboard Actions
    # ------------------------------------------------------------------ #
    def _refresh_status(self):
        self.dashboard_status.setText("Checking...")
        self._send_bridge_request("qgis.system.health", {},
            callback=self._on_health_response)

    def _on_health_response(self, response: dict):
        result = response.get("result", {})
        qgis_connected = result.get("qgis_connected", False)
        layer_count = result.get("layer_count", 0)
        project_open = result.get("project_open", False)

        status_text = f"QGIS: {'Connected' if qgis_connected else 'Disconnected'} | Project: {'Open' if project_open else 'Closed'} | Layers: {layer_count}"
        self.dashboard_status.setText(status_text)
        self.dashboard_bridge_status.setText("Connected" if qgis_connected else "Disconnected")
        self.dashboard_bridge_status.setStyleSheet("color: #44ff44;" if qgis_connected else "color: #ff4444;")
        self.dashboard_jobs_status.setText(f"{layer_count} layers")

        if hasattr(self, 'bridge_status_label'):
            self.bridge_status_label.setText(f"● Bridge: {'Connected' if qgis_connected else 'Disconnected'}")
            self.bridge_status_label.setStyleSheet(f"color: {'#44ff44' if qgis_connected else '#ff4444'}; font-weight: bold; padding: 4px;")

    def _test_bridge_connection(self):
        connected = self.bridge_client.health_check()
        if connected:
            QMessageBox.information(self, "Bridge Test", "✅ Bridge connection successful!")
            self._refresh_status()
        else:
            QMessageBox.warning(self, "Bridge Test", "❌ Bridge connection failed. Check if bridge server is running.")

    def _test_emergency_stop(self):
        self._send_bridge_request("qgis.system.inspect", {},
            callback=lambda r: QMessageBox.information(self, "Emergency Stop Test", "Bridge responded - emergency stop system is reachable"))

    # ------------------------------------------------------------------ #
    # Live Screen Actions
    # ------------------------------------------------------------------ #
    def _capture_screen_once(self):
        self.screen_status.setText("Capturing...")
        self._send_bridge_request("qgis.screen.capture", {},
            callback=self._on_screen_capture_response)

    def _on_screen_capture_response(self, response: dict):
        result = response.get("result", {})
        image_b64 = result.get("image_base64")
        if image_b64:
            try:
                img_data = base64.b64decode(image_b64)
                pixmap = QPixmap()
                pixmap.loadFromData(img_data, "PNG")
                scaled = pixmap.scaled(
                    self.screen_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.screen_label.setPixmap(scaled)
                self.screen_status.setText(f"Captured: {result.get('width')}x{result.get('height')}")
            except Exception as exc:
                self.screen_status.setText(f"Display error: {exc}")
        else:
            self.screen_status.setText("Capture failed: no image data")

    def _start_periodic_capture(self):
        interval = self.screen_interval.value()
        region_text = self.screen_region.text().strip()
        region = None
        if region_text:
            try:
                parts = [int(x.strip()) for x in region_text.split(",")]
                if len(parts) == 4:
                    region = parts
            except ValueError:
                QMessageBox.warning(self, "Invalid Region", "Region must be: left,top,right,bottom")
                return

        include_cursor = self.screen_include_cursor.isChecked()

        self._send_bridge_request("qgis.screen.capture.start_periodic", {
            "interval_seconds": interval,
            "region": region,
            "include_cursor": include_cursor
        }, callback=self._on_periodic_start_response)

    def _on_periodic_start_response(self, response: dict):
        result = response.get("result", {})
        if result.get("status") == "started":
            self._periodic_capture_active = True
            self.btn_start_periodic.setEnabled(False)
            self.btn_stop_periodic.setEnabled(True)
            self.screen_status.setText(f"Periodic capture started: {result.get('interval')}s interval")
        else:
            self.screen_status.setText(f"Failed to start: {result.get('status')}")

    def _stop_periodic_capture(self):
        self._send_bridge_request("qgis.screen.capture.stop_periodic", {},
            callback=self._on_periodic_stop_response)

    def _on_periodic_stop_response(self, response: dict):
        result = response.get("result", {})
        if result.get("status") == "stopped":
            self._periodic_capture_active = False
            self.btn_start_periodic.setEnabled(True)
            self.btn_stop_periodic.setEnabled(False)
            self.screen_status.setText("Periodic capture stopped")
        else:
            self.screen_status.setText(f"Stop result: {result.get('status')}")

    def _toggle_websocket(self):
        if self._ws_connected:
            self.ws_client.disconnect()
        else:
            ws_url = self.ws_url.text().strip() if hasattr(self, 'ws_url') else "ws://127.0.0.1:8767"
            self.ws_client.ws_url = ws_url
            self.ws_client.connect()

    def _on_ws_connected(self):
        self._ws_connected = True
        self.btn_connect_ws.setText("🔌 Disconnect WebSocket Stream")
        self.btn_ws_config.setEnabled(True)
        self.screen_ws_status.setText("WebSocket: Connected")
        self.screen_ws_status.setStyleSheet("color: #44ff44;")
        self.screen_status.setText("WebSocket connected - waiting for frames...")

    def _on_ws_disconnected(self):
        self._ws_connected = False
        self.btn_connect_ws.setText("🔌 Connect WebSocket Stream")
        self.btn_ws_config.setEnabled(False)
        self.screen_ws_status.setText("WebSocket: Disconnected")
        self.screen_ws_status.setStyleSheet("color: #ff4444;")
        self.screen_status.setText("WebSocket disconnected")

    def _on_ws_error(self, error: str):
        self.screen_status.setText(f"WebSocket error: {error}")

    def _on_ws_frame(self, frame: dict):
        """Handle incoming frame from WebSocket."""
        image_b64 = frame.get("image_base64")
        if image_b64:
            try:
                img_data = base64.b64decode(image_b64)
                pixmap = QPixmap()
                pixmap.loadFromData(img_data, "PNG")
                scaled = pixmap.scaled(
                    self.screen_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.screen_label.setPixmap(scaled)
                ts = frame.get("timestamp", 0)
                self.screen_status.setText(f"Streaming: {frame.get('width')}x{frame.get('height')} @ {time.strftime('%H:%M:%S', time.localtime(ts))}")
            except Exception as exc:
                self.screen_status.setText(f"Frame display error: {exc}")

    def _send_ws_config(self):
        if not self._ws_connected:
            return
        interval = self.screen_interval.value()
        region_text = self.screen_region.text().strip()
        region = None
        if region_text:
            try:
                parts = [int(x.strip()) for x in region_text.split(",")]
                if len(parts) == 4:
                    region = parts
            except ValueError:
                return
        config = {
            "interval": interval,
            "region": region,
            "include_cursor": self.screen_include_cursor.isChecked()
        }
        self.ws_client.send_config(config)
        self.screen_status.setText("Config sent to WebSocket server")

    # ------------------------------------------------------------------ #
    # AI Cursor Actions
    # ------------------------------------------------------------------ #
    def _cursor_move_smooth(self):
        x = self.cursor_x.value()
        y = self.cursor_y.value()
        self._send_bridge_request("qgis.cursor.move", {"x": x, "y": y},
            callback=self._on_cursor_move_response)

    def _cursor_move_instant(self):
        x = self.cursor_x.value()
        y = self.cursor_y.value()
        self._send_bridge_request("qgis.cursor.move", {"x": x, "y": y, "smooth": False},
            callback=self._on_cursor_move_response)

    def _on_cursor_move_response(self, response: dict):
        result = response.get("result", {})
        if result.get("ok"):
            self.cursor_status_pos.setText(f"({result.get('x')}, {result.get('y')})")
            self.cursor_status_active.setText("Active")
            self.cursor_status_active.setStyleSheet("color: #44ff44;")
        else:
            QMessageBox.warning(self, "Cursor Move Failed", str(result))

    def _cursor_click(self, button: str = "left"):
        self._send_bridge_request("qgis.cursor.click", {"button": button},
            callback=self._on_cursor_click_response)

    def _on_cursor_click_response(self, response: dict):
        result = response.get("result", {})
        if result.get("ok"):
            self.cursor_status_pos.setText(f"Clicked: {result.get('button', 'left')}")
        else:
            QMessageBox.warning(self, "Cursor Click Failed", str(result))

    def _cursor_drag(self):
        x1 = self.cursor_x.value()
        y1 = self.cursor_y.value()
        # For drag, we'd need end coordinates - use a dialog or secondary inputs
        # For now, just show a message
        QMessageBox.information(self, "Drag", "Drag requires start and end coordinates. Use bridge API directly for now.")

    def _cursor_pause(self):
        self._send_bridge_request("qgis.cursor.pause", {},
            callback=lambda r: self._update_cursor_status(r, paused=True))

    def _cursor_resume(self):
        self._send_bridge_request("qgis.cursor.resume", {},
            callback=lambda r: self._update_cursor_status(r, paused=False))

    def _cursor_emergency_stop(self):
        self._send_bridge_request("qgis.cursor.emergency_stop", {},
            callback=lambda r: self._update_cursor_status(r, emergency=True))

    def _cursor_release_emergency(self):
        self._send_bridge_request("qgis.cursor.release_emergency_stop", {},
            callback=lambda r: self._update_cursor_status(r, emergency=False))

    def _update_cursor_status(self, response: dict, paused: bool = None, emergency: bool = None):
        result = response.get("result", {})
        if result.get("ok"):
            if paused is not None:
                self.cursor_status_paused.setText("Yes" if paused else "No")
                self.cursor_status_paused.setStyleSheet(f"color: {'#ffaa00' if paused else '#44ff44'};")
            if emergency is not None:
                self.cursor_status_emergency.setText("ACTIVE" if emergency else "Normal")
                self.cursor_status_emergency.setStyleSheet(f"color: {'#ff4444' if emergency else '#44ff44'}; font-weight: bold;")
                # Update main toolbar emergency status too
                self._update_emergency_status_display(emergency)

    def _on_highlight_radius_changed(self, value: int):
        self._send_bridge_request("qgis.cursor.set_highlight_radius", {"radius": value})

    def _on_show_highlight_changed(self, checked: bool):
        self._send_bridge_request("qgis.cursor.set_show_highlight", {"show": checked})

    def _on_show_ripple_changed(self, checked: bool):
        self._send_bridge_request("qgis.cursor.set_show_ripple", {"show": checked})

    def _on_show_trail_changed(self, checked: bool):
        self._send_bridge_request("qgis.cursor.set_show_trail", {"show": checked})

    def _on_trail_length_changed(self, value: int):
        self._send_bridge_request("qgis.cursor.set_trail_max_length", {"length": value})

    # ------------------------------------------------------------------ #
    # Emergency Stop
    # ------------------------------------------------------------------ #
    def _trigger_emergency_stop(self):
        """Trigger global emergency stop."""
        self.btn_emergency_stop.setEnabled(False)
        self.btn_emergency_stop.setText("🛑 STOPPING...")
        self.emergency_status_label.setText("🛑 EMERGENCY STOP TRIGGERED")
        self.emergency_status_label.setStyleSheet("color: #ff4444; font-weight: bold; padding: 4px; background-color: #ffebeb;")
        self.dashboard_emergency_status.setText("ACTIVE")
        self.dashboard_emergency_status.setStyleSheet("color: #ff4444; font-weight: bold;")

        # Call emergency stop on bridge
        self._send_bridge_request("qgis.system.emergency_stop", {"reason": "User triggered via UI/hotkey"},
            callback=self._on_emergency_stop_response,
            error_callback=self._on_emergency_stop_error)

    def _on_emergency_stop_response(self, response: dict):
        result = response.get("result", {})
        callbacks = result.get("callbacks_executed", 0)
        failed = result.get("callbacks_failed", 0)
        QMessageBox.critical(self, "Emergency Stop Executed",
            f"Emergency stop triggered successfully.\n"
            f"Callbacks executed: {callbacks}\n"
            f"Callbacks failed: {failed}\n\n"
            f"All automation has been stopped.")
        self.btn_emergency_stop.setEnabled(True)
        self.btn_emergency_stop.setText("🛑 EMERGENCY STOP")

    def _on_emergency_stop_error(self, error: str):
        QMessageBox.critical(self, "Emergency Stop Failed", f"Failed to trigger emergency stop:\n{error}")
        self.btn_emergency_stop.setEnabled(True)
        self.btn_emergency_stop.setText("🛑 EMERGENCY STOP")

    def _update_emergency_status_display(self, active: bool):
        """Update emergency status display across UI."""
        if active:
            self.emergency_status_label.setText("🛑 EMERGENCY STOP ACTIVE")
            self.emergency_status_label.setStyleSheet("color: #ff4444; font-weight: bold; padding: 4px; background-color: #ffebeb;")
            if hasattr(self, 'dashboard_emergency_status'):
                self.dashboard_emergency_status.setText("ACTIVE")
                self.dashboard_emergency_status.setStyleSheet("color: #ff4444; font-weight: bold;")
            if hasattr(self, 'cursor_status_emergency'):
                self.cursor_status_emergency.setText("ACTIVE")
                self.cursor_status_emergency.setStyleSheet("color: #ff4444; font-weight: bold;")
        else:
            self.emergency_status_label.setText("")
            if hasattr(self, 'dashboard_emergency_status'):
                self.dashboard_emergency_status.setText("Normal")
                self.dashboard_emergency_status.setStyleSheet("color: #44ff44;")
            if hasattr(self, 'cursor_status_emergency'):
                self.cursor_status_emergency.setText("Normal")
                self.cursor_status_emergency.setStyleSheet("color: #44ff44;")

    # ------------------------------------------------------------------ #
    # Other Panel Actions
    # ------------------------------------------------------------------ #
    def _send_chat(self):
        text = self.chat_input.toPlainText().strip()
        if not text:
            return
        self.chat_output.append(f"> {text}")
        self.chat_output.append("[AI response will appear here once MCP client is configured.]")
        self.chat_input.clear()

    def _save_api_provider(self):
        provider = self.api_provider.text().strip()
        key = self.api_key.text().strip()
        if provider and key:
            QMessageBox.information(self, "API Provider", f"Provider '{provider}' saved.")
        else:
            QMessageBox.warning(self, "API Provider", "Please enter provider and key.")

    def _refresh_agents(self):
        from agents.builtins import (
            DataAcquisitionAgent, DataManagementAgent, VectorProcessingAgent,
            RasterProcessingAgent, CRSTransformAgent, SpatialAnalysisAgent,
            TerrainAnalysisAgent, HydrologyAnalysisAgent, NetworkAnalysisAgent,
            RemoteSensingAgent, ClassificationAgent, ChangeDetectionAgent,
            Analysis3DAgent, LiDARProcessingAgent, AIMLAgent, SurveyAgent,
            CadastralAgent, CartographyAgent, TemporalAgent, DatabaseAgent,
            WebGISAgent, FieldDataAgent, AutomationAgent, QualityControlAgent,
            GeoreferencingAgent, AgentsManagerAgent, OrchestratorAgent,
            CustomBuilderAgent, SupervisorAgent,
        )
        agents = [
            DataAcquisitionAgent, DataManagementAgent, VectorProcessingAgent,
            RasterProcessingAgent, CRSTransformAgent, SpatialAnalysisAgent,
            TerrainAnalysisAgent, HydrologyAnalysisAgent, NetworkAnalysisAgent,
            RemoteSensingAgent, ClassificationAgent, ChangeDetectionAgent,
            Analysis3DAgent, LiDARProcessingAgent, AIMLAgent, SurveyAgent,
            CadastralAgent, CartographyAgent, TemporalAgent, DatabaseAgent,
            WebGISAgent, FieldDataAgent, AutomationAgent, QualityControlAgent,
            GeoreferencingAgent, AgentsManagerAgent, OrchestratorAgent,
            CustomBuilderAgent, SupervisorAgent,
        ]
        self.agent_table.setRowCount(len(agents))
        for i, agent_cls in enumerate(agents):
            agent = agent_cls()
            self.agent_table.setItem(i, 0, QTableWidgetItem(agent.agent_id))
            self.agent_table.setItem(i, 1, QTableWidgetItem(agent.name))
            btn = QPushButton("Execute")
            btn.clicked.connect(lambda _, a=agent: self._execute_agent(a))
            self.agent_table.setCellWidget(i, 2, btn)

    def _execute_agent(self, agent):
        result = agent.execute({})
        QMessageBox.information(
            self, "Agent Executed",
            f"{agent.name}\nStatus: {result.get('status', 'unknown')}\nNote: {result.get('note', '')}"
        )

    def _import_skill(self):
        QMessageBox.information(self, "Skill Manager", "Skill import dialog not yet implemented.")

    def _validate_skills(self):
        QMessageBox.information(self, "Skill Manager", "No skills found to validate.")

    def _refresh_clusters(self):
        clusters = [(f"M{i:02d}", f"Cluster {i}") for i in range(1, 26)]
        self.cluster_table.setRowCount(len(clusters))
        for i, (cid, name) in enumerate(clusters):
            self.cluster_table.setItem(i, 0, QTableWidgetItem(cid))
            self.cluster_table.setItem(i, 1, QTableWidgetItem(name))
            btn = QPushButton("Run")
            btn.clicked.connect(lambda _, c=cid: self._run_cluster(c))
            self.cluster_table.setCellWidget(i, 2, btn)

    def _run_cluster(self, cluster_id):
        QMessageBox.information(self, "Cluster", f"Cluster {cluster_id} execution not yet wired to bridge.")

    def _discover_algorithms(self):
        try:
            import processing
            from qgis.core import QgsApplication
            registry = QgsApplication.processingRegistry()
            algs = []
            for alg in registry.algorithms():
                algs.append(f"{alg.id()} — {alg.name()} [{alg.group()}]")
            self.algo_output.setPlainText("\n".join(algs[:100]))
            if len(algs) > 100:
                self.algo_output.append(f"\n... and {len(algs) - 100} more algorithms")
        except Exception as exc:
            QMessageBox.warning(self, "Algorithm Discovery", str(exc))

    def _refresh_audit_log(self):
        try:
            from database.db import Database
            from database.repositories.audit_repository import AuditRepository
            db = Database()
            db.connect()
            audit = AuditRepository(db)
            logs = audit.list(limit=50)
            db.close()

            lines = []
            for log in logs:
                ts = log.get("timestamp", "")
                actor = log.get("actor", "")
                action = log.get("action", "")
                target = log.get("target", "")
                outcome = log.get("outcome", "")
                details = log.get("details", {})
                lines.append(f"[{ts}] {actor} | {action} | {target} | {outcome}")
                if details:
                    lines.append(f"  Details: {json.dumps(details, indent=2)}")

            self.audit_output.setPlainText("\n".join(lines) if lines else "No audit logs found.")
        except Exception as exc:
            QMessageBox.warning(self, "Audit Log", f"Failed to load audit log: {exc}")

    # ------------------------------------------------------------------ #
    # Macro Recorder Actions
    # ------------------------------------------------------------------ #
    def _macro_start_recording(self):
        """Start recording a macro."""
        name = self.macro_name.text().strip() or "Untitled Macro"
        description = self.macro_description.text().strip()

        # Collect template variables
        templates = []
        for row in range(self.template_table.rowCount()):
            var_item = self.template_table.item(row, 0)
            default_item = self.template_table.item(row, 1)
            type_item = self.template_table.item(row, 2)
            desc_item = self.template_table.item(row, 3)
            if var_item and var_item.text().strip():
                templates.append({
                    "name": var_item.text().strip(),
                    "default": default_item.text() if default_item else "",
                    "type": type_item.text() if type_item else "string",
                    "description": desc_item.text() if desc_item else "",
                })

        self._send_bridge_request("qgis.macro.start_recording", {
            "name": name,
            "description": description,
            "templates": templates,
        }, callback=self._on_macro_recording_started)

        self.btn_macro_record.setEnabled(False)
        self.btn_macro_stop.setEnabled(True)
        self.btn_macro_save.setEnabled(False)

    def _on_macro_recording_started(self, response: dict):
        result = response.get("result", {})
        if result.get("status") == "started":
            self.macro_status = QLabel(f"Recording: {result.get('macro_id')}")
            # Add status label if not exists
            if not hasattr(self, '_macro_status_label'):
                self._macro_status_label = QLabel("Recording...")
                self._macro_status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
            self._macro_status_label.setText(f"🔴 Recording: {result.get('macro_id')}")
            self._macro_status_label.setStyleSheet("color: #ff4444; font-weight: bold;")
        else:
            QMessageBox.warning(self, "Recording Failed", str(result.get("error", "Unknown error")))
            self.btn_macro_record.setEnabled(True)
            self.btn_macro_stop.setEnabled(False)

    def _macro_stop_recording(self):
        """Stop recording a macro."""
        self._send_bridge_request("qgis.macro.stop_recording", {},
            callback=self._on_macro_recording_stopped)

    def _on_macro_recording_stopped(self, response: dict):
        result = response.get("result", {})
        if result.get("macro"):
            macro = result["macro"]
            self._macro_status_label.setText(f"✅ Recorded: {macro.get('name')} ({len(macro.get('events', []))} events)")
            self._macro_status_label.setStyleSheet("color: #44ff44; font-weight: bold;")
            self.btn_macro_record.setEnabled(True)
            self.btn_macro_stop.setEnabled(False)
            self.btn_macro_save.setEnabled(True)
            # Store the macro for saving
            self._last_recorded_macro = macro
        else:
            QMessageBox.warning(self, "Stop Failed", str(result.get("error", "Unknown error")))
            self.btn_macro_record.setEnabled(True)
            self.btn_macro_stop.setEnabled(False)

    def _macro_save(self):
        """Save the last recorded macro."""
        if not hasattr(self, '_last_recorded_macro'):
            QMessageBox.warning(self, "No Macro", "No recorded macro to save.")
            return
        self._send_bridge_request("qgis.macro.save", {"macro": self._last_recorded_macro},
            callback=self._on_macro_saved)

    def _on_macro_saved(self, response: dict):
        result = response.get("result", {})
        if result.get("status") == "saved":
            QMessageBox.information(self, "Saved", f"Macro saved: {result.get('macro_id')}")
            self._macro_refresh_list()
        else:
            QMessageBox.warning(self, "Save Failed", str(result.get("error", "Unknown error")))

    def _macro_play(self):
        """Play a macro."""
        # Get selected macro from list
        current_row = self.macro_list.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Macro Selected", "Please select a macro from the list.")
            return

        macro_id = self.macro_list.item(current_row, 0).text()
        speed = self.macro_speed.value()

        self._send_bridge_request("qgis.macro.play", {
            "macro_id": macro_id,
            "speed": speed,
        }, callback=self._on_macro_play_started)

        self.btn_macro_play.setEnabled(False)
        self.btn_macro_pause.setEnabled(True)
        self.btn_macro_stop_play.setEnabled(True)

    def _on_macro_play_started(self, response: dict):
        result = response.get("result", {})
        if result.get("status") == "started":
            self._macro_status_label.setText(f"▶ Playing: {result.get('macro_id')}")
            self._macro_status_label.setStyleSheet("color: #44aaff; font-weight: bold;")
        else:
            QMessageBox.warning(self, "Play Failed", str(result.get("error", "Unknown error")))
            self.btn_macro_play.setEnabled(True)
            self.btn_macro_pause.setEnabled(False)
            self.btn_macro_stop_play.setEnabled(False)

    def _macro_pause(self):
        """Pause macro playback."""
        self._send_bridge_request("qgis.macro.pause", {},
            callback=lambda r: self._macro_status_label.setText("⏸ Paused"))

    def _macro_stop_play(self):
        """Stop macro playback."""
        self._send_bridge_request("qgis.macro.stop", {},
            callback=lambda r: self._on_macro_playback_stopped())

    def _on_macro_playback_stopped(self):
        self.btn_macro_play.setEnabled(True)
        self.btn_macro_pause.setEnabled(False)
        self.btn_macro_stop_play.setEnabled(False)
        self._macro_status_label.setText("⏹ Stopped")
        self._macro_status_label.setStyleSheet("color: #888;")

    def _macro_add_template(self):
        """Add a template variable row."""
        row = self.template_table.rowCount()
        self.template_table.insertRow(row)
        self.template_table.setItem(row, 0, QTableWidgetItem(""))
        self.template_table.setItem(row, 1, QTableWidgetItem(""))
        self.template_table.setItem(row, 2, QTableWidgetItem("string"))
        self.template_table.setItem(row, 3, QTableWidgetItem(""))

    def _macro_remove_template(self):
        """Remove selected template variable row."""
        current_row = self.template_table.currentRow()
        if current_row >= 0:
            self.template_table.removeRow(current_row)

    def _macro_refresh_list(self):
        """Refresh the macro list from storage."""
        self._send_bridge_request("qgis.macro.list", {},
            callback=self._on_macro_list_response)

    def _on_macro_list_response(self, response: dict):
        result = response.get("result", {})
        macros = result.get("macros", [])
        self.macro_list.setRowCount(len(macros))
        for i, macro in enumerate(macros):
            self.macro_list.setItem(i, 0, QTableWidgetItem(macro.get("id", "")))
            self.macro_list.setItem(i, 1, QTableWidgetItem(macro.get("name", "")))
            self.macro_list.setItem(i, 2, QTableWidgetItem(str(len(macro.get("events", [])))))
            self.macro_list.setItem(i, 3, QTableWidgetItem(f"{macro.get('duration', 0):.1f}"))

            # Action buttons
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setContentsMargins(2, 2, 2, 2)

            btn_play = QPushButton("▶")
            btn_play.setToolTip("Play")
            btn_play.setMaximumWidth(30)
            btn_play.clicked.connect(lambda _, m=macro: self._macro_play_selected(m))
            btn_layout.addWidget(btn_play)

            btn_export = QPushButton("📤")
            btn_export.setToolTip("Export")
            btn_export.setMaximumWidth(30)
            btn_export.clicked.connect(lambda _, m=macro: self._macro_export_selected(m))
            btn_layout.addWidget(btn_export)

            btn_delete = QPushButton("🗑")
            btn_delete.setToolTip("Delete")
            btn_delete.setMaximumWidth(30)
            btn_delete.clicked.connect(lambda _, m=macro: self._macro_delete_selected(m))
            btn_layout.addWidget(btn_delete)

            self.macro_list.setCellWidget(i, 4, btn_widget)

    def _macro_play_selected(self, macro: dict):
        """Play a specific macro from the list."""
        macro_id = macro.get("id")
        speed = self.macro_speed.value()
        self._send_bridge_request("qgis.macro.play", {
            "macro_id": macro_id,
            "speed": speed,
        }, callback=self._on_macro_play_started)

    def _macro_export_selected(self, macro: dict):
        """Export a specific macro."""
        macro_id = macro.get("id")
        self._send_bridge_request("qgis.macro.export", {"macro_id": macro_id},
            callback=self._on_macro_exported)

    def _on_macro_exported(self, response: dict):
        result = response.get("result", {})
        if result.get("status") == "exported":
            QMessageBox.information(self, "Exported", f"Macro exported to: {result.get('path')}")
        else:
            QMessageBox.warning(self, "Export Failed", str(result.get("error", "Unknown error")))

    def _macro_delete_selected(self, macro: dict):
        """Delete a specific macro."""
        macro_id = macro.get("id")
        reply = QMessageBox.question(self, "Delete Macro",
            f"Delete macro '{macro.get('name')}' ({macro_id})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self._send_bridge_request("qgis.macro.delete", {"macro_id": macro_id},
                callback=lambda r: self._macro_refresh_list())

    def _macro_import(self):
        """Import a macro from file."""
        from qgis.PyQt.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Macro", "", "JSON Files (*.json)")
        if file_path:
            self._send_bridge_request("qgis.macro.import", {"file_path": file_path},
                callback=self._on_macro_imported)

    def _on_macro_imported(self, response: dict):
        result = response.get("result", {})
        if result.get("status") == "imported":
            QMessageBox.information(self, "Imported", f"Macro imported: {result.get('macro_id')}")
            self._macro_refresh_list()
        else:
            QMessageBox.warning(self, "Import Failed", str(result.get("error", "Unknown error")))

    def _macro_export(self):
        """Export selected macro."""
        current_row = self.macro_list.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Macro Selected", "Please select a macro from the list.")
            return
        macro_id = self.macro_list.item(current_row, 0).text()
        self._macro_export_selected({"id": macro_id})

    # ------------------------------------------------------------------ #
    # Visual Verification Actions
    # ------------------------------------------------------------------ #
    def _verify_compare(self):
        """Compare two images."""
        ref_path = self.verify_ref_image.text().strip()
        test_path = self.verify_test_image.text().strip()
        threshold = self.verify_threshold.value()

        ignore_regions = []
        ignore_text = self.verify_ignore_regions.text().strip()
        if ignore_text:
            try:
                for region_str in ignore_text.split(";"):
                    parts = [int(x.strip()) for x in region_str.split(",")]
                    if len(parts) == 4:
                        ignore_regions.append(parts)
            except ValueError:
                QMessageBox.warning(self, "Invalid Regions", "Format: x,y,w,h;x,y,w,h")
                return

        self.verify_result.setText("Comparing...")
        self._send_bridge_request("qgis.visual.compare", {
            "reference": ref_path,
            "test": test_path,
            "threshold": threshold,
            "ignore_regions": ignore_regions,
        }, callback=self._on_verify_compare_response)

    def _on_verify_compare_response(self, response: dict):
        result = response.get("result", {})
        if result.get("status") == "completed":
            comparison = result.get("comparison", {})
            self.verify_result.setText(json.dumps(comparison, indent=2))

            # Display diff image if available
            diff_b64 = comparison.get("diff_image_base64")
            if diff_b64:
                try:
                    img_data = base64.b64decode(diff_b64)
                    pixmap = QPixmap()
                    pixmap.loadFromData(img_data, "PNG")
                    scaled = pixmap.scaled(
                        self.verify_diff_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.verify_diff_label.setPixmap(scaled)
                except Exception as exc:
                    self.verify_result.append(f"\nDiff display error: {exc}")
        else:
            self.verify_result.setText(f"Error: {result.get('error', 'Unknown error')}")

    def _verify_batch_compare(self):
        """Run batch comparison."""
        ref_dir = self.batch_ref_dir.text().strip()
        test_dir = self.batch_test_dir.text().strip()
        pattern = self.batch_pattern.text().strip() or "*.png"
        threshold = self.verify_threshold.value()

        if not ref_dir or not test_dir:
            QMessageBox.warning(self, "Missing Directories", "Please specify both reference and test directories.")
            return

        self.batch_result.setText("Running batch comparison...")
        self._send_bridge_request("qgis.visual.batch_compare", {
            "reference_dir": ref_dir,
            "test_dir": test_dir,
            "pattern": pattern,
            "threshold": threshold,
        }, callback=self._on_verify_batch_compare_response)

    def _on_verify_batch_compare_response(self, response: dict):
        result = response.get("result", {})
        if result.get("status") == "completed":
            results = result.get("results", [])
            lines = [f"Batch comparison completed: {len(results)} files"]
            for r in results:
                file = r.get("file", "")
                if "error" in r:
                    lines.append(f"  {file}: ERROR - {r['error']}")
                else:
                    comp = r.get("result", {})
                    status = comp.get("result", "unknown")
                    ssim = comp.get("ssim_score", 0)
                    lines.append(f"  {file}: {status} (SSIM: {ssim:.4f})")
            self.batch_result.setText("\n".join(lines))
        else:
            self.batch_result.setText(f"Error: {result.get('error', 'Unknown error')}")

    # ------------------------------------------------------------------ #
    # Missing Handler Methods
    # ------------------------------------------------------------------ #
    def _send_chat(self):
        """Send AI chat message to bridge."""
        message = self.chat_input.toPlainText().strip()
        if not message:
            return
        self.chat_output.append(f"User: {message}")
        self.chat_input.clear()
        self._send_bridge_request("qgis.ai.chat", {"message": message},
            callback=self._on_chat_response)

    def _on_chat_response(self, response: dict):
        result = response.get("result", {})
        reply = result.get("reply", "No response")
        self.chat_output.append(f"AI: {reply}")

    def _save_api_provider(self):
        """Save API provider configuration."""
        provider = self.api_provider.text().strip()
        api_key = self.api_key.text().strip()
        if not provider or not api_key:
            QMessageBox.warning(self, "Missing Data", "Please enter both provider and API key.")
            return
        # Save via bridge config
        self._send_bridge_request("qgis.config.set_api_key", {
            "provider": provider,
            "api_key": api_key
        }, callback=lambda r: QMessageBox.information(self, "Saved", "API provider saved successfully!"))

    def _refresh_agents(self):
        """Refresh agent list from bridge."""
        self._send_bridge_request("qgis.agents.list", {},
            callback=self._on_agents_list_response)

    def _on_agents_list_response(self, response: dict):
        result = response.get("result", {})
        agents = result.get("agents", [])
        self.agent_table.setRowCount(len(agents))
        for row, agent in enumerate(agents):
            self.agent_table.setItem(row, 0, QTableWidgetItem(agent.get("id", "")))
            self.agent_table.setItem(row, 1, QTableWidgetItem(agent.get("name", "")))
            btn = QPushButton("Run")
            btn.clicked.connect(lambda _, aid=agent.get("id"): self._run_agent(aid))
            self.agent_table.setCellWidget(row, 2, btn)

    def _run_agent(self, agent_id: str):
        self._send_bridge_request("qgis.agents.run", {"agent_id": agent_id},
            callback=lambda r: QMessageBox.information(self, "Agent Run", f"Agent {agent_id} started"))

    def _import_skill(self):
        """Import a skill from file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Skill", "", "Python Files (*.py);;All Files (*)")
        if file_path:
            self._send_bridge_request("qgis.skills.import", {"file_path": file_path},
                callback=lambda r: QMessageBox.information(self, "Import", "Skill imported successfully!"))

    def _validate_skills(self):
        """Validate all skills."""
        self._send_bridge_request("qgis.skills.validate", {},
            callback=lambda r: QMessageBox.information(self, "Validation", "Skills validated successfully!"))

    def _refresh_clusters(self):
        """Refresh GIS clusters list."""
        self._send_bridge_request("qgis.clusters.list", {},
            callback=self._on_clusters_list_response)

    def _on_clusters_list_response(self, response: dict):
        result = response.get("result", {})
        clusters = result.get("clusters", [])
        self.cluster_table.setRowCount(len(clusters))
        for row, cluster in enumerate(clusters):
            self.cluster_table.setItem(row, 0, QTableWidgetItem(cluster.get("id", "")))
            self.cluster_table.setItem(row, 1, QTableWidgetItem(cluster.get("name", "")))
            btn = QPushButton("Run")
            btn.clicked.connect(lambda _, cid=cluster.get("id"): self._run_cluster(cid))
            self.cluster_table.setCellWidget(row, 2, btn)

    def _run_cluster(self, cluster_id: str):
        self._send_bridge_request("qgis.clusters.run", {"cluster_id": cluster_id},
            callback=lambda r: QMessageBox.information(self, "Cluster Run", f"Cluster {cluster_id} started"))

    def _discover_algorithms(self):
        """Discover QGIS processing algorithms."""
        self.algo_output.setText("Discovering algorithms...")
        self._send_bridge_request("qgis.algorithms.discover", {},
            callback=self._on_algorithms_discover_response)

    def _on_algorithms_discover_response(self, response: dict):
        result = response.get("result", {})
        algorithms = result.get("algorithms", [])
        text = f"Found {len(algorithms)} algorithms:\n"
        for alg in algorithms[:50]:  # Limit to first 50
            text += f"  {alg.get('id', '')}: {alg.get('name', '')}\n"
        if len(algorithms) > 50:
            text += f"\n... and {len(algorithms) - 50} more"
        self.algo_output.setText(text)

    def _refresh_audit_log(self):
        """Refresh security audit log."""
        self.audit_output.setText("Loading audit log...")
        self._send_bridge_request("qgis.security.audit_log", {},
            callback=self._on_audit_log_response)

    def _on_audit_log_response(self, response: dict):
        result = response.get("result", {})
        logs = result.get("logs", [])
        if logs:
            text = "\n".join([f"{log.get('timestamp', '')} - {log.get('event', '')}: {log.get('details', '')}" for log in logs])
        else:
            text = "No audit logs found."
        self.audit_output.setText(text)

    def _refresh_version_info(self):
        """Refresh version control information."""
        try:
            import subprocess
            import sys
            import platform
            from qgis.PyQt.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
            from qgis.core import Qgis

            # App version from config
            if hasattr(self, 'config') and self.config:
                self.version_app_version.setText(self.config.get("app_version", "1.0.0"))

            # Git info - use project root dynamically
            project_root = os.environ.get("UAGIS_PROJECT_ROOT", r"D:\1 2 3 QGIS\Universal-AI-GIS-Studio")
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    capture_output=True, text=True, timeout=3,
                    cwd=project_root
                )
                if result.returncode == 0:
                    self.version_git_hash.setText(result.stdout.strip())
                else:
                    self.version_git_hash.setText("Not a git repo")

                result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True, text=True, timeout=3,
                    cwd=project_root
                )
                if result.returncode == 0:
                    self.version_git_branch.setText(result.stdout.strip())
                else:
                    self.version_git_branch.setText("Unknown")

                result = subprocess.run(
                    ["git", "describe", "--tags", "--always"],
                    capture_output=True, text=True, timeout=3,
                    cwd=project_root
                )
                if result.returncode == 0:
                    self.version_git_tag.setText(result.stdout.strip())
                else:
                    self.version_git_tag.setText("No tags")

            except Exception:
                self.version_git_hash.setText("Git not available")
                self.version_git_branch.setText("Git not available")
                self.version_git_tag.setText("Git not available")

            # Build date from config
            if hasattr(self, 'config') and self.config:
                build_date = self.config.get("build_date", "")
                build_number = self.config.get("build_number", "")
                self.version_build_date.setText(build_date if build_date else "Not set")
                self.version_build_number.setText(build_number if build_number else "Not set")

            # QGIS version
            self.version_qgis_version.setText(f"{Qgis.QGIS_VERSION} ({Qgis.QGIS_RELEASE_NAME})")

            # Python version
            self.version_python_version.setText(f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

            # PyQt version
            self.version_pyqt_version.setText(f"Qt {QT_VERSION_STR}, PyQt {PYQT_VERSION_STR}")

            # Runtime info
            self.runtime_os.setText(f"{platform.system()} {platform.release()}")
            self.runtime_platform.setText(platform.platform())
            self.runtime_arch.setText(platform.machine())

            # Data directory
            from core.config import default_data_dir
            self.runtime_data_dir.setText(default_data_dir())

        except Exception as exc:
            QMessageBox.warning(self, "Version Info", f"Failed to load version info: {exc}")

    def _save_settings(self):
        """Save bridge and connection settings."""
        if not hasattr(self, 'config') or self.config is None:
            QMessageBox.warning(self, "Config Error", "Configuration system not available.")
            return

        try:
            # Bridge settings
            bridge_host = self.settings_bridge_host.text().strip()
            bridge_port = self.settings_bridge_port.value()
            bridge_token = self.settings_bridge_token.text().strip()
            
            self.config.set("bridge_host", bridge_host)
            self.config.set("bridge_port", bridge_port)
            self.config.set("bridge_auth_token", bridge_token)

            # WebSocket settings
            ws_host = self.settings_ws_host.text().strip()
            ws_port = self.settings_ws_port.value()
            
            self.config.set("ws_host", ws_host)
            self.config.set("ws_port", ws_port)

            # Update bridge client
            bridge_url = f"http://{bridge_host}:{bridge_port}"
            ws_url = f"ws://{ws_host}:{ws_port}"
            
            self.bridge_client.set_base_url(bridge_url)
            self.bridge_client.set_auth_token(bridge_token)
            self.ws_client.ws_url = ws_url

            QMessageBox.information(self, "Saved", f"Bridge: {bridge_url}\nWebSocket: {ws_url}\nSettings saved successfully!")
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", f"Failed to save settings:\n{exc}")

    # ------------------------------------------------------------------ #
    # Helper Methods for Panels
    # ------------------------------------------------------------------ #
    def _browse_file(self, line_edit: QLineEdit):
        """Open file dialog and set path in line edit."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File", "", "All Files (*.*)")
        if file_path:
            line_edit.setText(file_path)

    # ------------------------------------------------------------------ #
    # Georeferencing Handlers
    # ------------------------------------------------------------------ #
    def _georef_analyze(self):
        """Analyze image for georeferencing."""
        image_path = self.georef_image.text().strip()
        if not image_path:
            QMessageBox.warning(self, "Missing Image", "Please select an image file.")
            return
        self.georef_output.setText("Analyzing image...")
        self._send_bridge_request("qgis.georeference.analyze", {"image_path": image_path},
            callback=self._on_georef_analyze_response)

    def _on_georef_analyze_response(self, response: dict):
        result = response.get("result", {})
        if result.get("analyzed"):
            dims = result.get("dimensions", [])
            self.georef_output.setText(f"Image analyzed: {dims[0]}x{dims[1]} {result.get('format', '')} ({result.get('mode', '')})")
        else:
            self.georef_output.setText(f"Error: {result.get('error', 'Analysis failed')}")

    def _georef_run(self):
        """Run georeferencing."""
        image_path = self.georef_image.text().strip()
        reference = self.georef_reference.text().strip()
        method = self.georef_gcp_method.currentText()
        if not image_path or not reference:
            QMessageBox.warning(self, "Missing Data", "Please provide image and reference.")
            return
        self.georef_output.setText("Running georeferencing...")
        self._send_bridge_request("qgis.georeference.run", {
            "image_path": image_path,
            "reference": reference,
            "method": method
        }, callback=self._on_georef_run_response)

    def _on_georef_run_response(self, response: dict):
        result = response.get("result", {})
        if result.get("ok"):
            self.georef_output.setText(f"Georeferencing completed: {result.get('output', 'success')}")
        else:
            self.georef_output.setText(f"Error: {result.get('error', 'Failed')}")

    # ------------------------------------------------------------------ #
    # GCP Intelligence Handlers
    # ------------------------------------------------------------------ #
    def _gcp_generate(self):
        """Generate GCPs."""
        image_path = self.gcp_image.text().strip()
        reference = self.gcp_reference.text().strip()
        count = self.gcp_count.value()
        if not image_path or not reference:
            QMessageBox.warning(self, "Missing Data", "Please provide image and reference.")
            return
        self.gcp_output.setText("Generating GCPs...")
        self._send_bridge_request("qgis.gcp.generate", {
            "image_path": image_path,
            "reference_source": reference,
            "count": count
        }, callback=self._on_gcp_generate_response)

    def _on_gcp_generate_response(self, response: dict):
        result = response.get("result", {})
        gcps = result.get("gcps", [])
        self.gcp_output.setText(f"Generated {len(gcps)} GCPs")

    def _gcp_validate(self):
        """Validate GCPs."""
        self.gcp_output.setText("Validating GCPs...")
        self._send_bridge_request("qgis.gcp.validate", {"gcps": []},
            callback=self._on_gcp_validate_response)

    def _on_gcp_validate_response(self, response: dict):
        result = response.get("result", {})
        valid = result.get("valid_gcps", [])
        rejected = result.get("rejected", [])
        self.gcp_output.setText(f"Valid: {len(valid)}, Rejected: {len(rejected)}, RMSE: {result.get('rmse', 'N/A')}")

    def _gcp_optimize(self):
        """Optimize GCPs for minimum RMSE."""
        self.gcp_output.setText("Optimizing GCPs...")
        self._send_bridge_request("qgis.gcp.optimize", {},
            callback=lambda r: self.gcp_output.setText("Optimization completed"))

    # ------------------------------------------------------------------ #
    # Workflow Builder Handlers
    # ------------------------------------------------------------------ #
    def _workflow_add_step(self):
        """Add a step to the workflow."""
        row = self.workflow_steps.rowCount()
        self.workflow_steps.insertRow(row)
        self.workflow_steps.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.workflow_steps.setItem(row, 1, QTableWidgetItem(""))
        self.workflow_steps.setItem(row, 2, QTableWidgetItem("{}"))
        # Add action button
        btn = QPushButton("🗑")
        btn.setMaximumWidth(30)
        btn.clicked.connect(lambda _, r=row: self._workflow_remove_step_row(r))
        self.workflow_steps.setCellWidget(row, 3, btn)

    def _workflow_remove_step(self):
        """Remove selected step."""
        current_row = self.workflow_steps.currentRow()
        if current_row >= 0:
            self._workflow_remove_step_row(current_row)

    def _workflow_remove_step_row(self, row: int):
        """Remove specific step row."""
        self.workflow_steps.removeRow(row)
        # Renumber steps
        for r in range(self.workflow_steps.rowCount()):
            self.workflow_steps.setItem(r, 0, QTableWidgetItem(str(r + 1)))

    def _workflow_run(self):
        """Execute the workflow."""
        name = self.workflow_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter a workflow name.")
            return
        # Collect steps
        steps = []
        for row in range(self.workflow_steps.rowCount()):
            tool = self.workflow_steps.item(row, 1).text() if self.workflow_steps.item(row, 1) else ""
            params_text = self.workflow_steps.item(row, 2).text() if self.workflow_steps.item(row, 2) else "{}"
            try:
                import json
                params = json.loads(params_text)
            except json.JSONDecodeError:
                params = {}
            if tool:
                steps.append({"tool": tool, "params": params})
        
        self.workflow_output.setText(f"Running workflow '{name}' with {len(steps)} steps...")
        self._send_bridge_request("qgis.workflow.execute", {"steps": steps},
            callback=self._on_workflow_run_response)

    def _on_workflow_run_response(self, response: dict):
        result = response.get("result", {})
        if result.get("ok"):
            self.workflow_output.setText(f"Workflow completed: {result.get('job_id', 'success')}")
        else:
            self.workflow_output.setText(f"Error: {result.get('error', 'Failed')}")

    # ------------------------------------------------------------------ #
    # Data Manager Handlers
    # ------------------------------------------------------------------ #
    def _dm_load_layer(self):
        """Load a data layer."""
        path = self.dm_layer_path.text().strip()
        if not path:
            QMessageBox.warning(self, "Missing Path", "Please select a layer file.")
            return
        name = self.dm_layer_name.text().strip() or None
        provider = self.dm_provider.currentText().lower() if self.dm_provider.currentText() != "Auto" else None
        
        self._send_bridge_request("qgis.layers.load", {
            "path": path,
            "layer_name": name,
            "provider": provider
        }, callback=self._on_dm_load_layer_response)

    def _on_dm_load_layer_response(self, response: dict):
        result = response.get("result", {})
        if result.get("id"):
            self._dm_refresh_layers()
            QMessageBox.information(self, "Loaded", f"Layer loaded: {result.get('name')}")
        else:
            QMessageBox.warning(self, "Failed", f"Failed to load layer: {result.get('error', 'Unknown')}")

    def _dm_refresh_layers(self):
        """Refresh the layer list."""
        self._send_bridge_request("qgis.layers.inspect", {},
            callback=self._on_dm_refresh_layers_response)

    def _on_dm_refresh_layers_response(self, response: dict):
        result = response.get("result", {})
        layers = result.get("layers", [])
        self.dm_layers.setRowCount(len(layers))
        for row, layer in enumerate(layers):
            self.dm_layers.setItem(row, 0, QTableWidgetItem(layer.get("id", "")))
            self.dm_layers.setItem(row, 1, QTableWidgetItem(layer.get("name", "")))
            self.dm_layers.setItem(row, 2, QTableWidgetItem(layer.get("type", "")))
            btn = QPushButton("🗑 Remove")
            btn.setMaximumWidth(80)
            btn.clicked.connect(lambda _, lid=layer.get("id"): self._dm_remove_layer(lid))
            self.dm_layers.setCellWidget(row, 3, btn)

    def _dm_remove_layer(self, layer_id: str):
        """Remove a layer."""
        self._send_bridge_request("qgis.layers.remove", {"layer_id": layer_id},
            callback=lambda r: self._dm_refresh_layers())

    # ------------------------------------------------------------------ #
    # Quality Control Handlers
    # ------------------------------------------------------------------ #
    def _qc_run_check(self):
        """Run quality control check."""
        layer_id = self.qc_layer.currentText()
        check_type = self.qc_checks.currentText()
        if not layer_id:
            QMessageBox.warning(self, "Missing Layer", "Please select a layer.")
            return
        
        self.qc_output.setText(f"Running {check_type} on {layer_id}...")
        self._send_bridge_request("qgis.quality.run", {
            "layer_id": layer_id,
            "check_type": check_type
        }, callback=self._on_qc_run_check_response)

    def _on_qc_run_check_response(self, response: dict):
        result = response.get("result", {})
        if result.get("ok"):
            issues = result.get("issues", [])
            text = f"Check completed. Found {len(issues)} issues:\n"
            for issue in issues[:50]:
                text += f"  - {issue.get('type', '')}: {issue.get('description', '')}\n"
            if len(issues) > 50:
                text += f"\n... and {len(issues) - 50} more"
            self.qc_output.setText(text)
        else:
            self.qc_output.setText(f"Error: {result.get('error', 'Check failed')}")

    # ============================================================================
    # AI Chat Panel Handlers
    # ============================================================================

    def eventFilter(self, obj, event):
        """Event filter for chat input (Enter to send, Shift+Enter for newline)."""
        if obj == self.chat_input and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    # Shift+Enter = new line (default behavior)
                    return False
                else:
                    # Enter = send message
                    self._chat_send_message()
                    return True
        return super().eventFilter(obj, event)

    def _chat_populate_models(self):
        """Populate model combo box with available models from active provider."""
        if not LLM_PROVIDERS_AVAILABLE or not hasattr(self, 'config') or not self.config:
            return

        try:
            active_provider = self.config.get("llm_active_provider", "openai")
            providers_json = self.config.get("llm_providers", "{}")
            providers = json.loads(providers_json) if providers_json else {}
            provider_config = providers.get(active_provider, {})
            model = provider_config.get("model", "")

            self.chat_model_combo.blockSignals(True)
            self.chat_model_combo.clear()

            # Add models from known providers
            for provider_meta in list_providers():
                for m in provider_meta.get("default_models", []):
                    self.chat_model_combo.addItem(f"{provider_meta['name']}: {m}", m)

            # Add current model if not in list
            if model and self.chat_model_combo.findData(model) == -1:
                self.chat_model_combo.addItem(f"Current: {model}", model)

            # Select current model
            if model:
                idx = self.chat_model_combo.findData(model)
                if idx >= 0:
                    self.chat_model_combo.setCurrentIndex(idx)

            self.chat_model_combo.blockSignals(False)

            # Set temperature from config
            temp = self.config.get("llm_temperature", 0.7)
            self.chat_temperature.setValue(temp)

        except Exception:
            pass

    def _chat_model_changed(self, index: int):
        """Handle model selection change."""
        if index >= 0:
            model = self.chat_model_combo.itemData(index)
            if model and hasattr(self, 'config') and self.config:
                active_provider = self.config.get("llm_active_provider", "openai")
                providers_json = self.config.get("llm_providers", "{}")
                providers = json.loads(providers_json) if providers_json else {}
                if active_provider in providers:
                    providers[active_provider]["model"] = model
                    self.config.set("llm_providers", json.dumps(providers))

    def _chat_toggle_context(self, checked: bool):
        """Toggle context attachment."""
        if checked:
            self._chat_attach_context_dialog()
        else:
            self._chat_attached_context = {}
            self.chat_context_label.setText("No context attached")
            self.chat_context_label.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 2px 8px;")
            self.chat_attach_context.setChecked(False)

    def _chat_attach_context_dialog(self):
        """Show dialog to attach context (layers, selection, project)."""
        from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QDialogButtonBox, QGroupBox, QLabel

        dialog = QDialog(self)
        dialog.setWindowTitle("Attach Context")
        dialog.setMinimumWidth(400)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)

        # Project context
        project_group = QGroupBox("Project")
        project_layout = QVBoxLayout()
        self.ctx_project_cb = QCheckBox("Current QGIS Project")
        self.ctx_project_cb.setChecked(True)
        project_layout.addWidget(self.ctx_project_cb)
        project_group.setLayout(project_layout)
        layout.addWidget(project_group)

        # Layers context
        layers_group = QGroupBox("Layers")
        layers_layout = QVBoxLayout()
        self.ctx_all_layers_cb = QCheckBox("All Layers")
        self.ctx_selected_layers_cb = QCheckBox("Selected Layers Only")
        self.ctx_visible_layers_cb = QCheckBox("Visible Layers Only")
        layers_layout.addWidget(self.ctx_all_layers_cb)
        layers_layout.addWidget(self.ctx_selected_layers_cb)
        layers_layout.addWidget(self.ctx_visible_layers_cb)
        layers_group.setLayout(layers_layout)
        layout.addWidget(layers_group)

        # Selection context
        selection_group = QGroupBox("Selection")
        selection_layout = QVBoxLayout()
        self.ctx_selection_cb = QCheckBox("Current Feature Selection")
        self.ctx_selection_cb.setChecked(True)
        selection_layout.addWidget(self.ctx_selection_cb)
        selection_group.setLayout(selection_layout)
        layout.addWidget(selection_group)

        # Canvas extent
        extent_group = QGroupBox("Map Canvas")
        extent_layout = QVBoxLayout()
        self.ctx_extent_cb = QCheckBox("Current Canvas Extent")
        self.ctx_extent_cb.setChecked(True)
        extent_layout.addWidget(self.ctx_extent_cb)
        extent_group.setLayout(extent_layout)
        layout.addWidget(extent_group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(lambda: self._chat_apply_context(dialog))
        buttons.rejected.connect(lambda: (self.chat_attach_context.setChecked(False), dialog.reject()))
        layout.addWidget(buttons)

        dialog.exec()

    def _chat_apply_context(self, dialog):
        """Apply selected context options."""
        self._chat_attached_context = {
            "project": self.ctx_project_cb.isChecked(),
            "all_layers": self.ctx_all_layers_cb.isChecked(),
            "selected_layers": self.ctx_selected_layers_cb.isChecked(),
            "visible_layers": self.ctx_visible_layers_cb.isChecked(),
            "selection": self.ctx_selection_cb.isChecked(),
            "extent": self.ctx_extent_cb.isChecked(),
        }

        # Count enabled contexts
        count = sum(1 for v in self._chat_attached_context.values() if v)
        if count > 0:
            self.chat_context_label.setText(f"Context: {count} item(s) attached")
            self.chat_context_label.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 11px; padding: 2px 8px;")
        else:
            self.chat_context_label.setText("No context attached")
            self.chat_context_label.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 2px 8px;")
            self.chat_attach_context.setChecked(False)

        dialog.accept()

    def _chat_send_message(self):
        """Send user message to LLM."""
        text = self.chat_input.toPlainText().strip()
        if not text:
            return

        # Clear input
        self.chat_input.clear()

        # Add user message to chat
        self._chat_add_message("user", text)

        # Prepare messages for LLM
        messages = self._chat_prepare_messages(text)

        # Start streaming response
        self._chat_streaming = True
        self.chat_send_btn.hide()
        self.chat_stop_btn.show()
        self.chat_input.setEnabled(False)

        # Get active provider and config
        if not hasattr(self, 'config') or not self.config or not LLM_PROVIDERS_AVAILABLE:
            self._chat_add_message("assistant", "❌ LLM providers not configured. Please configure in AI Connections → LLM Models tab.")
            self._chat_streaming_finished()
            return

        active_provider = self.config.get("llm_active_provider", "openai")
        providers_json = self.config.get("llm_providers", "{}")
        providers = json.loads(providers_json) if providers_json else {}
        provider_config = providers.get(active_provider, {})

        if not provider_config.get("api_key") and active_provider != "custom":
            self._chat_add_message("assistant", f"❌ No API key configured for {active_provider}. Please configure in AI Connections → LLM Models tab.")
            self._chat_streaming_finished()
            return

        # Create provider instance
        try:
            from integrations.llm_providers import get_provider, LLMProviderConfig, LLMMessage
            config = LLMProviderConfig(
                api_key=provider_config.get("api_key", ""),
                base_url=provider_config.get("base_url", "") or None,
                model=provider_config.get("model", "") or self.chat_model_combo.currentData(),
                temperature=provider_config.get("temperature", self.chat_temperature.value()),
                max_tokens=provider_config.get("max_tokens", self.config.get("llm_max_tokens", 4096)),
                top_p=provider_config.get("top_p", self.config.get("llm_top_p", 1.0)),
                frequency_penalty=provider_config.get("frequency_penalty", 0.0),
                presence_penalty=provider_config.get("presence_penalty", 0.0),
            )
            provider = get_provider(active_provider, config=config)

            # System prompt
            system_prompt = provider_config.get("system_prompt", "") or self.config.get("llm_default_system_prompt", "")

            # Convert to LLMMessage format
            llm_messages = []
            if system_prompt:
                llm_messages.append(LLMMessage.system(system_prompt))

            # Add conversation history (last 20 messages)
            for msg in self._chat_messages[-20:]:
                if msg["role"] == "user":
                    llm_messages.append(LLMMessage.user(msg["content"]))
                elif msg["role"] == "assistant":
                    llm_messages.append(LLMMessage.assistant(msg["content"]))
                elif msg["role"] == "tool":
                    llm_messages.append(LLMMessage.tool(msg.get("tool_call_id", ""), msg["content"], msg.get("name")))

            # Add current user message
            llm_messages.append(LLMMessage.user(text))

            # Get tools from MCP
            tools = self._chat_get_available_tools()

            # Stream response in background thread
            self._chat_current_response = ""
            self._chat_current_message_widget = None

            import threading
            def stream_thread():
                try:
                    for chunk in provider.chat_stream(llm_messages, tools=tools):
                        if not self._chat_streaming:
                            break
                        QTimer.singleShot(0, lambda c=chunk: self._chat_on_stream_chunk(c))
                    QTimer.singleShot(0, self._chat_streaming_finished)
                except Exception as exc:
                    QTimer.singleShot(0, lambda e=exc: self._chat_on_stream_error(e))

            threading.Thread(target=stream_thread, daemon=True).start()

        except Exception as exc:
            self._chat_add_message("assistant", f"❌ Error: {exc}")
            self._chat_streaming_finished()

    def _chat_prepare_messages(self, current_text: str) -> list:
        """Prepare messages including context."""
        messages = []

        # Add attached context as system message
        if self._chat_attached_context:
            context_parts = ["Current GIS Context:"]
            if self._chat_attached_context.get("project"):
                context_parts.append("- Project: Active QGIS project")
            if self._chat_attached_context.get("all_layers"):
                context_parts.append("- All layers available")
            if self._chat_attached_context.get("selected_layers"):
                context_parts.append("- Selected layers only")
            if self._chat_attached_context.get("visible_layers"):
                context_parts.append("- Visible layers only")
            if self._chat_attached_context.get("selection"):
                context_parts.append("- Current feature selection active")
            if self._chat_attached_context.get("extent"):
                context_parts.append("- Current canvas extent")

            context_text = "\n".join(context_parts)
            messages.append({"role": "system", "content": context_text})

        # Add conversation history
        for msg in self._chat_messages[-20:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Add current message
        messages.append({"role": "user", "content": current_text})

        return messages

    def _chat_get_available_tools(self) -> list:
        """Get available GIS tools from MCP servers."""
        if not LLM_PROVIDERS_AVAILABLE:
            return []

        try:
            from integrations.llm_providers import LLMTool
            # Start with built-in GIS tools
            tools = [
                LLMTool(
                    name="qgis_layers_list",
                    description="List all loaded QGIS layers with their properties",
                    parameters={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                LLMTool(
                    name="qgis_layer_load",
                    description="Load a vector or raster layer into QGIS",
                    parameters={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Path to layer file (shapefile, GeoJSON, GeoPackage, TIFF, etc.)"},
                            "name": {"type": "string", "description": "Optional layer name"},
                            "provider": {"type": "string", "description": "Provider: ogr, gdal, wms, etc."},
                        },
                        "required": ["path"]
                    }
                ),
                LLMTool(
                    name="qgis_layer_remove",
                    description="Remove a layer from QGIS",
                    parameters={
                        "type": "object",
                        "properties": {
                            "layer_id": {"type": "string", "description": "Layer ID to remove"},
                        },
                        "required": ["layer_id"]
                    }
                ),
                LLMTool(
                    name="qgis_processing_run",
                    description="Run a QGIS processing algorithm",
                    parameters={
                        "type": "object",
                        "properties": {
                            "algorithm": {"type": "string", "description": "Algorithm ID (e.g., native:buffer, qgis:clip, native:reprojectlayer)"},
                            "parameters": {"type": "object", "description": "Algorithm parameters as key-value pairs"},
                        },
                        "required": ["algorithm", "parameters"]
                    }
                ),
                LLMTool(
                    name="qgis_project_save",
                    description="Save the current QGIS project",
                    parameters={
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Project file path (optional, saves to current if not provided)"},
                        },
                        "required": []
                    }
                ),
                LLMTool(
                    name="qgis_project_new",
                    description="Create a new QGIS project",
                    parameters={
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                ),
                LLMTool(
                    name="qgis_canvas_set_extent",
                    description="Set the map canvas extent",
                    parameters={
                        "type": "object",
                        "properties": {
                            "xmin": {"type": "number", "description": "Minimum X"},
                            "ymin": {"type": "number", "description": "Minimum Y"},
                            "xmax": {"type": "number", "description": "Maximum X"},
                            "ymax": {"type": "number", "description": "Maximum Y"},
                            "crs": {"type": "string", "description": "CRS auth ID (e.g., EPSG:4326)"},
                        },
                        "required": ["xmin", "ymin", "xmax", "ymax"]
                    }
                ),
                LLMTool(
                    name="qgis_layer_select_features",
                    description="Select features in a layer by expression",
                    parameters={
                        "type": "object",
                        "properties": {
                            "layer_id": {"type": "string", "description": "Layer ID"},
                            "expression": {"type": "string", "description": "QGIS expression (e.g., \"population\" > 10000)"},
                        },
                        "required": ["layer_id", "expression"]
                    }
                ),
                LLMTool(
                    name="qgis_vector_create_buffer",
                    description="Create buffer around features",
                    parameters={
                        "type": "object",
                        "properties": {
                            "layer_id": {"type": "string", "description": "Input layer ID"},
                            "distance": {"type": "number", "description": "Buffer distance"},
                            "segments": {"type": "integer", "description": "Number of segments (default 5)"},
                            "dissolve": {"type": "boolean", "description": "Dissolve overlapping buffers"},
                            "output_name": {"type": "string", "description": "Output layer name"},
                        },
                        "required": ["layer_id", "distance", "output_name"]
                    }
                ),
                LLMTool(
                    name="qgis_raster_calculator",
                    description="Run raster calculator expression",
                    parameters={
                        "type": "object",
                        "properties": {
                            "expression": {"type": "string", "description": "Raster calculator expression (e.g., \"layer1@1 + layer2@1\")"},
                            "layers": {"type": "array", "items": {"type": "string"}, "description": "Layer IDs"},
                            "output_path": {"type": "string", "description": "Output raster path"},
                            "extent": {"type": "object", "description": "Extent: {xmin, ymin, xmax, ymax, crs}"},
                            "cell_size": {"type": "number", "description": "Output cell size"},
                        },
                        "required": ["expression", "layers", "output_path"]
                    }
                ),
                LLMTool(
                    name="qgis_field_calculator",
                    description="Calculate field values for a layer",
                    parameters={
                        "type": "object",
                        "properties": {
                            "layer_id": {"type": "string", "description": "Layer ID"},
                            "field_name": {"type": "string", "description": "New or existing field name"},
                            "expression": {"type": "string", "description": "QGIS expression"},
                            "field_type": {"type": "string", "description": "Field type: Integer, Double, String, Date"},
                            "field_length": {"type": "integer", "description": "Field length (for strings)"},
                            "field_precision": {"type": "integer", "description": "Field precision (for doubles)"},
                        },
                        "required": ["layer_id", "field_name", "expression"]
                    }
                ),
            ]

            # Add MCP tools if available
            if hasattr(self, '_chat_mcp_tools') and self._chat_mcp_tools:
                tools.extend(self._chat_mcp_tools)

            return tools
        except Exception:
            return []

    def _chat_fetch_mcp_tools(self):
        """Fetch tools from MCP servers via bridge."""
        # This would query the bridge for available MCP tools
        # and convert them to LLMTool format
        self._send_bridge_request("qgis.mcp.list_tools", {},
            callback=self._on_mcp_tools_list_response)

    def _on_mcp_tools_list_response(self, response: dict):
        """Handle MCP tools list response."""
        result = response.get("result", {})
        tools_data = result.get("tools", [])

        if not LLM_PROVIDERS_AVAILABLE:
            return

        from integrations.llm_providers import LLMTool
        mcp_tools = []
        for tool in tools_data:
            mcp_tools.append(LLMTool(
                name=tool.get("name", ""),
                description=tool.get("description", ""),
                parameters=tool.get("input_schema", {"type": "object", "properties": {}}),
                namespace=tool.get("namespace", "")
            ))

        # Store for use in chat
        self._chat_mcp_tools = mcp_tools

    def _chat_on_stream_chunk(self, chunk):
        """Handle streaming response chunk."""
        if not self._chat_streaming:
            return

        # Create or update assistant message widget
        if self._chat_current_message_widget is None:
            self._chat_current_message_widget = self._chat_create_assistant_message("")
            self._chat_messages_layout.insertWidget(self._chat_messages_layout.count() - 1, self._chat_current_message_widget)

        # Append content
        if chunk.content:
            self._chat_current_response += chunk.content
            self._chat_update_assistant_message(self._chat_current_message_widget, self._chat_current_response)

        # Handle tool calls
        if chunk.tool_calls:
            for tc in chunk.tool_calls:
                self._chat_handle_tool_call(tc)

        # Update token usage
        if chunk.usage:
            self._chat_update_token_usage(chunk.usage)

        # Scroll to bottom
        self._chat_scroll_to_bottom()

    def _chat_on_stream_error(self, error: Exception):
        """Handle streaming error."""
        error_msg = f"❌ Error: {str(error)}"
        if self._chat_current_message_widget:
            self._chat_update_assistant_message(self._chat_current_message_widget, self._chat_current_response + "\n\n" + error_msg)
        else:
            self._chat_add_message("assistant", error_msg)
        self._chat_streaming_finished()

    def _chat_streaming_finished(self):
        """Clean up after streaming finishes."""
        self._chat_streaming = False
        self.chat_send_btn.show()
        self.chat_stop_btn.hide()
        self.chat_input.setEnabled(True)
        self.chat_input.setFocus()

        # Save conversation
        self._chat_save_current_conversation()

    def _chat_stop_generation(self):
        """Stop current generation."""
        self._chat_streaming = False
        if self._chat_current_message_widget:
            self._chat_update_assistant_message(self._chat_current_message_widget, self._chat_current_response + "\n\n*[Generation stopped by user]*")
        self._chat_streaming_finished()

    def _chat_create_assistant_message(self, content: str) -> QWidget:
        """Create an assistant message widget with markdown rendering."""
        widget = QFrame()
        widget.setFrameShape(QFrame.Shape.StyledPanel)
        widget.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 12px;
            }
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Header with model info and actions
        header = QHBoxLayout()
        header.setSpacing(8)

        icon = QLabel("🤖")
        icon.setStyleSheet("font-size: 16px;")
        header.addWidget(icon)

        role_label = QLabel("Assistant")
        role_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        header.addWidget(role_label)

        # Token usage (will be updated)
        self._chat_current_token_label = QLabel("")
        self._chat_current_token_label.setStyleSheet("color: #7f8c8d; font-family: Consolas; font-size: 10px;")
        header.addWidget(self._chat_current_token_label)

        header.addStretch()

        # Copy button
        copy_btn = QPushButton("📋 Copy")
        copy_btn.setMaximumWidth(70)
        copy_btn.setStyleSheet("font-size: 10px; padding: 2px 6px;")
        copy_btn.clicked.connect(lambda: self._chat_copy_message(content))
        header.addWidget(copy_btn)

        # Regenerate button
        regen_btn = QPushButton("🔄 Regenerate")
        regen_btn.setMaximumWidth(85)
        regen_btn.setStyleSheet("font-size: 10px; padding: 2px 6px;")
        regen_btn.clicked.connect(self._chat_regenerate_response)
        header.addWidget(regen_btn)

        layout.addLayout(header)

        # Content area (markdown rendered)
        self._chat_current_content_label = QTextEdit()
        self._chat_current_content_label.setReadOnly(True)
        self._chat_current_content_label.setFont(QFont("Segoe UI", 10))
        self._chat_current_content_label.setStyleSheet("""
            QTextEdit {
                background-color: transparent;
                border: none;
                padding: 0;
            }
        """)
        self._chat_current_content_label.setHtml(self._chat_markdown_to_html(content))
        self._chat_current_content_label.setMaximumHeight(300)
        layout.addWidget(self._chat_current_content_label)

        # Tool calls area (initially hidden)
        self._chat_current_tools_widget = QWidget()
        self._chat_current_tools_layout = QVBoxLayout(self._chat_current_tools_widget)
        self._chat_current_tools_layout.setContentsMargins(0, 8, 0, 0)
        self._chat_current_tools_widget.hide()
        layout.addWidget(self._chat_current_tools_widget)

        return widget

    def _chat_update_assistant_message(self, widget: QFrame, content: str):
        """Update assistant message content."""
        # Find the content label
        for child in widget.findChildren(QTextEdit):
            if child.objectName() != "tool_output":
                child.setHtml(self._chat_markdown_to_html(content))
                break

    def _chat_add_message(self, role: str, content: str, tool_calls: list = None, tool_results: list = None):
        """Add a message to the chat."""
        if role == "user":
            widget = self._chat_create_user_message(content)
        elif role == "assistant":
            widget = self._chat_create_assistant_message(content)
        elif role == "tool":
            widget = self._chat_create_tool_message(content, tool_results)
        elif role == "system":
            widget = self._chat_create_system_message(content)
        else:
            return

        # Store message
        msg_data = {"role": role, "content": content}
        if tool_calls:
            msg_data["tool_calls"] = tool_calls
        if tool_results:
            msg_data["tool_results"] = tool_results
        self._chat_messages.append(msg_data)

        # Add to layout (before stretch)
        self._chat_messages_layout.insertWidget(self._chat_messages_layout.count() - 1, widget)

        # Scroll to bottom
        self._chat_scroll_to_bottom()

    def _chat_create_user_message(self, content: str) -> QWidget:
        """Create a user message widget."""
        widget = QFrame()
        widget.setFrameShape(QFrame.Shape.StyledPanel)
        widget.setStyleSheet("""
            QFrame {
                background-color: #e8f5e9;
                border: 1px solid #c8e6c9;
                border-radius: 12px;
            }
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        icon = QLabel("👤")
        icon.setStyleSheet("font-size: 16px;")
        header.addWidget(icon)

        role_label = QLabel("You")
        role_label.setStyleSheet("font-weight: bold; color: #27ae60;")
        header.addWidget(role_label)
        header.addStretch()

        copy_btn = QPushButton("📋 Copy")
        copy_btn.setMaximumWidth(70)
        copy_btn.setStyleSheet("font-size: 10px; padding: 2px 6px;")
        copy_btn.clicked.connect(lambda: self._chat_copy_message(content))
        header.addWidget(copy_btn)

        layout.addLayout(header)

        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setFont(QFont("Segoe UI", 10))
        content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(content_label)

        return widget

    def _chat_create_system_message(self, content: str) -> QWidget:
        """Create a system message widget."""
        widget = QFrame()
        widget.setFrameShape(QFrame.Shape.StyledPanel)
        widget.setStyleSheet("""
            QFrame {
                background-color: #fff3e0;
                border: 1px solid #ffe0b2;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 8, 10, 8)

        label = QLabel(f"⚙️ System: {content}")
        label.setWordWrap(True)
        label.setFont(QFont("Segoe UI", 9))
        label.setStyleSheet("color: #e65100;")
        layout.addWidget(label)

        return widget

    def _chat_create_tool_message(self, content: str, tool_results: list = None) -> QWidget:
        """Create a tool result message widget."""
        widget = QFrame()
        widget.setFrameShape(QFrame.Shape.StyledPanel)
        widget.setStyleSheet("""
            QFrame {
                background-color: #e3f2fd;
                border: 1px solid #bbdefb;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        icon = QLabel("🔧")
        header.addWidget(icon)

        label = QLabel("Tool Result")
        label.setStyleSheet("font-weight: bold; color: #1565c0;")
        header.addWidget(label)
        header.addStretch()
        layout.addLayout(header)

        # Show tool results
        if tool_results:
            for result in tool_results:
                result_widget = QFrame()
                result_widget.setStyleSheet("background-color: #ffffff; border-radius: 4px; padding: 8px;")
                result_layout = QVBoxLayout(result_widget)

                name_label = QLabel(f"📋 {result.get('name', 'unknown')}")
                name_label.setStyleSheet("font-weight: bold; font-family: Consolas; font-size: 10px;")
                result_layout.addWidget(name_label)

                if result.get("error"):
                    error_label = QLabel(f"❌ Error: {result['error']}")
                    error_label.setStyleSheet("color: #e74c3c; font-family: Consolas; font-size: 10px;")
                    error_label.setWordWrap(True)
                    result_layout.addWidget(error_label)
                else:
                    output_text = result.get("output", "")
                    if isinstance(output_text, dict):
                        output_text = json.dumps(output_text, indent=2)
                    output_label = QLabel(str(output_text)[:2000])
                    output_label.setStyleSheet("font-family: Consolas; font-size: 10px;")
                    output_label.setWordWrap(True)
                    output_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                    result_layout.addWidget(output_label)

                layout.addWidget(result_widget)

        return widget

    def _chat_handle_tool_call(self, tool_call):
        """Handle a tool call from the LLM."""
        if not self._chat_current_message_widget:
            return

        # Show tool calls area
        self._chat_current_tools_widget.show()

        # Create tool call display
        tool_widget = QFrame()
        tool_widget.setStyleSheet("""
            QFrame {
                background-color: #fff8e1;
                border: 1px solid #ffecb3;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        tool_layout = QVBoxLayout(tool_widget)
        tool_layout.setContentsMargins(8, 8, 8, 8)
        tool_layout.setSpacing(4)

        # Tool name
        name_label = QLabel(f"🔧 Calling: {tool_call.name}")
        name_label.setStyleSheet("font-weight: bold; font-family: Consolas; font-size: 11px; color: #f57f17;")
        tool_layout.addWidget(name_label)

        # Arguments
        args_text = json.dumps(tool_call.arguments, indent=2)
        args_label = QLabel(f"Arguments:\n{args_text}")
        args_label.setStyleSheet("font-family: Consolas; font-size: 10px; color: #7f8c8d;")
        args_label.setWordWrap(True)
        args_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        tool_layout.addWidget(args_label)

        # Execute tool via bridge
        self._chat_execute_tool_via_bridge(tool_call, tool_widget)

        self._chat_current_tools_layout.addWidget(tool_widget)

    def _chat_execute_tool_via_bridge(self, tool_call, tool_widget):
        """Execute a tool call via the QGIS Bridge."""
        # Map tool names to bridge tools
        bridge_tool_map = {
            "qgis_layers_list": "qgis.layers.inspect",
            "qgis_layer_load": "qgis.layers.load",
            "qgis_layer_remove": "qgis.layers.remove",
            "qgis_processing_run": "qgis.processing.run",
            "qgis_project_save": "qgis.project.save",
            "qgis_project_new": "qgis.project.new",
            "qgis_canvas_set_extent": "qgis.canvas.set_extent",
            "qgis_layer_select_features": "qgis.layer.select_features",
            "qgis_vector_create_buffer": "qgis.vector.create_buffer",
            "qgis_raster_calculator": "qgis.raster.calculator",
            "qgis_field_calculator": "qgis.field_calculator",
        }

        bridge_tool = bridge_tool_map.get(tool_call.name)
        if not bridge_tool:
            # Check if it's an MCP tool (namespaced)
            if tool_call.namespace or (hasattr(self, '_chat_mcp_tools') and any(t.name == tool_call.name for t in self._chat_mcp_tools)):
                # Execute via MCP
                self._send_bridge_request("qgis.mcp.call_tool", {
                    "tool_name": tool_call.name,
                    "arguments": tool_call.arguments,
                }, callback=lambda r, tc=tool_call, tw=tool_widget: self._chat_on_tool_result(tc, r.get("result", {}), tw))
                return

            self._chat_on_tool_result(tool_call, {"error": f"Unknown tool: {tool_call.name}"}, tool_widget)
            return

        # Execute via bridge
        self._send_bridge_request(bridge_tool, tool_call.arguments,
            callback=lambda r, tc=tool_call, tw=tool_widget: self._chat_on_tool_result(tc, r.get("result", {}), tw))

    def _chat_on_tool_result(self, tool_call, result: dict, tool_widget: QFrame):
        """Handle tool execution result."""
        # Update tool widget with result
        if result.get("error"):
            result_text = f"❌ Error: {result['error']}"
            color = "#e74c3c"
        else:
            output = result.get("output", result)
            if isinstance(output, dict):
                output_text = json.dumps(output, indent=2)
            else:
                output_text = str(output)
            result_text = f"✅ Result:\n{output_text[:3000]}"
            color = "#27ae60"

        # Add result to tool widget
        result_label = QLabel(result_text)
        result_label.setStyleSheet(f"font-family: Consolas; font-size: 10px; color: {color};")
        result_label.setWordWrap(True)
        result_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        tool_widget.layout().addWidget(result_label)

        # Add tool result to conversation for follow-up
        tool_result_msg = {
            "role": "tool",
            "content": result_text,
            "tool_call_id": tool_call.id,
            "name": tool_call.name,
        }
        self._chat_messages.append(tool_result_msg)

        # If we're still streaming, continue conversation with tool result
        if self._chat_streaming:
            self._chat_continue_after_tool(tool_call, result)

    def _chat_continue_after_tool(self, tool_call, result):
        """Continue conversation after tool execution."""
        # This would send the tool result back to the LLM for follow-up
        # For now, we just note it in the conversation
        pass

    def _chat_update_token_usage(self, usage: dict):
        """Update token usage display."""
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

        if hasattr(self, '_chat_current_token_label') and self._chat_current_token_label:
            self._chat_current_token_label.setText(f"Tokens: {total_tokens} (prompt: {prompt_tokens}, completion: {completion_tokens})")

        self.chat_token_label.setText(f"Tokens: {total_tokens}")

    def _chat_markdown_to_html(self, markdown: str) -> str:
        """Convert markdown to HTML for display."""
        if not markdown:
            return ""

        html = markdown

        # Escape HTML first
        html = html.replace("&", "&").replace("<", "<").replace(">", ">")

        # Code blocks (```lang\ncode```)
        import re
        def replace_code_block(match):
            lang = match.group(1) or ""
            code = match.group(2)
            return f'<pre style="background:#2d2d2d;color:#f8f8f2;padding:12px;border-radius:6px;overflow:auto;"><code class="language-{lang}">{code}</code></pre>'

        html = re.sub(r'```(\w*)\n(.*?)\n```', replace_code_block, html, flags=re.DOTALL)

        # Inline code
        html = re.sub(r'`([^`]+)`', r'<code style="background:#f0f0f0;padding:2px 4px;border-radius:3px;font-family:Consolas;">\1</code>', html)

        # Bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)

        # Italic
        html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)

        # Headers
        html = re.sub(r'^### (.+)$', r'<h3 style="margin:12px 0 6px 0;color:#2c3e50;">\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2 style="margin:16px 0 8px 0;color:#2c3e50;">\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h1 style="margin:20px 0 10px 0;color:#2c3e50;">\1</h1>', html, flags=re.MULTILINE)

        # Links
        html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color:#3498db;">\1</a>', html)

        # Lists
        html = re.sub(r'^\- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'(<li>.*</li>)', r'<ul style="margin:8px 0;padding-left:20px;">\1</ul>', html, flags=re.DOTALL)

        # Paragraphs
        html = html.replace('\n\n', '</p><p style="margin:8px 0;">')
        html = f'<p style="margin:8px 0;line-height:1.6;">{html}</p>'

        # Clean up empty paragraphs
        html = re.sub(r'<p style="margin:8px 0;line-height:1.6;"></p>', '', html)

        return html

    def _chat_copy_message(self, content: str):
        """Copy message content to clipboard."""
        QApplication.clipboard().setText(content)
        # Show brief tooltip
        pass

    def _chat_regenerate_response(self):
        """Regenerate the last assistant response."""
        # Remove last assistant message
        if self._chat_messages and self._chat_messages[-1]["role"] == "assistant":
            self._chat_messages.pop()
            # Remove widget
            if self._chat_messages_layout.count() > 1:
                item = self._chat_messages_layout.takeAt(self._chat_messages_layout.count() - 2)
                if item and item.widget():
                    item.widget().deleteLater()

        # Re-send last user message
        last_user_msg = None
        for msg in reversed(self._chat_messages):
            if msg["role"] == "user":
                last_user_msg = msg["content"]
                break

        if last_user_msg:
            self.chat_input.setPlainText(last_user_msg)
            self._chat_send_message()

    def _chat_scroll_to_bottom(self):
        """Scroll chat to bottom."""
        QTimer.singleShot(50, lambda: self.chat_scroll.verticalScrollBar().setValue(
            self.chat_scroll.verticalScrollBar().maximum()
        ))

    def _chat_new_conversation(self):
        """Start a new conversation."""
        # Save current conversation first
        self._chat_save_current_conversation()

        # Clear messages
        self._chat_clear_messages()
        self._chat_messages = []

        # Add welcome message
        self._chat_add_message("system", "New conversation started. How can I help you with GIS today?")

    def _chat_clear_messages(self):
        """Clear all message widgets."""
        while self._chat_messages_layout.count() > 1:  # Keep stretch
            item = self._chat_messages_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    def _chat_clear_conversation(self):
        """Clear current conversation."""
        reply = QMessageBox.question(
            self, "Clear Conversation",
            "Clear all messages in this conversation?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._chat_new_conversation()

    def _chat_save_current_conversation(self):
        """Save current conversation to config."""
        if not hasattr(self, 'config') or not self.config:
            return

        try:
            conversations_json = self.config.get("llm_conversations", "[]")
            conversations = json.loads(conversations_json) if conversations_json else []

            conversation = {
                "id": f"conv_{len(conversations) + 1}_{int(time.time())}",
                "title": self._chat_generate_title(),
                "messages": self._chat_messages,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "model": self.chat_model_combo.currentData(),
                "provider": self.config.get("llm_active_provider", "openai"),
            }

            conversations.append(conversation)
            # Keep only last 50 conversations
            if len(conversations) > 50:
                conversations = conversations[-50:]

            self.config.set("llm_conversations", json.dumps(conversations))
        except Exception:
            pass

    def _chat_generate_title(self) -> str:
        """Generate a title from the first user message."""
        for msg in self._chat_messages:
            if msg["role"] == "user":
                title = msg["content"][:50]
                if len(msg["content"]) > 50:
                    title += "..."
                return title
        return "New Conversation"

    def _chat_save_conversation(self):
        """Save conversation manually."""
        self._chat_save_current_conversation()
        QMessageBox.information(self, "Saved", "Conversation saved!")

    def _chat_load_conversation(self):
        """Load a saved conversation."""
        if not hasattr(self, 'config') or not self.config:
            return

        try:
            conversations_json = self.config.get("llm_conversations", "[]")
            conversations = json.loads(conversations_json) if conversations_json else []

            if not conversations:
                QMessageBox.information(self, "No Conversations", "No saved conversations found.")
                return

            # Show selection dialog
            from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox, QLabel

            dialog = QDialog(self)
            dialog.setWindowTitle("Load Conversation")
            dialog.setMinimumSize(500, 400)
            dialog.setModal(True)

            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel("Select a conversation to load:"))

            list_widget = QListWidget()
            for conv in reversed(conversations):  # Most recent first
                item = QListWidgetItem(f"{conv['title']} ({conv['created_at'][:10]})")
                item.setData(Qt.ItemDataRole.UserRole, conv)
                list_widget.addItem(item)
            layout.addWidget(list_widget)

            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                current_item = list_widget.currentItem()
                if current_item:
                    conv = current_item.data(Qt.ItemDataRole.UserRole)
                    self._chat_load_conversation_data(conv)

        except Exception as exc:
            QMessageBox.warning(self, "Load Failed", f"Failed to load conversation:\n{exc}")

    def _chat_load_conversation_data(self, conversation: dict):
        """Load conversation data into chat."""
        # Clear current
        self._chat_clear_messages()
        self._chat_messages = conversation.get("messages", [])

        # Restore model/provider if possible
        model = conversation.get("model")
        if model:
            idx = self.chat_model_combo.findData(model)
            if idx >= 0:
                self.chat_model_combo.setCurrentIndex(idx)

        # Reload messages
        for msg in self._chat_messages:
            if msg["role"] == "user":
                self._chat_create_user_message(msg["content"])
            elif msg["role"] == "assistant":
                self._chat_create_assistant_message(msg["content"])
            elif msg["role"] == "tool":
                self._chat_create_tool_message(msg["content"], msg.get("tool_results"))

        # Add widgets to layout
        for i in range(self._chat_messages_layout.count() - 1):
            widget = self._chat_messages_layout.itemAt(i).widget()
            if widget:
                # Already added by create methods
                pass

        self._chat_scroll_to_bottom()

    def _chat_load_default_conversation(self):
        """Load the most recent conversation on startup."""
        if not hasattr(self, 'config') or not self.config:
            return

        try:
            conversations_json = self.config.get("llm_conversations", "[]")
            conversations = json.loads(conversations_json) if conversations_json else []

            if conversations:
                # Load most recent
                self._chat_load_conversation_data(conversations[-1])
            else:
                # Show welcome
                self._chat_add_message("system", "Welcome to Universal AI GIS Studio! Ask me anything about GIS, spatial analysis, or QGIS automation.")
        except Exception:
            self._chat_add_message("system", "Welcome to Universal AI GIS Studio! Ask me anything about GIS, spatial analysis, or QGIS automation.")

    def _chat_export_conversation(self):
        """Export conversation to file."""
        from qgis.PyQt.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Conversation", "",
            "JSON Files (*.json);;Markdown Files (*.md);;Text Files (*.txt)"
        )
        if not file_path:
            return

        try:
            if file_path.endswith(".json"):
                data = {
                    "title": self._chat_generate_title(),
                    "messages": self._chat_messages,
                    "exported_at": datetime.now().isoformat(),
                    "model": self.chat_model_combo.currentData(),
                    "provider": self.config.get("llm_active_provider", "openai") if hasattr(self, 'config') and self.config else "unknown",
                }
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

            elif file_path.endswith(".md"):
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(f"# {self._chat_generate_title()}\n\n")
                    f.write(f"Exported: {datetime.now().isoformat()}\n")
                    f.write(f"Model: {self.chat_model_combo.currentData()}\n")
                    f.write(f"Provider: {self.config.get('llm_active_provider', 'openai') if hasattr(self, 'config') and self.config else 'unknown'}\n\n")
                    f.write("---\n\n")
                    for msg in self._chat_messages:
                        role = msg["role"].capitalize()
                        f.write(f"## {role}\n\n{msg['content']}\n\n")

            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    for msg in self._chat_messages:
                        f.write(f"[{msg['role'].upper()}] {msg['content']}\n\n")

            QMessageBox.information(self, "Exported", f"Conversation exported to:\n{file_path}")

        except Exception as exc:
            QMessageBox.warning(self, "Export Failed", f"Failed to export:\n{exc}")

    def _chat_show_settings(self):
        """Show chat settings dialog."""
        from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QCheckBox, QSpinBox, QDoubleSpinBox, QDialogButtonBox, QTextEdit, QFont

        dialog = QDialog(self)
        dialog.setWindowTitle("Chat Settings")
        dialog.setMinimumWidth(450)
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)

        form = QFormLayout()

        # System prompt
        system_prompt = QTextEdit()
        system_prompt.setPlainText(self.config.get("llm_default_system_prompt", "") if hasattr(self, 'config') and self.config else "")
        system_prompt.setFont(QFont("Consolas", 10))
        system_prompt.setMaximumHeight(100)
        form.addRow("Default System Prompt:", system_prompt)

        # Temperature
        temp_spin = QDoubleSpinBox()
        temp_spin.setRange(0.0, 2.0)
        temp_spin.setValue(self.config.get("llm_temperature", 0.7) if hasattr(self, 'config') and self.config else 0.7)
        temp_spin.setSingleStep(0.1)
        form.addRow("Default Temperature:", temp_spin)

        # Max tokens
        max_tokens_spin = QSpinBox()
        max_tokens_spin.setRange(100, 128000)
        max_tokens_spin.setValue(self.config.get("llm_max_tokens", 4096) if hasattr(self, 'config') and self.config else 4096)
        max_tokens_spin.setSingleStep(100)
        form.addRow("Default Max Tokens:", max_tokens_spin)

        # Streaming
        stream_cb = QCheckBox("Stream Responses")
        stream_cb.setChecked(self.config.get("llm_stream_responses", True) if hasattr(self, 'config') and self.config else True)
        form.addRow("", stream_cb)

        # Token usage
        token_cb = QCheckBox("Show Token Usage")
        token_cb.setChecked(self.config.get("llm_show_token_usage", True) if hasattr(self, 'config') and self.config else True)
        form.addRow("", token_cb)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(lambda: self._chat_apply_settings(
            system_prompt.toPlainText(), temp_spin.value(), max_tokens_spin.value(),
            stream_cb.isChecked(), token_cb.isChecked(), dialog
        ))
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.exec()

    def _chat_apply_settings(self, system_prompt: str, temperature: float, max_tokens: int,
                              stream: bool, token_usage: bool, dialog):
        """Apply chat settings."""
        if hasattr(self, 'config') and self.config:
            self.config.set("llm_default_system_prompt", system_prompt)
            self.config.set("llm_temperature", temperature)
            self.config.set("llm_max_tokens", max_tokens)
            self.config.set("llm_stream_responses", stream)
            self.config.set("llm_show_token_usage", token_usage)

            # Update UI
            self.llm_global_system_prompt.setPlainText(system_prompt)
            self.llm_global_temperature.setValue(temperature)
            self.llm_global_max_tokens.setValue(max_tokens)
            self.llm_stream_responses.setChecked(stream)
            self.llm_show_token_usage.setChecked(token_usage)

            self.chat_temperature.setValue(temperature)

        dialog.accept()

    def closeEvent(self, event):
        """Clean up on close."""
        # Stop any ongoing generation
        self._chat_streaming = False

        # Save current conversation
        self._chat_save_current_conversation()

        if self._ws_connected:
            self.ws_client.disconnect()
        super().closeEvent(event)