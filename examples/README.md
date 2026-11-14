# Universal AI GIS Studio — Examples

This directory contains client examples for connecting to the Universal AI GIS Studio MCP server.

## Contents

| File | Language | Transport | Description |
|------|----------|-----------|-------------|
| `python_client.py` | Python | stdio + HTTP | Comprehensive examples with error handling |
| `javascript_client.js` | JavaScript/TypeScript | stdio + HTTP | Modern ES modules with MCP SDK |

## Prerequisites

1. **QGIS 4.2.3** running with Universal AI GIS Studio plugin enabled
2. **Bridge started**: Plugins → Universal AI GIS Studio → Start Bridge (port 8765)
3. **Dependencies installed**:
   - Python: `pip install -e ".[mcp]"` (from project root)
   - JavaScript: `npm install @modelcontextprotocol/sdk`

## Quick Start

### Python (Stdio Transport)

```bash
cd Universal-AI-GIS-Studio
python examples/python_client.py
```

### JavaScript (Stdio Transport)

```bash
cd Universal-AI-GIS-Studio
node examples/javascript_client.js
```

### TypeScript

```bash
cd Universal-AI-GIS-Studio
npx ts-node examples/javascript_client.js
```

## Example Scripts Overview

### python_client.py

Run with different examples by uncommenting in `main()`:

1. **Stdio Transport** - Connect via subprocess (default)
2. **HTTP Transport** - Connect to running MCP HTTP server (port 8766)
3. **GIS Workflow** - Load layer → buffer → inspect (requires data file)
4. **Error Handling** - Demonstrate verification states
5. **Direct Bridge** - Bypass MCP, call Bridge HTTP directly

### javascript_client.js

Similar examples using `@modelcontextprotocol/sdk`:

1. **Stdio Transport** - Subprocess connection
2. **HTTP Transport** - Streamable HTTP client
3. **GIS Workflow** - Complete load → buffer → discover
4. **Error Handling** - Verification state extraction
5. **Direct Bridge** - Raw fetch() to Bridge

## Configuration

Set environment variables before running:

```bash
# Required for Bridge connection
export UAGIS_BRIDGE_URL=http://127.0.0.1:8765

# Optional: if Bridge auth token configured
export UAGIS_BRIDGE_TOKEN=your-secret-token
```

**Windows PowerShell:**
```powershell
$env:UAGIS_BRIDGE_URL = "http://127.0.0.1:8765"
$env:UAGIS_BRIDGE_TOKEN = "your-secret-token"
```

## Data Files

Examples reference `D:/data/parcels.gpkg` — **update this path** to your actual data file.

Supported formats:
- Vector: `.gpkg`, `.shp`, `.geojson`, `.kml`, `.gml`
- Raster: `.tif`, `.tiff`, `.geotiff`, `.img`

## Expected Output

Successful run shows:
```
✓ MCP session initialized
✓ Discovered 35 tools
→ Calling qgis.system.inspect...
  ✓ Status: ok | Verification: SUCCESS
    qgis_version: 4.2.3
    gdal_version: 3.13.3
    python_version: 3.12.15
    bridge_connected: true
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: mcp` | `pip install -e ".[mcp]"` |
| `Connection refused` | Start Bridge in QGIS plugin |
| `401 Unauthorized` | Set correct `UAGIS_BRIDGE_TOKEN` |
| `File not found` | Update data path in example |
| `Timeout` | Increase timeout, check QGIS responsiveness |

See `docs/TROUBLESHOOTING.md` for complete guide.

## Extending Examples

Add your own tools by importing the client pattern:

```python
# Python
result = await session.call_tool("qgis.algorithms.execute", {
    "algorithm": "native:reprojectlayer",
    "parameters": {"INPUT": layer_id, "TARGET_CRS": "EPSG:3857", "OUTPUT": "memory:"}
})
```

```javascript
// JavaScript
const result = await client.callTool({
    name: "qgis.algorithms.execute",
    arguments: {
        algorithm: "native:reprojectlayer",
        parameters: {INPUT: layerId, TARGET_CRS: "EPSG:3857", OUTPUT: "memory:"}
    }
});
```

## Tool Reference

See `docs/TOOL_REFERENCE.md` for all 35 tools with schemas.

## Architecture

See `docs/ARCHITECTURE.md` for system architecture and data flow.