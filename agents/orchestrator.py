"""Universal AI GIS Studio — Agent Orchestrator.

Supervisor-worker architecture: task planning, delegation, sequential and
safe parallel execution, context sharing, agent-to-agent communication,
progress monitoring, error recovery, cancellation, and final verification.
"""

import asyncio
import json
import logging
import uuid
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone

from core.job_manager import JobManager
from core.logging import get_logger
from core.exceptions import NotFoundError

logger = get_logger("agents.orchestrator")


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ChainStep:
    """A single step in an agent chain."""
    step: int
    agent: str
    task: dict
    depends_on: List[int] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: Optional[dict] = None
    error: Optional[str] = None
    job_id: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class ChainResult:
    """Result of a chain execution."""
    chain_id: str
    steps: List[ChainStep]
    completed: List[Dict] = field(default_factory=list)
    failed: List[Dict] = field(default_factory=list)
    status: str = "running"
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None


class AgentOrchestrator:
    def __init__(self, agent_manager, job_manager: JobManager):
        self.agent_manager = agent_manager
        self.job_manager = job_manager
        self._running_jobs: dict[str, str] = {}  # job_id -> agent_id
        self._active_chains: dict[str, ChainResult] = {}

    def delegate(self, agent_id: str, task: dict) -> str:
        """Synchronous delegate - runs async execute in event loop."""
        agent = self.agent_manager.get_agent(agent_id)
        if not agent or not agent.enabled:
            raise NotFoundError(f"Agent {agent_id} not found or disabled")
        job_id = self.job_manager.create_job(
            job_type="agent_task", input_payload=json.dumps(task),
            agent_id=agent_id)
        self.job_manager.start_job(job_id)
        self._running_jobs[job_id] = agent_id
        
        try:
            # Run async execute in event loop
            if hasattr(agent, 'execute') and asyncio.iscoroutinefunction(agent.execute):
                result = asyncio.run(agent.execute(task))
            else:
                result = agent.execute_task(task)
            
            self.job_manager.complete_job(
                job_id, json.dumps(result), "SUCCESS")
            return job_id
        except Exception as exc:
            logger.exception("Agent task failed: %s", exc)
            self.job_manager.fail_job(job_id, str(exc))
            # Note: job_id returned even on failure for tracking
            return job_id
        finally:
            self._running_jobs.pop(job_id, None)

    async def delegate_async(self, agent_id: str, task: dict) -> dict:
        """Async delegate - calls agent's async execute method."""
        agent = self.agent_manager.get_agent(agent_id)
        if not agent or not agent.enabled:
            raise NotFoundError(f"Agent {agent_id} not found or disabled")
        
        job_id = self.job_manager.create_job(
            job_type="agent_task", input_payload=json.dumps(task),
            agent_id=agent_id)
        self.job_manager.start_job(job_id)
        self._running_jobs[job_id] = agent_id
        
        try:
            # Call async execute method
            if hasattr(agent, 'execute') and asyncio.iscoroutinefunction(agent.execute):
                result = await agent.execute(task)
            else:
                result = agent.execute_task(task)
            
            self.job_manager.complete_job(
                job_id, json.dumps(result), "SUCCESS")
            return result
        except Exception as exc:
            logger.exception("Agent task failed: %s", exc)
            self.job_manager.fail_job(job_id, str(exc))
            result = {"agent_id": agent_id, "status": "failed", "error": str(exc)}
            return result
        finally:
            self._running_jobs.pop(job_id, None)

    def cancel_job(self, job_id: str) -> None:
        self.job_manager.cancel_job(job_id)
        self._running_jobs.pop(job_id, None)

    def status(self, job_id: str) -> dict:
        return self.job_manager.get_job(job_id)

    async def chain(
        self,
        plan: List[dict],
        max_parallel: int = 3,
        context: Optional[dict] = None,
        on_step_complete: Optional[Callable[[ChainStep], None]] = None,
    ) -> ChainResult:
        """
        Execute a chain of agent tasks with dependency resolution.
        
        Args:
            plan: List of step dicts with keys:
                - step: step number (int)
                - agent: agent_id (str)
                - task: task dict for the agent
                - depends_on: list of step numbers this step depends on
            max_parallel: Maximum parallel executions
            context: Shared context passed to all tasks
            on_step_complete: Callback when a step completes
            
        Returns:
            ChainResult with all step results
        """
        chain_id = f"chain_{uuid.uuid4().hex[:12]}"
        
        # Build step objects
        steps = []
        for step_def in plan:
            step = ChainStep(
                step=step_def["step"],
                agent=step_def["agent"],
                task=step_def.get("task", {}),
                depends_on=step_def.get("depends_on", []),
            )
            # Inject context into task
            if context:
                step.task["context"] = context
            steps.append(step)
        
        chain_result = ChainResult(chain_id=chain_id, steps=steps)
        self._active_chains[chain_id] = chain_result
        
        # Execute with dependency resolution
        await self._execute_chain(chain_result, max_parallel, on_step_complete)
        
        chain_result.completed_at = datetime.now(timezone.utc).isoformat()
        chain_result.status = "completed" if not chain_result.failed else "partial_failure"
        
        del self._active_chains[chain_id]
        return chain_result

    async def _execute_chain(
        self,
        chain_result: ChainResult,
        max_parallel: int,
        on_step_complete: Optional[Callable[[ChainStep], None]] = None,
    ) -> None:
        """Execute chain with topological sorting for dependencies."""
        steps_by_num = {s.step: s for s in chain_result.steps}
        completed_steps = set()
        running_tasks = {}
        
        while len(completed_steps) < len(chain_result.steps):
            # Find ready steps (dependencies met, not running, not completed)
            ready_steps = []
            for step in chain_result.steps:
                if step.step in completed_steps:
                    continue
                if step.step in running_tasks:
                    continue
                if step.status == StepStatus.RUNNING:
                    continue
                # Check dependencies
                deps_met = all(d in completed_steps for d in step.depends_on)
                if deps_met:
                    ready_steps.append(step)
            
            if not ready_steps and not running_tasks:
                # No ready steps and nothing running - check for circular deps
                remaining = [s for s in chain_result.steps if s.step not in completed_steps]
                if remaining:
                    logger.warning("Possible circular dependency in chain %s", chain_result.chain_id)
                    for s in remaining:
                        s.status = StepStatus.FAILED
                        s.error = "Circular dependency or unmet dependency"
                        chain_result.failed.append({
                            "step": s.step,
                            "agent": s.agent,
                            "error": s.error,
                        })
                break
            
            # Start ready steps up to max_parallel
            available_slots = max_parallel - len(running_tasks)
            for step in ready_steps[:available_slots]:
                step.status = StepStatus.RUNNING
                step.started_at = datetime.now(timezone.utc).isoformat()
                
                # Create async task
                task = asyncio.create_task(self._run_step(chain_result, step))
                running_tasks[step.step] = task
            
            # Wait for at least one to complete
            if running_tasks:
                done, pending = await asyncio.wait(
                    running_tasks.values(),
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                for task in done:
                    # Find which step this was
                    step_num = None
                    for num, t in running_tasks.items():
                        if t == task:
                            step_num = num
                            break
                    
                    if step_num is not None:
                        step = steps_by_num[step_num]
                        del running_tasks[step_num]
                        
                        try:
                            step.result = task.result()
                            step.status = StepStatus.COMPLETED
                            step.completed_at = datetime.now(timezone.utc).isoformat()
                            chain_result.completed.append({
                                "step": step.step,
                                "agent": step.agent,
                                "status": "completed",
                                "result": step.result,
                            })
                        except Exception as exc:
                            step.status = StepStatus.FAILED
                            step.error = str(exc)
                            step.completed_at = datetime.now(timezone.utc).isoformat()
                            chain_result.failed.append({
                                "step": step.step,
                                "agent": step.agent,
                                "error": step.error,
                            })
                            logger.exception("Step %d (%s) failed", step.step, step.agent)
                        
                        completed_steps.add(step_num)
                        
                        if on_step_complete:
                            on_step_complete(step)
        
        # Wait for any remaining
        if running_tasks:
            await asyncio.gather(*running_tasks.values(), return_exceptions=True)

    async def _run_step(self, chain_result: ChainResult, step: ChainStep) -> dict:
        """Run a single chain step."""
        agent = self.agent_manager.get_agent(step.agent)
        if not agent or not agent.enabled:
            raise NotFoundError(f"Agent {step.agent} not found or disabled")
        
        # Pass previous results as context
        if step.depends_on:
            dep_results = {}
            for dep_num in step.depends_on:
                dep_step = next((s for s in chain_result.steps if s.step == dep_num), None)
                if dep_step and dep_step.result:
                    dep_results[f"step_{dep_num}"] = dep_step.result
            step.task["dependency_results"] = dep_results
        
        # Execute agent
        if hasattr(agent, 'execute') and asyncio.iscoroutinefunction(agent.execute):
            return await agent.execute(step.task)
        else:
            return agent.execute_task(step.task)

    def get_chain_status(self, chain_id: str) -> Optional[ChainResult]:
        """Get status of an active or completed chain."""
        return self._active_chains.get(chain_id)

    def cancel_chain(self, chain_id: str) -> bool:
        """Cancel a running chain."""
        if chain_id in self._active_chains:
            chain = self._active_chains[chain_id]
            for step in chain.steps:
                if step.status == StepStatus.RUNNING and step.job_id:
                    self.cancel_job(step.job_id)
                if step.status == StepStatus.PENDING:
                    step.status = StepStatus.SKIPPED
            chain.status = "cancelled"
            chain.completed_at = datetime.now(timezone.utc).isoformat()
            return True
        return False

    async def pipeline(
        self,
        agents: List[str],
        initial_task: dict,
        context: Optional[dict] = None,
    ) -> List[dict]:
        """
        Simple sequential pipeline: output of each agent becomes input to next.
        
        Args:
            agents: List of agent_ids to run in sequence
            initial_task: Task for the first agent
            context: Shared context
            
        Returns:
            List of results from each agent
        """
        results = []
        current_task = initial_task.copy()
        
        for agent_id in agents:
            if context:
                current_task["context"] = context
            if results:
                current_task["previous_result"] = results[-1]
            
            result = await self.delegate_async(agent_id, current_task)
            results.append(result)
            
            if result.get("status") == "failed":
                logger.warning("Pipeline stopped at %s due to failure", agent_id)
                break
        
        return results

    async def execute_tool(
        self,
        agent_id: str,
        tool_name: str,
        params: dict,
        request_id: str | None = None,
        timeout_seconds: int | None = None,
    ) -> dict:
        """
        Execute a single tool via an agent (convenience method).
        
        This creates a temporary task with the tool specification and delegates
        to the agent for execution.
        
        Args:
            agent_id: Agent to use for execution
            tool_name: MCP tool name (e.g., "qgis.layers.load")
            params: Tool parameters
            request_id: Optional request ID
            timeout_seconds: Optional timeout override
            
        Returns:
            Tool execution result
        """
        task = {
            "tool": tool_name,
            "params": params,
            "request_id": request_id,
            "timeout_seconds": timeout_seconds,
        }
        return await self.delegate_async(agent_id, task)

    async def execute_tools_sequential(
        self,
        agent_id: str,
        tools: List[dict],
        continue_on_error: bool = False,
    ) -> dict:
        """
        Execute multiple tools sequentially via an agent.
        
        Args:
            agent_id: Agent to use for execution
            tools: List of tool tasks, each with "tool" and "params" keys
            continue_on_error: Whether to continue after a tool fails
            
        Returns:
            Aggregated result with all tool outputs
        """
        task = {
            "tools": tools,
            "continue_on_error": continue_on_error,
        }
        return await self.delegate_async(agent_id, task)
