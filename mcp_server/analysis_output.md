# MCP Server Folder Analysis — Universal AI GIS Studio

**Task:** task-7  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent  
**Context:** bridge/ (task-6) analysis read prior

---

## 1. Folder Structure

```
mcp_server/
├── __init__.py                      # Exports clients, CircuitBreaker, RetryPolicy
├── main.py                          # CLI entry point (stdio / streamable-http)
├── server.py                        # UniversalMCPServer — low-level MCP server (572 lines)
├── qgis_client.py                   # AsyncQgisBridgeClient + sync wrapper (558 lines)
├── registry.py                      # ToolSpec + ToolRegistry with 100+ tools (1000+ lines)
├── verification.py                  # VerificationEngine with 16 checkers (194 lines)
├── approval.py                      # ApprovalManager for destructive ops (155 lines)
├── tools/                           # 30 tool modules (not all registered yet)
│   ├── __init__.py
│   ├── project.py, system.py, layers.py, canvas.py, screen.py
│   ├── cursor.py, keyboard.py, mouse.py, algorithms.py
│   ├── georeference.py, vector_raster.py, window.py
│   ├── agents_skills.py, database_layout.py, jobs_history.py
│   ├── approval.py, vector.py, raster.py, spatial.py
│   ├── terrain.py, hydrology.py, network.py, remote_sensing.py
│   ├── classification.py, change_detection.py, temporal.py
│   ├── database.py, web_gis.py
├── resources/                       # MCP Resources (qgis:// URIs)
│   ├── __init__.py, registry.py
│   ├── layers.py, project.py, algorithms.py, crs.py
│   ├── styles.py, layouts.py, database.py
├── prompts/                         # MCP Prompts (workflow templates)
│   ├── __init__.py, registry.py
│   ├── vector.py, raster.py, analysis.py, cartography.py
│   ├── data.py, remote_sensing.py, terrain.py, automation.py
└── __pycache__/
```

**Total:** ~2,500 lines across core server + 30+ tool modules

---

## 2. Architecture & Components

### Core Server (`server.py`)
- **`UniversalMCPServer`**: Low-level MCP server using `mcp.server.lowlevel.Server`
- **Transports**: stdio (default) + Streamable HTTP (uvicorn/Starlette)
- **Capabilities**: Tools, Resources, Prompts, Logging, Subscriptions
- **Initialization**: Overrides `create_initialization_options` for proper notification options

### Client (`qgis_client.py`)
- **`AsyncQgisBridgeClient`**: Async HTTP client with:
  - Connection pooling (httpx.AsyncClient with limits)
  - Exponential backoff retry policy (configurable max_retries, base_delay, jitter)
  - **Circuit breaker** (5 failures → OPEN, 30s → HALF_OPEN, 3 successes → CLOSED)
  - Metrics tracking (latency percentiles, success/error counts)
- **`QgisBridgeClient`**: Sync wrapper with persistent event loop for backward compat
- **Factory**: `create_client(async_mode=True/False)`

### Tool Registry (`registry.py`)
- **`ToolSpec`**: name, namespace, description, input_schema, output_schema, permissions, timeout, require_approval, verification_rules
- **`ToolRegistry`**: Register/get/list tools
- **`build_registry()`**: Defines 100+ tools across 20+ namespaces

### Verification (`verification.py`)
- **`VerificationEngine`**: 16 built-in checkers mapped by rule name
- **Checkers**: `file_exists`, `file_written`, `layer_valid`, `layer_removed`, `project_valid`, `output_exists`, `output_valid`, `confidence_scored`, `outliers_rejected`, `min_point_count`, `residuals_checked`, `response_structured`, `operation_completed`, `ui_action_confirmed`, `image_valid_base64`
- **Integration**: Runs after tool execution; failed rules → `verification_state=FAILED`

