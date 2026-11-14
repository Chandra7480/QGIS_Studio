# Agents Folder Analysis — Universal AI GIS Studio

**Task:** task-4  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent  
**Context:** core/ (task-1), clusters/ (task-2), engines/ (task-3) analyses read prior

---

## 1. Folder Structure

```
agents/
├── __init__.py                  # Empty package marker
├── base_agent.py                # BaseAgent, SpecializedAgent, AgentContext (299 lines)
├── supervisor.py                # AGISSupervisorAgent (simple, 25 lines)
├── agent_manager.py             # AgentManager, AGENT_TOOL_ALLOWLISTS (399 lines)
├── orchestrator.py              # AgentOrchestrator, ChainStep, ChainResult (347 lines)
├── custom/
│   ├── __init__.py
│   └── custom_builder.py        # CustomAgentBuilder (47 lines)
├── builtins/
│   ├── __init__.py              # Exports 30 agent classes, BUILTIN_AGENT_CLASSES map
│   ├── agent_gis_supervisor.py  # AGISSupervisorAgent with keyword planner (315 lines)
│   ├── agent_gis_research.py
│   ├── agent_data_acquisition.py
│   ├── agent_data_management.py
│   ├── agent_georeferencing.py
│   ├── agent_digitization.py
│   ├── agent_vector_processing.py
│   ├── agent_raster_processing.py
│   ├── agent_spatial_analysis.py
│   ├── agent_terrain.py
│   ├── agent_hydrology.py
│   ├── agent_network.py
│   ├── agent_remote_sensing.py
│   ├── agent_classification.py
│   ├── agent_change_detection.py
│   ├── agent_3d_gis.py
│   ├── agent_lidar.py
│   ├── agent_survey_gps.py
│   ├── agent_cadastral.py
│   ├── agent_cartography.py
│   ├── agent_temporal_gis.py
│   ├── agent_database.py
│   ├── agent_web_gis.py
│   ├── agent_automation.py
│   ├── agent_quality_control.py
│   ├── agent_reporting.py
│   ├── agent_visual_desktop_control.py
│   ├── agent_computer_vision.py
│   ├── agent_gis_verification.py
│   ├── agent_01_data_acquisition.py    # Legacy numbered agents (M01-M25 + 3)
│   ├── agent_02_data_management.py
│   ├── ... (up to agent_29_supervisor.py)
│   ├── agent_gis_supervisor.py         # Duplicate name with supervisor.py
│   ├── agent_gis_research.py           # Duplicate name
│   ├── agent_data_acquisition.py       # Duplicate name
│   ├── agent_georeferencing.py         # Duplicate name
│   ├── agent_digitization.py           # Duplicate name
│   ├── agent_vector_processing.py      # Duplicate name
│   ├── agent_raster_processing.py      # Duplicate name
│   ├── agent_spatial_analysis.py       # Duplicate name
│   ├── agent_terrain.py                # Duplicate name
│   ├── agent_hydrology.py              # Duplicate name
│   ├── agent_network.py                # Duplicate name
│   ├── agent_remote_sensing.py         # Duplicate name
│   ├── agent_classification.py         # Duplicate name
│   ├── agent_change_detection.py       # Duplicate name
│   ├── agent_3d_gis.py                 # Duplicate name
│   ├── agent_lidar.py                  # Duplicate name
│   ├── agent_survey_gps.py             # Duplicate name
│   ├── agent_cadastral.py              # Duplicate name
│   ├── agent_cartography.py            # Duplicate name
│   ├── agent_temporal_gis.py           # Duplicate name
│   ├── agent_database.py               # Duplicate name
│   ├── agent_web_gis.py                # Duplicate name
│   ├── agent_automation.py             # Duplicate name
│   ├── agent_quality_control.py        # Duplicate name
│   ├── agent_reporting.py
│   ├── agent_visual_desktop_control.py # Duplicate name
│   ├── agent_computer_vision.py        # Duplicate name
│   ├── agent_gis_verification.py       # Duplicate name
│   └── __pycache__/
└── __pycache__/
```

**Total:** ~60 agent files (30 modern + 29 legacy numbered + duplicates), ~2,000 lines

---

## 2. Agent Architecture

### Core Classes

