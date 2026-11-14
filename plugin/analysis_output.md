# Plugin Folder Analysis — Universal AI GIS Studio

**Task:** task-25  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector-2 agent  
**Context:** release/ (task-24) analysis read prior

---

## 1. Folder Structure

```
plugin/
└── universal_ai_gis/
    ├── __init__.py              (36 lines) — Package init, QGIS entry point
    ├── plugin.py                (441 lines) — Main plugin class, QGIS integration
    ├── main_window.py           (2500+ lines) — Dock widget UI with 21 panels
    ├── metadata.txt             (12 lines) — QGIS plugin metadata
    ├── about.html               (194 lines) — About dialog HTML
    ├── compat.py                (27 lines) — PyQt6/QGIS 4.x compatibility
    ├── constants.py             (28 lines) — Plugin constants & paths
    ├── configurator.py          (498 lines) — MCP client configuration dialog
    ├── resources/
    │   └── icon.png             — Plugin icon
    └── __pycache__/             — Compiled bytecode
```

---

## 2. Architecture Overview

### Plugin Entry Points
| File | Purpose |
|------|---------|
| `__init__.py` | `classFactory(iface)` — QGIS plugin factory, path setup for bundled modules |
| `plugin.py` | `UniversalAIGISPlugin` — Main plugin class, toolbar, socket server lifecycle |

### Key Design Pattern: Path Injection
Both `__init__.py` and `plugin.py` inject the plugin directory into `sys.path` **before** importing internal modules. This allows the plugin to bundle and use `bridge/`, `core/`, `database/`, etc. as packages inside the QGIS Python environment.

```python
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)
```

**Environment Override:** `UAGIS_PROJECT_ROOT` env var allows pointing to an external source tree (useful for development).

---

## 3. Core Components

### 3.1 UniversalAIGISPlugin (plugin.py)
**Responsibilities:**
- QGIS toolbar with dropdown menu (port selector, auto-start checkbox, configure action)
- SocketServer lifecycle (start/stop on port 9876 default)
- Client connection badge on toolbar icon
- First-run welcome dialog
- Stale MCP config detection (removes `--refresh-package` from client configs)

**Dependencies:** `bridge.socket_server.SocketServer`, `configurator.MCPConfiguratorDialog`

**Settings Persistence:** `QgsSettings` under prefix `uagis/mcp`

### 3.2 UniversalAIGISMainWindow (main_window.py) — **2500+ lines**
**21 Functional Panels:**
| Panel | Purpose |
|-------|---------|
| Dashboard | System status, quick actions |
| AI Chat | Streaming chat with markdown, code highlighting, tool calls |
| Live Screen | Desktop capture, periodic screenshots, WebSocket streaming |
| AI Cursor | Visual overlay: smooth move, click ripple, trails, emergency stop |
| AI Connections | 7 tabs: OpenCode, Codex, MCP Servers, Bridge, WebSocket, LLM Models, Version Info |
| API Providers | LLM API key management |
| MCP Manager | External MCP server configs with trust levels |
| Agent Manager | 29 built-in specialized GIS agents |
| Skill Manager | Import/validate custom skills |
| GIS Clusters | Browse/execute M01–M25 cluster tools |
| Georeferencing | Auto georeference with CV + GCP |
| GCP Intelligence | Generate, validate, optimize Ground Control Points |
| Workflow Builder | Visual GIS workflow creation |
| Algorithm Discovery | Explore QGIS Processing algorithms |
| Data Manager | Load, inspect, manage layers |
| Quality Control | Geometry, topology, data validation |
| Task History | Job execution logs, audit trail |
| Security | Permissions, approvals, audit logs |
| Settings | Bridge, WebSocket, auth configuration |
| Macro & Visual Verification | Record/playback macros, SSIM image comparison |

**Key Classes:**
- `BridgeClient` — HTTP/JSON-RPC client to bridge server (port 8765)
- `WebSocketClient` — Real-time screen streaming (port 8767)
- `MCPServerDialog` — Add/edit MCP server configs (stdio/HTTP)

**Emergency Stop:** `Ctrl+Shift+X` global shortcut, red toolbar button

### 3.3 MCPConfiguratorDialog (configurator.py)
**Supported Clients (14):**
- Claude Desktop, Claude Code, Cursor, VS Code, Windsurf, Zed
- Codex CLI, OpenCode, LM Studio, Hermes, Kimi Code
- Gemini CLI, Qwen Code, GitHub Copilot CLI

