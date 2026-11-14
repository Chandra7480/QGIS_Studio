# Universal AI GIS Studio — Test Plan

**Version:** 1.0.0  
**Last Updated:** 2026-11-11  
**Rule:** No test is reported as passed unless actually executed. No fabricated results.

## 1. Test Levels

| Level | Scope | Tools |
|-------|-------|-------|
| Unit | Individual modules/classes/functions | `pytest`, mocks where QGIS unavailable |
| Integration | Module-to-module (bridge ↔ MCP, bridge ↔ QGIS, DB repositories) | `pytest`, real SQLite, real QGIS where available |
| System | End-to-end: MCP tool → bridge → QGIS operation → verification | Real QGIS Desktop, real MCP client |
| Visual | Screen capture, cursor, mouse/keyboard, dialog inspection | Real QGIS Desktop, screenshots |
| Georeferencing | GCP generation, validation, transformation, RMSE on real sample data | Real sample scanned map + reference raster |
| Security | Credential storage, allowlists, approvals, audit logs, extension trust | Unit + integration |
| Acceptance | Final acceptance criteria (Section 28 of master prompt) | Real QGIS + MCP client |

## 2. Test Directory Structure

```
tests/
├── unit/
│   ├── test_config.py
│   ├── test_database.py
│   ├── test_logging.py
│   ├── test_event_bus.py
│   ├── test_job_manager.py
│   ├── test_permission_manager.py
│   └── test_capability_registry.py
├── integration/
│   ├── test_bridge_connection.py
│   ├── test_mcp_tool_registry.py
│   ├── test_qgis_project_inspect.py
│   ├── test_qgis_layer_inspect.py
│   └── test_mcp_qgis_end_to_end.py
├── security/
├── visual/
├── georeferencing/
└── acceptance/
```

## 3. Stage 2 Tests (Core Foundation)

- `test_config`: settings read/write, defaults, type coercion
- `test_database`: schema creation, WAL mode, migrations, FKs, transactions
- `test_logging`: log rotation, structured output, levels
- `test_event_bus`: publish/subscribe, delivery, unsubscribe
- `test_job_manager`: job create/update/cancel, event persistence
- `test_permission_manager`: allowlist check, agent permission, approval flow
- `test_capability_registry`: register/lookup capability, version-aware

## 4. Stage 3 Tests (QGIS Bridge)

- Bridge starts and binds to localhost port
- Health endpoint returns OK
- `qgis.project.inspect` returns project metadata (title, path, CRS, layer count)
- `qgis.layers.inspect` returns layer list with validity, type, CRS, extent
- `qgis.layers.load` loads a real vector/raster file; layer appears in project
- Long-running job supports cancellation
- Reconnection after bridge restart
- No GUI operations from background threads (verified by code review + test)

## 5. Stage 4 Tests (MCP Server)

- MCP server starts on stdio and Streamable HTTP
- `qgis.system.inspect` returns QGIS version, GDAL version, Python version
- `qgis.system.health` returns bridge connection status
- `qgis.layers.load` via MCP loads a real layer in QGIS
- Tool input schema validation rejects invalid input
- Tool returns structured output (never fabricated success)
- Permission denial returns structured error
- OpenCode can discover tools via MCP
- No fake tools registered

## 6. Stage 5 Tests (Visual Automation)

- QGIS window detection returns window handle/title
- Screenshot capture returns valid image of QGIS canvas
- AI cursor moves within authorized QGIS window only
- Mouse click/double-click/right-click/drag/scroll execute
- Keyboard type/hotkey execute
- Dialog inspection detects open dialogs
- Screen re-check after action (verification loop)
- Emergency stop halts cursor/mouse/keyboard
- Human override restores control

## 7. Stage 6 Tests (Computer Vision & Georeferencing)

