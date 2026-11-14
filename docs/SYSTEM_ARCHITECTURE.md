# Universal AI GIS Studio — System Architecture

**Version:** 1.0.0  
**Status:** Draft (implementation in progress)  
**Platform:** QGIS Desktop 4.2.3 (Qt6), PyQGIS, GDAL/OGR 3.13.3, Python 3.12  
**OS:** Windows 10 x64  
**AI Policy:** External AI only — no bundled/local models

---

## 1. Overview

Universal AI GIS Studio is a complete, extensible, MCP-first AI-controlled GIS automation ecosystem integrated with QGIS Desktop. It lets an external AI assistant (OpenCode, Codex, or any MCP-compatible client) control QGIS through natural language, while the platform provides actual GIS execution, visual interaction, verification, and control.

**Core principle:** AI provides reasoning and decision-making. Universal AI GIS Studio provides actual GIS execution, visual interaction, verification, and control.

---

## 2. High-Level Architecture

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

### Supporting Modules (all in-process with the QGIS Bridge)

| Module | Responsibility |
|--------|---------------|
| AI Host Manager | Configure/enable/disable/test/switch OpenCode, Codex, and optional API providers |
| Optional API Manager | OpenAI, Gemini, Anthropic, OpenRouter, OpenAI-compatible, custom endpoints (secure credential storage) |
| MCP Server Manager | Add/remove/connect/disconnect external MCP servers; discover tools; enable/disable per-tool |
| AI Agent Engine | 29 built-in agents + custom agent builder; supervisor-worker orchestration |
| Agent Orchestrator | Task planning, delegation, sequential/parallel execution, context sharing, error recovery |
| Skill Engine | Create/import/export/validate/enable/disable skills; versioning; dependency validation |
| Workflow Engine | Visual workflow builder; node execution; pause/resume/cancel/retry; history |
| Native QGIS Engine | Direct PyQGIS operations (project, layers, raster, vector, CRS, layouts, processing) |
| Visual Desktop Automation Engine | Window detection, dialog inspection, toolbar/menu recognition |
| Live Screen Capture Engine | On-demand + periodic screenshots; multi-monitor aware; resolution detection |
| AI Cursor Controller | Visible AI cursor; smooth movement; highlighting; click/drag animation; emergency stop |
| Mouse & Keyboard Controller | Move, click, double-click, right-click, drag, scroll, type, hotkeys |
| Computer Vision Engine | OpenCV feature detection (ORB/SIFT), matching, template matching, RANSAC, OCR |
| Automatic Georeferencing Engine | Image inspection → landmark detection → CV → GCP gen → validation → transformation → verify |
| GCP Intelligence Engine | GCP candidate gen, duplicate/outlier rejection, spatial distribution, residuals, RMSE |
| GIS Capability Discovery Engine | Inspect installed QGIS/GDAL/providers/algorithms/plugins dynamically |
| GIS Algorithm Registry | Dynamic algorithm discovery; no hardcoded algorithm assumptions |
| Verification Engine | SUCCESS / PARTIAL_SUCCESS / FAILED / NEEDS_REVIEW / CANCELLED states |
| Database & Storage Layer | SQLite (WAL), migrations, repositories, FKs, indexes |
| Security & Permission Manager | Authenticated bridge, tool allowlists, agent permissions, approvals, audit logs |
| Monitoring & Audit System | Job events, audit logs, resource monitoring, temp file cleanup |
| Extension Manager | ZIP/directory install, dependency checking, version compat, enable/disable, trust checks |
| Task History & Recovery System | Job persistence, replay, recovery after failure |

---

## 3. Module Interfaces

All components communicate through documented, typed interfaces (Python dataclasses / Pydantic models where available). The architecture avoids tight coupling:

- **Bridge ↔ MCP Server:** Authenticated localhost IPC/HTTP, request/response with request IDs
- **MCP Server ↔ Tools:** Registry-based, schema-validated, permission-checked
- **Bridge ↔ QGIS:** Main-thread-safe via `QgsTask` / `QMetaObject.invokeMethod`; no GUI from background threads
- **Agents ↔ Tools:** Via MCP tool registry with permission gating
- **Orchestrator ↔ Agents:** Context sharing, progress monitoring, cancellation
- **All modules → Database:** Repository/service layer only; no direct SQL in UI