| Class | File | Purpose |
|-------|------|---------|
| **`AgentContext`** | `base_agent.py:24` | Persistent context: conversation history, working memory, tool results, step count |
| **`BaseAgent`** | `base_agent.py:35` | Foundation: MCP tool calling (`call_tool`), permission checking, context persistence, tool allowlist |
| **`SpecializedAgent`** | `base_agent.py:282` | Domain-specific: `domain`, `tool_namespace`, `get_domain_tools()` |
| **`AGISSupervisorAgent`** | `builtins/agent_gis_supervisor.py` | Top-level planner: keyword-based request decomposition → agent chain |
| **`AgentManager`** | `agent_manager.py` | Registry + factory for 30 built-in + custom agents; manages `AGENT_TOOL_ALLOWLISTS` |
| **`AgentOrchestrator`** | `orchestrator.py` | Executes agent chains with dependency resolution, parallel execution, job tracking |
| **`CustomAgentBuilder`** | `custom/custom_builder.py` | Persists user-defined agents to DB with permissions/skills |

### Agent Hierarchy
```
BaseAgent (core)
    ├── SpecializedAgent (domain + tool namespace)
    │   ├── DataAcquisitionAgent (qgis.layers)
    │   ├── GeoreferencingAgent
    │   ├── VectorProcessingAgent
    │   ├── RasterProcessingAgent
    │   ├── SpatialAnalysisAgent
    │   ├── ... (27 total specialized agents)
    │   └── VisualDesktopControlAgent (qgis.screen)
    │
    ├── AGISSupervisorAgent (planner, uses AgentOrchestrator)
    │
    └── Custom Agents (user-defined, via CustomAgentBuilder)
```

---

## 3. Built-in Agents (30 Modern Agents)

| Agent ID | Domain | Tool Namespace | Permission | Key Tools (from AGENT_TOOL_ALLOWLISTS) |
|----------|--------|----------------|------------|----------------------------------------|
| `agent_gis_supervisor` | supervision | — | elevated | agents.*, skills.*, jobs.*, approval.*, workflows.*, algorithms.*, project.*, layers.*, system.* |
| `agent_gis_research` | research | — | read | algorithms.*, system.*, layers.*, project.*, agents.*, skills.*, verify.* |
| `agent_data_acquisition` | data_acquisition | qgis.layers | standard | layers.load/inspect/remove, project.*, system.*, database.info, algorithms.discover |
| `agent_data_management` | data_management | — | standard | layers.inspect/remove/load, project.save, algorithms.* |
| `agent_georeferencing` | georeferencing | — | standard | georeference.*, gcp.*, layers.load/inspect, algorithms.execute, raster.info |
| `agent_digitization` | digitization | — | standard | layers.load/inspect, algorithms.execute, cursor.*, keyboard.*, screen.capture, window/dialog.inspect |
| `agent_vector_processing` | vector | — | standard | algorithms.*, vector.info, layers.inspect/load, project.inspect |
| `agent_raster_processing` | raster | — | standard | algorithms.*, raster.info, layers.inspect/load, project.inspect |
| `agent_spatial_analysis` | spatial | — | standard | algorithms.*, spatial/vector/raster.info, layers.inspect, project.inspect |
| `agent_terrain` | terrain | — | standard | algorithms.*, raster.info, layers.inspect, project.inspect |
| `agent_hydrology` | hydrology | — | standard | algorithms.*, raster.info, layers.inspect, project.inspect |
| `agent_network` | network | — | standard | algorithms.*, vector.info, layers.inspect, project.inspect |
| `agent_remote_sensing` | remote_sensing | — | standard | algorithms.*, raster.info, layers.inspect/load, web_gis, project.inspect |
| `agent_classification` | classification | — | standard | algorithms.*, raster.info, layers.inspect, project.inspect |
| `agent_change_detection` | change_detection | — | standard | algorithms.*, raster.info, layers.inspect, project.inspect |
| `agent_3d_gis` | 3d | — | standard | algorithms.*, raster/vector.info, layers.inspect, canvas.inspect, screen.capture |
| `agent_lidar` | lidar | — | standard | algorithms.*, raster.info, layers.inspect/load, project.inspect |
| `agent_survey_gps` | survey | — | standard | algorithms.*, vector.info, layers.inspect/load, project.inspect, database.info |
| `agent_cadastral` | cadastral | — | standard | algorithms.*, vector.info, layers.inspect/load, project.inspect, database.info |
| `agent_cartography` | cartography | — | standard | algorithms.*, layout.info, layers.inspect, vector/raster.info, project.*, screen.capture |
| `agent_temporal_gis` | temporal | — | standard | algorithms.*, raster/vector.info, layers.inspect, project.inspect |
| `agent_database` | database | — | standard | database.info, algorithms.*, layers.load/inspect, project.inspect, system.inspect |
| `agent_web_gis` | web_gis | — | standard | layers.load/inspect, project.inspect, algorithms.discover, system.inspect |
| `agent_automation` | automation | — | standard | workflow.execute, algorithms.*, jobs.cancel, history.inspect, project.inspect |
| `agent_quality_control` | quality | — | standard | algorithms.*, vector/raster.info, layers.inspect, project.inspect, verify.status |
| `agent_reporting` | reporting | — | read | algorithms.*, layout.info, layers.inspect, project.inspect, screen.capture, verify.status |
| `agent_visual_desktop_control` | visual_desktop | qgis.screen | elevated | screen.capture, cursor.*, keyboard.*, mouse.scroll, window/dialog.inspect, canvas.inspect |
| `agent_computer_vision` | computer_vision | — | standard | georeference.*, gcp.*, raster.info, layers.inspect, algorithms.execute, screen.capture |
| `agent_gis_verification` | verification | — | read | verify.status, algorithms.*, vector/raster.info, layers.inspect, project.inspect, gcp.validate |

