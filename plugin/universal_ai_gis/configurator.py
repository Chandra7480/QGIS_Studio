"""Universal AI GIS Studio — MCP Client Configurator Dialog.

Helps users configure their AI clients (Claude Code, Codex, Cursor, etc.)
to connect to the QGIS MCP server.
"""

import contextlib
import json
import os
import shutil
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, Optional

from qgis.PyQt.QtCore import Qt, QUrl, QCoreApplication
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QLineEdit,
    QFont,
)

tr = QCoreApplication.translate

from .constants import SETTINGS_PREFIX, DEFAULT_PORT
from .compat import (
    MSG_CRITICAL,
    MSG_INFO,
    MSG_WARNING,
    MSGBOX_ACCEPT_ROLE,
    MSGBOX_REJECT_ROLE,
    MSGBOX_QUESTION,
)


def _client_config_registry(repo_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Return a registry of known MCP client config locations."""
    home = Path.home()
    return {
        "claude-desktop": {
            "path": home / ".config" / "claude" / "claude_desktop_config.json",
            "key": "mcpServers",
            "print_only": False,
        },
        "cursor": {
            "path": home / ".cursor" / "mcp.json",
            "key": "mcpServers",
            "print_only": False,
        },
        "vscode": {
            "path": home / ".vscode" / "mcp.json",
            "key": "mcpServers",
            "print_only": False,
        },
        "windsurf": {
            "path": home / ".windsurf" / "mcp.json",
            "key": "mcpServers",
            "print_only": False,
        },
        "zed": {
            "path": home / ".config" / "zed" / "settings.json",
            "key": "mcp",
            "print_only": False,
        },
        "claude-code": {
            "path": home / ".claude.json",
            "key": "mcpServers",
            "print_only": False,
        },
        "codex": {
            "path": home / ".codex" / "config.toml",
            "key": "mcp_servers",
            "print_only": False,
        },
        "opencode": {
            "path": Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "opencode" / "config.json",
            "key": "mcp",
            "print_only": False,
        },
        "hermes": {
            "path": Path(os.environ.get("APPDATA", home / "AppData" / "Roaming")) / "Hermes" / "config.yaml",
            "key": "mcpServers",
            "print_only": False,
        },
        "kimi": {
            "path": home / ".kimi-code" / "mcp.json",
            "key": "mcpServers",
            "print_only": False,
        },
        "gemini": {
            "path": home / ".gemini" / "settings.json",
            "key": "mcpServers",
            "print_only": False,
        },
        "qwen": {
            "path": home / ".qwen" / "mcp.json",
            "key": "mcpServers",
            "print_only": False,
        },
        "copilot-cli": {
            "path": Path(os.environ.get("COPILOT_HOME", home / ".copilot")) / "mcp-config.json",
            "key": "mcpServers",
            "print_only": False,
        },
        "lmstudio": {
            "path": home / ".lmstudio" / "mcp.json",
            "key": "mcpServers",
            "print_only": False,
        },
    }


def _qgis_entry_has_refresh(entry: Dict) -> bool:
    """Check if a qgis MCP entry uses --refresh-package."""
    if not entry:
        return False
    args = entry.get("args", [])
    return "--refresh-package" in args


def _remove_refresh_from_entry(entry: Dict) -> None:
    """Remove --refresh-package from a qgis MCP entry's args."""
    if not entry:
        return
    args = entry.get("args", [])
    if "--refresh-package" in args:
        idx = args.index("--refresh-package")
        del args[idx:idx + 2]


def write_json_atomic(path: Path, data: Dict) -> None:
    """Write JSON atomically using a temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)


class MCPConfiguratorDialog(QDialog):
    """Dialog for configuring MCP clients to connect to this QGIS instance."""

    def __init__(self, iface, parent, server=None, start_server=None):
        super().__init__(parent)
        self.iface = iface
        self.server = server
        self.start_server = start_server
        self.setWindowTitle("MCP Setup & Configurator")
        self.setMinimumWidth(500)
        self._build_ui()
        self._load_existing_configs()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(
            tr("<h2>MCP Client Configuration</h2>")
            + tr("<p>Select your AI client to generate or update its MCP configuration.</p>")
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        client_row = QHBoxLayout()
        client_row.addWidget(QLabel(tr("Client:")))
        self.client_combo = QComboBox()
        self.client_combo.addItems([
            tr("Claude Desktop"),
            tr("Claude Code"),
            tr("Cursor"),
            tr("VS Code"),
            tr("Windsurf"),
            tr("Zed"),
            tr("Codex CLI"),
            tr("OpenCode"),
            tr("LM Studio"),
            tr("Hermes"),
            tr("Kimi Code"),
            tr("Gemini CLI"),
            tr("Qwen Code"),
            tr("GitHub Copilot CLI"),
        ])
        self.client_combo.currentTextChanged.connect(self._on_client_changed)
        client_row.addWidget(self.client_combo)
        layout.addLayout(client_row)

        port_row = QHBoxLayout()
        self.port_label = QLabel(tr("Server port: {port}").format(port=DEFAULT_PORT))
        self.port_label.setStyleSheet("font-family: monospace; font-weight: bold;")
        port_row.addWidget(self.port_label)
        port_row.addStretch()
        layout.addLayout(port_row)

        auth_row = QHBoxLayout()
        auth_row.addWidget(QLabel(tr("Auth token:")))
        self.token_edit = QLineEdit()
        self.token_edit.setPlaceholderText(tr("Optional: set QGIS_MCP_TOKEN for authentication"))
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        auth_row.addWidget(self.token_edit)
        layout.addLayout(auth_row)

        self.show_token_cb = QCheckBox(tr("Show token"))
        self.show_token_cb.toggled.connect(
            lambda checked: self.token_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        layout.addWidget(self.show_token_cb)

        layout.addWidget(QLabel(tr("Generated config (copy to your client config):")))
        self.config_output = QTextEdit()
        self.config_output.setReadOnly(True)
        self.config_output.setFont(QFont("Consolas", 10))
        self.config_output.setMinimumHeight(200)
        layout.addWidget(self.config_output)

        btn_layout = QHBoxLayout()
        self.copy_btn = QPushButton(tr("Copy to Clipboard"))
        self.copy_btn.clicked.connect(self._copy_config)
        btn_layout.addWidget(self.copy_btn)

        self.apply_btn = QPushButton(tr("Apply to Client Config"))
        self.apply_btn.clicked.connect(self._apply_config)
        btn_layout.addWidget(self.apply_btn)

        self.start_btn = QPushButton(tr("Start Server"))
        self.start_btn.clicked.connect(self._start_server)
        btn_layout.addWidget(self.start_btn)

        btn_layout.addStretch()

        close_btn = QPushButton(tr("Close"))
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _on_client_changed(self, client_name):
        self._generate_config(client_name)

    def _generate_config(self, client_name):
        """Generate MCP config for the selected client."""
        port = DEFAULT_PORT
        token = self.token_edit.text().strip()

        # Use a realistic local command; the AI client must have the repo installed.
        # This avoids the broken placeholder GitHub package URLs used by the old config.
        base_args = ["-m", "mcp_server.main", "--transport", "stdio"]
        if token:
            base_args.extend(["--token", token])

        configs = {
            "Claude Desktop": {
                "mcpServers": {
                    "uagis": {
                        "command": "python",
                        "args": base_args,
                    }
                }
            },
            "Claude Code": {
                "mcpServers": {
                    "uagis": {
                        "command": "python",
                        "args": base_args,
                    }
                }
            },
            "Cursor": {
                "mcpServers": {
                    "uagis": {
                        "command": "python",
                        "args": base_args,
                    }
                }
            },
            "VS Code": {
                "mcpServers": {
                    "uagis": {
                        "command": "python",
                        "args": base_args,
                    }
                }
            },
            "Windsurf": {
                "mcpServers": {
                    "uagis": {
                        "command": "python",
                        "args": base_args,
                    }
                }
            },
            "Zed": {
                "mcpServers": {
                    "uagis": {
                        "command": "python",
                        "args": base_args,
                    }
                }
            },
            "Codex CLI": {
                "mcpServers": {
                    "uagis": {
                        "command": "python",
                        "args": base_args,
                    }
                }
            },
            "OpenCode": {
                "mcp": {
                    "uagis": {
                        "type": "local",
                        "command": ["python", *base_args],
                        "enabled": True,
                    }
                }
            },
            "LM Studio": {
                "mcpServers": {
                    "uagis": {
                        "command": "python",
                        "args": base_args,
                    }
                }
            },
            "Hermes": {
                "mcpServers": {
                    "uagis": {
                        "command": "python",
                        "args": base_args,
                    }
                }
            },
            "Kimi Code": {
                "mcpServers": {
                    "uagis": {
                        "command": "python",
                        "args": base_args,
                    }
                }
            },
            "Gemini CLI": {
                "mcpServers": {
                    "uagis": {
                        "command": "python",
                        "args": base_args,
                    }
                }
            },
            "Qwen Code": {
                "mcpServers": {
                    "uagis": {
                        "command": "python",
                        "args": base_args,
                    }
                }
            },
            "GitHub Copilot CLI": {
                "mcpServers": {
                    "uagis": {
                        "command": "python",
                        "args": base_args,
                    }
                }
            },
        }

        config = configs.get(client_name, {})
        self.config_output.setPlainText(json.dumps(config, indent=2))

    def _load_existing_configs(self):
        """Load and display existing configs if any."""
        pass

    def _copy_config(self):
        """Copy config to clipboard."""
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.clipboard().setText(self.config_output.toPlainText())
        QMessageBox.information(self, tr("Copied"), tr("Configuration copied to clipboard!"))

    def _apply_config(self):
        """Apply config to the selected client's config file."""
        client_name = self.client_combo.currentText()
        config_text = self.config_output.toPlainText()

        try:
            config = json.loads(config_text)
        except json.JSONDecodeError:
            QMessageBox.warning(self, tr("Invalid Config"), tr("Generated config is not valid JSON."))
            return

        repo_dir = Path(__file__).resolve().parent.parent
        registry = _client_config_registry(repo_dir)

        client_map = {
            "Claude Desktop": "claude-desktop",
            "Claude Code": "claude-code",
            "Cursor": "cursor",
            "VS Code": "vscode",
            "Windsurf": "windsurf",
            "Zed": "zed",
            "Codex CLI": "codex",
            "OpenCode": "opencode",
            "LM Studio": "lmstudio",
            "Hermes": "hermes",
            "Kimi Code": "kimi",
            "Gemini CLI": "gemini",
            "Qwen Code": "qwen",
            "GitHub Copilot CLI": "copilot-cli",
        }

        key = client_map.get(client_name)
        if not key or key not in registry:
            QMessageBox.warning(self, tr("Unsupported"), tr("Auto-config not supported for {client_name}.").format(client_name=client_name))
            return

        info = registry[key]
        path = info["path"]
        json_key = info["key"]

        data = {}
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    if path.suffix == ".toml":
                        import tomli
                        data = tomli.loads(f.read())
                    else:
                        data = json.load(f)
            except (json.JSONDecodeError, OSError, ImportError):
                data = {}

        if json_key not in data:
            data[json_key] = {}
        data[json_key]["uagis"] = config.get("mcpServers", {}).get("uagis", config.get("mcp", {}).get("uagis", {}))

        try:
            write_json_atomic(path, data)
            QMessageBox.information(self, tr("Success"), tr("Updated {path}").format(path=path))
        except OSError as e:
            QMessageBox.critical(self, tr("Error"), tr("Failed to write config: {error}").format(error=e))

    def _start_server(self):
        """Start the server via the plugin."""
        if self.start_server:
            server = self.start_server()
            if server:
                QMessageBox.information(self, "Started", f"Server started on port {server.port}")
            else:
                QMessageBox.warning(self, "Failed", f"Could not start server: {server.start_error if server else 'unknown'}")


def _qgis_entry_has_refresh(entry: Dict) -> bool:
    """Check if a qgis MCP entry uses --refresh-package."""
    if not entry:
        return False
    args = entry.get("args", [])
    return "--refresh-package" in args


def _remove_refresh_from_entry(entry: Dict) -> None:
    """Remove --refresh-package from a qgis MCP entry's args."""
    if not entry:
        return
    args = entry.get("args", [])
    if "--refresh-package" in args:
        idx = args.index("--refresh-package")
        del args[idx:idx + 2]


def write_json_atomic(path: Path, data: Dict) -> None:
    """Write JSON atomically using a temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)