---

## 4. QGIS Bridge (Key Technical Requirements)

- Detect QGIS installation and running instance
- Connect to correct QGIS process
- Use authenticated localhost IPC or HTTP
- Keep QGIS GUI operations on QGIS main thread
- Use `QgsTask` for background processing
- Request IDs + structured responses
- Timeouts and error handling
- Prevent duplicate/conflicting operations
- Connection health monitoring + safe reconnection
- Long-running job support + cancellation
- Task and execution logs

---

## 5. MCP Server (Key Technical Requirements)

- Transports: stdio and Streamable HTTP
- Maintained MCP SDK (inspect compatibility before implementation)
- 25+ tool namespaces (`qgis.system.*` through `qgis.history.*`)
- Every tool: description, strict input schema, structured output schema, permission requirements, timeout, error handling, execution logging, verification rules
- No fake tools or fabricated results

---

## 6. Data Flow Example (Natural Language → GIS Action)

1. User tells AI host: "Load the parcels GeoPackage and buffer by 100m"
2. AI host calls `qgis.layers.load` via MCP → QGIS Bridge
3. Bridge validates, executes PyQGIS on main thread, returns structured result
4. AI host calls `qgis.algorithms.execute` (native:buffer) → Bridge
5. Verification Engine checks output existence, validity, CRS, feature count
6. Bridge returns `SUCCESS` with verification details (never just "submitted")

---

## 7. Security Model

- Authenticated QGIS Bridge
- Tool allowlists + agent permission levels
- User approval required before destructive operations (delete data, overwrite files, remove layers, destructive DB ops, shell commands)
- Secure credential storage (OS credential manager where available); never plaintext API keys in DB or logs
- Audit logs for all important operations
- Project backups before high-impact actions
- Extension validation + trust checks
- Emergency stop + cancellation + safe recovery

---

## 8. Performance (8GB RAM, no dedicated GPU, HDD)

- No local LLM inference
- Lazy module loading
- Limited background workers
- Raster chunk processing
- Streaming large datasets
- Avoid unnecessary image duplication
- Resource monitoring + temp file cleanup
- Configurable cache limits

---

## 9. Database Schema (SQLite, WAL)

Tables: `app_settings`, `ai_hosts`, `api_providers`, `api_profiles`, `mcp_servers`, `mcp_tools`, `agents`, `agent_tools`, `skills`, `agent_skills`, `workflows`, `workflow_steps`, `jobs`, `job_events`, `tool_runs`, `approvals`, `project_context`, `capability_registry`, `gcp_records`, `datasets`, `audit_logs`

---

## 10. Known Environment Constraints (documented)

| Constraint | Detail | Mitigation |
|------------|--------|------------|
| QGIS not on system PATH | QGIS 4.2.3 at `C:\Program Files\QGIS 4.2.3` | Bridge locates QGIS install dynamically; uses bundled Python 3.12.15 |
| PyQGIS requires QGIS Python env | `import qgis` only works with QGIS's bundled Python + PYTHONPATH | Bridge runs inside QGIS plugin process; system Python used for MCP server |
| Qt6 (QGIS 4.x) | PyQt6, not PyQt5 | UI code targets PyQt6/QGIS 4 API |
| 8GB RAM, HDD | Limited memory, slower disk | Lazy loading, chunked raster processing, cache limits |
| No OpenCode/Codex config yet | OpenCode 1.19.5 installed but not configured for MCP | Documentation includes setup steps; config is additive, never overwrites existing |
| Single CPU | Limited parallelism | Safe parallel execution with worker limits; sequential by default for project mutations |

---

## 11. Acceptance Criteria (mapped to architecture)

- QGIS plugin installs and loads ✓ (planned)
- QGIS Bridge connects reliably ✓ (planned)
- MCP server starts correctly ✓ (planned)
- OpenCode discovers and executes real GIS tools ✓ (planned)
- Real QGIS screenshots captured ✓ (planned)
- AI cursor moves inside authorized QGIS window ✓ (planned)
- Dynamic algorithm discovery works ✓ (planned)
- All 25 clusters contain tested real functionality ✓ (planned)
- Automatic GCP generation works on real sample data ✓ (planned)
- Georeferencing produces real output raster ✓ (planned)
- Installable release package generated and tested ✓ (planned)