**Features:**
- Generates client-specific MCP JSON config
- Auto-applies to client config files (atomic writes)
- Token authentication support
- `--refresh-package` detection/removal utility

---

## 4. Metadata & Packaging

### metadata.txt
```ini
name=universal_ai_gis
version=1.0.0
qgisMinimumVersion=3.0
qgisMaximumVersion=4.99
license=MIT
icon=resources/icon.png
about=about.html
```
**Issues:** `homepage` and `repository` point to `https://example.com/` (placeholder)

---

## 5. Dependencies

### Internal (bundled via sys.path injection)
- `bridge.socket_server` — SocketServer for MCP
- `core/`, `database/`, `engines/`, `clusters/`, `agents/`, `skills/`, `workflows/`, `extensions/`, `monitoring/`, `security/`, `utils/`, `integrations/`

### External (PyQt6/QGIS)
- `qgis.core`, `qgis.PyQt.QtCore/QtGui/QtWidgets/QtNetwork`
- `websockets` (optional, for WebSocket streaming)

---

## 6. Issues Found

### 🔴 Critical
| Issue | Location | Description |
|-------|----------|-------------|
| **Monolithic main_window.py** | main_window.py | 2500+ lines, 21 panels in one class — violates SRP, hard to maintain/test |
| **Duplicate websockets import** | main_window.py:35-39, 53-57 | Imported twice with same try/except |
| **Hardcoded placeholder URLs** | metadata.txt:9-10 | homepage/repository = example.com |
| **Missing icons** | plugin.py:106, 265 | References `icons/icon.png` and `icons/icon_active.png` but `icons/` folder doesn't exist |

### 🟡 Medium
| Issue | Location | Description |
|-------|----------|-------------|
| **No plugin tests** | plugin/ | No unit/integration tests for plugin logic |
| **Tight coupling** | main_window.py | Direct imports of `integrations.llm_providers` — fails if not available |
| **Configurator duplication** | configurator.py:474-498 | `_qgis_entry_has_refresh` and `_remove_refresh_from_entry` duplicated from module level |
| **Large __init__.py responsibility** | __init__.py | Does path setup AND imports plugin class — should separate |

### 🟢 Low
| Issue | Location | Description |
|-------|----------|-------------|
| **Version sync** | constants.py:28, metadata.txt:3, __init__.py:29 | Version defined in 3 places |
| **Unused imports** | main_window.py | `QSysInfo`, `QEvent`, `QRect`, `QBuffer`, `QByteArray`, `QIODevice`, `QEventLoop`, `QRegularExpression` — may be unused |
| **Missing type hints** | Across plugin | Most methods lack type annotations |

---

## 7. Recommendations

### Priority 1 (Immediate)
1. **Create `icons/` folder** with `icon.png` and `icon_active.png` (referenced in plugin.py)
2. **Fix metadata.txt** — Update homepage/repository to real URLs
3. **Remove duplicate websockets import** in main_window.py

### Priority 2 (Short-term)
4. **Split main_window.py** into:
   - `main_window.py` — Core window, navigation, toolbar
   - `panels/` subpackage — One file per panel (dashboard.py, ai_chat.py, etc.)
   - `panels/__init__.py` — Panel registry
5. **Extract configurator utilities** — Move `_qgis_entry_has_refresh`, `_remove_refresh_from_entry`, `write_json_atomic` to `configurator_utils.py`
6. **Add version single source** — Read version from `pyproject.toml` or `__version__` in one place

### Priority 3 (Medium-term)
7. **Add plugin tests** — Unit tests for plugin logic, integration tests for QGIS hook
8. **Add type hints** — Full typing for public APIs
9. **Lazy-load heavy panels** — Defer panel creation until first navigation
10. **Decouple LLM providers** — Use plugin system instead of direct import

---

## 8. Output for Next Task (.github/)

**Context to pass forward:**
- Plugin is a QGIS 4.x (PyQt6) plugin with entry point `classFactory`
- Bundles entire backend via sys.path injection
- Main UI is a 21-panel dock widget (main_window.py ~2500 lines)
- MCP integration via SocketServer (port 9876) and configurator for 14 AI clients
- No CI/CD workflows exist yet (.github/ folder to be analyzed next)
- Version hardcoded in multiple places (1.0.0)
- Missing icons folder referenced in code
- No automated tests for plugin layer

---

*End of plugin/ folder analysis*