- Image inspection returns dimensions, resolution, quality metrics
- ORB feature detection returns keypoints + descriptors
- Feature matching returns candidate correspondences
- GCP generation returns candidates with source/dest coords, confidence, description
- GCP validation rejects duplicates and outliers; reports RMSE/residuals
- Georeferencing produces a real output raster file
- Output CRS and extent verified
- Visual overlay comparison shows alignment
- RMSE report generated
- No coordinates invented (verified on synthetic test where reference known)

## 8. Stage 7 Tests (25 Clusters)

Each cluster M01–M25 has at least one integration test executing a real operation:
- M01: discover/import a real dataset
- M03: buffer/clip/dissolve on real vector layer; check output validity + feature count
- M04: raster calculation on real raster; check output exists + dimensions
- M06: reproject a layer; check output CRS matches target
- M07: spatial join; check output has joined attributes
- M18: create a layout; check export file exists
- M20: connect to GeoPackage; run spatial SQL; check results
- M25: validate geometry; report invalid features

Rule: Every cluster test uses real data, real algorithms, and verification checks (not just "submitted").

## 9. Stage 8–10 Tests (Integrations, Agents, Skills)

- API provider connection test (when credentials configured)
- MCP server add/remove/connect/disconnect
- Agent delegation: supervisor assigns task to worker; worker reports result
- Custom agent creation via builder; agent executes within permissions
- Skill import + validation + execution
- Untrusted skill blocked from shell/fs/network

## 10. Stage 11 Tests (Workflow Builder)

- Workflow with GIS Tool node executes real handler
- Pause/resume/cancel/retry function
- Error recovery path executes
- Execution history recorded

## 11. Stage 13 Tests (Security)

- Destructive operation requires approval (delete layer, overwrite file)
- Audit log records the action + approver + timestamp
- Credential not retrievable in plaintext from DB/logs
- Extension with invalid manifest rejected
- Emergency stop halts running jobs

## 12. Stage 14 Acceptance Tests (Final)

| # | Criterion | Test Method | Status |
|---|-----------|-------------|--------|
| A1 | QGIS plugin installs and loads | Install ZIP in QGIS plugin manager; confirm plugin enabled | ⬜ |
| A2 | QGIS Bridge connects reliably | Restart QGIS; health endpoint returns OK | ⬜ |
| A3 | MCP server starts correctly | Launch MCP server; stdio + HTTP listen | ⬜ |
| A4 | OpenCode discovers/executes real GIS tools | Configure OpenCode MCP; call `qgis.layers.inspect`; confirm layer list returned | ⬜ |
| A5 | Real QGIS screenshots captured | `qgis.screen.capture` returns valid image | ⬜ |
| A6 | AI cursor moves inside QGIS window | `qgis.cursor.move` + screenshot confirms cursor position | ⬜ |
| A7 | Dynamic algorithm discovery | `qgis.algorithms.discover` returns installed algorithms only | ⬜ |
| A8 | All 25 clusters tested real | Run M01–M25 integration tests | ⬜ |
| A9 | Auto GCP generation on real sample | Run georeferencing on sample scanned map | ⬜ |
| A10 | Georeferencing produces real output raster | Output file exists; CRS + extent verified | ⬜ |
| A11 | Agents execute delegated tasks | Supervisor → worker task completes | ⬜ |
| A12 | Skills imported and validated | Import built-in skill; execute; confirm result | ⬜ |
| A13 | Workflows execute real GIS ops | Workflow with GIS Tool node completes | ⬜ |
| A14 | Emergency stop works | Trigger emergency stop; jobs halt | ⬜ |
| A15 | Audit logs + backups work | Confirm log entries + backup file exist | ⬜ |
| A16 | Installable release package generated + tested | Build ZIP; install on clean QGIS; confirm functions | ⬜ |

## 13. Test Data

Sample test data (not bundled with release; referenced in docs):
- A small GeoPackage vector layer
- A small GeoTIFF raster
- A sample scanned map (for georeferencing tests)
- A reference raster with known CRS

Test data paths are configurable; tests skip gracefully if data unavailable (recorded as "skipped", not "passed").
