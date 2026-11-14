# Changelog

## 1.0.0 (2026-11-11) — Initial release

- Complete Universal AI GIS Studio platform
- QGIS plugin + QGIS Bridge (localhost HTTP/IPC)
- Universal MCP server (stdio + Streamable HTTP) with all qgis.* namespaces
- QGIS Desktop integration (project, layers, canvas, algorithms)
- Live screen capture, AI cursor, mouse/keyboard control
- Computer vision engine (OpenCV ORB/SIFT, matching, RANSAC)
- Automatic georeferencing + GCP intelligence + RMSE verification
- All 25 GIS functional clusters (M01–M25)
- 29 built-in agents + custom agent builder + orchestrator
- Skills, workflows, extensions
- SQLite database (WAL), audit logs, verification engine
- Security: permissions, approvals, auth, emergency stop
- Automated test suite (46 unit tests)
- Documentation: architecture, decisions, status, checklist, test plan

## AI policy

No local AI model is bundled. AI is supplied externally (OpenCode, Codex,
MCP clients, optional APIs).