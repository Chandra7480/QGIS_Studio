# Universal AI GIS Studio — FastMCP Server

External MCP server for Universal AI GIS Studio. Connects to QGIS via TCP socket.

## Quick Start

```bash
# Install from GitHub
uvx --from https://github.com/your-org/uagis-mcp/archive/refs/heads/main.zip uagis-mcp-server

# Or local development
git clone https://github.com/your-org/uagis-mcp
cd uagis-mcp
uv run --no-sync uagis-mcp-server
```

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `QGIS_MCP_HOST` | `localhost` | QGIS plugin host |
| `QGIS_MCP_PORT` | `9876` | QGIS plugin port |
| `QGIS_MCP_TOKEN` | `` | Shared secret |
| `QGIS_MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http` |

## MCP Client Configuration

### Claude Code
```bash
claude mcp add -s user uagis -- uvx --from https://github.com/your-org/uagis-mcp/archive/refs/heads/main.zip uagis-mcp-server
```

### Cursor / VS Code / Windsurf
```json
{
  "mcpServers": {
    "uagis": {
      "command": "uvx",
      "args": ["--from", "https://github.com/your-org/uagis-mcp/archive/refs/heads/main.zip", "uagis-mcp-server"]
    }
  }
}
```

### Codex CLI
```bash
codex mcp add uagis -- uvx --from https://github.com/your-org/uagis-mcp/archive/refs/heads/main.zip uagis-mcp-server
```

### OpenCode
```json
{
  "mcp": {
    "uagis": {
      "type": "local",
      "command": ["uvx", "--from", "https://github.com/your-org/uagis-mcp/archive/refs/heads/main.zip", "uagis-mcp-server"],
      "enabled": true
    }
  }
}
```

## Available Tools

| Tool | Description |
|------|-------------|
| `ping` | Test connection |
| `diagnose` | Run diagnostics |
| `get_project_info` | Get project info |
| `load_project` | Load .qgz file |
| `create_new_project` | New project |
| `save_project` | Save project |
| `get_layers` | List layers |
| `add_vector_layer` | Add vector layer |
| `add_raster_layer` | Add raster layer |
| `remove_layer` | Remove layer |
| `get_layer_features` | Get features |
| `add_features` | Add features |
| `execute_processing` | Run processing |
| `execute_sql` | Execute SQL |
| `render_map` | Render map image |
| `execute_code` | Execute PyQGIS |

## Development

```bash
# Install in dev mode
uv pip install -e ".[dev]"

# Run tests
uv run --no-sync pytest tests/ -v

# Run server
uv run --no-sync uagis-mcp-server
```

## License

MIT License