---

## 4. Key Patterns & Design Decisions

### ✅ Strong Patterns

1. **Tool Allowlist System** — `AGENT_TOOL_ALLOWLISTS` (167 lines) maps each agent to permitted MCP tools; enforced in `BaseAgent.call_tool()` and `AgentManager.get_agent()`

2. **Permission Levels** — Three tiers: `read` (1), `standard` (2), `elevated` (3); checked via `can_use_tool()` against tool spec permissions

3. **Persistent Agent Context** — `AgentContext` with conversation history, working memory, last tool results; auto-saved to `agent_contexts` SQLite table

4. **Async MCP Tool Calling** — `BaseAgent.call_tool()` uses `AsyncQgisBridgeClient` with request tracing, timeout, error capture in context

5. **Supervisor-Worker Architecture** — `AGISSupervisorAgent` creates keyword-based plan → `AgentOrchestrator` executes with dependency resolution & parallelism

6. **AgentOrchestrator Chain Execution** — Topological sort for dependencies, `max_parallel` control, `ChainStep`/`ChainResult` tracking, job integration via `JobManager`

7. **Domain-Specific Specialization** — `SpecializedAgent` with `tool_namespace` for auto-discovering relevant tools from MCP registry

8. **Custom Agent Support** — `CustomAgentBuilder` persists user agents to DB with permissions, skills, AI host config

### ⚠️ Areas of Concern

1. **Duplicate Agent Files** — Two sets: `agent_XX_name.py` (numbered, legacy) AND `agent_name.py` (modern) with identical names in `builtins/__init__.py` exports — which is used?

2. **Legacy Numbered Agents** — `agent_01_data_acquisition.py` through `agent_29_supervisor.py` (29 files) appear to be older versions; not imported in `__init__.py` but exist on disk

3. **Keyword-Based Planning** — `AGISSupervisorAgent._create_plan()` uses simple string matching (250+ lines of `if kw in request_lower`) instead of LLM-based planning

4. **No LLM Integration** — Agents have `ai_host_id` field but no actual AI host invocation in `execute()` methods

5. **Sync/Async Mix** — `BaseAgent.execute_task()` is sync, `execute()` is async; `AgentOrchestrator.delegate()` is sync, `delegate_async()` is async — potential confusion

6. **Missing Circuit Breaker** — No failure isolation around `call_tool()` MCP dispatch

7. **No EventBus Integration** — Agent lifecycle events (start, complete, fail) not published

---

## 5. Dependencies

### Internal
```
agents.base_agent          → core.logging, core.exceptions, mcp_server.qgis_client, mcp_server.server
agents.supervisor          → agents.base_agent, agents.orchestrator
agents.agent_manager       → database.db, core.exceptions, agents.base_agent, agents.custom.custom_builder, agents.builtins
agents.orchestrator        → core.job_manager, core.logging, core.exceptions
agents.custom.custom_builder → database.db, core.exceptions
agents.builtins.*          → agents.base_agent (SpecializedAgent), mcp_server.registry (via base_agent)
```

