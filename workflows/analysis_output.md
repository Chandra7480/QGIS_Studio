# Workflows Folder Analysis — Universal AI GIS Studio

**Task:** task-10  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent  
**Context:** skills/ (task-9) analysis read prior

---

## 1. Folder Structure

```
workflows/
├── __init__.py                          # Empty package marker
├── workflow_engine.py                   # WorkflowEngine: DAG execution, checkpointing, node handlers (946 lines)
└── __pycache__/
```

**Total:** 1 Python module (~950 lines)

---

## 2. Architecture & Components

### Core Classes

| Class | Purpose |
|-------|---------|
| **`WorkflowState`** | Persisted execution state for pause/resume: job_id, workflow_id, step_index, context, completed/pending steps, status |
| **`StepExecution`** | Represents a step ready for execution: step_id, step_index, node_type, config, depends_on |
| **`WorkflowEngine`** | Main orchestration engine: CRUD, DAG building, topological sort, parallel execution, checkpointing, node handlers |

### Workflow Definition Structure
```json
{
  "name": "string",
  "description": "string",
  "steps": [
    {
      "id": "step_1",
      "type": "gis_tool",
      "step_index": 0,
      "config": {
        "cluster_id": "M03",
        "operation": "buffer",
        "params": {"distance": 100},
        "depends_on": []
      }
    }
  ]
}
```

### Database Tables Used
- `workflows` — id, name, description, definition (JSON), version, enabled, created_at, updated_at
- `workflow_steps` — id, workflow_id, step_index, node_type, config (JSON)
- `workflow_states` — job_id (PK), workflow_id, step_index, context (JSON), completed_steps (JSON), pending_steps (JSON), status, created_at, updated_at

---

## 3. Node Types (13 Types)

| Node Type | Handler | Description |
|-----------|---------|-------------|
| `start` | `_start_handler` | Workflow entry point |
| `end` | `_end_handler` | Workflow exit point |
| `gis_tool` | `_gis_tool_handler` | Execute cluster operation via `ClusterRegistry` |
| `agent` | `_agent_handler` | Delegate to agent via `AgentManager` |
| `mcp_tool` | `_mcp_tool_handler` | Call MCP tool via `AsyncQgisBridgeClient` |
| `api` | `_api_handler` / `_api_handler_async` | Call LLM API (OpenAI, Anthropic, Gemini, OpenRouter, custom) |
| `condition` | `_condition_handler` | Evaluate Python/JMESPath expression for branching |
| `loop` | `_loop_handler` | Iterate over array or fixed count with body steps |
| `input` | `_input_handler` | Pass input data |
| `output` | `_output_handler` | Map outputs via JMESPath |
| `approval` | `_approval_handler` | Pause for human approval via `ApprovalManager` |
| `validation` | `_validation_handler` | Validate outputs against JMESPath expressions |
| `report` | `_report_handler` | Generate report via string template |

---

## 4. Execution Model

### DAG-Based Parallel Execution
1. **`_build_dag()`** — Builds step map with `depends_on` relationships
2. **`_topological_sort()`** — Kahn's algorithm returning levels (parallel groups)
3. **Level-by-level execution** — All steps in a level run in parallel via `asyncio.gather()`
4. **Context propagation** — Dependency outputs injected via `_build_step_context()`

### Checkpoint/Pause/Resume
- **State persisted** to `workflow_states` table after each level
- **`pause()`** — Saves state with `status="paused"`, stores approval_id
- **`resume()`** — Loads state, validates approval, continues from `step_index`
- **`cancel()`** — Marks cancelled, stops job
- **`retry()`** — Resets state to beginning or failed step

### Condition Evaluation (`_condition_handler`)
- **Python expressions** (with `==`, `!=`, `>`, `<`, `>=`, `<=`, `in`, `not in`, `and`, `or`, `not`) evaluated via `eval()` with restricted builtins
- **JMESPath expressions** for path-based truthy checks
- Returns `{"proceed": bool, "evaluation": result}`

### Loop Execution (`_loop_handler`)
- **Iterator mode**: JMESPath to array from context outputs
- **Fixed count mode**: `max_iterations` with optional `iterator_var`
- Executes `body` steps sequentially per iteration
- Returns aggregated results

---

## 5. Dependencies

### Internal
```
workflows.workflow_engine.WorkflowEngine
    → database.db.Database
    → core.job_manager.JobManager
    → core.exceptions.WorkflowError, NotFoundError
    → agents.agent_manager.AgentManager
    → security.approval_manager.ApprovalManager
    → clusters.registry (cluster_registry parameter)
    → mcp_server.qgis_client.AsyncQgisBridgeClient (mcp_client parameter)
    → httpx.AsyncClient (api_client parameter)
    → executor (PyQGISExecutor, for gis_tool)
```

### External
- **`httpx`** — Async HTTP for API node
- **`jmespath`** — Path expressions for condition/validation/output mapping
- **`asyncio`** — Parallel execution, event loop management
- **`string.Template`** — Prompt templating

---

## 6. Integration Points (from skills/ context)

### Current Integrations
```
WorkflowEngine.execute()
    → JobManager.create_job/start_job/complete_job/fail_job
    → ClusterRegistry.get_cluster_handler() → ClusterHandler.execute()
    → AgentManager.get_agent() → BaseAgent.execute_task()
    → AsyncQgisBridgeClient.dispatch() → Bridge /dispatch
    → ApprovalManager.request()/is_approved()
    → httpx.AsyncClient.post() for API calls
```

