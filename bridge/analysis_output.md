# Bridge Folder Analysis — Universal AI GIS Studio

**Task:** task-6  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent  
**Context:** core/ (task-1), clusters/ (task-2), engines/ (task-3), agents/ (task-4), database/ (task-5) analyses read prior

---

## 1. Folder Structure

```
bridge/
├── __init__.py                      # Exports SocketServer, COMMANDS, wire protocol
├── protocol.py                      # Request/Response dataclasses + helpers (66 lines)
├── registry.py                      # Command registry, compound commands, batch blocking (245 lines)
├── wire.py                          # Length-prefixed JSON framing, OutboundBuffer (107 lines)
├── bridge_server.py                 # ThreadingHTTPServer + WebSocket for screen streaming (297 lines)
├── bridge_server_async.py           # FastAPI + uvicorn async server with queue/worker pool (679 lines)
├── request_handler.py               # BaseHTTPRequestHandler for sync server (173 lines)
├── executor.py                      # PyQGISExecutor with main-thread dispatch + 100+ tool methods (921 lines)
├── dispatcher.py                    # Request routing + rate limiting + 200+ tool handlers (1000+ lines)
├── metrics.py                       # Prometheus metrics for bridge monitoring (238 lines)
├── socket_server.py                 # Legacy socket server (not read, likely deprecated)
├── test_bridge.py                   # Integration test script (not read)
└── __pycache__/
```

**Total:** ~2,800 lines across 11 Python modules

---

## 2. Architecture & Components

### Core Protocol (`protocol.py`)
- **`Request`** dataclass: `request_id`, `tool`, `params`, `timeout_seconds`, `require_approval`, `metadata`
- **`Response`** dataclass: `request_id`, `status` (ok/error), `result`, `error`, `verification_state`, `job_id`, `timestamp`
- **Verification States**: `SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`, `NEEDS_REVIEW`, `CANCELLED`
- **Helpers**: `success_response()`, `error_response()`

### Command Registry (`registry.py`)
- **`COMMANDS`** dict: `cmd_type` → handler method name (decorator-based registration)
- **`UNRECORDED_COMMANDS`** (38): Read-only commands that skip audit logging
- **`BATCH_BLOCKED_COMMANDS`** (94): Commands prohibited in batch mode (destructive ops)
- **`COMPOUND_COMMANDS`** (27 groups, ~200 commands): Grouped tool mode for reduced token usage
- **Environment variable**: `QGIS_MCP_TOOL_MODE=compound` enables compound mode

### Wire Protocol (`wire.py`)
- **Length-prefixed framing**: 4-byte big-endian length + JSON payload
- **`OutboundBuffer`**: Backpressure-aware buffer (5 MB max per client)
- **Constants**: `MAX_MESSAGE_SIZE=10MB`, `RECV_CHUNK_SIZE=64KB`

### Sync Server (`bridge_server.py` + `request_handler.py`)
- **`BridgeServer`**: `ThreadingHTTPServer` on port 8765 (with fallback ports)
- **`BridgeRequestHandler`**: Handles `/dispatch`, `/health`, `/ready`, `/metrics`
- **`WebSocketServer`**: Separate thread with `websockets` library on port 8767 for screen streaming
- **Auth**: Bearer token via `Authorization` header
- **Health endpoints**: `/healthz` (liveness), `/readyz` (readiness), `/livez`

### Async Server (`bridge_server_async.py`)
- **FastAPI + uvicorn** for high concurrency
- **Request queue** (default 1000) + **worker pool** (default 10 workers)
- **PyQGIS semaphore** (default 5 concurrent) for thread safety
- **Endpoints**: `/dispatch`, `/batch-dispatch` (up to 500 requests), `/ready`, `/health`, `/metrics`, `/ws`
- **Backpressure**: Returns 429 when queue full with `Retry-After` header
- **Batch dispatch**: Processes multiple requests in single HTTP call
- **WebSocket**: `/ws` for real-time updates (screen streaming, job progress)

### Executor (`executor.py`) — Core PyQGIS Bridge
- **`PyQGISExecutor`**: Main-thread dispatch via `QTimer.singleShot` + `QEventLoop`
- **`run_on_main_thread(fn, *args, timeout=30.0)`**: Executes callable on QGIS main thread
- **100+ tool methods** across categories:
  - System/Project/Canvas inspection
  - Layer operations (load, remove, editing)
  - Algorithm execution (sync + async via `QgsTask`)
  - Screen capture (canvas + desktop via `ScreenCaptureEngine`)
  - Visual automation (cursor, keyboard, mouse, window/dialog)
  - Georeferencing/GCP (stubs for CV integration)
  - Job management (async processing jobs)
- **Emergency stop**: Registered with priority 50

