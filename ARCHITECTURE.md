# Universal AI GIS Studio — Architecture Document

## Overview

Universal AI GIS Studio is an MCP-first AI-controlled QGIS automation platform that bridges natural language AI agents with professional GIS workflows. It provides a QGIS Bridge, MCP server integration, visual automation, AI cursor, georeferencing, and 25 GIS functional clusters.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Universal AI GIS Studio                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────────┐ │
│  │   AI Clients    │    │  MCP Server     │    │    QGIS Plugin          │ │
│  │                 │    │  (FastMCP)      │    │    (Socket Server)      │ │
│  │ • Claude Code   │◄──►│                 │◄──►│                         │ │
│  │ • Codex CLI     │    │ • stdio         │    │ • TCP Socket (9876)     │ │
│  │ • Cursor        │    │ • HTTP/SSE      │    │ • Length-prefixed JSON  │ │
│  │ • VS Code       │    │ • Tool Registry │    │ • Command Registry      │ │
│  │ • OpenCode      │    │ • Auth Guard    │    │ • QTimer Event Loop     │ │
│  │ • LM Studio     │    │                 │    │ • PyQGIS on Main Thread │ │
│  └─────────────────┘    └─────────────────┘    └─────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. QGIS Plugin (`plugin/universal_ai_gis/`)
- **Entry Point**: `classFactory(iface)` → `UniversalAIGISPlugin`
- **UI**: Toolbar with dropdown (port, autostart) + badge icon + configurator dialog
- **Server**: `SocketServer` (TCP, non-blocking, QTimer-driven)
- **Lifecycle**: `initGui()` → `_init_core()` → `_start_bridge()` → `_create_ui()`

### 2. Socket Server (`bridge/socket_server.py`)
- **Protocol**: Length-prefixed JSON (4-byte big-endian length + UTF-8 payload)
- **Transport**: Non-blocking TCP socket + QTimer (25ms tick)
- **Authentication**: `QGIS_MCP_TOKEN` env var + constant-time compare
- **Security**: Non-loopback bind requires token
- **Commands**: 18+ core commands + `batch` support
- **Validation**: Signature inspection + unknown parameter rejection

### 3. Command Registry (`bridge/registry.py`)
- **Decorator**: `@command` registers handlers
- **Metadata**: `UNRECORDED_COMMANDS`, `BATCH_BLOCKED_COMMANDS`
- **Validation**: Signature inspection + unknown parameter rejection

### 3. Wire Protocol (`bridge/wire.py`)
- **Framing**: 4-byte big-endian length + JSON payload
- **Buffers**: `OutboundBuffer` with backpressure
- **Limits**: 10 MB max message, 5 MB per-client outbound

### 4. FastMCP Server (`integrations/fastmcp_server/main.py`)
- **Transport**: stdio (default) + HTTP/SSE
- **Tools**: 14+ mapped to QGIS socket commands
- **Transports**: stdio (default) + streamable-http
- **Installation**: `uvx --from <zip> uagis-mcp-server`

### 4. Plugin UI (`plugin/universal_ai_gis/plugin.py`)
- **Toolbar**: ToolButton with dropdown menu (port spinner, autostart, configure)
- **Badge**: Green logo + client count badge
- **Configurator**: MCP client setup dialog (Claude, Cursor, Codex, etc.)
- **Auto-start**: Persisted via QgsSettings

## Data Flow

```
AI Client → MCP Server (stdio/HTTP) → TCP Socket (9876) → QGIS Plugin
                                                              ↓
                                              SocketServer.process_server()
                                                              ↓
                                              execute_command() → _dispatch()
                                                              ↓
                                              Command Handler (PyQGIS API)
                                                              ↓
                                              Response → Length-prefixed JSON → Client
```

## Security Model

1. **Token Authentication**: `QGIS_MCP_TOKEN` env var (constant-time compare)
2. **Network Binding**: Non-loopback requires token (prevents accidental exposure)
3. **Command Validation**: Signature inspection + unknown parameter rejection
4. **Batch Guard**: Destructive commands blocked in batch mode
5. **Input Sanitization**: Version/fix command sanitization

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `QGIS_MCP_HOST` | `localhost` | Socket bind host |
| `QGIS_MCP_PORT` | `9876` | Socket bind port |
| `QGIS_MCP_TOKEN` | `` | Shared secret (optional) |
| `QGIS_MCP_TRANSPORT` | `stdio` | MCP transport: `stdio` or `streamable-http` |
| `QGIS_MCP_LOG_FILE` | `~/.local/share/uagis-mcp/server.log` | Log file |
| `QGIS_MCP_LOG_LEVEL` | `INFO` | Log level |

## Plugin Settings (QgsSettings)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `uagis/mcp/port` | int | 9876 | Server port |
| `uagis/mcp/autostart` | bool | false | Auto-start on QGIS launch |
| `uagis/mcp/first_run` | bool | true | Show welcome dialog |
| `uagis/mcp/refresh_removal_prompted` | bool | false | Config migration prompted |

## Extending Commands

1. Add handler method to `SocketServer` class
2. Decorate with `@command`
3. For batch blocking: add to `BATCH_BLOCKED_COMMANDS`
5. For no-journal: add to `UNRECORDED_COMMANDS`

## Deployment

### QGIS Plugin
1. Build: `python build_plugin.py`
2. Install: QGIS → Plugins → Install from ZIP
3. Enable: Check `universal_ai_gis` in plugin manager

### MCP Server (External)
```bash
# Install via uvx (auto-updates from GitHub)
uvx --from https://github.com/your-org/uagis-mcp/archive/refs/heads/main.zip uagis-mcp-server

# Or local development
git clone https://github.com/your-org/uagis-mcp
cd uagis-mcp
uv run --no-sync src/uagis_mcp/main.py
```

## Client Configuration

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

## Testing

```bash
# Unit tests (no QGIS needed)
uv run --no-sync pytest tests/test_socket_server.py -v

# Integration tests (requires QGIS plugin running)
uv run --no-sync pytest tests/test_qgis_live.py -v
```

## License

MIT License — see LICENSE file for details.