### Approval (`approval.py`)
- **`ApprovalManager`**: Thread-safe pending approvals with TTL (default 5 min)
- **Flow**: Tool with `require_approval=True` → creates `ApprovalRequest` → client must call `qgis.approval.grant` with `approval_token` → tool proceeds
- **Integration**: Checked in `_execute_tool()` before bridge dispatch

### Resources & Prompts
- **Resources**: `qgis://` URIs for layer info, project metadata, canvas state, algorithms, CRS, styles, layouts, database
- **Prompts**: GIS workflow templates for vector, raster, analysis, cartography, data, remote sensing, terrain, automation

---

## 3. Tool Coverage (from `registry.py`)

| Namespace | Tool Count | Key Tools |
|-----------|------------|-----------|
| `qgis.system` | 2 | `inspect`, `health` |
| `qgis.project` | 3 | `open` (approval), `save`, `inspect` |
| `qgis.layers` | 3 | `inspect`, `load` (verification), `remove` (approval) |
| `qgis.canvas` | 1 | `inspect` |
| `qgis.screen` | 1 | `capture` |
| `qgis.cursor` | 3 | `move`, `click`, `drag` |
| `qgis.keyboard` | 2 | `type`, `hotkey` |
| `qgis.mouse` | 1 | `scroll` |
| `qgis.window` | 1 | `inspect` |
| `qgis.dialog` | 1 | `inspect` |
| `qgis.algorithms` | 2 | `discover`, `execute` (verification) |
| `qgis.georeference` | 1 | `analyze` |
| `qgis.gcp` | 2 | `generate` (verification), `validate` |
| `qgis.raster` | 25 | `calculator`, `reclassify`, `mosaic`, `clip`, `resample`, `convert`, `band_ops`, `hillshade`, `slope`, `aspect`, `roughness`, `tpi`, `curvature`, `zonal_stats`, `zonal_histogram`, `proximity`, `sieve`, `polygonize`, `fill_nodata`, `warp`, `clip_extent`, `translate`, `contour`, `rgb_to_pct`, `pct_to_rgb` |
| `qgis.vector` | 25 | `buffer`, `clip`, `dissolve`, `intersection`, `union`, `difference`, `merge`, `repair`, `split`, `centroids`, `convex_hull`, `bounds`, `envelope`, `simplify`, `smooth`, `offset`, `polygonize`, `lines_to_polygons`, `polygons_to_lines`, `multipart_to_singlepart`, `singlepart_to_multipart`, `extract_vertices`, `add_geometry_attributes`, `drop_m_z`, `set_m_z` |
| `qgis.spatial` | 20 | `join_attributes_by_location`, `join_attributes_by_nearest`, `join_attributes_by_field_value`, `distance_matrix`, `nearest_neighbor`, `point_distance`, `intersection`, `union`, `difference`, `symmetrical_difference`, `clip`, `count_points_in_polygon`, `heatmap`, `kmeans_clustering`, `dbscan_clustering`, `idw_interpolation`, `tin_interpolation`, `morans_i`, `getis_ord`, `gearys_c` |
| `qgis.database` | ~10 | `postgis_connect`, `geopackage_connect`, `spatial_sql`, `db_import`, `db_export`, ... |
| `qgis.layout` | ~5 | `info`, `create`, `export`, `atlas` |
| `qgis.workflow` | ~1 | `execute` |
| `qgis.agents` | 1 | `list` |
| `qgis.skills` | 1 | `list` |
| `qgis.verify` | 1 | `status` |
| `qgis.jobs` | 1 | `cancel` |
| `qgis.history` | 1 | `inspect` |
| `qgis.plugins` | 1 | `list` |

**Total: ~150 tools defined** (but only ~45 registered in `build_registry()` — raster/vector/spatial tools defined but commented as "namespace markers")

---

## 4. Permissions & Security