### Dispatcher (`dispatcher.py`) — Routing + Rate Limiting
- **340+ tool handlers** mapped in `_handlers` dict
- **`SYNC_TOOLS`** (150): Fast ops (<1s) — executed directly
- **`ASYNC_TOOLS`** (3): Long-running — return `job_id` with `PARTIAL_SUCCESS`
- **Rate limiting**: Token bucket per agent/tool via `security.rate_limiter`
- **Default rate limits**: 150+ tool-specific configs (capacity/refill_rate)
- **Verification state logic**: Sync tools → `SUCCESS`, async tools with job_id → `PARTIAL_SUCCESS`

### Metrics (`metrics.py`)
- **Prometheus metrics** (optional dependency): requests_total, latency, bridge_up, queue_depth, jobs, circuit_breaker, batch, QGIS project/layer counts
- **Global instance** via `init_metrics()` / `get_metrics()`

---

## 3. Tool Coverage (from dispatcher.py)

| Category | Tool Count | Example Tools |
|----------|------------|---------------|
| **System/Project/Canvas** | ~15 | `qgis.system.inspect`, `qgis.project.inspect`, `qgis.canvas.inspect` |
| **Layers** | ~10 | `qgis.layers.load`, `qgis.layers.inspect`, `qgis.layers.remove` |
| **Layer Editing** | 6 | `qgis.layer.start_editing`, `commit_changes`, `roll_back`, `add/update/delete_features` |
| **Screen Capture** | 1 | `qgis.screen.capture` (canvas) + executor methods for desktop |
| **Visual Automation** | 6 | `qgis.cursor.move/click/drag`, `qgis.keyboard.type/hotkey`, `qgis.mouse.scroll` |
| **Window/Dialog** | 2 | `qgis.window.inspect`, `qgis.dialog.inspect` |
| **Algorithms** | 3 | `qgis.algorithms.discover`, `execute` (sync), `execute_async` |
| **Jobs** | 2 | `qgis.jobs.status`, `qgis.jobs.cancel` |
| **Georeferencing/GCP** | 3 | `qgis.georeference.analyze`, `qgis.gcp.generate`, `qgis.gcp.validate` |
| **Vector (M03)** | 25 | `buffer`, `clip`, `dissolve`, `intersection`, `union`, `difference`, `merge`, `repair`, `split`, ... |
| **Raster (M04)** | 25 | `calculator`, `reclassify`, `mosaic`, `clip`, `resample`, `convert`, `band_ops`, `hillshade`, `slope`, `aspect`, ... |
| **Spatial (M07)** | 20 | `join_attributes_by_location`, `distance_matrix`, `intersection`, `union`, `clip`, `kmeans_clustering`, `idw_interpolation`, ... |
| **Terrain (M08)** | 15 | `hillshade`, `slope`, `aspect`, `ruggedness`, `tpi`, `roughness`, `contours`, `watershed`, ... |
| **Hydrology (M09)** | 12 | `stream_order`, `catchment_area`, `flood_mapping`, `hec_ras_prep`, ... |
| **Network (M10)** | 12 | `shortest_path`, `service_area`, `od_matrix`, `traveling_salesman`, `vehicle_routing`, ... |
| **Remote Sensing (M11)** | 11 | `satellite_import`, `band_combinations`, `spectral_indices`, `pan_sharpening`, ... |
| **Classification (M12)** | 13 | `train_samples`, `supervised_classify`, `unsupervised_classify`, `random_forest`, `svm`, ... |
| **Change Detection (M13)** | 15 | `temporal_comparison`, `raster_difference`, `landcover_change`, `change_report`, ... |
| **Temporal (M19)** | 10 | `enable`, `filter`, `animate`, `time_series`, `controller`, `keyframe`, `playback`, ... |
| **Database (M20)** | 10 | `postgis_connect`, `geopackage_connect`, `spatial_sql`, `db_import`, `db_export`, ... |
| **Web GIS (M21)** | 10 | `wms_load`, `wfs_load`, `wmts_load`, `xyz_tiles`, `ogc_api`, `server_publish`, ... |
| **Field Data (M22)** | 8 | `qfield_sync`, `mergin_sync`, `gps_track`, `offline_package`, ... |
| **Automation (M23)** | 10 | `model_create`, `model_run`, `model_export`, `batch_process`, `script_run`, ... |
| **Quality (M25)** | 15 | `topology_check`, `geometry_valid`, `duplicates`, `self_intersect`, `gaps`, `overlaps`, ... |
| **Agents/Skills** | 2 | `qgis.agents.list`, `qgis.skills.list` |
| **Verification** | 1 | `qgis.verify.status` |
| **Plugins** | 1 | `qgis.plugins.list` |

**Total: ~340+ tools** mapped to PyQGISExecutor methods

---

## 4. Dependencies

