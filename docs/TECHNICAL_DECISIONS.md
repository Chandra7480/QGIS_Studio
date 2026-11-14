# Universal AI GIS Studio — Technical Decisions

**Version:** 1.0.0  
**Last Updated:** 2026-11-11  
**Based on:** Environment inspection of Windows 10 x64, QGIS 4.2.3, Python 3.12, GDAL 3.13.3, OpenCode 1.19.5

## 1. Language & Runtime

**Decision:** Python 3.12 as the primary implementation language.

**Rationale:**
- QGIS 4.2.3 bundles Python 3.12.15 and PyQGIS is built against it.
- The QGIS Bridge (in-plugin code) must run in QGIS's embedded Python to access `qgis`, `qgis.PyQt`, `qgis.core`, `qgis.gui`, `qgis.processing`.
- The MCP server and supporting tools run on the system Python 3.12.10 and communicate with the bridge over IPC/HTTP.
- PyQt6 is available (QGIS 4.x is Qt6-based). All UI code targets PyQt6.

**Constraint:** `import qgis` fails on system Python. The bridge must run inside QGIS.

## 2. QGIS Bridge Location

**Decision:** The QGIS Bridge runs as a QGIS plugin (in-process with QGIS Desktop).

**Rationale:**
- GUI operations (canvas, layers, dialogs, windows) must run on the QGIS main thread.
- Running the bridge inside QGIS avoids cross-process PyQGIS marshaling complexity.
- The MCP server (out-of-process) talks to the bridge over authenticated localhost HTTP/IPC.

**Alternative considered:** Out-of-process bridge via `qgis_process` or standalone PyQGIS.
**Rejected:** QGIS 4.x `qgis_process` has limited GUI access and version drift risk; in-process is more reliable for visual automation.

## 3. IPC Transport: Bridge ↔ MCP Server

**Decision:** Authenticated localhost HTTP (REST/JSON-RPC style) with optional stdio for local MCP server invocation.

**Rationale:**
- QGIS plugin (in-process) can host a lightweight HTTP server (e.g., stdlib `http.server` or `aiohttp` if available).
- HTTP is firewall-friendly on localhost, supports request IDs, structured JSON responses, health endpoints, and reconnection.
- Stdio used when the MCP server is launched as a subprocess of the bridge or AI host.

**Security:** localhost-only binding, optional token-based authentication, CORS disabled.

## 4. MCP SDK

**Decision:** Use the official Python MCP SDK (`mcp` package) for the Universal MCP Server.

**Rationale:**
- Maintained SDK with stdio and Streamable HTTP transport support.
- Provides tool/resource/prompt primitives matching the MCP specification.
- Compatible with OpenCode and Codex MCP clients.

**Constraint:** Must inspect current MCP SDK compatibility before implementation (QGIS 4.2.3 / Python 3.12 environment).

## 5. Database

**Decision:** SQLite with WAL mode, migrations, indexes, foreign keys, transactions.

**Rationale:**
- Zero external database dependency (fits 8GB RAM / HDD environment).
- Single file, easy backup, ACID transactions.
- Repository + service layers keep SQL out of UI components.

**Tables:** `app_settings`, `ai_hosts`, `api_providers`, `api_profiles`, `mcp_servers`, `mcp_tools`, `agents`, `agent_tools`, `skills`, `agent_skills`, `workflows`, `workflow_steps`, `jobs`, `job_events`, `tool_runs`, `approvals`, `project_context`, `capability_registry`, `gcp_records`, `datasets`, `audit_logs`.

## 6. Credential Storage

**Decision:** Use OS credential manager where available (Windows Credential Manager via `keyring` or `ctypes`); fallback to encrypted local file (DPAPI-protected) only if credential manager unavailable.

**Rule:** Never store API keys in plaintext database fields or logs.

## 7. AI Integration

**Decision:** External AI only. No local LLM inference, no bundled models.

**Supported:**
- External AI hosts: OpenCode, Codex, other MCP-compatible clients (via MCP)
- Optional direct APIs: OpenAI, Gemini, Anthropic, OpenRouter, OpenAI-compatible, custom HTTP endpoints

**Configuration:** User-configurable providers, API keys (secure storage), model IDs, timeouts, retries, enable/disable, default provider. API integrations optional; plugin functions without any AI provider.

**Capability detection:** Detect image/screenshot support per client; document client-specific config.

## 8. UI Framework

**Decision:** PyQt6 (Qt6) for the QGIS plugin UI.

**Rationale:** QGIS 4.x is Qt6-based. PyQt5 is not available in the QGIS Python env. Native QGIS-compatible UI practices (dock widgets, toolbars, dialogs).

**Responsiveness:** Long GIS operations run in background `QgsTask` / worker threads with progress reporting; UI never blocks.

## 9. Threading Model

**Decision:** 
- QGIS GUI operations: strictly on QGIS main thread (via `QMetaObject.invokeMethod` or `QgsTask` with `mainThread()`).
- Background processing: `QgsTask` for raster/vector jobs; Python `threading` for non-GUI workers.
- No GUI operations from unsafe background threads (strict rule).

## 10. Concurrency Control

**Decision:** Sequential-by-default for project mutations; safe parallel execution only for independent read-only operations.

**Rationale:** Single CPU, 8GB RAM, and risk of conflicting writes to the same QGIS project/files. Agent orchestration prevents concurrent agents modifying the same project.

## 11. Georeferencing / Computer Vision

**Decision:** OpenCV (if installable) for feature detection (ORB, SIFT where available), matching, RANSAC, template matching. Fall back to pure-Python/Numpy methods if OpenCV unavailable.

**Rule:** Never invent coordinates. Match source pixels to trusted reference coordinates from reference rasters or verified geospatial sources. If insufficient, ask for reference data or human assistance.

## 12. Packaging

**Decision:** Installable QGIS plugin ZIP + standalone MCP server package; release ZIP containing both.

**Rationale:** QGIS plugins install via ZIP into the user profile plugins directory. The MCP server is a separate installable Python package.

## 13. Testing

**Decision:** `pytest` for unit/integration tests. Real QGIS tests where a QGIS instance is available; mocks/fakes only where QGIS cannot be headless.

**Rule:** Do not claim a test passed unless actually executed. No fabricated test results.

## 14. Path Handling (Windows)

**Decision:** Use `pathlib` and raw strings/quote handling for paths with spaces (e.g., `C:\Program Files\QGIS 4.2.3`, `D:\1 2 3 QGIS`).

**Rationale:** PowerShell and cmd break on unquoted spaces; `--` parsed as operator. All installation/runtime scripts quote paths.

## 15. Known Constraints (documented, not worked around silently)

| # | Constraint | Decision |
|---|-----------|----------|
| C1 | QGIS 4.x = Qt6 / PyQt6 only | UI targets PyQt6; no PyQt5 fallback |
| C2 | `import qgis` only in QGIS bundled Python | Bridge in-process; MCP server out-of-process via IPC |
| C3 | OpenCode `.ps1` blocked by execution policy | Use `opencode.cmd`; config via JSON files |
| C4 | Single CPU / 8GB RAM / HDD | Lazy loading, limited workers, chunked raster, sequential project writes |
| C5 | No bundled AI models | External AI hosts / optional APIs only |
| C6 | Existing QGIS plugin `magic_georeferencer` present | Not overwritten; our plugin installed side-by-side |
