"""Universal AI GIS Studio — Workflow Builder & Execution Engine.

Node types: Start, End, GIS Tool, Agent, MCP Tool, API, Condition, Loop,
Input, Output, Approval, Validation, Report.

Workflows execute real registered handlers (cluster operations / MCP tools),
not merely diagrams. Supports save/load, pause/resume/cancel/retry, and
execution history.
"""

import json
import uuid
import datetime as dt
import logging
import asyncio
from typing import Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque

import httpx
import jmespath
from simpleeval import EvalWithCompoundTypes

from database.db import Database
from core.job_manager import JobManager
from core.exceptions import WorkflowError, NotFoundError
from core.emergency_stop import is_emergency_stop_active, EmergencyStopActiveError
from agents.agent_manager import AgentManager
from security.approval_manager import ApprovalManager

logger = logging.getLogger("uagis.workflow")

VALID_NODE_TYPES = {
    "start", "end", "gis_tool", "agent", "mcp_tool", "api", "condition",
    "loop", "input", "output", "approval", "validation", "report",
}


@dataclass
class WorkflowState:
    """Persisted workflow execution state for pause/resume."""
    job_id: str
    workflow_id: str
    step_index: int
    context: dict
    completed_steps: list[str] = field(default_factory=list)
    pending_steps: list[str] = field(default_factory=list)
    failed_step: str | None = None
    error_message: str | None = None
    status: str = "running"  # running, paused, completed, failed, cancelled
    created_at: str = field(default_factory=lambda: dt.datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: dt.datetime.utcnow().isoformat())


@dataclass
class StepExecution:
    """Represents a step ready for execution."""
    step_id: str
    step_index: int
    node_type: str
    config: dict
    depends_on: list[str] = field(default_factory=list)