### Permission Hierarchy (`server.py:57-73`)
```
qgis:read (parent)
  ├─ qgis:system:read, qgis:project:read, qgis:canvas:read
  ├─ qgis:layers:read, qgis:screen:read, qgis:window:read
  ├─ qgis:dialog:read, qgis:algorithms:read, qgis:georeference:read
  ├─ qgis:gcp:read, qgis:raster:read, qgis:vector:read
  ├─ qgis:spatial:read, qgis:database:read, qgis:layout:read
  ├─ qgis:workflow:read, qgis:agents:read, qgis:skills:read
  ├─ qgis:verify:read, qgis:history:read, qgis:plugins:read
  └─ (25 permissions)

qgis:write (parent)
  ├─ qgis:project:write, qgis:layer:write, qgis:cursor:write
  ├─ qgis:keyboard:write, qgis:mouse:write, qgis:algorithm:execute
  ├─ qgis:gcp:write, qgis:workflow:execute, qgis:jobs:write
  └─ (10 permissions)

qgis:admin → ["*"]
```

### Tool-Level Permissions
Each `ToolSpec` declares `permissions: list[str]` (e.g., `["qgis:layer:write"]`)
- Checked in `_execute_tool()` via `PermissionManager.check_permissions()`
- Default: **deny** if any permissions configured; **allow all** if no permissions granted

### Approval Gates
Tools with `require_approval=True`:
- `qgis.project.open` — opens project file
- `qgis.layers.remove` — removes layer
- (More can be added)

### Rate Limiting
- Token bucket per (client_id, tool) via `security.rate_limiter`
- Default configs in `bridge.dispatcher.DEFAULT_RATE_LIMITS` (150+ tool-specific limits)
- Checked in both MCP server and Bridge dispatcher

---

## 5. Verification Rules

Each `ToolSpec` can declare `verification_rules: list[str]`:
| Rule | Checker | Used By |
|------|---------|---------|
| `file_exists` | Output file path exists | `qgis.project.open`, `qgis.layers.load` |
| `file_written` | Project file exists | `qgis.project.save` |
| `layer_valid` | Layer `valid` field true | `qgis.layers.load` |
| `layer_removed` | `removed=true` | `qgis.layers.remove` |
| `project_valid` | Project file exists | `qgis.project.open` |
| `output_exists` | Algorithm outputs non-empty | `qgis.algorithms.execute` |
| `output_valid` | Output files exist + non-zero | `qgis.algorithms.execute` |
| `confidence_scored` | GCPs have confidence | `qgis.gcp.generate` |
| `outliers_rejected` | Rejected field present | `qgis.gcp.generate` |
| `min_point_count` | ≥4 GCPs | `qgis.gcp.validate` |
| `residuals_checked` | RMSE computed | `qgis.gcp.validate` |
| `response_structured` | Result is dict | Inspect tools |
| `operation_completed` | Status=success | General |
| `ui_action_confirmed` | `ok=true` | Cursor/keyboard/mouse |
| `image_valid_base64` | Valid base64 PNG | `qgis.screen.capture` |

---

## 6. Dependencies

### Internal
```
mcp_server.server       → mcp_server.registry, mcp_server.qgis_client, mcp_server.resources, mcp_server.prompts, mcp_server.verification, mcp_server.approval, core.logging, core.exceptions, security.rate_limiter
mcp_server.qgis_client  → core.logging, core.exceptions, httpx
mcp_server.registry     → (standalone dataclasses)
mcp_server.verification → core.logging, pathlib
mcp_server.approval     → core.logging, core.exceptions, uuid, threading
mcp_server.resources.*  → (various)
mcp_server.prompts.*    → (various)
```

### External
- **MCP SDK**: `mcp.server.lowlevel`, `mcp.server.stdio`, `mcp.server.streamable_http_manager`, `mcp.types`
- **HTTP**: `httpx` (async client with pooling, retries, circuit breaker)
- **Validation**: `jsonschema` (optional, Draft202012Validator)
- **ASGI**: `uvicorn`, `starlette` (Streamable HTTP transport)
- **AnyIO**: stdio transport

