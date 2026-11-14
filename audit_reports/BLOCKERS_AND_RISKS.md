# BLOCKERS AND RISKS — Universal AI GIS Studio

## Critical Blockers

### B1: QGIS Plugin Load Not Verified
**Severity:** Critical  
**Impact:** Cannot verify core product functionality  
**Details:** The QGIS plugin could not be loaded in a running QGIS instance during this audit. Initial load failed due to `classFactory` missing from `__init__.py` (since fixed in release ZIP). The fix is in code but not retested against QGIS.  
**Evidence:** QGIS_INTEGRATION_AUDIT.md  
**Resolution:** Load plugin in QGIS 4.2.3 and verify `classFactory` is called, bridge starts, and tools respond.

### B2: Real QGIS GIS Execution Not Verified
**Severity:** Critical  
**Impact:** Cannot confirm any GIS operation actually works in production  
**Details:** All PyQGISExecutor code paths are correct but untested against a running QGIS instance. No test proves that `qgis.layers.load`, `qgis.algorithms.execute`, or `qgis.screen.capture` actually work inside QGIS.  
**Evidence:** REAL_EXECUTION_AUDIT.md  
**Resolution:** Run integration tests with a QGIS instance; verify layer loading, algorithm execution, and screenshot capture.

### B3: No End-to-End MCP → QGIS Test
**Severity:** Critical  
**Impact:** Cannot confirm AI can control QGIS through MCP  
**Details:** MCP server code is complete but tool invocation end-to-end (MCP client → MCP server → Bridge → QGIS → output) was never tested.  
**Evidence:** MCP_AUDIT.md  
**Resolution:** Configure OpenCode with the MCP server, start QGIS Bridge, and execute a real tool chain.

## High Risks

### R1: Plugin sys.path Issue
**Severity:** High  
**Details:** `plugin.py` imports `bridge.*`, `core.*`, `database.*` without adding project root to `sys.path`. Inside QGIS, these imports will fail unless the path is fixed.  
**Fix:** Already applied in release ZIP (sys.path.insert added). Source file still needs the fix for consistency.  
**Evidence:** bridge/executor.py imports in plugin.py

### R2: Bridge Auth Optional (Dev Mode)
**Severity:** High  
**Details:** When `bridge_auth_token` is not configured, the bridge allows all connections without authentication. This is acceptable for development but a security risk in production.  
**Fix:** Make authentication mandatory in production mode.  
**Evidence:** bridge/request_handler.py `_check_auth()` returns True when token is None

### R3: Agent Tool Execution Not Implemented
**Severity:** High  
**Details:** 29 agents exist but `agent.execute_task()` only returns delegation status. Agents do not actually call GIS tools or MCP tools.  
**Fix:** Implement agent-to-tool dispatch through the orchestrator.  
**Evidence:** AGENTS_29_AUDIT.md

### R4: Workflow Placeholder Nodes
**Severity:** High  
**Details:** MCP Tool, Agent, and API workflow nodes return placeholders (`mcp_tool_placeholder`, `api_placeholder`). Complete workflows cannot execute end-to-end.  
**Fix:** Implement real node handlers for MCP Tool, Agent, and API.  
**Evidence:** WORKFLOW_AUDIT.md

### R5: No System-Wide Emergency Stop
**Severity:** Medium  
**Details:** Emergency stop exists only for the AI cursor. No system-wide emergency stop that halts all jobs, bridge connections, and MCP operations.  
**Fix:** Implement system-wide emergency stop.  
**Evidence:** DATABASE_SECURITY_AUDIT.md

### R6: Missing Built-in Skills
**Severity:** Medium  
**Details:** Documentation claims 7 built-in skills but only 1 exists (automatic-georeferencing).  
**Fix:** Implement remaining 6 skills or update documentation.  
**Evidence:** SKILLS_AUDIT.md

### R7: No Temp File Cleanup / Cache Limits
**Severity:** Medium  
**Details:** Configuration options exist but no implementation for temp file cleanup or cache limits. Important for 8 GB RAM / HDD environment.  
**Fix:** Implement cleanup and cache limit enforcement.  
**Evidence:** DATABASE_SECURITY_AUDIT.md

## Moderate Risks

### R8: No Real-World Georeferencing Test
**Severity:** Medium  
**Details:** No sample scanned map + reference raster available for end-to-end georeferencing test.  
**Fix:** Acquire test data and run real georeferencing pipeline.  
**Evidence:** GEOREFERENCING_AUDIT.md

### R9: No UI Panel Implementation
**Severity:** Medium  
**Details:** All 19 plugin UI panels are placeholder labels ("implementation in progress").  
**Fix:** Implement actual UI panels.  
**Evidence:** FAKE_EXECUTOR_AUDIT.md

### R10: No Import/Export for Workflows or Skills
**Severity:** Low  
**Details:** Workflow and skill import/export not implemented.  
**Fix:** Add ZIP/JSON import/export.  
**Evidence:** WORKFLOW_AUDIT.md, SKILLS_AUDIT.md

## Blocker Summary

| Blocker | Severity | Resolution Required Before Production Use |
|---------|----------|------------------------------------------|
| QGIS plugin load not verified | Critical | YES |
| Real QGIS GIS execution not verified | Critical | YES |
| No end-to-end MCP → QGIS test | Critical | YES |
| Plugin sys.path issue | High | YES (fixed in ZIP, fix source) |
| Bridge auth optional | High | YES |
| Agent tool execution not implemented | High | YES |
| Workflow placeholder nodes | High | YES |
| No system-wide emergency stop | Medium | YES |
| Missing built-in skills | Medium | YES |
| No temp file cleanup | Medium | YES |