class WorkflowEngine:
    def __init__(
        self,
        db: Database,
        job_manager: JobManager,
        cluster_registry=None,
        mcp_client=None,
        agent_manager: AgentManager | None = None,
        api_client: httpx.AsyncClient | None = None,
        executor=None,
        approval_manager: ApprovalManager | None = None,
    ):
        self.db = db
        self.job_manager = job_manager
        self.cluster_registry = cluster_registry
        self.mcp_client = mcp_client
        self.agent_manager = agent_manager
        self.api_client = api_client
        self.executor = executor
        self.approval_manager = approval_manager
        self._running: dict[str, dict] = {}
        self._state_cache: dict[str, WorkflowState] = {}

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #
    def create_workflow(self, name: str, definition: dict) -> str:
        wid = f"wf_{uuid.uuid4().hex[:10]}"
        now = dt.datetime.utcnow().isoformat()
        self.db.execute(
            "INSERT INTO workflows(id, name, description, definition, version, "
            "enabled, created_at, updated_at) VALUES(?, ?, ?, ?, 1, 1, ?, ?)",
            (wid, name, definition.get("description", ""),
             json.dumps(definition), now, now))
        self._save_steps(wid, definition.get("steps", []))
        return wid

    def _save_steps(self, wid: str, steps: list) -> None:
        self.db.execute("DELETE FROM workflow_steps WHERE workflow_id = ?", (wid,))
        for i, step in enumerate(steps):
            self.db.execute(
                "INSERT INTO workflow_steps(id, workflow_id, step_index, node_type, config) "
                "VALUES(?, ?, ?, ?, ?)",
                (f"{wid}_step_{i}", wid, i, step.get("type", "gis_tool"),
                 json.dumps(step.get("config", {}))))

    def get_workflow(self, wid: str) -> dict | None:
        row = self.db.fetchone("SELECT * FROM workflows WHERE id = ?", (wid,))
        if not row:
            return None
        wf = dict(row)
        try:
            wf["definition"] = json.loads(wf["definition"])
        except Exception:
            pass
        steps = self.db.fetchall(
            "SELECT * FROM workflow_steps WHERE workflow_id = ? ORDER BY step_index",
            (wid,))
        wf["steps"] = [dict(s) for s in steps]
        return wf

    def list_workflows(self) -> list[dict]:
        rows = self.db.fetchall("SELECT * FROM workflows ORDER BY name")
        return [dict(r) for r in rows]

    def delete_workflow(self, wid: str) -> None:
        self.db.execute("DELETE FROM workflow_steps WHERE workflow_id = ?", (wid,))
        self.db.execute("DELETE FROM workflows WHERE id = ?", (wid,))

    # ------------------------------------------------------------------ #
    # DAG Building & Execution
    # ------------------------------------------------------------------ #
    def execute(self, wid: str, input_data: dict | None = None) -> str:
        wf = self.get_workflow(wid)
        if not wf:
            raise NotFoundError(f"Workflow {wid} not found")
        job_id = self.job_manager.create_job(
            job_type="workflow", input_payload=json.dumps(input_data or {}))
        self.job_manager.start_job(job_id)
        self._running[job_id] = {"wid": wid, "step_index": 0}
        try:
            result = self._run_dag(wf, input_data or {}, job_id)
            self.job_manager.complete_job(job_id, json.dumps(result), "SUCCESS")
        except Exception as exc:
            logger.exception("Workflow %s failed: %s", wid, exc)
            self.job_manager.fail_job(job_id, str(exc))
            result = {"status": "failed", "error": str(exc)}
        finally:
            self._running.pop(job_id, None)
            self._state_cache.pop(job_id, None)
        return job_id

    def _build_dag(self, steps: list) -> dict[str, StepExecution]:
        """Build DAG from steps with depends_on relationships."""
        step_map = {}
        for step in steps:
            step_id = step.get("id", f"step_{step.get('step_index', 0)}")
            config = step.get("config", {})
            depends_on = config.get("depends_on", [])
            step_map[step_id] = StepExecution(
                step_id=step_id,
                step_index=step.get("step_index", 0),
                node_type=step.get("type", "gis_tool"),
                config=config,
                depends_on=depends_on,
            )
        return step_map

    def _topological_sort(self, step_map: dict[str, StepExecution]) -> list[list[str]]:
        """Return list of levels (parallel groups) for topological execution."""
        # Build adjacency list and in-degree count
        adj = defaultdict(list)
        in_degree = defaultdict(int)
        
        for step_id, step in step_map.items():
            in_degree[step_id] = 0
        
        for step_id, step in step_map.items():
            for dep in step.depends_on:
                if dep in step_map:
                    adj[dep].append(step_id)
                    in_degree[step_id] += 1
                else:
                    logger.warning("Step %s depends on unknown step %s", step_id, dep)
        
        # Kahn's algorithm - group by level for parallel execution
        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        levels = []
        
        while queue:
            level = []
            for _ in range(len(queue)):
                node = queue.popleft()
                level.append(node)
                for neighbor in adj[node]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
            if level:
                levels.append(level)
        
        # Check for cycles
        total_processed = sum(len(l) for l in levels)
        if total_processed != len(step_map):
            remaining = set(step_map.keys()) - {n for l in levels for n in l}
            raise WorkflowError(f"Circular dependency detected in workflow: {remaining}")
        
        return levels

    async def _execute_step(self, step: StepExecution, context: dict) -> dict:
        """Execute a single step and return its output."""
        handler = self._node_handler(step.node_type)
        # Pass step_id in config for context key
        config_with_id = {**step.config, "_step_id": step.step_id}
        if asyncio.iscoroutinefunction(handler):
            return await handler(config_with_id, context)
        else:
            # Run sync handler in thread pool to avoid blocking event loop
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(self.executor, handler, config_with_id, context)

    def _run_dag(self, wf: dict, input_data: dict, job_id: str) -> dict:
        """Execute workflow as DAG with parallel execution."""
        steps = wf.get("steps", [])
        if not steps:
            return {"status": "completed", "outputs": {}}
        
        step_map = self._build_dag(steps)
        levels = self._topological_sort(step_map)
        
        context = {"input": input_data, "outputs": {}}
        completed_steps = []
        
        # Save initial state
        self._save_state(job_id, wf["id"], 0, context, completed_steps, 
                        [s for level in levels for s in level], status="running")
        
        for level_idx, level in enumerate(levels):
            # Check for emergency stop before each level
            if is_emergency_stop_active():
                logger.warning("Workflow %s stopped: emergency stop active", job_id)
                self.job_manager.fail_job(job_id, "Emergency stop active - workflow cancelled")
                return {"status": "cancelled", "outputs": context["outputs"], "reason": "emergency_stop"}
            
            # Check for pause/cancel
            self._check_pause(job_id)
            
            # Execute all steps in this level in parallel
            level_tasks = []
            for step_id in level:
                step = step_map[step_id]
                # Inject context from dependencies
                step_context = self._build_step_context(step, context)
                task = self._execute_step(step, step_context)
                level_tasks.append((step_id, task))
            
            # Wait for all tasks in this level
            if level_tasks:
                results = self._run_parallel_tasks(level_tasks)
                for step_id, result in results.items():
                    context["outputs"][step_id] = result
                    completed_steps.append(step_id)
                    
                    # Handle condition node
                    step = step_map[step_id]
                    if step.node_type == "condition" and not result.get("proceed", True):
                        logger.info("Condition failed at step %s, stopping workflow", step_id)
                        return {"status": "completed", "outputs": context["outputs"], "stopped_at": step_id}
                    
                    # Handle approval node - pause if approval required
                    if step.node_type == "approval" and result.get("status") == "approval_required":
                        approval_id = result.get("approval_id")
                        if approval_id:
                            # Pause workflow until approval
                            self._save_state(job_id, wf["id"], level_idx + 1, context, completed_steps,
                                           [s for l in levels[level_idx+1:] for s in l], status="paused")
                            self.pause(job_id, approval_id)
                            # Resume will be called externally after approval decision
                            return {"status": "paused", "approval_id": approval_id, "outputs": context["outputs"]}
            
            # Save checkpoint after each level
            self._save_state(job_id, wf["id"], level_idx + 1, context, completed_steps,
                           [s for l in levels[level_idx+1:] for s in l], status="running")
        
        return {"status": "completed", "outputs": context["outputs"]}

    def _run_parallel_tasks(self, tasks: list[tuple[str, Any]]) -> dict[str, dict]:
        """Run multiple async tasks in parallel using asyncio.gather."""
        if not tasks:
            return {}
        
        step_ids = [t[0] for t in tasks]
        coros = [t[1] for t in tasks]
        
        # Run in event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        results = loop.run_until_complete(asyncio.gather(*coros, return_exceptions=True))
        
        output = {}
        for step_id, result in zip(step_ids, results):
            if isinstance(result, Exception):
                logger.error("Step %s failed: %s", step_id, result)
                raise WorkflowError(f"Step {step_id} failed: {result}")
            output[step_id] = result
        return output

    def _build_step_context(self, step: StepExecution, context: dict) -> dict:
        """Build context for a step including outputs from its dependencies."""
        step_context = {**context}
        # Add dependency outputs directly for easy access
        for dep_id in step.depends_on:
            if dep_id in context.get("outputs", {}):
                step_context[f"dep_{dep_id}"] = context["outputs"][dep_id]
        return step_context

    # ------------------------------------------------------------------ #
    # State Persistence (Checkpoint/Pause/Resume)
    # ------------------------------------------------------------------ #
    def _save_state(
        self,
        job_id: str,
        workflow_id: str,
        step_index: int,
        context: dict,
        completed_steps: list[str],
        pending_steps: list[str],
        status: str = "running",
    ) -> None:
        """Save workflow execution state to database."""
        updated_at = dt.datetime.utcnow().isoformat()
        
        # Update existing cached state or create new one
        if job_id in self._state_cache:
            state = self._state_cache[job_id]
            state.step_index = step_index
            state.context = context
            state.completed_steps = completed_steps
            state.pending_steps = pending_steps
            state.status = status
            state.updated_at = updated_at
        else:
            state = WorkflowState(
                job_id=job_id,
                workflow_id=workflow_id,
                step_index=step_index,
                context=context,
                completed_steps=completed_steps,
                pending_steps=pending_steps,
                status=status,
                updated_at=updated_at,
            )
            self._state_cache[job_id] = state
        
        # Persist to database
        self.db.execute(
            """INSERT OR REPLACE INTO workflow_states 
               (job_id, workflow_id, step_index, context, completed_steps, pending_steps, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_id, workflow_id, step_index,
                json.dumps(context),
                json.dumps(completed_steps),
                json.dumps(pending_steps),
                status,
                updated_at,
            )
        )

    def _load_state(self, job_id: str) -> WorkflowState | None:
        """Load workflow execution state from database."""
        if job_id in self._state_cache:
            return self._state_cache[job_id]
        
        row = self.db.fetchone(
            "SELECT * FROM workflow_states WHERE job_id = ?", (job_id,))
        if not row:
            return None
        
        state = WorkflowState(
            job_id=row["job_id"],
            workflow_id=row["workflow_id"],
            step_index=row["step_index"],
            context=json.loads(row["context"]) if row["context"] else {},
            completed_steps=json.loads(row["completed_steps"]) if row["completed_steps"] else [],
            pending_steps=json.loads(row["pending_steps"]) if row["pending_steps"] else [],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        self._state_cache[job_id] = state
        return state

    def pause(self, job_id: str, approval_id: str | None = None) -> None:
        """Pause workflow execution."""
        state = self._load_state(job_id)
        if state:
            state.status = "paused"
            if approval_id:
                state.context["_pending_approval"] = approval_id
            self._save_state(
                job_id, state.workflow_id, state.step_index, state.context,
                state.completed_steps, state.pending_steps, status="paused"
            )
        self.job_manager.update_status(job_id, "paused")
        logger.info("Workflow %s paused", job_id)

    def resume(self, job_id: str) -> str:
        """Resume paused workflow from checkpoint."""
        state = self._load_state(job_id)
        if not state:
            raise NotFoundError(f"No saved state for job {job_id}")
        
        if state.status != "paused":
            raise WorkflowError(f"Job {job_id} is not paused (status: {state.status})")
        
        # Check if approval was required and is now approved
        approval_id = state.context.get("_pending_approval")
        if approval_id and self.approval_manager:
            if not self.approval_manager.is_approved(approval_id):
                raise WorkflowError(f"Approval {approval_id} not yet granted")
            # Clear pending approval
            state.context.pop("_pending_approval", None)
        
        state.status = "running"
        state.updated_at = dt.datetime.utcnow().isoformat()
        self._save_state(
            job_id, state.workflow_id, state.step_index, state.context,
            state.completed_steps, state.pending_steps, status="running"
        )
        
        # Re-create job manager entry
        self.job_manager.update_status(job_id, "running")
        self._running[job_id] = {"wid": state.workflow_id, "step_index": state.step_index}
        
        # Continue execution from saved state
        wf = self.get_workflow(state.workflow_id)
        if not wf:
            raise NotFoundError(f"Workflow {state.workflow_id} not found")
        
        try:
            result = self._resume_dag(wf, state, job_id)
            self.job_manager.complete_job(job_id, json.dumps(result), "SUCCESS")
        except Exception as exc:
            logger.exception("Workflow resume %s failed: %s", job_id, exc)
            self.job_manager.fail_job(job_id, str(exc))
            result = {"status": "failed", "error": str(exc)}
        finally:
            self._running.pop(job_id, None)
            self._state_cache.pop(job_id, None)
        
        return job_id

    def _resume_dag(self, wf: dict, state: WorkflowState, job_id: str) -> dict:
        """Resume DAG execution from saved state."""
        steps = wf.get("steps", [])
        step_map = self._build_dag(steps)
        levels = self._topological_sort(step_map)
        
        # Ensure context has outputs key
        context = state.context
        if "outputs" not in context:
            context["outputs"] = {}
        completed_steps = set(state.completed_steps)
        
        # Find starting level
        start_level_idx = state.step_index
        
        for level_idx in range(start_level_idx, len(levels)):
            # Check for emergency stop before each level
            if is_emergency_stop_active():
                logger.warning("Workflow %s stopped on resume: emergency stop active", job_id)
                self.job_manager.fail_job(job_id, "Emergency stop active - workflow cancelled")
                return {"status": "cancelled", "outputs": context["outputs"], "reason": "emergency_stop"}
            
            level = levels[level_idx]
            
            # Skip already completed steps in this level
            level_tasks = []
            for step_id in level:
                if step_id in completed_steps:
                    continue
                step = step_map[step_id]
                step_context = self._build_step_context(step, context)
                task = self._execute_step(step, step_context)
                level_tasks.append((step_id, task))
            
            if level_tasks:
                results = self._run_parallel_tasks(level_tasks)
                for step_id, result in results.items():
                    context["outputs"][step_id] = result
                    completed_steps.add(step_id)
                    
                    step = step_map[step_id]
                    if step.node_type == "condition" and not result.get("proceed", True):
                        return {"status": "completed", "outputs": context["outputs"], "stopped_at": step_id}
                    
                    if step.node_type == "approval" and result.get("status") == "approval_required":
                        approval_id = result.get("approval_id")
                        if approval_id:
                            self._save_state(job_id, wf["id"], level_idx + 1, context, 
                                           list(completed_steps),
                                           [s for l in levels[level_idx+1:] for s in l], status="paused")
                            self.pause(job_id, approval_id)
                            return {"status": "paused", "approval_id": approval_id, "outputs": context["outputs"]}
            
            self._save_state(job_id, wf["id"], level_idx + 1, context, 
                           list(completed_steps),
                           [s for l in levels[level_idx+1:] for s in l], status="running")
        
        return {"status": "completed", "outputs": context["outputs"]}

    def cancel(self, job_id: str) -> None:
        """Cancel workflow execution."""
        state = self._load_state(job_id)
        if state:
            state.status = "cancelled"
            self._save_state(
                job_id, state.workflow_id, state.step_index, state.context,
                state.completed_steps, state.pending_steps, status="cancelled"
            )
        self.job_manager.cancel_job(job_id)
        self._running.pop(job_id, None)
        logger.info("Workflow %s cancelled", job_id)

    def retry(self, job_id: str) -> str:
        """Retry failed workflow from beginning or failed step."""
        state = self._load_state(job_id)
        if not state:
            raise NotFoundError(f"No saved state for job {job_id}")
        
        if state.status not in ("failed", "cancelled"):
            raise WorkflowError(f"Cannot retry job with status {state.status}")
        
        # Reset state for retry
        state.status = "running"
        state.step_index = 0
        state.completed_steps = []
        state.failed_step = None
        state.error_message = None
        state.updated_at = dt.datetime.utcnow().isoformat()
        
        self._save_state(
            job_id, state.workflow_id, 0, state.context, [], state.pending_steps, status="running"
        )
        
        return self.resume(job_id)

    def _check_pause(self, job_id: str) -> None:
        """Check if workflow should pause (external signal)."""
        job = self.job_manager.get_job(job_id)
        if job and job.get("status") == "paused":
            raise WorkflowError("Workflow paused externally")

    # ------------------------------------------------------------------ #
    # Node Handlers
    # ------------------------------------------------------------------ #
    def _node_handler(self, node_type: str):
        handlers = {
            "gis_tool": self._gis_tool_handler,
            "agent": self._agent_handler,
            "mcp_tool": self._mcp_tool_handler,
            "api": self._api_handler_async,  # Use async version for parallel execution
            "condition": self._condition_handler,
            "loop": self._loop_handler,
            "input": self._input_handler,
            "output": self._output_handler,
            "approval": self._approval_handler,
            "validation": self._validation_handler,
            "report": self._report_handler,
            "start": self._start_handler,
            "end": self._end_handler,
        }
        if node_type not in handlers:
            raise WorkflowError(f"Unknown node type: {node_type}")
        return handlers[node_type]

    # ---- Core handlers ----
    def _start_handler(self, config, context):
        return {"status": "started"}

    def _end_handler(self, config, context):
        return {"status": "ended"}

    async def _gis_tool_handler(self, config, context) -> dict:
        """Execute GIS tool via cluster registry (runs blocking call in executor)."""
        if not self.cluster_registry:
            raise WorkflowError("No cluster registry for gis_tool node")
        cluster_id = config.get("cluster_id")
        operation = config.get("operation")
        params = config.get("params", {})
        if config.get("use_context", True):
            params = {**self._flatten_outputs(context.get("outputs", {})), **params}
        
        handler = self.cluster_registry.get_cluster_handler(cluster_id, self.executor)
        
        # Run blocking execute in executor
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(
                self.executor,
                lambda: handler.execute(operation, params)
            )
            result_dict = result.to_dict()
            return {
                "status": "completed" if result.ok else "failed",
                "result": result_dict,
            }
        except Exception as exc:
            logger.exception("GIS tool %s.%s failed: %s", cluster_id, operation, exc)
            return {
                "status": "failed",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "cluster_id": cluster_id,
                "operation": operation,
            }

    async def _agent_handler(self, config, context) -> dict:
        """Delegate task to agent via AgentManager."""
        if not self.agent_manager:
            raise WorkflowError("No agent manager available for agent node")
        agent_id = config.get("agent_id")
        if not agent_id:
            raise WorkflowError("agent_id is required for agent node")
        
        # Build task from config
        # Config can specify either a single tool call or multi-tool task
        tool = config.get("tool")
        tools = config.get("tools")
        params = config.get("params", {})
        
        if config.get("use_context", True):
            flat_outputs = self._flatten_outputs(context.get("outputs", {}))
            # Merge context into params for single tool, or into each tool's params for multi-tool
            if tool:
                params = {**flat_outputs, **params}
            elif tools:
                for tool_config in tools:
                    tool_config.setdefault("params", {})
                    tool_config["params"] = {**flat_outputs, **tool_config["params"]}
        
        # Build task dict for agent.execute()
        if tool:
            task = {
                "tool": tool,
                "params": params,
                "request_id": config.get("request_id", f"wf_{agent_id}_{uuid.uuid4().hex[:8]}"),
                "timeout_seconds": config.get("timeout_seconds"),
            }
        elif tools:
            task = {
                "tools": tools,
                "continue_on_error": config.get("continue_on_error", False),
            }
        else:
            # Fallback: pass params as-is (for custom agents that handle arbitrary tasks)
            task = params
        
        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            raise WorkflowError(f"Agent {agent_id} not found")
        
        try:
            # Use async execute method directly
            result = await agent.execute(task)
            # Ensure consistent response format
            if isinstance(result, dict) and "status" in result:
                return result
            return {"status": "completed", "result": result}
        except Exception as exc:
            logger.exception("Agent %s execution failed: %s", agent_id, exc)
            return {
                "status": "failed",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "agent_id": agent_id,
            }

    async def _mcp_tool_handler(self, config, context) -> dict:
        """Execute MCP tool via AsyncQgisBridgeClient or sync QgisBridgeClient."""
        if not self.mcp_client:
            raise WorkflowError("No MCP client available for mcp_tool node")
        tool = config.get("tool")
        if not tool:
            raise WorkflowError("tool is required for mcp_tool node")
        params = config.get("params", {})
        if config.get("use_context", True):
            params = {**self._flatten_outputs(context.get("outputs", {})), **params}
        request_id = config.get("request_id", f"wf_{uuid.uuid4().hex[:8]}")
        timeout_seconds = config.get("timeout_seconds")
        
        # Handle both async and sync MCP clients
        dispatch_method = getattr(self.mcp_client, "dispatch", None)
        if not dispatch_method:
            raise WorkflowError("MCP client does not have a dispatch method")
        
        try:
            if asyncio.iscoroutinefunction(dispatch_method):
                # Async client (AsyncQgisBridgeClient)
                result = await dispatch_method(
                    tool=tool, params=params, request_id=request_id, timeout_seconds=timeout_seconds
                )
            else:
                # Sync client (QgisBridgeClient) - run in executor
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    self.executor,
                    lambda: dispatch_method(
                        tool=tool, params=params, request_id=request_id, timeout_seconds=timeout_seconds
                    )
                )
            return {"status": "completed", "result": result}
        except Exception as exc:
            logger.exception("MCP tool %s failed: %s", tool, exc)
            return {
                "status": "failed",
                "error": str(exc),
                "error_type": type(exc).__name__,
                "tool": tool,
            }

    async def _api_handler_async(self, config, context) -> dict:
        """Async implementation of API handler."""
        provider = config.get("provider")
        if not provider:
            return {"status": "failed", "error": "provider is required for api node", "error_type": "WorkflowError"}
        
        row = self.db.fetchone(
            "SELECT * FROM api_providers WHERE id = ? AND enabled = 1", (provider,))
        if not row:
            return {"status": "failed", "error": f"API provider {provider} not found or not enabled", "error_type": "WorkflowError"}
        
        provider_config = dict(row)
        model = config.get("model") or provider_config.get("model_id")
        if not model:
            return {"status": "failed", "error": "model is required for api node", "error_type": "WorkflowError"}
        
        prompt = config.get("prompt")
        if not prompt:
            return {"status": "failed", "error": "prompt is required for api node", "error_type": "WorkflowError"}
        
        if config.get("use_context", True):
            import string
            template = string.Template(prompt)
            flat_outputs = self._flatten_outputs(context.get("outputs", {}))
            prompt = template.safe_substitute(flat_outputs)
        
        base_url = provider_config.get("base_url")
        api_key = self._get_api_key(provider)
        
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        timeout = provider_config.get("timeout_seconds", 60)
        max_retries = provider_config.get("retry_count", 3)
        
        payload = self._build_api_payload(provider, model, prompt, config)
        
        client = self.api_client or httpx.AsyncClient(timeout=timeout)
        should_close = self.api_client is None
        
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                response = await client.post(
                    f"{base_url.rstrip('/')}/chat/completions" if base_url else self._get_default_endpoint(provider),
                    headers=headers, json=payload, timeout=timeout,
                )
                response.raise_for_status()
                result = response.json()
                parsed = self._parse_api_response(provider, result)
                return {"status": "completed", "result": parsed}
            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exception = exc
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            except httpx.HTTPStatusError as exc:
                last_exception = exc
                if exc.response.status_code >= 500 or exc.response.status_code == 429:
                    if attempt < max_retries:
                        await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
                # Don't retry 4xx errors (except 429)
                error_msg = f"API error: {exc.response.status_code} - {exc.response.text}"
                logger.error("API call failed: %s", error_msg)
                if should_close:
                    await client.aclose()
                return {"status": "failed", "error": error_msg, "error_type": "HTTPStatusError", "status_code": exc.response.status_code}
            except Exception as exc:
                last_exception = exc
                logger.exception("API call unexpected error")
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                continue
        
        if should_close:
            await client.aclose()
        error_msg = f"API call failed after {max_retries + 1} attempts: {last_exception}"
        logger.error(error_msg)
        return {"status": "failed", "error": error_msg, "error_type": type(last_exception).__name__ if last_exception else "UnknownError"}

    def _api_handler(self, config, context):
        """Sync wrapper for async API handler."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self._api_handler_async(config, context))

    # ---- Condition/Loop handlers ----
    def _condition_handler(self, config, context):
        """Evaluate condition expression against context.
        
        Supports two modes:
        1. Python comparison (e.g., "count > 5", "name == 'test'") - evaluated via Python
        2. JMESPath expression (e.g., "count", "step1.result.success") - truthy check
        
        For Python comparisons, the expression should reference variables available
        in the flattened context (input + outputs).
        """
        expression = config.get("expression")
        if not expression:
            return {"proceed": True}
        
        # Build evaluation context
        flat = self._flatten_outputs(context.get("outputs", {}))
        flat.update(context.get("input", {}))
        
        try:
            # Check if expression contains comparison/logical operators - evaluate as Python
            if any(op in expression for op in ['==', '!=', '>', '<', '>=', '<=', ' in ', ' not in ', ' and ', ' or ', ' not ']):
                # Evaluate as Python expression using the flattened context as variables
                # Use simpleeval for safe evaluation (no eval() RCE)
                evaluator = EvalWithCompoundTypes()
                proceed = bool(evaluator.eval(expression, flat))
                return {"proceed": proceed, "evaluation": proceed}
            
            # Otherwise try JMESPath for path expressions
            result = jmespath.search(expression, flat)
            
            # If JMESPath returns a boolean, use it directly
            if isinstance(result, bool):
                proceed = result
            else:
                # Truthy check
                proceed = bool(result)
            
            return {"proceed": proceed, "evaluation": result}
        except Exception as exc:
            logger.warning("Condition evaluation failed: %s", exc)
            return {"proceed": False, "error": str(exc)}

    def _loop_handler(self, config, context):
        """Execute loop body for each item or fixed iterations."""
        max_iterations = config.get("max_iterations", 1)
        loop_body = config.get("body", [])  # List of step configs
        iterator = config.get("iterator")  # JMESPath to array
        iterator_var = config.get("iterator_var", "item")
        
        if iterator:
            # Iterate over array from context
            items = jmespath.search(iterator, self._flatten_outputs(context.get("outputs", {})))
            if not isinstance(items, list):
                items = [items]
        else:
            # Fixed iterations
            items = list(range(max_iterations))
        
        results = []
        for i, item in enumerate(items[:max_iterations]):
            iteration_context = {**context, "outputs": {**context.get("outputs", {}), iterator_var: item}}
            iteration_context["outputs"][f"loop_index"] = i
            
            # Execute loop body steps sequentially (could be parallelized in future)
            for body_step in loop_body:
                step_type = body_step.get("type", "gis_tool")
                step_config = body_step.get("config", {})
                handler = self._node_handler(step_type)
                out = handler(step_config, iteration_context)
                iteration_context["outputs"][body_step.get("id", step_type)] = out
            
            results.append(iteration_context["outputs"])
        
        return {"status": "loop_done", "iterations": len(results), "results": results}

    # ---- Input/Output handlers ----
    def _input_handler(self, config, context):
        return {"input": context.get("input")}

    def _output_handler(self, config, context):
        output_map = config.get("map", {})
        if output_map:
            mapped = {}
            for key, path in output_map.items():
                mapped[key] = jmespath.search(path, self._flatten_outputs(context.get("outputs", {})))
            return {"output": mapped}
        return {"output": context.get("outputs")}

    # ---- Approval handler ----
    def _approval_handler(self, config, context):
        if not self.approval_manager:
            raise WorkflowError("No approval manager available for approval node")
        
        action_type = config.get("action_type", "workflow_step")
        target = config.get("target", "workflow_execution")
        requested_by = config.get("requested_by", "system")
        
        approval_id = self.approval_manager.request(action_type, target, requested_by)
        
        # Store approval details in context for resume
        return {
            "status": "approval_required",
            "approval_id": approval_id,
            "action": config.get("action"),
            "message": config.get("message", "Approval required to continue"),
        }

    # ---- Validation handler ----
    def _validation_handler(self, config, context):
        """Validate outputs against JMESPath expressions."""
        validations = config.get("validations", [])
        all_passed = True
        results = {}
        
        eval_context = self._flatten_outputs(context.get("outputs", {}))
        eval_context["input"] = context.get("input", {})
        
        for validation in validations:
            name = validation.get("name", "validation")
            expression = validation.get("expression")
            expected = validation.get("expected")
            message = validation.get("message", "")
            
            if not expression:
                results[name] = {"passed": False, "error": "No expression provided"}
                all_passed = False
                continue
            
            try:
                actual = jmespath.search(expression, eval_context)
                passed = True
                if expected is not None:
                    passed = (actual == expected)
                results[name] = {"passed": passed, "actual": actual, "expected": expected}
                if not passed:
                    all_passed = False
            except Exception as exc:
                results[name] = {"passed": False, "error": str(exc)}
                all_passed = False
        
        return {"status": "validated", "passed": all_passed, "results": results}

    # ---- Report handler ----
    def _report_handler(self, config, context):
        template = config.get("template", "")
        if template:
            import string
            tpl = string.Template(template)
            flat = self._flatten_outputs(context.get("outputs", {}))
            flat["input"] = context.get("input", {})
            rendered = tpl.safe_substitute(flat)
        else:
            rendered = json.dumps(context.get("outputs", {}), indent=2)
        return {"status": "report_generated", "content": rendered}

    # ------------------------------------------------------------------ #
    # Utility methods
    # ------------------------------------------------------------------ #
    def _flatten_outputs(self, outputs: dict) -> dict:
        """Flatten nested step outputs for template/JMESPath access."""
        flat = {}
        for step_id, output in outputs.items():
            if isinstance(output, dict):
                flat.update(output)
            else:
                flat[step_id] = output
        return flat

    def _get_api_key(self, provider: str) -> str | None:
        if hasattr(self, '_credential_store') and self._credential_store:
            try:
                return self._credential_store.get(f"uagis_api_{provider}")
            except Exception:
                pass
        row = self.db.fetchone(
            "SELECT credential_ref FROM api_profiles WHERE provider_id = ? AND is_default = 1",
            (provider,))
        if row:
            logger.warning("API key for %s not resolved from credential store", provider)
        return None

    def _get_default_endpoint(self, provider: str) -> str:
        endpoints = {
            "openai": "https://api.openai.com/v1/chat/completions",
            "gemini": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            "anthropic": "https://api.anthropic.com/v1/messages",
            "openrouter": "https://openrouter.ai/api/v1/chat/completions",
        }
        return endpoints.get(provider, "")

    def _build_api_payload(self, provider: str, model: str, prompt: str, config: dict) -> dict:
        temperature = config.get("temperature", 0.7)
        max_tokens = config.get("max_tokens", 2048)
        system_prompt = config.get("system_prompt")
        
        if provider in ("openai", "openrouter", "openai_compatible"):
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            return {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        elif provider == "anthropic":
            payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens, "temperature": temperature}
            if system_prompt:
                payload["system"] = system_prompt
            return payload
        elif provider == "gemini":
            return {"contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}}
        elif provider == "custom":
            custom_payload = config.get("custom_payload", {})
            custom_payload.setdefault("model", model)
            custom_payload.setdefault("prompt", prompt)
            return custom_payload
        else:
            return {"model": model, "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature, "max_tokens": max_tokens}

    def _parse_api_response(self, provider: str, response: dict) -> dict:
        if provider in ("openai", "openrouter", "openai_compatible", "custom"):
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"content": content, "raw": response}
        elif provider == "anthropic":
            content = response.get("content", [{}])[0].get("text", "")
            return {"content": content, "raw": response}
        elif provider == "gemini":
            content = response.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return {"content": content, "raw": response}
        else:
            return {"content": str(response), "raw": response}

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def status(self, job_id: str) -> dict:
        job = self.job_manager.get_job(job_id)
        state = self._load_state(job_id)
        if state:
            job["workflow_state"] = {
                "step_index": state.step_index,
                "completed_steps": state.completed_steps,
                "pending_steps": state.pending_steps,
                "status": state.status,
            }
        return job