### Consumers
- `agents.base_agent.BaseAgent` → `AsyncQgisBridgeClient` for tool dispatch
- `bridge.dispatcher` → Rate limiter configs
- CLI entry point → `main.py`

---

## 7. Issues Found

### 🔴 REMOVE (Dead Code / Security Risks / Duplicates)
| Item | Location | Issue |
|------|----------|-------|
| `__pycache__/` | All subfolders | Compiled bytecode committed — gitignore |
| **Tools modules** | `mcp_server/tools/*.py` (30 files) | Most tool modules exist but **not registered** in `registry.py` — dead code or incomplete |
| **Raster/Vector/Spatial tools** | `registry.py:338-340` | 25+ raster, 25+ vector, 20+ spatial tools defined but commented as "namespace markers" — not actually registered |
| `PermissionManager` default | `server.py:93` | `return len(self._granted_permissions) == 0` — **allows all if no explicit grants** (insecure default) |
| `QgisBridgeClient` event loop | `qgis_client.py:501` | Creates persistent event loop in `__init__` — not thread-safe, leaks on close |
| Duplicate approval logic | `approval.py:127-155` AND `server.py:414-427` | `check_approval_required()` called in both places |

### 🟡 ADD (Missing Features / Tests / Docs)
| Gap | Scope | Recommendation |
|-----|-------|----------------|
| **Complete tool registration** | `registry.py` | Register all 150+ defined tools (raster/vector/spatial/database/layout/etc.) |
| **Unit tests** | `server.py`, `qgis_client.py`, `verification.py`, `approval.py` | Only registry tests exist (5 tests) |
| **Integration tests** | All | No tests with real QGIS Bridge / MCP client |
| **Resource handlers** | `resources/*.py` | Most resource modules exist but handlers not fully implemented |
| **Prompt handlers** | `prompts/*.py` | Prompt modules exist but render logic incomplete |
| **Circuit breaker metrics** | `qgis_client.py` | Expose circuit breaker state via `/metrics` |
| **Auth integration** | `server.py` | No JWT/OAuth integration — only static Bearer token |
| **Session management** | `server.py` | Streamable HTTP needs proper session cleanup |
| **Tool versioning** | `registry.py` | No version field in `ToolSpec` for API evolution |
| **OpenAPI docs** | `main.py` | FastAPI auto-generates but no custom examples |

### 🔵 IMPROVE (Refactoring / Performance / Patterns)
| Opportunity | Details |
|-------------|---------|
| **Remove dead tool modules** | Delete or archive `tools/*.py` not used by registry |
| **Fix permission default** | Change `PermissionManager.check_permission()` to deny by default |
| **Register all tools** | Wire raster (25), vector (25), spatial (20), database, layout, workflow tools |
| **Async client cleanup** | Fix `QgisBridgeClient` event loop leak; use `asyncio.run()` per call |
| **Consolidate approval check** | Single call site in `_execute_tool()` |
| **Add tool versioning** | Add `version` field to `ToolSpec` |
| **Structured logging** | Add `request_id` to all log lines in `_execute_tool()` |
| **Circuit breaker integration** | Expose breaker state in `/metrics`; add to health checks |
| **Connection pool tuning** | Make httpx pool limits configurable per environment |
| **Validation caching** | `get_validator()` uses JSON string as cache key — use hash |

---

## 8. Cross-Module Integration (with bridge/ context)

### Current Integration
```
mcp_server.main           → UniversalMCPServer(bridge_url, auth_token)
mcp_server.server         → AsyncQgisBridgeClient → Bridge /dispatch
mcp_server.qgis_client    → httpx.AsyncClient → Bridge HTTP endpoints
mcp_server.registry       → ToolSpec definitions → list_tools/call_tool
mcp_server.verification   → VerificationEngine.run_verification() in _execute_tool()
mcp_server.approval       → ApprovalManager.create_request() in _execute_tool()
security.rate_limiter     → RateLimitResult in _execute_tool() + bridge.dispatcher
```