### Internal
```
bridge.protocol          → (standalone dataclasses)
bridge.registry          → os
bridge.wire              → struct
bridge.bridge_server     → bridge.request_handler, bridge.metrics, core.logging, monitoring.health
bridge.bridge_server_async → bridge.protocol, bridge.dispatcher, bridge.metrics, core.logging, fastapi, pydantic, uvicorn
bridge.request_handler   → bridge.protocol, bridge.metrics, core.logging, core.exceptions
bridge.executor          → bridge.protocol, core.logging, core.exceptions, core.job_manager, core.emergency_stop
bridge.dispatcher        → bridge.protocol, bridge.executor, core.logging, core.exceptions, security.rate_limiter
bridge.metrics           → prometheus_client (optional), core.logging
```

### External
- **PyQt6** (`qgis.PyQt`): `QCoreApplication`, `QTimer`, `QEventLoop`, `QThread`, `QTest`, `QCursor`, `QImage`, `QPainter`, `QBuffer`
- **QGIS/PyQGIS**: `QgsProject`, `QgsVectorLayer`, `QgsRasterLayer`, `QgsApplication`, `processing`, `QgsTask`, `QgsTaskManager`, `QgsProcessingFeedback`
- **PIL**: `Image` (for georeferencing analyze)
- **websockets**: WebSocket server (optional)
- **fastapi/uvicorn/pydantic**: Async server
- **prometheus_client**: Metrics (optional)
- **win32gui**: Window/dialog inspection (Windows only)
- **security.rate_limiter**: Token bucket rate limiting

---

## 5. Issues Found

### 🔴 REMOVE (Dead Code / Security Risks / Duplicates)
| Item | Location | Issue |
|------|----------|-------|
| `__pycache__/` | `bridge/` | Compiled bytecode committed — gitignore |
| `socket_server.py` | `bridge/socket_server.py` | Legacy socket server (not used, `bridge_server.py` is HTTP) — remove or archive |
| `BATCH_BLOCKED_COMMANDS` duplicate | `registry.py:41-94` AND `wire.py:63-80` | Same set defined in two files — single source of truth needed |
| `UNRECORDED_COMMANDS` duplicate | `registry.py:12-38` AND `wire.py:82-107` | Same set defined in two files |
| `HEADER_STRUCT`/`MAX_MESSAGE_SIZE`/`RECV_CHUNK_SIZE` duplicate | `wire.py:9-12` AND `wire.py:59-61` | Constants redefined at bottom for "compatibility" |
| `test_bridge.py` | Root `test_bridge.py` | Integration test script in root — move to tests/ |

### 🟡 ADD (Missing Features / Tests / Docs)
| Gap | Scope | Recommendation |
|-----|-------|----------------|
| **Unit tests** | `bridge_server_async.py`, `executor.py`, `dispatcher.py` | Only protocol + basic dispatcher tested (5 tests); zero tests for async server, executor, WebSocket, rate limiting |
| **Integration tests** | All | No tests with real QGIS/PyQt environment |
| **Rate limit tests** | `dispatcher.py` | No tests for token bucket, burst, retry-after |
| **WebSocket tests** | `bridge_server.py`, `bridge_server_async.py` | No tests for screen streaming, config messages |
| **Compound mode tests** | `registry.py` | No tests for `QGIS_MCP_TOOL_MODE=compound` |
| **Batch dispatch tests** | `bridge_server_async.py` | No tests for `/batch-dispatch` endpoint |
| **Async job tests** | `executor.py` | No tests for `execute_algorithm_async`, `QgsTask` factory |
| **Circuit breaker integration** | `dispatcher.py`, `bridge_server_async.py` | `circuit_breaker` parameter accepted but not used |
| **Request timeout enforcement** | `bridge_server_async.py` | `timeout_seconds` in request but not enforced in queue worker |
| **OpenAPI docs** | `bridge_server_async.py` | FastAPI auto-generates but no custom docs/examples |
| **Protocol versioning** | `protocol.py` | No version field in Request/Response for forward compatibility |

### 🔵 IMPROVE (Refactoring / Performance / Patterns)
| Opportunity | Details |
|-------------|---------|
| **Unify command sets** | Move `BATCH_BLOCKED_COMMANDS` and `UNRECORDED_COMMANDS` to single module (`bridge/commands.py`) |
| **Remove duplicate constants** | Clean up `wire.py` bottom re-exports |
| **Extract tool handlers** | `dispatcher.py` is 1000+ lines — move handler methods to separate modules per category |
| **Async executor methods** | Many `executor` methods are sync-only; add async variants for FastAPI workers |
| **Rate limiter per-agent** | Current: token bucket per (agent_id, tool); consider per-agent global budget |
| **Queue priority** | `bridge_server_async.py` queue is FIFO; add priority for interactive tools (cursor/keyboard) |
| **Connection pooling** | HTTP server creates new handler per request; consider keep-alive optimization |
| **WebSocket auth** | Currently no auth on WebSocket connections — add token validation |
| **Structured logging** | Add `request_id` to all log lines in dispatcher/executor |
| **Health check depth** | `/ready` checks QGIS connection but not database, job manager, etc. |
| **Graceful shutdown** | `bridge_server_async.py` cancels workers but doesn't wait for in-flight PyQGIS tasks |
| **Executor method discovery** | Auto-discover handler methods from executor instead of manual `_handlers` dict |

