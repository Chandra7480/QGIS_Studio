# GAP REPORT — Universal AI GIS Studio
**Generated:** 2026-11-11  
**Project:** D:\1 2 3 QGIS\Universal-AI-GIS-Studio  
**Environment:** Windows 10 x64, QGIS 4.2.3 (Qt6), Python 3.12, GDAL 3.13.3, OpenCode 1.19.5

---

## 1. Tool Namespace Mismatch (Registry vs Dispatcher)

**mcp_server/registry.py** declares ~50 tools across these namespaces:
- qgis.system (inspect, health)
- qgis.project (open, save, inspect)
- qgis.layers (inspect, load, remove)
- qgis.canvas (inspect)
- qgis.screen (capture)
- qgis.cursor (move, click, drag)
- qgis.keyboard (type, hotkey)
- qgis.mouse (scroll)
- qgis.window (inspect)
- qgis.dialog (inspect)
- qgis.algorithms (discover, execute)
- qgis.georeference (analyze)
- qgis.gcp (generate, validate)
- qgis.raster (*)
- qgis.vector (*)
- qgis.spatial (*)
- qgis.database (*)
- qgis.layout (*)
- qgis.workflow (execute)
- qgis.agents (*)
- qgis.skills (*)
- qgis.verify (*)
- qgis.jobs (cancel)
- qgis.history (inspect)
- qgis.plugins (*)

**bridge/dispatcher.py** registers only **11 handlers** (lines 21-32):
```
qgis.system.inspect, qgis.system.health,
qgis.project.inspect,
qgis.layers.inspect, qgis.layers.load, qgis.layers.remove,
qgis.canvas.inspect,
qgis.screen.capture,
qgis.algorithms.discover, qgis.algorithms.execute
```

**Missing handlers (declared in registry but NOT in dispatcher):**
- qgis.project.open
- qgis.project.save
- qgis.cursor.move, qgis.cursor.click, qgis.cursor.drag
- qgis.keyboard.type, qgis.keyboard.hotkey
- qgis.mouse.scroll
- qgis.window.inspect
- qgis.dialog.inspect
- qgis.georeference.analyze
- qgis.gcp.generate, qgis.gcp.validate
- qgis.workflow.execute
- qgis.raster.*, qgis.vector.*, qgis.spatial.*, qgis.database.*, qgis.layout.*
- qgis.agents.*, qgis.skills.*, qgis.verify.*, qgis.plugins.*
- qgis.jobs.cancel, qgis.history.inspect

---

## 2. Executor Method Mismatch (Dispatcher vs Executor)

**bridge/executor.py** has these methods:
- inspect_project, inspect_layers, inspect_canvas
- load_layer, remove_layer
- capture_canvas
- execute_algorithm
- health

**Missing executor methods for dispatcher tools:**
- open_project(path)
- save_project(path=None)
- cursor_move(x, y), cursor_click(), cursor_drag(x1, y1, x2, y2)
- keyboard_type(text), keyboard_hotkey(keys)
- mouse_scroll(delta)
- window_inspect()
- dialog_inspect()
- georeference_analyze(image_path)
- gcp_generate(image_path, reference_source)
- gcp_validate(gcps)
- workflow_execute(workflow_id)

---

## 3. Agents Folder Empty

**agents/builtins/** — **0 files** (empty directory)
Documentation claims 29 built-in agents. No agent files exist.

---

## 4. MCP Server Tools Folder Empty

**mcp_server/tools/** — **0 entries** (empty directory)
No tool implementation modules exist.

---

## 5. Docs Folder Empty

**docs/** — **0 entries** (empty directory)
README.md says documentation should be in docs/:
- SYSTEM_ARCHITECTURE.md
- DEVELOPMENT_STATUS.md
- IMPLEMENTATION_CHECKLIST.md
- TECHNICAL_DECISIONS.md
- TEST_PLAN.md

These 5 files currently exist at project root but NOT in docs/.

---

## 6. Port Mismatch

- **bridge/bridge_server.py** (line 18): default port = **8765**
- **mcp_server/qgis_client.py** (line 24-25): default URL = `http://127.0.0.1:8766` (via UAGIS_BRIDGE_URL)
- **mcp_server/main.py** (line 28): default port = **8766**

**Result:** MCP client tries to connect to port 8766, but bridge serves on 8765. Connection will fail unless UAGIS_BRIDGE_URL is manually overridden.

---

## 7. UI Placeholder Panels

**plugin/universal_ai_gis/main_window.py** — All 19 panels show placeholder QLabel "implementation in progress":
Dashboard, AI Chat, Live Screen, AI Cursor, AI Connections, API Providers, MCP Manager, Agent Manager, Skill Manager, GIS Clusters, Georeferencing, GCP Intelligence, Workflow Builder, Algorithm Discovery, Data Manager, Quality Control, Task History, Security, Settings.

---

## 8. Testing Gap

- 46 unit tests pass, but ALL use FakeExecutor mocks — **no real QGIS 4.2.3 integration**
- tests/integration/ folder exists but has no real QGIS integration tests

---

## Summary of Fixes Required

| # | Issue | File(s) | Priority |
|---|-------|---------|----------|
| 1 | Port mismatch (8765 vs 8766) | bridge/bridge_server.py, mcp_server/qgis_client.py, mcp_server/main.py | Critical |
| 2 | Missing executor methods (~14) | bridge/executor.py | Critical |
| 3 | Missing dispatcher handlers (~25) | bridge/dispatcher.py | Critical |
| 4 | Wildcard stub tools | mcp_server/registry.py | High |
| 5 | 29 built-in agents missing | agents/builtins/ | High |
| 6 | MCP tools modules missing | mcp_server/tools/ | High |
| 7 | Docs folder empty | docs/ | Medium |
| 8 | UI placeholder panels | plugin/universal_ai_gis/main_window.py | Medium |
| 9 | Real QGIS integration tests missing | tests/integration/ | Medium |