### External
- `mcp_server.qgis_client.AsyncQgisBridgeClient` — MCP tool dispatch
- `mcp_server.registry.build_registry` — Tool spec lookup for permissions
- `mcp_server.server.get_permission_manager` — Permission checking

---

## 6. Issues Found

### 🔴 REMOVE (Dead Code / Security Risks / Duplicates)
| Item | Location | Issue |
|------|----------|-------|
| `__pycache__/` | `agents/`, `agents/builtins/`, `agents/custom/` | Compiled bytecode committed — gitignore |
| **29 Legacy numbered agents** | `builtins/agent_01_*.py` through `agent_29_*.py` | Duplicate implementations; not imported but clutter filesystem |
| **Duplicate agent files** | `builtins/agent_gis_supervisor.py` (modern) + `supervisor.py` (legacy) | Same class name `AGISSupervisorAgent` — confusion |
| `AGENT_TOOL_ALLOWLISTS` placeholder | `custom_builder.py:40` | Inserts `__custom_spec__` as tool_id — corrupts agent_tools table |
| `agent_27_orchestrator.py` | `builtins/agent_27_orchestrator.py` | Legacy agent that doesn't match `AgentOrchestrator` class |

### 🟡 ADD (Missing Features / Tests / Docs)
| Gap | Scope | Recommendation |
|-----|-------|----------------|
| **LLM-based planning** | `AGISSupervisorAgent` | Replace keyword matching with AI host call (OpenCode/Codex) for plan generation |
| **AI host integration** | All agents | `ai_host_id` field exists but never used; implement `call_ai()` in `BaseAgent` |
| **Unit tests** | All 30 agents | Zero dedicated agent tests; only workflow handler tests mock agent_manager |
| **Integration tests** | Orchestrator + agents | No tests with real MCP tools / QGIS |
| **Parameter schemas** | Agent `execute()` methods | No validation of `task` dict structure |
| **Agent health checks** | `AgentManager` | No `health_check()` method for agent status |
| **Metrics/telemetry** | Orchestrator | No timing, success rate, token usage tracking |
| **Agent-to-agent messaging** | Orchestrator | Only `dependency_results` passed; no direct communication channel |
| **Cancellation propagation** | Orchestrator | `cancel_chain()` cancels jobs but doesn't interrupt agent `execute()` |
| **Documentation** | All agents | No per-agent README or capability catalog |

### 🔵 IMPROVE (Refactoring / Performance / Patterns)
| Opportunity | Details |
|-------------|---------|
| **Remove legacy agents** | Delete `agent_01_*.py` through `agent_29_*.py` and duplicate `agent_*.py` files |
| **Unify sync/async** | Make `BaseAgent.execute()` the primary async method; deprecate `execute_task()` |
| **Add CircuitBreaker** | Wrap `call_tool()` in `core.circuit_breaker.CircuitBreaker` per agent |
| **EventBus integration** | Publish `agent.task.started`, `agent.task.completed`, `agent.chain.completed` events |
| **CapabilityRegistry registration** | Register each agent's domain capabilities on startup |
| **Structured planning** | Replace keyword planner with LLM-based planner using `ai_host_id` |
| **Agent communication protocol** | Add `send_message(agent_id, message)` for direct agent-to-agent |
| **Tool allowlist from DB** | `sync_agent_tools()` reads from DB but `AGENT_TOOL_ALLOWLISTS` is source of truth — unify |
| **Custom agent spec storage** | Store full spec as JSON in `agents` table, not placeholder tool_id |
| **Async job tracking** | `AgentOrchestrator.delegate_async()` should return job_id for polling, not block |

---

## 7. Cross-Module Integration (with core/, clusters/, engines/ context)