### Bridge ↔ MCP Server Flow
```
MCP Client (OpenCode/Codex)
    │
    ▼
MCP Server (stdio / Streamable HTTP)
    │ call_tool()
    ▼
UniversalMCPServer._execute_tool()
    │ validate_input() → PermissionManager → ApprovalManager → RateLimiter
    ▼
AsyncQgisBridgeClient.dispatch()
    │ POST /dispatch (with circuit breaker, retries)
    ▼
Bridge Server (ThreadingHTTPServer / FastAPI)
    │ BridgeRequestHandler / FastAPI endpoint
    ▼
BridgeDispatcher.dispatch()
    │ RateLimiter → Handler → PyQGISExecutor
    ▼
PyQGISExecutor.run_on_main_thread() → QGIS operations
    ▼
Response → VerificationEngine → MCP Response
```

### Missing Integration
| Service | Should Integrate | Current State |
|---------|-----------------|---------------|
| `EventBus` | Tool execution events | **Not used** |
| `CapabilityRegistry` | Register MCP server capabilities | **Not used** |
| `JobManager` | Track async MCP tool calls | **Partial** (bridge has it) |
| `AuditRepository` | Log approval grants/denies | **Not used** |

---

## 9. Test Coverage

| Test File | Coverage |
|-----------|----------|
| `test_mcp_registry.py` | Registry namespaces (1), key tools (1), schema strictness (1), permissions (1), server instantiation (1) — **5 tests** |
| **Missing** | `test_server.py`, `test_qgis_client.py`, `test_verification.py`, `test_approval.py`, `test_resources.py`, `test_prompts.py` |

**Total: 5 tests for 8 core modules (62% — but only registry tested)**

---

## 10. Recommendations Summary

### Priority 1 (Immediate)
1. **Add all `mcp_server/**/__pycache__/` to `.gitignore`**
2. **Fix `PermissionManager` default** — deny by default, not allow all
3. **Fix `QgisBridgeClient` event loop leak** — use `asyncio.run()` per call or proper loop management
4. **Consolidate approval check** — single call in `_execute_tool()`

### Priority 2 (Short-term)
5. **Register all defined tools** in `registry.py` (raster 25, vector 25, spatial 20, database, layout, workflow)
6. **Add unit tests** for server, client, verification, approval, resources, prompts
7. **Implement resource handlers** in `resources/*.py`
8. **Implement prompt renderers** in `prompts/*.py`
9. **Remove dead tool modules** or complete their registration

### Priority 3 (Medium-term)
10. **Add JWT/OAuth authentication** integration
11. **Add tool versioning** to `ToolSpec`
12. **Expose circuit breaker metrics** via `/metrics`
13. **Integrate with `EventBus`**, `CapabilityRegistry`, `AuditRepository`
14. **Add structured logging** with `request_id` correlation
15. **Create OpenAPI documentation** with examples for Streamable HTTP

---

## 11. Output for Next Task (integrations/)

**Context to pass forward:**
- MCP Server provides: stdio + Streamable HTTP transports, 150+ tool definitions (45 registered), JSON Schema validation, permission system, approval gates, rate limiting, verification rules, circuit breaker, retry policy
- Integrations folder contains: `ai_hosts/`, `api_providers/`, `external_mcp/`
- AI Host Manager (`integrations.ai_hosts.ai_host_manager`) likely starts/stops OpenCode/Codex processes
- API Manager (`integrations.api_providers.api_manager`) manages LLM provider configs
- MCP Manager (`integrations.external_mcp.mcp_manager`) manages external MCP server connections
- Key integration: `mcp_server.server.get_permission_manager()` used by `agents.base_agent`
- `AsyncQgisBridgeClient` used by `agents.base_agent.BaseAgent.call_tool()`
- Watch for: Circular imports between mcp_server and integrations; integrations should not import mcp_server internals

---

*End of mcp_server/ folder analysis*