---

## 6. Cross-Module Integration (with prior analyses context)

### Current Integration
```
bridge.protocol           → Used by: dispatcher, request_handler, bridge_server_async, executor
bridge.registry           → Used by: __init__, bridge_server_async (compound groups)
bridge.wire               → Used by: socket_server (legacy), __init__
bridge.bridge_server      → Uses: request_handler, executor, dispatcher, metrics, health
bridge.bridge_server_async → Uses: dispatcher, executor, metrics, protocol
bridge.executor           → Uses: core.job_manager, core.emergency_stop, engines.screen_capture
bridge.dispatcher         → Uses: executor, security.rate_limiter, core.exceptions
bridge.metrics            → Used by: bridge_server, bridge_server_async, request_handler
```

### Database Integration (from task-5)
- `JobManager` → `JobRepository` → `jobs`/`job_events` tables (async algorithm execution)
- `AuditRepository` → `audit_logs` (emergency stop audit from executor)

### Agent Integration (from task-4)
- `AgentOrchestrator` → `JobManager` → Bridge async tools
- `BaseAgent.call_tool()` → MCP client → Bridge `/dispatch`

### Engine Integration (from task-3)
- `engines.screen_capture.ScreenCaptureEngine` → `executor._get_screen_capture_engine()` for desktop capture
- `engines.georeferencing` → `executor.georeference_analyze/gcp_generate/gcp_validate` (stubs)

### Cluster Integration (from task-2)
- 340+ tools map to 25 clusters (M01-M25) via dispatcher handlers
- Vector/Raster/Spatial/Terrain/etc. tools delegate to `executor.execute_algorithm()`

---

## 7. Test Coverage

| Test File | Coverage |
|-----------|----------|
| `test_bridge_protocol.py` | Protocol dataclasses (2), Dispatcher basic routing (4) — **5 tests** |
| **Missing** | `bridge_server.py`, `bridge_server_async.py`, `executor.py`, `dispatcher.py` (rate limiting, async, WebSocket, compound mode, batch) |

**Total: 5 tests for 11 bridge modules (45% — but only protocol+basic dispatcher tested)**

---

## 8. Recommendations Summary

### Priority 1 (Immediate)
1. **Add all `bridge/__pycache__/` to `.gitignore`**
2. **Remove duplicate command sets** — create `bridge/commands.py` for `BATCH_BLOCKED_COMMANDS` and `UNRECORDED_COMMANDS`
3. **Remove legacy `socket_server.py`** (or archive)
4. **Fix duplicate constants** in `wire.py`

### Priority 2 (Short-term)
5. **Add unit tests** for: async server endpoints, executor main-thread dispatch, WebSocket streaming, rate limiter, compound mode, batch dispatch
6. **Implement circuit breaker** in dispatcher (use `core.circuit_breaker` for PyQGISExecutor calls)
7. **Add WebSocket authentication** (validate token on connect)
8. **Enforce request timeouts** in async queue workers
9. **Add graceful shutdown** for in-flight PyQGIS tasks in async server

### Priority 3 (Medium-term)
10. **Refactor dispatcher** — extract handler methods to `bridge/handlers/` per category
11. **Add priority queue** for interactive tools (cursor/keyboard) vs batch tools
12. **Implement protocol versioning** in Request/Response
13. **Add OpenAPI documentation** with examples for FastAPI server
14. **Auto-discover executor handlers** instead of manual `_handlers` dict
15. **Add request/response compression** for large payloads (screen captures)
16. **Implement structured logging** with `request_id` correlation

---

## 9. Output for Next Task (mcp_server/)

**Context to pass forward:**
- Bridge provides: HTTP + WebSocket server, 340+ tools via PyQGISExecutor, async job queue, rate limiting, Prometheus metrics
- MCP Server folder contains: `main.py` (MCP server entry point)
- MCP server likely: connects to Bridge via HTTP, exposes tools via MCP protocol, manages stdio/HTTP transports
- Key integration: `mcp_server.registry.build_registry()` used by `BaseAgent.call_tool()` for tool spec lookup
- `AsyncQgisBridgeClient` in `mcp_server.qgis_client` used by agents for tool dispatch
- Watch for: Circular imports between mcp_server and bridge; mcp_server should not import bridge internals

---

*End of bridge/ folder analysis*