### Current Integration
```
AGISSupervisorAgent          ──uses──▶ AgentOrchestrator
AgentOrchestrator            ──uses──▶ AgentManager, JobManager (core)
BaseAgent.call_tool()        ──uses──▶ AsyncQgisBridgeClient (MCP) → Clusters via Bridge
AgentManager                 ──uses──▶ AGENT_TOOL_ALLOWLISTS (maps to MCP tool IDs)
SpecializedAgent             ──uses──▶ tool_namespace → MCP registry filtering
VisualDesktopControlAgent    ──uses──▶ qgis.screen, qgis.cursor, qgis.keyboard, qgis.mouse, qgis.window (engines)
GeoreferencingAgent          ──uses──▶ qgis.georeference, qgis.gcp (engines.georeferencing)
ComputerVisionAgent          ──uses──▶ qgis.georeference, qgis.gcp, qgis.raster (engines.computer_vision)
```

### Missing Integration (from prior analyses)
| Core Service | Should Integrate With | Current State |
|--------------|----------------------|---------------|
| `EventBus` | AgentOrchestrator (chain start/step/complete), BaseAgent (tool call) | **Not used** |
| `ResourceQuotaManager` | AgentOrchestrator (per-agent quotas), BaseAgent (tool call tracking) | **Not used** |
| `EmergencyStop` | AgentOrchestrator (check in chain loop), BaseAgent (check in call_tool) | **Not used** |
| `CapabilityRegistry` | AgentManager (register agent capabilities), SpecializedAgent (declare domain) | **Not used** |
| `CircuitBreaker` | BaseAgent.call_tool() (wrap MCP dispatch) | **Not used** |
| `Keyring` | CustomAgentBuilder (store AI host API keys) | **Not used** |

---

## 8. Test Coverage

| Test File | Coverage |
|-----------|----------|
| `tests/unit/test_workflow_handlers.py` | Mocks `agent_manager` for workflow agent handler (4 tests) |
| **Missing** | `test_base_agent.py`, `test_agent_manager.py`, `test_orchestrator.py`, `test_supervisor.py`, `test_custom_builder.py` |
| **Missing** | Per-agent tests (30 agents × 0 tests) |

**Total: 0/33 agent modules have dedicated tests (0%)**

---

## 9. Recommendations Summary

### Priority 1 (Immediate)
1. **Add all `agents/**/__pycache__/` to `.gitignore`**
2. **Remove 29 legacy numbered agents** (`agent_01_*.py` through `agent_29_*.py`)
3. **Resolve duplicate agent files** — keep modern `agent_*.py` in `builtins/`, remove `supervisor.py` (legacy) and duplicate exports
4. **Fix `CustomAgentBuilder`** — store full spec as JSON, not `__custom_spec__` placeholder

### Priority 2 (Short-term)
5. **Add unit tests** for `BaseAgent`, `AgentManager`, `AgentOrchestrator`, `AGISSupervisorAgent`, `CustomAgentBuilder`
6. **Implement LLM-based planning** in `AGISSupervisorAgent` using `ai_host_id` and AI host integration
7. **Add `EventBus` publishing** for agent lifecycle events
8. **Wire `EmergencyStop`** checks in `AgentOrchestrator._execute_chain()` and `BaseAgent.call_tool()`
9. **Add `CircuitBreaker`** around MCP `dispatch()` in `BaseAgent.call_tool()`
10. **Unify sync/async** — make `execute()` primary, deprecate `execute_task()`

### Priority 3 (Medium-term)
11. **Implement agent-to-agent messaging** protocol
12. **Add `CapabilityRegistry` registration** for each agent's domain capabilities
13. **Add `ResourceQuotaManager` tracking** for agent execution
14. **Implement structured tool allowlist sync** (DB ↔ memory)
15. **Add agent health check endpoint** and telemetry
16. **Create per-agent documentation** with capabilities, tools, examples

---

## 10. Output for Next Task (database/)

**Context to pass forward:**
- Agents depend on: `database.db.Database` (for `agent_contexts`, `agents`, `agent_tools` tables), `JobManager` (via orchestrator)
- `AgentContext` persists to `agent_contexts` table with JSON blob
- `CustomAgentBuilder` writes to `agents` table (custom agents)
- `AgentManager.populate_agent_tools_table()` writes to `agent_tools` table
- Database folder contains: `migrations/`, `repositories/` (settings_repository), `db.py` (not yet read)
- Key integration: `BaseAgent` takes optional `db` parameter for context persistence
- Watch for: Circular imports between agents and database; `agent_manager.py` imports `database.db.Database`

---

*End of agents/ folder analysis*