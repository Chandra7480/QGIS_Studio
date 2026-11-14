# Universal AI GIS Studio — Architecture Documentation

**Version:** 1.0.0  
**Last Updated:** 2026-11-12

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Data Flow](#data-flow)
4. [MCP Server Internals](#mcp-server-internals)
5. [QGIS Bridge Internals](#qgis-bridge-internals)
6. [Plugin Architecture](#plugin-architecture)
7. [Communication Protocols](#communication-protocols)
8. [Security Model](#security-model)
9. [Threading & Concurrency](#threading--concurrency)
10. [Database & Persistence](#database--persistence)
11. [Extension Points](#extension-points)

---

## System Overview

Universal AI GIS Studio is an **MCP-first AI-controlled GIS automation ecosystem** integrated with QGIS Desktop. It enables external AI assistants (OpenCode, Codex, or any MCP-compatible client) to control QGIS through natural language while the platform provides actual GIS execution, visual interaction, verification, and control.

### Core Principle

> **AI provides reasoning and decision-making. Universal AI GIS Studio provides actual GIS execution, visual interaction, verification, and control.**

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│  EXTERNAL AI CLIENTS                                                │
│  (OpenCode · Codex · MCP-compatible clients · Optional API clients) │
└────────────────────┬────────────────────────────────────────────────┘
                     │ MCP (stdio / Streamable HTTP)
┌────────────────────▼────────────────────────────────────────────────┐
│  UNIVERSAL MCP SERVER                                               │
│  • Tool registry · Schemas · Transports · Permission gating        │
│  Namespaces: qgis.system, qgis.project, qgis.layers, … qgis.history│
└────────────────────┬────────────────────────────────────────────────┘
                     │ Authenticated localhost IPC/HTTP
┌────────────────────▼────────────────────────────────────────────────┐
│  QGIS BRIDGE (runs inside QGIS Desktop)                             │
│  • Main-thread-safe PyQGIS executor · Job queue · Health monitoring │
│  • Request IDs · Structured responses · Cancellation · Reconnection │
└────────────────────┬────────────────────────────────────────────────┘
                     │ Native PyQGIS API calls (QGIS main thread)
┌────────────────────▼────────────────────────────────────────────────┐
│  QGIS DESKTOP 4.2.3 (PyQGIS, GDAL/OGR 3.13.3, Qt6)                  │
│  QgsProject · QgsMapCanvas · QgsVectorLayer · QgsRasterLayer ·     │
│  QgsProcessing · QgsLayout · QgsCoordinateReferenceSystem · …       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component Architecture

### 1. Universal MCP Server (`mcp_server/`)

**Location:** `Universal-AI-GIS-Studio/mcp_server/`

**Responsibilities:**
- Exposes 35+ tools across 17 namespaces via MCP protocol
- Manages stdio and Streamable HTTP transports
- Validates tool input/output against strict JSON schemas
- Enforces permission gating per tool
- Dispatches tool calls to QGIS Bridge via HTTP
- Returns verified, structured results (never fabricated success)

**Key Files:**
| File | Purpose |
|------|---------|
| `main.py` | Entry point, transport selection, argument parsing |
| `server.py` | `UniversalMCPServer` class, handler setup, tool execution |
| `registry.py` | `ToolRegistry`, `ToolSpec`, all tool definitions (single source of truth) |
| `qgis_client.py` | HTTP client for Bridge communication |
| `tools/*.py` | Cluster-specific tool implementations (wired to bridge) |

**Transport Support:**
- **stdio**: For OpenCode, Codex, local MCP clients (subprocess)
- **Streamable HTTP**: For web clients, remote access (requires uvicorn)

### 2. QGIS Bridge (`bridge/`)

**Location:** `Universal-AI-GIS-Studio/bridge/`

**Responsibilities:**
- Runs **inside QGIS Desktop** as a plugin (in-process)
- Hosts HTTP server on localhost (default port 8765)
- Receives authenticated dispatch requests from MCP Server
- Executes PyQGIS operations on QGIS main thread
- Manages job queue with cancellation support
- Returns structured responses with verification states
- Health monitoring and reconnection support

**Key Files:**
| File | Purpose |
|------|---------|
| `request_handler.py` | HTTP request handling, auth, JSON parsing |
| `protocol.py` | Request/Response dataclasses, verification states |
| `dispatcher.py` | Tool dispatch to cluster handlers (not yet created) |

**Why In-Process?**
- GUI operations (canvas, layers, dialogs, windows) **must** run on QGIS main thread
- Avoids cross-process PyQGIS marshaling complexity
- Direct access to `qgis.core`, `qgis.gui`, `qgis.processing`, `qgis.PyQt`

### 3. QGIS Plugin (`plugin/universal_ai_gis/`)

**Location:** `Universal-AI-GIS-Studio/plugin/universal_ai_gis/`

**Responsibilities:**
- QGIS plugin entry point (`__init__.py`, `metadata.txt`)
- Starts/stops the Bridge HTTP server
- Provides QGIS GUI integration (dock widgets, menus, toolbars)
- Manages plugin settings (bridge port, auth token)
- Handles QGIS lifecycle events (project open/close, layer changes)

### 4. GIS Clusters (`clusters/m01_*` through `m25_*`)

**Location:** `Universal-AI-GIS-Studio/clusters/`

**Architecture:** 25 functional clusters (M01–M25), each implementing `ClusterBase`

| Cluster | Domain | Key Operations |
|---------|--------|----------------|
| M01 | Data Acquisition | Discover, import, download datasets |
| M02 | Data Management | Copy, rename, delete, organize |
| M03 | Vector Analysis | Buffer, clip, dissolve, join, spatial queries |
| M04 | Raster Analysis | Calculator, reproject, mosaic, statistics |
| M05 | Georeferencing | GCP generation, validation, transformation |
| M06 | CRS/Projection | Reproject, transform, validate CRS |
| M07 | Spatial Analysis | Overlay, proximity, density, interpolation |
| M08 | Terrain Analysis | Hillshade, slope, aspect, viewshed, contours |
| M09 | Hydrology | Watersheds, flow accumulation, stream networks |
| M10 | Network Analysis | Routing, service areas, connectivity |
| M11 | Remote Sensing | Band math, indices, classification |
| M12 | Classification | Supervised/unsupervised, accuracy assessment |
| M13 | Change Detection | Temporal comparison, differencing |
| M14 | 3D Visualization | 3D scenes, extrusion, point clouds |
| M15 | LiDAR Processing | LAS/LAZ, classification, DTM/DSM |
| M16 | Survey/GNSS | GNSS processing, coordinate conversion |
| M17 | Cadastral | Parcels, boundaries, topology |
| M18 | Cartography | Symbology, labeling, layouts, export |
| M19 | Temporal | Time manager, animation, temporal queries |
| M20 | Database | PostGIS, GeoPackage, spatial SQL |
| M21 | Web GIS | QGIS2Web, vector tiles, Mapbox GL |
| M22 | Field Data | QField, Input, offline sync |
| M23 | Automation | Workflows, batch processing, scheduling |
| M24 | AI/ML | GeoAI, feature extraction, prediction |
| M25 | Validation | Geometry validation, topology checks |

**Cluster Interface:**
```python
class ClusterBase:
    CLUSTER_ID = "M18"
    CLUSTER_NAME = "Cartography"
    OPERATIONS = {"create_layout": "Create a map layout", ...}
    
    def execute(self, operation: str, params: dict) -> ClusterResult:
        # Dispatch to _operation_method(params)
        pass
    
    def discover_algorithm(self, name_patterns: list[str]) -> Optional[str]:
        # Dynamic algorithm discovery via QgsApplication.processingRegistry()
        pass
    
    def run_algorithm(self, algorithm_id: str, parameters: dict) -> dict:
        # Execute via processing.run()
        pass
```

**Key Principle:** **Dynamic algorithm discovery** — no hardcoded algorithm IDs. Clusters use `discover_algorithm()` to find algorithms at runtime.

---

## Data Flow

### Natural Language → GIS Action (Complete Flow)

```
1. User: "Load parcels.gpkg and buffer by 100m"
                    │
                    ▼
2. AI Host (OpenCode) calls MCP tool: qgis.layers.load
   {
     "method": "tools/call",
     "params": {"name": "qgis.layers.load", "arguments": {"path": "parcels.gpkg"}}
   }
                    │
                    ▼
3. MCP Server (stdio/HTTP)
   - Validates input against tool schema
   - Checks permissions (qgis:layer:write)
   - Generates request_id: "req_abc123"
   - POSTs to Bridge: http://127.0.0.1:8765/dispatch
                    │
                    ▼
4. QGIS Bridge (in QGIS process)
   - Validates auth token
   - Parses request, creates Request object
   - Dispatches to cluster handler (M01 Data Acquisition)
   - Executes PyQGIS on MAIN THREAD via QMetaObject.invokeMethod
   - Layer loaded, validity verified
   - Returns Response with verification_state
                    │
                    ▼
5. MCP Server receives Bridge response
   - Checks verification_state
   - Formats MCP-compliant response
   - Returns to AI Host
                    │
                    ▼
6. AI Host calls qgis.algorithms.execute (native:buffer)
   - Same flow: validation → Bridge → Cluster M03 → PyQGIS → verification
                    │
                    ▼
7. Verification Engine checks:
   - Output exists (file/layer created)
   - Output valid (geometry valid, CRS correct)
   - Feature count matches expectations
   - Returns SUCCESS / PARTIAL_SUCCESS / FAILED / NEEDS_REVIEW
                    │
                    ▼
8. AI Host receives verified result, continues conversation
```

### Request/Response Protocol

**MCP Server → Bridge (HTTP POST /dispatch):**
```json
{
  "request_id": "req_abc123def",
  "tool": "qgis.layers.load",
  "params": {"path": "D:/data/parcels.gpkg"},
  "timeout_seconds": 300,
  "require_approval": false,
  "metadata": {}
}
```

**Bridge → MCP Server (HTTP Response):**
```json
{
  "request_id": "req_abc123def",
  "status": "ok",
  "result": {
    "id": "parcels_abc123",
    "name": "parcels",
    "type": "vector",
    "valid": true,
    "crs": "EPSG:4326"
  },
  "error": null,
  "verification_state": "SUCCESS",
  "job_id": "job_xyz789",
  "timestamp": "2026-11-12T08:00:00Z"
}
```

**Error Response:**
```json
{
  "request_id": "req_abc123def",
  "status": "error",
  "result": {},
  "error": {
    "code": "LAYER_INVALID",
    "message": "Failed to load layer: not a valid vector dataset",
    "context": {"path": "D:/data/bad_file.shp"}
  },
  "verification_state": "FAILED",
  "job_id": null,
  "timestamp": "2026-11-12T08:00:00Z"
}
```

### Verification States

| State | Code | Meaning | When Used |
|-------|------|---------|-----------|
| `SUCCESS` | 200 | Operation completed and fully verified | Output exists, valid, correct |
| `PARTIAL_SUCCESS` | 200 | Operation ran but verification incomplete | Layout created but not exported |
| `FAILED` | 400/500 | Operation failed | Layer invalid, algorithm error |
| `NEEDS_REVIEW` | 200 | Human review required | Georeferencing residuals high |
| `CANCELLED` | 200 | Job cancelled by user/timeout | Long-running job stopped |

**Rule:** AI must **never** infer success from submission alone. Always check `verification_state`.

---

## MCP Server Internals

### UniversalMCPServer Class (`server.py`)

```python
class UniversalMCPServer:
    def __init__(self, bridge_url: str, auth_token: str, name: str):
        self.client = QgisBridgeClient(base_url=bridge_url, auth_token=auth_token)
        self.registry = build_registry()  # ToolRegistry with 35 tools
        self.server = Server(name)
        self._setup_handlers()
    
    def _setup_handlers(self):
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            # Convert ToolSpec to MCP Tool with inputSchema
            pass
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> List[TextContent]:
            spec = self.registry.get(name)
            return self._execute_tool(spec, arguments)
    
    def _execute_tool(self, spec: ToolSpec, params: dict) -> List[TextContent]:
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        result = self.client.dispatch(
            tool=spec.name, params=params, request_id=request_id,
            timeout_seconds=spec.timeout_seconds
        )
        # Check verification_state, raise MCPError on failure
        # Return structured JSON as TextContent
```

### Tool Registry (`registry.py`)

**Single Source of Truth** — All 35 tools defined here with:
- Strict input/output JSON schemas (`additionalProperties: false`)
- Permission requirements
- Timeout values
- Approval requirements
- Verification rules

```python
@dataclass
class ToolSpec:
    name: str                      # "qgis.system.inspect"
    namespace: str                 # "qgis.system"
    description: str
    input_schema: dict             # JSON Schema
    output_schema: dict            # JSON Schema
    permissions: list[str]         # ["qgis:read"]
    timeout_seconds: int           # 300
    require_approval: bool         # False
    verification_rules: list[str]  # ["file_exists", "layer_valid"]
```

### QGIS Bridge Client (`qgis_client.py`)

```python
class QgisBridgeClient:
    def __init__(self, base_url: str, auth_token: str, timeout_seconds: int):
        self.base_url = base_url  # http://127.0.0.1:8765
        self.auth_token = auth_token
        self.timeout_seconds = timeout_seconds
    
    def dispatch(self, tool: str, params: dict, request_id: str,
                 timeout_seconds: int = None) -> dict:
        # POST to /dispatch with auth header
        # Returns parsed JSON response
        pass
    
    def health(self) -> dict:
        # GET /health
        pass
```

---

## QGIS Bridge Internals

### Request Handler (`request_handler.py`)

```python
class BridgeRequestHandler(BaseHTTPRequestHandler):
    dispatcher = None  # Injected: Dispatcher instance
    auth_token = None  # Injected: auth token string
    
    def do_POST(self):
        if self.path == "/dispatch":
            # 1. Check auth
            # 2. Parse JSON body
            # 3. Validate request_id, tool
            # 4. Create Request object
            # 5. Call dispatcher.dispatch(req)
            # 6. Return Response as JSON
        elif self.path == "/health":
            # Return {"status": "ok"}
```

### Protocol (`protocol.py`)

```python
# Verification States
VERIFICATION_SUCCESS = "SUCCESS"
VERIFICATION_PARTIAL = "PARTIAL_SUCCESS"
VERIFICATION_FAILED = "FAILED"
VERIFICATION_NEEDS_REVIEW = "NEEDS_REVIEW"
VERIFICATION_CANCELLED = "CANCELLED"

@dataclass
class Request:
    request_id: str
    tool: str
    params: dict = field(default_factory=dict)
    timeout_seconds: int = 300
    require_approval: bool = False
    metadata: dict = field(default_factory=dict)

@dataclass
class Response:
    request_id: str
    status: str  # 'ok' | 'error'
    result: Optional[dict] = None
    error: Optional[dict] = None
    verification_state: Optional[str] = None
    job_id: Optional[str] = None
    timestamp: str = field(default_factory=utc_now_iso)
```

### Dispatcher (Planned)

The dispatcher will:
1. Map tool names to cluster operations (e.g., `qgis.layers.load` → `M01DataAcquisition.execute("load_layer", params)`)
2. Execute on QGIS main thread using `QMetaObject.invokeMethod` or `QgsTask`
3. Handle long-running jobs with progress reporting
4. Support cancellation via job_id
5. Return structured Response with verification

---

## Plugin Architecture

### Plugin Entry Point

```python
# plugin/universal_ai_gis/__init__.py
def classFactory(iface):
    from .plugin import UniversalAIGISPlugin
    return UniversalAIGISPlugin(iface)
```

### Plugin Class Responsibilities

```python
class UniversalAIGISPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.bridge_server = None
        self.settings = PluginSettings()
    
    def initGui(self):
        # Add menu actions, toolbar, dock widgets
        # Start bridge server on configured port
        pass
    
    def unload(self):
        # Stop bridge server
        # Remove GUI elements
        pass
    
    def start_bridge(self):
        # Initialize BridgeRequestHandler with dispatcher
        # Start HTTP server in background thread
        pass
```

### Settings Management

```python
class PluginSettings:
    BRIDGE_PORT = 8765
    BRIDGE_HOST = "127.0.0.1"
    AUTH_TOKEN = ""  # Optional, generated on first run
    ALLOWED_ORIGINS = ["http://127.0.0.1:8766"]
    
    def load(self): ...
    def save(self): ...
```

---

## Communication Protocols

### MCP Protocol (stdio / Streamable HTTP)

**Based on:** Model Context Protocol Specification 2024-11-05

**Transports:**
1. **stdio**: JSON-RPC over stdin/stdout (OpenCode, Codex default)
2. **Streamable HTTP**: HTTP POST with JSON-RPC, Server-Sent Events for streaming

**Key Methods:**
- `initialize` — Handshake, protocol version, capabilities
- `tools/list` — List available tools with schemas
- `tools/call` — Execute a tool with arguments
- `notifications/initialized` — Client ready
- `ping` / `pong` — Health check

### Bridge HTTP Protocol

**Base URL:** `http://127.0.0.1:8765`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/dispatch` | POST | Execute a tool |
| `/health` | GET | Health check |

**Headers:**
- `Content-Type: application/json`
- `Authorization: Bearer <token>` (if configured)
- `Accept: application/json`

**Request ID:** Every request must include a unique `request_id` for tracing.

---

## Security Model

### Authentication

1. **Bridge Token:** Optional Bearer token configured in QGIS plugin settings
2. **Localhost Only:** Bridge binds to `127.0.0.1` only (no external access)
3. **MCP Server Token:** MCP server passes token to Bridge via `Authorization` header

### Permission Gating

**MCP Server Side:** Each tool declares required permissions in registry
**Bridge Side:** Dispatcher checks permissions before execution

```python
# ToolSpec permissions
permissions=["qgis:layer:write", "qgis:algorithm:execute"]

# Bridge checks
if not permission_manager.check(agent_id, required_permissions):
    return error_response(..., "PERMISSION_DENIED", ...)
```

### Approval Flow

Tools with `require_approval: true`:
1. Bridge receives request
2. Checks if approval needed
3. If yes, creates approval record in DB
4. Returns `NEEDS_REVIEW` or queues for user approval
5. User approves via QGIS plugin UI
6. Bridge executes, returns result

### Credential Storage

- **OS Credential Manager** (Windows Credential Manager via `keyring`)
- **Fallback:** DPAPI-encrypted local file
- **Never:** Plaintext in database or logs

### Audit Logging

All tool executions logged with:
- Timestamp, request_id, tool, user/agent
- Parameters (sanitized), result summary
- Verification state, duration
- Approval ID (if applicable)

---

## Threading & Concurrency

### QGIS Main Thread Rule

> **All PyQGIS GUI operations MUST run on the QGIS main thread.**

```python
# Correct: Using QMetaObject.invokeMethod
from qgis.PyQt.QtCore import QMetaObject, Qt, Q_ARG

def run_on_main_thread(func, *args, **kwargs):
    QMetaObject.invokeMethod(
        iface.mainWindow(),  # QObject on main thread
        lambda: func(*args, **kwargs),
        Qt.ConnectionType.QueuedConnection
    )

# Correct: Using QgsTask for background processing
from qgis.core import QgsTask, QgsApplication

class BufferTask(QgsTask):
    def __init__(self, layer_id, distance):
        super().__init__("Buffer Task", QgsTask.CanCancel)
        self.layer_id = layer_id
        self.distance = distance
    
    def run(self):
        # Background processing (no GUI!)
        result = processing.run("native:buffer", {...})
        return True
    
    def finished(self, success):
        if success:
            # Update GUI on main thread
            iface.mapCanvas().refresh()
```

### Concurrency Control

| Operation Type | Concurrency Model |
|----------------|-------------------|
| Project mutations (open/save/layers) | **Sequential** (single writer) |
| Read-only operations (inspect/info) | **Parallel** (multiple readers) |
| Processing algorithms | **Limited parallel** (worker pool, configurable) |
| Visual automation (cursor/mouse/keyboard) | **Sequential** (single cursor) |
| Screen capture | **Parallel** (read-only) |

**Implementation:** Job queue in Bridge with `threading.Lock` for project mutations.

---

## Database & Persistence

### SQLite Schema (WAL Mode)

**File:** `Universal-AI-GIS-Studio/database/schema.py`

**Tables:**
| Table | Purpose |
|-------|---------|
| `app_settings` | Application configuration |
| `ai_hosts` | OpenCode, Codex, custom hosts |
| `api_providers` | OpenAI, Gemini, Anthropic, etc. |
| `api_profiles` | Model configs, API keys (encrypted) |
| `mcp_servers` | External MCP server connections |
| `mcp_tools` | Discovered tools from external servers |
| `agents` | Built-in + custom agents |
| `agent_tools` | Agent-tool permission mappings |
| `skills` | Skill definitions, versions |
| `agent_skills` | Agent-skill assignments |
| `workflows` | Workflow definitions |
| `workflow_steps` | Workflow nodes/edges |
| `jobs` | Job queue, status, progress |
| `job_events` | Job event log (start/progress/complete) |
| `tool_runs` | Tool execution history |
| `approvals` | Pending/approved/rejected approvals |
| `project_context` | Current project state snapshots |
| `capability_registry` | Discovered QGIS/GDAL capabilities |
| `gcp_records` | Ground Control Points |
| `datasets` | Registered datasets metadata |
| `audit_logs` | Security audit trail |

### Repository Pattern

```python
# database/repositories/job_repository.py
class JobRepository:
    def create(self, job: Job) -> str: ...
    def update_status(self, job_id: str, status: str, progress: int): ...
    def get_by_id(self, job_id: str) -> Job: ...
    def list_active(self) -> list[Job]: ...
```

---

## Extension Points

### 1. Custom Clusters

Create new cluster in `clusters/mXX_newdomain/`:
```python
# handler.py
from clusters.base import ClusterBase, ClusterResult

class MXXNewDomain(ClusterBase):
    CLUSTER_ID = "MXX"
    CLUSTER_NAME = "New Domain"
    OPERATIONS = {"custom_op": "Description"}
    
    def execute(self, operation: str, params: dict) -> ClusterResult:
        if operation == "custom_op":
            return self._custom_op(params)
        return ClusterResult(operation, False, "FAILED", {}, error="Unknown operation")
    
    def _custom_op(self, params: dict) -> ClusterResult:
        # Use self.discover_algorithm() and self.run_algorithm()
        pass

def create_handler(executor):
    return MXXNewDomain(executor)
```

Register in dispatcher tool mapping.

### 2. Custom MCP Tools

Add to `mcp_server/registry.py`:
```python
add(
    "qgis.custom.mytool", "qgis.custom",
    "Description",
    base_input(required=["param1"], properties={"param1": _str_prop("Desc")}),
    base_output({"result": _str_prop()}),
    permissions=["qgis:custom:write"],
    approval=False,
    verification=["custom_check"],
)
```

Add handler in `mcp_server/tools/custom.py` and wire to Bridge dispatcher.

### 3. External MCP Servers

Configure in QGIS plugin settings:
- Add server (stdio or HTTP)
- Discover tools automatically
- Enable/disable per tool
- Map to agent permissions

### 4. Custom Agents

Define in database or JSON:
```json
{
  "name": "My Custom Agent",
  "description": "Specialized for cadastral workflows",
  "system_prompt": "You are a cadastral expert...",
  "allowed_tools": ["qgis.layers.load", "qgis.algorithms.execute", "qgis.project.save"],
  "permissions": ["qgis:layer:write", "qgis:algorithm:execute"]
}
```

### 5. Skills

Skills are reusable instruction sets:
```yaml
# skills/cadastral_boundary_fix.yaml
name: "Cadastral Boundary Fix"
version: "1.0.0"
description: "Fix overlapping parcel boundaries"
steps:
  - tool: qgis.layers.load
    params: {path: "{{input_path}}"}
  - tool: qgis.algorithms.execute
    params: {algorithm: "native:fixgeometries", parameters: {...}}
  - tool: qgis.algorithms.execute
    params: {algorithm: "native:removegaps", parameters: {...}}
```

---

## Summary: Key Architectural Decisions

| Decision | Rationale |
|----------|-----------|
| **Bridge in-process (QGIS plugin)** | GUI operations require QGIS main thread; avoids IPC complexity |
| **MCP Server out-of-process** | Runs on system Python; communicates via HTTP; isolates AI from QGIS env |
| **Dynamic algorithm discovery** | No hardcoded algorithm IDs; works across QGIS versions |
| **Verification states (not just success)** | AI never infers success from submission; explicit verification |
| **Sequential project mutations** | Single CPU, 8GB RAM, prevents conflicting writes |
| **SQLite WAL + Repository pattern** | Zero external deps; ACID; testable; keeps SQL out of UI |
| **OS Credential Manager + DPAPI fallback** | Secure credential storage; no plaintext secrets |
| **OpenCode/Codex via MCP stdio** | Standard protocol; no custom client code needed |
| **Streamable HTTP for web clients** | Enables browser-based UIs, remote access |
| **25 clusters (M01-M25)** | Domain separation; each testable independently |

---

*This architecture enables reliable, verifiable, AI-controlled GIS automation with QGIS Desktop as the execution engine.*