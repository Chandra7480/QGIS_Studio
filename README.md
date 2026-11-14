# Universal AI GIS Studio

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-1.2+-orange.svg)](https://modelcontextprotocol.io/)
[![QGIS](https://img.shields.io/badge/QGIS-4.x-red.svg)](https://qgis.org/)
[![CI](https://github.com/Chandra7480/QGIS_Studio/actions/workflows/ci.yml/badge.svg)](https://github.com/Chandra7480/QGIS_Studio/actions/workflows/ci.yml)
[![Security](https://github.com/Chandra7480/QGIS_Studio/actions/workflows/security.yml/badge.svg)](https://github.com/Chandra7480/QGIS_Studio/actions/workflows/security.yml)

**Universal AI GIS Studio** is a complete, extensible, **MCP-first AI-controlled GIS automation ecosystem** integrated with QGIS Desktop. It lets an external AI assistant (OpenCode, Codex, Cursor, VS Code, or any MCP-compatible client) control QGIS through natural language, while the platform provides actual GIS execution, visual interaction, verification, and control.

**AI Policy:** No local AI model is bundled. AI is supplied externally via OpenCode, Codex, Cursor, VS Code, Claude, or any MCP-compatible client, plus optional API providers (OpenAI, Gemini, Anthropic, OpenRouter, OpenAI-compatible, custom).

---

## ✨ Key Features

| Category | Features |
|----------|----------|
| **MCP Server** | MCP 1.2+ compliance, stdio + Streamable HTTP, 150+ tools, 25+ namespaces |
| **QGIS Bridge** | FastAPI + WebSocket, 340+ tools, rate limiting, Prometheus metrics |
| **GIS Clusters** | 25 clusters (M01-M25), 430+ operations |
| **Agents** | 29 built-in + custom builder + orchestrator |
| **Workflows** | DAG engine, 13 node types, checkpointing, pause/resume |
| **Engines** | 7: screen, visual automation, cursor, mouse/keyboard, verification, CV, georeferencing |
| **Security** | Permissions, approvals, API keys, rate limiting, audit logs |
| **Monitoring** | Tamper-proof audit, health checks, resource quotas |
| **Plugin** | QGIS 4.x, 21 panels, MCP configurator for 14 AI clients |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **QGIS 4.x** (Qt6) - [Download](https://qgis.org/download)
- **Git**
- **OpenCode/Codex/Cursor** (or any MCP client)

### 1. Clone & Install

```bash
# Clone the repository
git clone https://github.com/Chandra7480/QGIS_Studio.git
cd QGIS_Studio

# Install dependencies (choose your method)
# Option A: Using Make (recommended)
make install-all

# Option B: Using pip with extras
pip install -e .[mcp,opencv,dev]

# Option C: Using requirements files
pip install -r requirements.txt
```

### 2. Install QGIS Plugin

```bash
# Windows
copy plugin\universal_ai_gis %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\universal_ai_gis

# Linux/macOS
cp -r plugin/universal_ai_gis ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/universal_ai_gis
```

Restart QGIS and enable **"Universal AI GIS Studio"** in Plugin Manager.

### 3. Start Services

```bash
# Terminal 1: Start QGIS Bridge (inside QGIS Python)
# The plugin auto-starts the bridge on port 8765

# Terminal 2: Start MCP Server (stdio for OpenCode/Codex)
python -m mcp_server.main --transport stdio

# Or: Streamable HTTP for web clients
python -m mcp_server.main --transport streamable-http --port 8766
```

### 4. Connect AI Client

**OpenCode:**
```bash
opencode mcp add uagis --global --command python --args -m mcp_server.main --transport stdio
```

**Cursor/VS Code (MCP):**
```json
{
  "mcpServers": {
    "uagis": {
      "command": "python",
      "args": ["-m", "mcp_server.main", "--transport", "stdio"]
    }
  }
}
```

**Claude Desktop:**
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "uagis": {
      "command": "python",
      "args": ["-m", "mcp_server.main", "--transport", "stdio"]
    }
  }
}
```

---

## 🐳 Docker Deployment

```bash
# Build and run full stack
docker-compose up -d

# Services:
# - MCP Server: http://localhost:8766
# - Bridge: http://localhost:8765
# - Grafana: http://localhost:3000 (admin/admin)
# - Prometheus: http://localhost:9090
```

---

## 🏗️ Architecture

```
┌─────────────────┐     MCP/HTTP      ┌─────────────────┐
│  AI Client      │ ◄────────────────► │  MCP Server     │
│ (OpenCode, etc) │                    │ (stdio/HTTP)    │
└─────────────────┘                    └────────┬────────┘
                                                │
                                                ▼
                                    ┌─────────────────────┐
                                    │   QGIS Bridge       │
                                    │ (FastAPI + WebSocket)│
                                    │ 340+ tools          │
                                    └─────────┬───────────┘
                                              │
                                              ▼
                                    ┌─────────────────────┐
                                    │     QGIS 4.x        │
                                    │ (PyQt6 + PyQGIS)    │
                                    └─────────────────────┘
```

### Core Components

| Component | Description |
|-----------|-------------|
| **core/** | EventBus, JobManager, EmergencyStop, ResourceQuota, CircuitBreaker, CapabilityRegistry |
| **database/** | SQLite WAL, migrations, repositories |
| **bridge/** | FastAPI + WebSocket, 340+ tools, rate limiting |
| **mcp_server/** | MCP 1.2+ server, stdio + Streamable HTTP, verification, approval |
| **clusters/** | 25 GIS clusters (M01-M25), 430 operations |
| **engines/** | 7 engines: screen, visual, cursor, mouse/keyboard, verification, CV, georeferencing |
| **agents/** | 29 built-in agents + custom builder + orchestrator |
| **workflows/** | DAG engine, 13 node types, checkpointing |
| **skills/** | Validation, CRUD, 1 builtin (automatic georeferencing) |
| **extensions/** | Install/uninstall/enable with manifests |
| **security/** | Permissions, approvals, API keys, rate limiting |
| **monitoring/** | Audit logs, health checks, resource quotas |

---

## 🛠️ Development

```bash
# Install dev dependencies
make install-dev

# Run tests
make test              # All tests
make test-unit         # Unit tests only
make test-coverage     # With coverage report

# Code quality
make lint              # Ruff linter
make format            # Ruff + Black + isort
make type-check        # MyPy

# Run servers
make run-mcp-stdio     # MCP server (stdio)
make run-mcp-http      # MCP server (HTTP)
make run-bridge        # QGIS Bridge
```

### Pre-commit Hooks

```bash
pre-commit install
```

---

## 📦 Installation Methods

| Method | Command |
|--------|---------|
| **pip (base)** | `pip install universal-ai-gis-studio` |
| **pip (MCP)** | `pip install universal-ai-gis-studio[mcp]` |
| **pip (OpenCV)** | `pip install universal-ai-gis-studio[opencv]` |
| **pip (dev)** | `pip install universal-ai-gis-studio[dev]` |
| **pip (all)** | `pip install universal-ai-gis-studio[all]` |
| **Docker** | `docker pull chandra7480/universal-ai-gis-studio:latest` |

---

## 🔧 Configuration

Copy `.env.example` to `.env` and customize:

```bash
cp .env.example .env
```

Key settings:
```bash
UAGIS_BRIDGE_URL=http://127.0.0.1:8765
UAGIS_BRIDGE_AUTH_TOKEN=your-secure-token
MCP_TRANSPORT=stdio          # or streamable-http
MCP_HTTP_PORT=8766
```

---

## 🧪 Testing

```bash
# Run all tests
make test

# Unit tests only
make test-unit

# With coverage
make test-coverage
```

---

## 📚 Documentation

- [Architecture](docs/SYSTEM_ARCHITECTURE.md)
- [Development Status](docs/DEVELOPMENT_STATUS.md)
- [Implementation Checklist](docs/IMPLEMENTATION_CHECKLIST.md)
- [Technical Decisions](docs/TECHNICAL_DECISIONS.md)
- [Test Plan](docs/TEST_PLAN.md)
- [Tool Reference](docs/TOOL_REFERENCE.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork & clone
2. Create feature branch
3. Write tests
4. Run quality checks: `make lint && make type-check && make test`
5. Submit PR

---

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

## 🙏 Acknowledgments

- [QGIS](https://qgis.org/) - The amazing open-source GIS platform
- [Model Context Protocol](https://modelcontextprotocol.io/) - The protocol enabling AI-tool interaction
- [OpenCode](https://opencode.ai/) - AI coding agent
- All contributors and the open-source GIS community

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Chandra7480/QGIS_Studio/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Chandra7480/QGIS_Studio/discussions)
- **Security**: Report security issues privately via GitHub Security Advisories

---

**Made with ❤️ for the GIS and AI communities**