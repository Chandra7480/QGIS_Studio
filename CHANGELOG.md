# Changelog

All notable changes to Universal AI GIS Studio will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-11-14

### 🎉 Initial Release

Universal AI GIS Studio - MCP-first AI-controlled QGIS automation platform.

### ✨ Added

#### Core Architecture
- **MCP Server** - Full MCP 1.2+ compliance with stdio and Streamable HTTP transports
- **QGIS Bridge** - FastAPI + WebSocket bridge with 340+ tools
- **25 GIS Clusters** (M01-M25) with 430+ operations covering vector, raster, CRS, spatial, terrain, hydrology, network, remote sensing, classification, change detection, 3D, LiDAR, survey, cadastral, cartography, temporal, database, web GIS, field data, automation, AI/ML, quality
- **7 Execution Engines** - Screen capture, visual automation, mouse/keyboard, cursor controller, verification (visual + functional), computer vision, georeferencing
- **Agent System** - 29 built-in specialized agents + custom agent builder + orchestrator
- **Workflow Engine** - DAG-based with 13 node types, checkpointing, pause/resume, parallel execution
- **Skills System** - Validation, CRUD, marketplace-ready (1 builtin: automatic georeferencing)
- **Extensions System** - Install/uninstall/enable with manifest validation

#### Core Services
- **EventBus** - In-process pub/sub for decoupled communication
- **JobManager** - Full job lifecycle with resource quotas
- **EmergencyStop** - System-wide emergency stop with priority callbacks
- **ResourceQuota** - Per-job memory/CPU/disk/duration limits
- **CircuitBreaker** - Unified circuit breaker for external calls
- **CapabilityRegistry** - Dynamic GIS capability discovery
- **Keyring** - OS credential manager (Windows/macOS/Linux + encrypted fallback)
- **Config** - SQLite-backed configuration with 70+ typed defaults

#### Security
- **PermissionManager** - Tool allowlists with deny-by-default
- **ApprovalManager** - User consent gates for destructive operations
- **APIKeyManager** - Full key lifecycle (rotation, fallback, notifications)
- **RateLimiter** - Token bucket (in-memory + Redis) with fail-closed
- **Audit Logs** - Tamper-proof hash chain with external anchoring

#### Infrastructure
- **QGIS 4.x Plugin** - 21-panel dock widget UI with MCP configurator for 14 AI clients
- **Valid QGIS Icons** - 24×24, 48×48, 128×128 PNG
- **CI/CD Workflows** - Release, Security (CodeQL, pip-audit, Bandit, TruffleHog), Plugin Validation
- **Docker Support** - Multi-stage Dockerfile + docker-compose.yml
- **Monitoring** - Prometheus metrics, Grafana dashboards, alerting

### 🔒 Security Fixes
- Removed `execute_code` RCE tool from FastMCP server
- Fixed fail-open Redis rate limiter → fail-closed
- Fixed PermissionManager insecure default (allow-all) → deny-by-default
- Replaced `eval()` in workflow conditions with `simpleeval`
- Removed 29 legacy duplicate agents
- Removed 6 placeholder builtin skills
- Fixed duplicate command constants and database methods

### 🛠️ Changed
- Made Bridge authentication mandatory (no dev mode bypass)
- Wired EventBus into JobManager, EmergencyStop, ResourceQuota
- Wired CircuitBreaker around PyQGISExecutor calls
- Added CapabilityRegistry registration for clusters, engines, agents, skills
- Implemented real workflow placeholder nodes (MCP Tool, Agent, API)
- Implemented system-wide emergency stop with 9 subsystem integrations
- Implemented agent tool execution via MCP bridge

### 🧪 Testing
- 46 core unit tests passing
- 140+ total tests with major gaps identified
- Contract tests for tool definitions

### 📚 Documentation
- Comprehensive README with installation guides
- SYSTEM_ARCHITECTURE.md with full architecture diagrams
- DEVELOPMENT_STATUS.md with audit findings
- IMPLEMENTATION_CHECKLIST.md
- TECHNICAL_DECISIONS.md
- TEST_PLAN.md
- TOOL_REFERENCE.md
- TROUBLESHOOTING.md

### 📦 Distribution
- PyPI package with optional dependencies (`mcp`, `opencv`, `dev`, `keyring`, `redis`, `all`)
- Entry points: `uagis-mcp`, `uagis-bridge`, `uagis-build`, `uagis-icons`, `uagis-test-data`
- QGIS plugin ZIP for easy installation
- Windows MSI / Linux packages / macOS DMG planned

## [Unreleased]

### Planned
- Cross-platform engine backends (Linux/macOS)
- Windows MSI / Linux packages (DEB, RPM, AppImage, Flatpak, Snap)
- macOS DMG/PKG
- PyPI trusted publishing (OIDC)
- Code signing (Windows Authenticode, macOS notarization)
- SBOM generation in CI
- Auto-update framework
- 6 missing builtin skills implementation
- Extension sandbox (RestrictedPython/subprocess)
- Skill marketplace with dependency resolution
- Workflow visual editor
- Sub-workflow node type
- Parallel loop execution
- Distributed tracing with correlation IDs
- Health history storage for SLA reporting
- Audit log retention policy
- Temp file compression
- Redis reconnection logic
- Permission scopes/hierarchy
- Approval TTL with auto-deny
- Distributed in-memory rate limiter
- Provider key generation API integration

---

## Version History

| Version | Date | Type | Description |
|---------|------|------|-------------|
| 1.0.0 | 2026-11-14 | Major | Initial release |

---

*For detailed changes, see [GitHub Releases](https://github.com/Chandra7480/QGIS_Studio/releases)*