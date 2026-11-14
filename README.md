# Universal AI GIS Studio

Universal AI GIS Studio is a complete, extensible, MCP-first AI-controlled GIS
automation ecosystem integrated with QGIS Desktop. It lets an external AI
assistant (OpenCode, Codex, or any MCP-compatible client) control QGIS through
natural language, while the platform provides actual GIS execution, visual
interaction, verification, and control.

**AI policy:** No local AI model is bundled. AI is supplied externally via
OpenCode, Codex, other MCP-compatible clients, or optional API providers
(OpenAI, Gemini, Anthropic, OpenRouter, OpenAI-compatible, custom).

## Verified environment (development host)

- OS: Windows 10 Home x64, 8 GB RAM, 1 CPU, HDD
- QGIS Desktop: 4.2.3 (Qt6) at `C:\Program Files\QGIS 4.2.3`
- Python: 3.12.10 (system), 3.12.15 (QGIS bundled)
- GDAL/OGR: 3.13.3
- OpenCode: 1.19.5
- Node: v24.22.1
- PyQGIS importable inside QGIS bundled Python

## Package layout

```
Universal-AI-GIS-Studio/
├── plugin/universal_ai_gis/   # QGIS plugin (installs into QGIS profile)
│   ├── __init__.py
│   ├── metadata.txt
│   ├── plugin.py              # classFactory entry point + bridge
│   └── main_window.py
├── bridge/                    # QGIS Bridge (localhost HTTP/IPC)
├── mcp_server/                # Universal MCP server (stdio + Streamable HTTP)
├── core/                      # config, database, logging, jobs, events
├── database/                  # SQLite schema + repositories
├── engines/                   # screen capture, cursor, CV, georeferencing, verification
├── clusters/                  # M01–M25 GIS functional clusters
├── agents/                    # 29 built-in agents + custom builder + orchestrator
├── skills/                    # skill manager + loader + validator
├── workflows/                 # workflow builder + execution engine
├── extensions/                # extension manager
├── integrations/              # AI host, API provider, MCP managers
├── security/                  # permissions, approvals, auth
├── monitoring/                # audit, resource monitoring
├── tests/unit/                # automated test suite
├── requirements/
├── pyproject.toml
├── README.md
├── CHANGELOG.md
├── LICENSE
└── docs/
    ├── SYSTEM_ARCHITECTURE.md
    ├── DEVELOPMENT_STATUS.md
    ├── IMPLEMENTATION_CHECKLIST.md
    ├── TECHNICAL_DECISIONS.md
    └── TEST_PLAN.md
```

## Installation

### 1. QGIS Plugin

Copy `plugin/universal_ai_gis/` into your QGIS profile plugins folder:

- Windows: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
- Then restart QGIS and enable "Universal AI GIS Studio" in the Plugin Manager.

The plugin starts the QGIS Bridge (localhost HTTP, default `127.0.0.1:8765`)
inside QGIS.

### 2. Universal MCP Server

```bash
cd Universal-AI-GIS-Studio
pip install -r requirements/mcp.txt -r requirements/base.txt

# stdio transport (OpenCode / local MCP clients)
python -m mcp_server.main --transport stdio

# Streamable HTTP transport
python -m mcp_server.main --transport streamable-http --port 8766
```

Configure the bridge URL via `UAGIS_BRIDGE_URL` (default `http://127.0.0.1:8765`).

### 3. OpenCode MCP integration

OpenCode supports MCP servers natively. Add the Universal GIS MCP server:

```bash
opencode mcp add uagis --global --command python \
  --args -m mcp_server.main --transport stdio
opencode mcp list
```

Then, in an OpenCode session, ask it to list and call tools such as
`qgis.system.inspect`, `qgis.layers.inspect`, `qgis.layers.load`,
`qgis.algorithms.discover`, `qgis.screen.capture`, `qgis.cursor.move`.

## Core capabilities

- QGIS project & layer inspection and management
- Live QGIS screen capture + AI cursor + mouse/keyboard control
- 25 GIS functional clusters (vector, raster, CRS, spatial, terrain,
  hydrology, network, remote sensing, cartography, database, quality, …)
- Automatic georeferencing + GCP intelligence (OpenCV ORB/SIFT, RANSAC)
- 29 built-in agents + custom agent builder + orchestrator
- Skills, workflows, extensions
- SQLite database, audit logs, verification engine, security approvals

## Verified test suite

```bash
cd Universal-AI-GIS-Studio
pip install pytest
python -m pytest tests/unit/
```

All unit tests pass against the real environment (no QGIS GUI required for
unit tests; integration tests need a running QGIS instance).

## Security

- Authenticated QGIS Bridge (token optional)
- Tool allowlists and agent permission levels
- User approval required before destructive operations
- API keys stored in OS credential manager (never plaintext in DB/logs)
- Audit logs for all security-relevant operations
- Emergency stop and job cancellation

## Limitations (documented)

- QGIS 4.x is Qt6-based; UI targets PyQt6 (not PyQt5).
- `import qgis` works only inside QGIS's bundled Python; the MCP server runs
  outside QGIS and talks to the bridge over localhost HTTP.
- No local AI model; AI is external only.
- 8 GB RAM / single CPU / HDD: lazy loading, limited workers, sequential
  project writes by default.

See `docs/` for architecture, decisions, status, checklist, and test plan.