### Skills Integration (Missing)
- **No skill node type** — Workflows cannot directly invoke skills
- **SkillManager not injected** — Despite skills/ having `assign_to_agent()`
- **Skill capabilities not discoverable** — No integration with `CapabilityRegistry`

---

## 7. Issues Found

### 🔴 REMOVE (Security Risks / Bugs)
| Item | Location | Issue |
|------|----------|-------|
| `__pycache__/` | `workflows/__pycache__/` | Compiled bytecode committed — gitignore |
| **`eval()` in condition handler** | `workflow_engine.py:725` | **Arbitrary code execution** — `eval(expression, {"__builtins__": {}}, flat)` — user-controlled expression can escape sandbox |
| **`exec`/`eval` in agent handler** | `workflow_engine.py:602-606` | Creates new event loop per call — resource leak, not thread-safe |

### 🟡 ADD (Missing Features / Tests / Docs)
| Gap | Scope | Recommendation |
|-----|-------|----------------|
| **Unit tests** | `workflow_engine.py` | Zero tests for DAG execution, checkpointing, handlers |
| **Skill node type** | `VALID_NODE_TYPES`, `_node_handler` | Add `"skill"` node type invoking `SkillManager`/`SkillLoader` |
| **Workflow validation** | `create_workflow()` | No validation of DAG (cycles, unknown deps, missing cluster/agent) |
| **Workflow versioning** | `workflows` table | `version` column exists but unused; no migration/upgrade logic |
| **Sub-workflow support** | Node types | No `sub_workflow` node for composition |
| **Parallel loop execution** | `_loop_handler` | Loop body executes sequentially; could parallelize independent iterations |
| **EventBus integration** | All lifecycle | No events for workflow start/step/complete/pause/resume/cancel |
| **Metrics/telemetry** | Execution | No latency, success rate, retry count tracking |
| **Dead letter queue** | Failed workflows | No automatic retry with backoff or DLQ for persistent failures |
| **Workflow templates** | `create_workflow()` | No template system for common patterns |
| **Visual workflow editor** | N/A | No UI/frontend integration defined |

### 🔵 IMPROVE (Refactoring / Performance / Patterns)
| Opportunity | Details |
|-------------|---------|
| **Replace `eval()`** | Use safe expression evaluator (e.g., `asteval`, `simpleeval`, or custom AST walker) |
| **Async event loop management** | Remove manual `asyncio.new_event_loop()`; require async context or use `asyncio.run()` |
| **Dependency injection** | Pass `SkillManager`, `CapabilityRegistry`, `EventBus` in constructor |
| **Async-first execution** | Make `_run_dag()` fully async; remove `loop.run_until_complete()` calls |
| **State serialization** | Use Pydantic models for `WorkflowState` instead of manual JSON |
| **Node handler registry** | Plugin system for custom node types instead of hardcoded dict |
| **Circuit breaker** | Wrap external calls (MCP, API, cluster) in `core.circuit_breaker` |
| **Resource quota** | Track per-workflow memory/CPU via `core.resource_quota` |
| **Emergency stop** | Check `is_emergency_stop_active()` in execution loop |
| **JMESPath caching** | Compile expressions once per workflow |
| **Output schema validation** | Validate step outputs against declared schemas |

---

## 8. Test Coverage

| Test File | Coverage |
|-----------|----------|
| **None** | Zero tests for workflow engine |

**Total: 0 tests for 1 module (0%)**

---

## 9. Recommendations Summary

### Priority 1 (Immediate)
1. **Add `workflows/__pycache__/` to `.gitignore`**
2. **REMOVE `eval()` in `_condition_handler`** — replace with safe evaluator (`simpleeval`, `asteval`, or custom AST-based)
3. **Fix event loop management** — remove manual `asyncio.new_event_loop()` in `_agent_handler`; make execution fully async

### Priority 2 (Short-term)
4. **Add skill node type** — integrate `SkillManager`/`SkillLoader` for skill invocation
5. **Add unit tests** for DAG building, topological sort, checkpointing, each handler
6. **Add workflow validation** in `create_workflow()` (DAG cycles, valid deps, known clusters/agents)
7. **Add workflow versioning/migration** logic
8. **Add EventBus events** for workflow lifecycle

### Priority 3 (Medium-term)
9. **Add sub-workflow node** for composition
10. **Implement parallel loop execution** for independent iterations
11. **Add CircuitBreaker** around external calls (MCP, API, cluster)
12. **Add ResourceQuota tracking** per workflow
13. **Add EmergencyStop** checks in execution loop
14. **Add workflow templates** and visual editor integration
15. **Add structured logging** with correlation IDs (`job_id`, `workflow_id`)

---

## 10. Output for Next Task (extensions/)

**Context to pass forward:**
- Workflows provide: DAG-based orchestration with 13 node types, checkpointing, pause/resume, parallel execution, condition/loop/approval/validation/report nodes
- Key integrations: `JobManager`, `ClusterRegistry`, `AgentManager`, `AsyncQgisBridgeClient`, `ApprovalManager`, `httpx.AsyncClient`
- Security issue: `eval()` in condition handler — must be fixed
- Extensions folder contains: `__init__.py`, `extension_manager.py`
- Extension manager likely: loads/installs/uninstalls extensions, manages permissions
- Extensions may provide: custom node types, custom tools, custom skills, UI components
- Watch for: Circular imports between extensions and workflows/skills/agents; extension manager should not import workflow internals directly

---

*End of workflows/ folder analysis*