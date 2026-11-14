# Universal AI GIS Studio — Troubleshooting Guide

**Version:** 1.0.0  
**Last Updated:** 2026-11-12

---

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [MCP Server Issues](#mcp-server-issues)
3. [QGIS Bridge Connection Issues](#qgis-bridge-connection-issues)
4. [QGIS Plugin Issues](#qgis-plugin-issues)
5. [Tool Execution Failures](#tool-execution-failures)
6. [Authentication & Permission Errors](#authentication--permission-errors)
7. [Visual Automation Issues](#visual-automation-issues)
8. [Georeferencing & CV Issues](#georeferencing--cv-issues)
9. [Performance & Resource Issues](#performance--resource-issues)
10. [OpenCode / Codex Integration Issues](#opencode--codex-integration-issues)
11. [Debugging Tools](#debugging-tools)
12. [Getting Help](#getting-help)

---

## Quick Diagnostics

Run these checks first to isolate the problem:

```bash
# 1. Check QGIS is running and plugin is enabled
# In QGIS: Plugins → Manage and Install Plugins → "Universal AI GIS Studio" ✓

# 2. Check Bridge health
curl http://127.0.0.1:8765/health
# Expected: {"status": "ok"}

# 3. Check MCP server starts
cd "D:\1 2 3 QGIS\Universal-AI-GIS-Studio"
python -m mcp_server.main --transport stdio
# Expected: [uagis] MCP server 'universal-ai-gis-studio' starting on stdio

# 4. Test basic tool via MCP (use OpenCode or test script)
# Should return qgis_version, gdal_version, bridge_connected: true
```

---

## MCP Server Issues

### Problem: `ModuleNotFoundError: No module named 'mcp'`

**Cause:** MCP SDK not installed in the current Python environment.

**Solution:**
```bash
# Install in the environment running the MCP server
pip install "mcp>=1.2.0"

# Or install the package with MCP extras
pip install -e ".[mcp]"
```

**Verify:**
```bash
python -c "import mcp; print(mcp.__version__)"
```

---

### Problem: `ModuleNotFoundError: No module named 'mcp.server.lowlevel'`

**Cause:** MCP SDK version mismatch. The code uses `mcp.server.lowlevel.Server` which requires MCP SDK 1.2+.

**Solution:**
```bash
pip install --upgrade "mcp>=1.2.0"
```

---

### Problem: `ImportError: cannot import name 'StreamableHTTPSessionManager'`

**Cause:** MCP SDK version doesn't have Streamable HTTP support, or uvicorn not installed.

**Solution:**
```bash
# For Streamable HTTP transport
pip install "mcp>=1.2.0" uvicorn

# Or use stdio transport instead (no uvicorn needed)
python -m mcp_server.main --transport stdio
```

---

### Problem: MCP server starts but OpenCode/Codex can't discover tools

**Cause:** MCP client configuration incorrect, or server not properly initialized.

**Checklist:**
1. ✅ MCP server running (stdio or HTTP)
2. ✅ Client config points to correct command/port
3. ✅ Working directory set correctly in client config
4. ✅ Environment variables passed (UAGIS_BRIDGE_URL, UAGIS_BRIDGE_TOKEN)

**OpenCode config example:**
```json
{
  "mcpServers": {
    "universal-ai-gis-studio": {
      "command": "python",
      "args": ["-m", "mcp_server.main", "--transport", "stdio"],
      "cwd": "D:\\1 2 3 QGIS\\Universal-AI-GIS-Studio",
      "env": {
        "UAGIS_BRIDGE_URL": "http://127.0.0.1:8765",
        "UAGIS_BRIDGE_TOKEN": "your-token"
      }
    }
  }
}
```

**Restart OpenCode after config changes.**

---

### Problem: `uvicorn` not found when using Streamable HTTP

**Cause:** uvicorn not installed.

**Solution:**
```bash
pip install uvicorn
```

---

## QGIS Bridge Connection Issues

### Problem: `Bridge unreachable at http://127.0.0.1:8765`

**Cause:** Bridge not running, wrong port, or firewall.

**Solutions:**

1. **Check Bridge is started in QGIS:**
   - Plugins → Universal AI GIS Studio → Start Bridge
   - Should show: "Bridge started on http://127.0.0.1:8765"

2. **Verify port in QGIS Plugin Settings:**
   - Plugins → Universal AI GIS Studio → Settings
   - Bridge Port: 8765 (default)

3. **Check Windows Firewall:**
   - Allow Python/QGIS through firewall for localhost
   - Or run: `netsh advfirewall firewall add rule name="UAGIS Bridge" dir=in action=allow protocol=TCP localport=8765`

4. **Test with curl:**
   ```bash
   curl http://127.0.0.1:8765/health
   ```

---

### Problem: `Bridge HTTP 401 UNAUTHORIZED`

**Cause:** Auth token mismatch or missing.

**Solutions:**

1. **Check token in QGIS Plugin Settings:**
   - Plugins → Universal AI GIS Studio → Settings
   - Copy the "Auth Token" value

2. **Set token in MCP server env:**
   ```bash
   set UAGIS_BRIDGE_TOKEN=your-token-here
   python -m mcp_server.main --transport stdio
   ```

3. **Or disable auth for development (not for production):**
   - In QGIS Plugin Settings, clear the Auth Token field
   - Restart Bridge

---

### Problem: `Bridge HTTP 404 NOT_FOUND`

**Cause:** Wrong endpoint path.

**Solution:** Bridge only exposes:
- `POST /dispatch` — Tool execution
- `GET /health` — Health check

**Check MCP server bridge_url:** Should be `http://127.0.0.1:8765` (no trailing slash, no `/api` prefix)

---

### Problem: `Bridge HTTP 500` or timeout

**Cause:** Bridge crashed, QGIS not responding, or operation timed out.

**Debugging:**
1. Check QGIS message log: **View → Panels → Log Messages**
2. Look for Python errors in QGIS Log Messages panel
3. Increase timeout: `UAGIS_MCP_TIMEOUT=600` (seconds)
4. Restart Bridge: Stop → Start in QGIS plugin menu

---

## QGIS Plugin Issues

### Problem: Plugin doesn't appear in QGIS Plugin Manager

**Cause:** Plugin not installed, or installed to wrong profile.

**Solutions:**
1. **Install from ZIP:**
   - Plugins → Manage and Install Plugins → Install from ZIP
   - Select `universal_ai_gis-1.0.0.zip` from build output

2. **Check plugin path:**
   - Windows: `%APPDATA%\QGIS\QGIS4\python\plugins\universal_ai_gis`
   - Or: `%USERPROFILE%\AppData\Roaming\QGIS\QGIS4\python\plugins\universal_ai_gis`

3. **Enable experimental plugins:**
   - Settings → Options → Plugins → ✓ Show also experimental plugins

---

### Problem: Plugin fails to load: `ModuleNotFoundError: No module named 'bridge'`

**Cause:** Plugin can't find bridge module — Python path issue.

**Solution:** The plugin must be installed in QGIS's Python environment, not system Python.

```bash
# Install in QGIS Python environment
"C:\Program Files\QGIS 4.2.3\bin\python.exe" -m pip install -e "D:\1 2 3 QGIS\Universal-AI-GIS-Studio"
```

Then restart QGIS.

---

### Problem: Bridge won't start — "Address already in use"

**Cause:** Port 8765 already occupied.

**Solutions:**
1. **Change port in Plugin Settings** (e.g., 8767)
2. **Update MCP server env:** `UAGIS_BRIDGE_URL=http://127.0.0.1:8767`
3. **Kill existing process:**
   ```powershell
   netstat -ano | findstr :8765
   taskkill /PID <PID> /F
   ```

---

### Problem: QGIS crashes when Bridge starts

**Cause:** HTTP server thread conflict with QGIS main thread.

**Debug:**
1. Check QGIS Log Messages for Python traceback
2. Ensure bridge uses `QThread` or `threading.Thread` properly
3. Report issue with crash dump

---

## Tool Execution Failures

### Problem: `qgis.layers.load` returns `FAILED` / `LAYER_INVALID`

**Cause:** File path wrong, format unsupported, or file corrupted.

**Checklist:**
- ✅ Path uses forward slashes or raw strings: `D:/data/file.gpkg` or `r"D:\data\file.gpkg"`
- ✅ File exists and is readable
- ✅ Format supported (GeoPackage, Shapefile, GeoJSON, GeoTIFF, etc.)
- ✅ File not open exclusively in another application

**Debug:**
```json
{
  "tool": "qgis.layers.load",
  "arguments": {"path": "D:/data/parcels.gpkg"}
}
```
Check error context for details.

---

### Problem: `qgis.algorithms.execute` returns `FAILED` / `ALGORITHM_ERROR`

**Cause:** Algorithm not found, invalid parameters, or processing framework issue.

**Debugging Steps:**

1. **Discover available algorithms first:**
   ```json
   {"tool": "qgis.algorithms.discover", "arguments": {}}
   ```

2. **Check algorithm ID is exact:** e.g., `native:buffer` not `buffer`

3. **Verify parameters match algorithm specification:**
   - Required vs optional
   - Correct types (string vs number vs layer reference)
   - Output parameter: use `"OUTPUT": "memory:"` for temporary layers

4. **Check layer references:** Use layer IDs from `qgis.layers.inspect`, not names

**Example correct buffer call:**
```json
{
  "algorithm": "native:buffer",
  "parameters": {
    "INPUT": "parcels_abc123",
    "DISTANCE": 100,
    "SEGMENTS": 5,
    "END_CAP_STYLE": 0,
    "JOIN_STYLE": 0,
    "MITER_LIMIT": 2,
    "DISSOLVE": false,
    "OUTPUT": "memory:"
  }
}
```

---

### Problem: Tool returns `PARTIAL_SUCCESS` — what does it mean?

**Cause:** Operation executed but verification incomplete.

**Common Cases:**
| Tool | Why PARTIAL_SUCCESS | Next Step |
|------|---------------------|-----------|
| `qgis.project.open` | Project opened but layer count not verified | Call `qgis.project.inspect` |
| Layout creation | Layout created but not exported | Call export tool |
| Long algorithm | Job queued, not yet complete | Check `qgis.jobs.inspect` or `qgis.verify.status` |

**Action:** Check `result` for details, then call follow-up tool or verify status.

---

### Problem: Tool returns `NEEDS_REVIEW`

**Cause:** Human review required (typically georeferencing).

**Action:** 
1. Open QGIS and inspect visually
2. Use `qgis.verify.status` with request_id for details
3. Approve/reject via QGIS plugin UI or appropriate tool

---

## Authentication & Permission Errors

### Problem: `PERMISSION_DENIED` for tool

**Cause:** Agent/user lacks required permission.

**Solutions:**
1. **Check tool permissions in TOOL_REFERENCE.md**
2. **Grant permission in QGIS Plugin → Settings → Agent Permissions**
3. **Or use admin agent with full permissions**

**Permission hierarchy:**
```
qgis:read                          # Base read access
qgis:layer:write                   # Load/remove layers
qgis:algorithm:execute             # Run processing
qgis:project:write                 # Open/save projects
qgis:cursor:write                  # AI cursor control
... (see TOOL_REFERENCE.md for full list)
```

---

### Problem: `APPROVAL_REQUIRED` but no approval prompt

**Cause:** Approval system not configured, or UI not showing.

**Solutions:**
1. Check QGIS Plugin → Approvals panel
2. Look for notification in QGIS message bar
3. Check `approvals` table in database
4. For development: set `require_approval: false` in tool registry (not recommended for production)

---

## Visual Automation Issues

### Problem: AI cursor not visible / not moving

**Cause:** Cursor controller not initialized, or wrong window handle.

**Debug:**
1. Call `qgis.window.inspect` — verify QGIS window detected
2. Call `qgis.screen.capture` — verify screenshot works
3. Check cursor permissions: `qgis:cursor:write`
4. Ensure QGIS window is active and not minimized

---

### Problem: `qgis.cursor.move` succeeds but click doesn't work

**Cause:** Click target not under cursor, or QGIS focus issue.

**Debug:**
1. Add small delay between move and click
2. Verify cursor position with screenshot after move
3. Ensure QGIS has focus: `qgis.window.inspect` shows active state

---

### Problem: Screen capture returns black/empty image

**Cause:** Canvas not rendered, or capture target wrong.

**Solutions:**
1. Ensure QGIS map canvas is visible (not covered by dialogs)
2. Pan/zoom canvas to trigger render
3. Call `qgis.canvas.inspect` to verify extent/layers

---

## Georeferencing & CV Issues

### Problem: `qgis.georeference.analyze` returns low quality_score

**Cause:** Image blurry, low contrast, no clear landmarks.

**Solutions:**
- Use higher resolution scan (300+ DPI)
- Ensure map has clear grid lines, text, known features
- Try `qgis.gcp.generate` with good reference raster

---

### Problem: `qgis.gcp.generate` returns 0 GCPs

**Cause:** No matches found between image and reference.

**Solutions:**
1. Verify reference_source path is correct and loaded in QGIS
2. Check reference raster has same geographic area
3. Try manual GCP entry first
4. Ensure OpenCV is installed: `pip install opencv-python-headless`

---

### Problem: `qgis.gcp.validate` returns high RMSE

**Cause:** Poor GCP distribution, outliers, or wrong reference.

**Solutions:**
1. Check `rejected` array for outliers
2. Ensure GCPs spread across image (not clustered)
3. Minimum 4 GCPs, prefer 6+ for polynomial transforms
4. Verify reference raster CRS matches target CRS

---

### Problem: OpenCV not available / `ImportError: cv2`

**Cause:** OpenCV not installed in QGIS Python environment.

**Solution:**
```bash
# In QGIS Python environment
"C:\Program Files\QGIS 4.2.3\bin\python.exe" -m pip install opencv-python-headless
```

**Fallback:** System uses pure Python/NumPy methods if OpenCV unavailable (slower, fewer features).

---

## Performance & Resource Issues

### Problem: Operations very slow / time out

**Cause:** 8GB RAM, HDD, single CPU constraints.

**Optimizations:**
1. **Use memory outputs:** `"OUTPUT": "memory:"` instead of file paths
2. **Chunk large rasters:** Process in tiles
3. **Limit parallel workers:** Set `QGIS_MAX_THREADS=2` env var
4. **Close unused layers/projects** to free memory
5. **Use spatial indexes** on vector layers before spatial operations

---

### Problem: Out of memory / QGIS crashes on large rasters

**Cause:** 8GB RAM limit exceeded.

**Solutions:**
1. Process in chunks using `gdal:warpreproject` with tile options
2. Use virtual rasters (VRT) for mosaics
3. Increase Windows page file
4. Close other applications

---

### Problem: Bridge becomes unresponsive

**Cause:** Long-running job blocking HTTP server thread.

**Solutions:**
1. Bridge should use `QgsTask` for background jobs
2. Increase MCP server timeout: `UAGIS_MCP_TIMEOUT=600`
3. Restart Bridge from QGIS plugin menu

---

## OpenCode / Codex Integration Issues

### Problem: OpenCode `.ps1` script blocked by execution policy

**Cause:** PowerShell execution policy prevents running OpenCode.

**Solution:** Use `opencode.cmd` instead:
```json
{
  "mcpServers": {
    "universal-ai-gis-studio": {
      "command": "opencode.cmd",
      "args": ["mcp", "stdio"],
      "cwd": "D:\\1 2 3 QGIS\\Universal-AI-GIS-Studio"
    }
  }
}
```

Or configure OpenCode MCP via JSON config file (see GETTING_STARTED.md).

---

### Problem: Codex doesn't show MCP tools

**Cause:** MCP server not configured correctly in Codex settings.

**Solution:** 
1. Codex Settings → MCP Servers → Add Server
2. Transport: stdio
3. Command: `python`
4. Args: `["-m", "mcp_server.main", "--transport", "stdio"]`
5. Working Directory: `D:/1 2 3 QGIS/Universal-AI-GIS-Studio`
6. Restart Codex

---

### Problem: AI calls tool but gets no response / hangs

**Cause:** MCP server crashed, or Bridge not responding.

**Debug:**
1. Check MCP server console for errors
2. Check Bridge health: `curl http://127.0.0.1:8765/health`
3. Restart both MCP server and Bridge

---

## Debugging Tools

### Enable Debug Logging

**MCP Server:**
```bash
set UAGIS_LOG_LEVEL=DEBUG
python -m mcp_server.main --transport stdio
```

**QGIS Bridge:** Check QGIS Log Messages panel (View → Panels → Log Messages)

**Python Debugging:**
```python
# Add to any tool for debugging
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

### Test Bridge Directly (without MCP)

```bash
# Health check
curl http://127.0.0.1:8765/health

# Direct tool dispatch
curl -X POST http://127.0.0.1:8765/dispatch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-token" \
  -d '{
    "request_id": "test_123",
    "tool": "qgis.system.inspect",
    "params": {},
    "timeout_seconds": 30
  }'
```

---

### Inspect Database

```bash
# SQLite database location
# Windows: %APPDATA%\Universal-AI-GIS-Studio\uagis.db

sqlite3 "%APPDATA%\Universal-AI-GIS-Studio\uagis.db" ".tables"
sqlite3 "%APPDATA%\Universal-AI-GIS-Studio\uagis.db" "SELECT * FROM jobs ORDER BY created_at DESC LIMIT 10;"
```

---

### QGIS Python Console Debugging

Open QGIS → Plugins → Python Console:

```python
# Test PyQGIS directly
from qgis.core import QgsProject, QgsVectorLayer
layer = QgsVectorLayer("D:/data/parcels.gpkg", "test", "ogr")
print("Valid:", layer.isValid())
print("CRS:", layer.crs().authid())
print("Features:", layer.featureCount())

# Test processing
import processing
result = processing.run("native:buffer", {
    'INPUT': layer, 'DISTANCE': 100, 'OUTPUT': 'memory:'
})
print("Buffer result:", result)
```

---

## Getting Help

### Before Reporting Issues

Collect:
1. **OS/QGIS versions:** Windows version, QGIS 4.2.3, Python 3.12
2. **Error messages:** Full traceback from logs
3. **Steps to reproduce:** Minimal sequence
4. **Configuration:** Relevant env vars, plugin settings
5. **Tool call:** Exact JSON request that failed

### Log Locations

| Component | Log Location |
|-----------|--------------|
| MCP Server | Console output (stderr) |
| QGIS Bridge | QGIS Log Messages panel |
| QGIS Plugin | QGIS Log Messages panel |
| Database | `%APPDATA%\Universal-AI-GIS-Studio\logs\` |
| Audit | `audit_logs` table in SQLite |

### Common Resources

- **Documentation:** `docs/` folder (GETTING_STARTED, TOOL_REFERENCE, ARCHITECTURE)
- **Test Plan:** `docs/TEST_PLAN.md` for verification criteria
- **Source Code:** `mcp_server/`, `bridge/`, `clusters/`, `plugin/`
- **Schema:** `database/schema.py` for database structure

---

## Quick Reference: Error Codes

| Code | HTTP | Meaning | Typical Fix |
|------|------|---------|-------------|
| `VALIDATION_ERROR` | 400 | Input schema invalid | Check tool input schema |
| `UNAUTHORIZED` | 401 | Bad/missing token | Set correct UAGIS_BRIDGE_TOKEN |
| `NOT_FOUND` | 404 | Tool/endpoint unknown | Check tool name, Bridge URL |
| `LAYER_INVALID` | 400 | Layer load failed | Verify file path/format |
| `ALGORITHM_ERROR` | 400 | Processing failed | Check algorithm ID, parameters |
| `BRIDGE_ERROR` | 500/502 | Bridge communication failed | Restart Bridge, check QGIS |
| `TIMEOUT` | 504 | Operation too slow | Increase timeout, optimize |
| `APPROVAL_REQUIRED` | 403 | Needs human approval | Approve in QGIS plugin |
| `PERMISSION_DENIED` | 403 | Insufficient permissions | Grant permission to agent |

---

*If your issue isn't covered here, check the GitHub issues or start a new discussion with the collected diagnostic information.*