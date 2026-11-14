# Universal AI GIS Studio — Getting Started Guide

**Version:** 1.0.0  
**Last Updated:** 2026-11-12

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the MCP Server](#running-the-mcp-server)
5. [Connecting an MCP Client](#connecting-an-mcp-client)
6. [Your First Tool Call](#your-first-tool-call)
7. [Verification States Explained](#verification-states-explained)
8. [Next Steps](#next-steps)

---

## Prerequisites

| Component | Minimum Version | Notes |
|-----------|----------------|-------|
| **QGIS Desktop** | 4.2.3 (Qt6) | Windows: `C:\Program Files\QGIS 4.2.3` |
| **Python** | 3.11+ | QGIS bundles Python 3.12.15 |
| **GDAL/OGR** | 3.13.3 | Bundled with QGIS |
| **OpenCode / Codex / MCP Client** | Latest | Any MCP-compatible client |
| **uvicorn** | 0.30+ | For Streamable HTTP transport |

**System Requirements:**
- Windows 10 x64 (tested)
- 8 GB RAM minimum
- HDD/SSD for project storage
- No GPU required (external AI only)

---

## Installation

### 1. Install QGIS 4.2.3

Download from [qgis.org](https://qgis.org/downloads/) and install to the default location:
```
C:\Program Files\QGIS 4.2.3
```

Verify QGIS Python environment:
```powershell
"C:\Program Files\QGIS 4.2.3\bin\python.exe" -c "import qgis; print(qgis.__version__)"
# Expected: 4.2.3
```

### 2. Clone the Repository

```powershell
git clone <repository-url> "D:\1 2 3 QGIS"
cd "D:\1 2 3 QGIS\Universal-AI-GIS-Studio"
```

### 3. Install Python Dependencies

**For the MCP Server (system Python 3.11+):**
```powershell
# Using pip
pip install -e ".[mcp]"

# Or with pipx (recommended for isolation)
pipx install -e ".[mcp]"
```

**For the QGIS Bridge (QGIS bundled Python):**
```powershell
# Inside QGIS Python environment
"C:\Program Files\QGIS 4.2.3\bin\python.exe" -m pip install -e "D:\1 2 3 QGIS\Universal-AI-GIS-Studio"
```

### 4. Install the QGIS Plugin

```powershell
# Build plugin ZIP
cd "D:\1 2 3 QGIS\Universal-AI-GIS-Studio"
python -m build --wheel --sdist  # or use the provided build script

# In QGIS: Plugins → Manage and Install Plugins → Install from ZIP
# Select the generated universal_ai_gis-1.0.0.zip
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root or set in your shell:

```bash
# MCP Server Configuration
UAGIS_MCP_TRANSPORT=stdio              # or "streamable-http"
UAGIS_MCP_PORT=8766                    # HTTP port
UAGIS_BRIDGE_URL=http://127.0.0.1:8765 # QGIS Bridge endpoint
UAGIS_BRIDGE_TOKEN=                    # Optional auth token

# QGIS Bridge Configuration (set in QGIS plugin settings)
# BRIDGE_HOST=127.0.0.1
# BRIDGE_PORT=8765
# BRIDGE_AUTH_TOKEN=your-secret-token
```

### QGIS Plugin Settings

1. Open QGIS
2. Go to **Plugins → Universal AI GIS Studio → Settings**
3. Configure:
   - **Bridge Port**: 8765 (default)
   - **Auth Token**: Generate a secure token (or leave empty for dev)
   - **Allowed Origins**: `http://127.0.0.1:8766` (for HTTP transport)

---

## Running the MCP Server

### Option A: Stdio Transport (Recommended for OpenCode/Codex)

```powershell
cd "D:\1 2 3 QGIS\Universal-AI-GIS-Studio"
python -m mcp_server.main --transport stdio
```

**Output:**
```
[uagis] MCP server 'universal-ai-gis-studio' starting on stdio
```

### Option B: Streamable HTTP Transport

```powershell
cd "D:\1 2 3 QGIS\Universal-AI-GIS-Studio"
python -m mcp_server.main --transport streamable-http --port 8766
```

**Output:**
```
[uagis] MCP server 'universal-ai-gis-studio' starting on Streamable HTTP http://127.0.0.1:8766
```

### Verify Server is Running (HTTP only)

```powershell
# Health check
curl http://127.0.0.1:8766/health

# List tools (MCP initialize + list_tools)
# Use an MCP client or the test script below
```

---

## Connecting an MCP Client

### OpenCode Configuration

Create `~/.config/opencode/mcp.json` (or `%USERPROFILE%\.config\opencode\mcp.json` on Windows):

```json
{
  "mcpServers": {
    "universal-ai-gis-studio": {
      "command": "python",
      "args": ["-m", "mcp_server.main", "--transport", "stdio"],
      "cwd": "D:\\1 2 3 QGIS\\Universal-AI-GIS-Studio",
      "env": {
        "UAGIS_BRIDGE_URL": "http://127.0.0.1:8765",
        "UAGIS_BRIDGE_TOKEN": "your-token-if-configured"
      }
    }
  }
}
```

### Codex Configuration

Add to Codex MCP settings:

```json
{
  "mcpServers": {
    "universal-ai-gis-studio": {
      "transport": "stdio",
      "command": "python",
      "args": ["-m", "mcp_server.main", "--transport", "stdio"],
      "workingDirectory": "D:/1 2 3 QGIS/Universal-AI-GIS-Studio"
    }
  }
}
```

### Generic HTTP Client

```python
import httpx
import json

async def call_tool(tool_name: str, params: dict):
    async with httpx.AsyncClient() as client:
        # Initialize
        await client.post("http://127.0.0.1:8766/mcp", json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {}}
        })
        
        # Call tool
        response = await client.post("http://127.0.0.1:8766/mcp", json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": params}
        })
        return response.json()
```

---

## Your First Tool Call

### 1. Start QGIS Desktop

Ensure QGIS is running and the Universal AI GIS Studio plugin is **enabled**.

### 2. Start the Bridge (via QGIS Plugin)

In QGIS: **Plugins → Universal AI GIS Studio → Start Bridge**

You should see: `Bridge started on http://127.0.0.1:8765`

### 3. Start the MCP Server

```powershell
cd "D:\1 2 3 QGIS\Universal-AI-GIS-Studio"
python -m mcp_server.main --transport stdio
```

### 4. Test with a Simple Tool Call

Using OpenCode (or any MCP client):

```
> Use the qgis.system.inspect tool
```

**Expected Response:**
```json
{
  "request_id": "req_abc123",
  "tool": "qgis.system.inspect",
  "status": "ok",
  "verification_state": "SUCCESS",
  "result": {
    "qgis_version": "4.2.3",
    "gdal_version": "3.13.3",
    "python_version": "3.12.15",
    "bridge_connected": true
  },
  "job_id": null,
  "timestamp": "2026-11-12T08:00:00Z"
}
```

### 5. Load a Layer

```
> Use qgis.layers.load with path "D:/data/parcels.gpkg"
```

**Expected Response:**
```json
{
  "request_id": "req_def456",
  "tool": "qgis.layers.load",
  "status": "ok",
  "verification_state": "SUCCESS",
  "result": {
    "id": "parcels_abc123",
    "name": "parcels",
    "type": "vector",
    "valid": true,
    "crs": "EPSG:4326"
  },
  "job_id": "job_xyz789",
  "timestamp": "2026-11-12T08:01:00Z"
}
```

### 6. Run a Processing Algorithm

```
> Use qgis.algorithms.execute with algorithm "native:buffer" and parameters {"INPUT": "parcels_abc123", "DISTANCE": 100, "OUTPUT": "memory:"}
```

---

## Verification States Explained

Every tool response includes a `verification_state`. **Never assume success from submission alone.**

| State | Meaning | Action |
|-------|---------|--------|
| `SUCCESS` | Operation completed and verified (output exists, valid, correct) | Proceed confidently |
| `PARTIAL_SUCCESS` | Operation ran but verification incomplete (e.g., layout created but not exported) | Check result details, may need follow-up |
| `FAILED` | Operation failed; error details in response | Review error, fix input, retry |
| `NEEDS_REVIEW` | Human review required (e.g., georeferencing residuals high) | Inspect visually, approve/reject |
| `CANCELLED` | Job was cancelled by user or timeout | Resubmit if needed |

**Example FAILED response:**
```json
{
  "request_id": "req_xyz",
  "tool": "qgis.layers.load",
  "status": "error",
  "verification_state": "FAILED",
  "result": {},
  "error": {
    "code": "LAYER_INVALID",
    "message": "Failed to load layer: not a valid vector dataset",
    "context": {"path": "D:/data/bad_file.shp"}
  },
  "job_id": null,
  "timestamp": "..."
}
```

---

## Next Steps

1. **Explore the Tool Reference** → [`TOOL_REFERENCE.md`](TOOL_REFERENCE.md)
2. **Understand the Architecture** → [`ARCHITECTURE.md`](ARCHITECTURE.md)
3. **See Python/JS Examples** → [`examples/`](../examples/)
4. **Troubleshooting** → [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)
5. **Run Integration Tests** → See [`TEST_PLAN.md`](TEST_PLAN.md)

---

## Quick Reference: Common Tools

| Namespace | Tool | Purpose |
|-----------|------|---------|
| `qgis.system` | `inspect`, `health` | System diagnostics |
| `qgis.project` | `open`, `save`, `inspect` | Project management |
| `qgis.layers` | `inspect`, `load`, `remove` | Layer operations |
| `qgis.algorithms` | `discover`, `execute` | Processing algorithms |
| `qgis.screen` | `capture` | Screenshots |
| `qgis.cursor` | `move`, `click`, `drag` | AI cursor control |
| `qgis.georeference` | `analyze` | Image analysis |
| `qgis.gcp` | `generate`, `validate` | Ground Control Points |
| `qgis.raster` | `info` | Raster metadata |
| `qgis.vector` | `info` | Vector metadata |
| `qgis.layout` | `info` | Print layouts |
| `qgis.agents` | `list` | AI agents |
| `qgis.skills` | `list` | Skills |
| `qgis.verify` | `status` | Verification status |
| `qgis.jobs` | `cancel` | Job control |
| `qgis.history` | `inspect` | Execution history |
| `qgis.plugins` | `list` | Installed plugins |

---

*Happy mapping! 🗺️*