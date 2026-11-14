"""Universal AI GIS Studio — Base Agent.

Provides common functionality for all agents including tool calling via MCP,
permission checking, and context persistence.
"""

import asyncio
import logging
import json
import uuid
import time
from typing import Optional, Any, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.logging import get_logger
from core.exceptions import UAGISPermissionError
from core.emergency_stop import is_emergency_stop_active, EmergencyStopActiveError
from mcp_server.qgis_client import AsyncQgisBridgeClient
from mcp_server.server import get_permission_manager

logger = get_logger("uagis.agents")


@dataclass
class AgentContext:
    """Persistent context for agent across calls."""
    agent_id: str
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    working_memory: Dict[str, Any] = field(default_factory=dict)
    last_tool_results: List[Dict[str, Any]] = field(default_factory=list)
    step_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BaseAgent:
    """Base class for all GIS agents."""
    
    def __init__(
        self,
        agent_id: str,
        name: str,
        description: str,
        instructions: str,
        permission_level: str = "standard",
        max_steps: int = 10,
        timeout_seconds: int = 300,
        ai_host_id: str | None = None,
        db=None,  # Database for context persistence
    ):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self.instructions = instructions
        self.permission_level = permission_level
        self.max_steps = max_steps
        self.timeout_seconds = timeout_seconds
        self.ai_host_id = ai_host_id
        self.enabled = True
        self._db = db
        self._context: Optional[AgentContext] = None
        self._mcp_client: Optional[AsyncQgisBridgeClient] = None
        self._permission_manager = get_permission_manager()
        self._allowed_tools: List[str] = []

    def _load_context(self) -> AgentContext:
        """Load agent context from database."""
        if self._db and self._context is None:
            row = self._db.fetchone(
                "SELECT context_data FROM agent_contexts WHERE agent_id = ?",
                (self.agent_id,)
            )
            if row and row["context_data"]:
                try:
                    data = json.loads(row["context_data"])
                    self._context = AgentContext(
                        agent_id=self.agent_id,
                        conversation_history=data.get("conversation_history", []),
                        working_memory=data.get("working_memory", {}),
                        last_tool_results=data.get("last_tool_results", []),
                        step_count=data.get("step_count", 0),
                        created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
                        updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
                    )
                except (json.JSONDecodeError, KeyError):
                    pass
        if self._context is None:
            self._context = AgentContext(agent_id=self.agent_id)
        return self._context

    def _save_context(self) -> None:
        """Save agent context to database."""
        if self._db and self._context:
            self._context.updated_at = datetime.now(timezone.utc).isoformat()
            self._db.execute(
                "INSERT OR REPLACE INTO agent_contexts(agent_id, context_data, updated_at) "
                "VALUES(?, ?, ?)",
                (self.agent_id, json.dumps({
                    "conversation_history": self._context.conversation_history,
                    "working_memory": self._context.working_memory,
                    "last_tool_results": self._context.last_tool_results,
                    "step_count": self._context.step_count,
                    "created_at": self._context.created_at,
                    "updated_at": self._context.updated_at,
                }), self._context.updated_at)
            )

    def get_context(self) -> AgentContext:
        """Get current agent context (loads if needed)."""
        return self._load_context()

    def set_working_memory(self, key: str, value: Any) -> None:
        """Set a value in working memory."""
        ctx = self.get_context()
        ctx.working_memory[key] = value
        self._save_context()

    def get_working_memory(self, key: str, default: Any = None) -> Any:
        """Get a value from working memory."""
        ctx = self.get_context()
        return ctx.working_memory.get(key, default)

    def add_to_history(self, role: str, content: str, metadata: Dict = None) -> None:
        """Add an entry to conversation history."""
        ctx = self.get_context()
        ctx.conversation_history.append({
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._save_context()

    def get_history(self, limit: int = 50) -> List[Dict]:
        """Get recent conversation history."""
        ctx = self.get_context()
        return ctx.conversation_history[-limit:]

    async def _get_mcp_client(self) -> AsyncQgisBridgeClient:
        """Get or create MCP client."""
        if self._mcp_client is None:
            self._mcp_client = AsyncQgisBridgeClient()
        return self._mcp_client

    def can_use_tool(self, tool_permission: str) -> bool:
        """Check if agent has permission to use a tool."""
        levels = {"read": 1, "standard": 2, "elevated": 3}
        need = levels.get(tool_permission, 2)
        have = levels.get(self.permission_level, 2)
        return have >= need

    def check_tool_permissions(self, required_permissions: List[str]) -> List[str]:
        """Check multiple tool permissions, return list of missing ones."""
        missing = []
        for perm in required_permissions:
            if not self.can_use_tool(perm):
                missing.append(perm)
        return missing

    def set_allowed_tools(self, tool_ids: List[str]) -> None:
        """Set the list of tool IDs this agent is allowed to use."""
        self._allowed_tools = tool_ids

    def is_tool_allowed(self, tool_id: str) -> bool:
        """Check if a tool is in the agent's allowed tools list."""
        if not self._allowed_tools:
            return True  # No restriction if not set
        return tool_id in self._allowed_tools

    async def call_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        request_id: str | None = None,
        timeout_seconds: int | None = None,
    ) -> Dict[str, Any]:
        """
        Call an MCP tool via the QGIS Bridge.
        
        Args:
            tool_name: Name of the tool (e.g., "qgis.layers.load")
            params: Tool parameters
            request_id: Optional request ID for tracing
            timeout_seconds: Optional timeout override
            
        Returns:
            Tool result dict with status, result, verification_state, etc.
            
        Raises:
            UAGISPermissionError: If agent lacks required permissions
            EmergencyStopActiveError: If emergency stop is active
            Exception: If tool execution fails
        """
        # Check emergency stop before any tool execution
        if is_emergency_stop_active():
            raise EmergencyStopActiveError(f"Emergency stop active - agent {self.agent_id} cannot execute tools")

        # Check if tool is allowed for this agent
        if not self.is_tool_allowed(tool_name):
            raise UAGISPermissionError(
                f"Agent {self.agent_id} is not allowed to use tool {tool_name}",
                error_code="TOOL_NOT_ALLOWED",
                context={"agent_id": self.agent_id, "tool": tool_name},
            )

        # Get tool spec from registry to check permissions
        from mcp_server.registry import build_registry
        registry = build_registry()
        spec = registry.get(tool_name)
        
        if spec and spec.permissions:
            missing = self.check_tool_permissions(spec.permissions)
            if missing:
                raise UAGISPermissionError(
                    f"Missing required permissions for {tool_name}: {', '.join(missing)}",
                    error_code="PERMISSION_DENIED",
                    context={"required": spec.permissions, "missing": missing, "tool": tool_name},
                )

        # Execute tool via MCP client
        client = await self._get_mcp_client()
        request_id = request_id or f"req_{self.agent_id}_{uuid.uuid4().hex[:8]}"
        
        try:
            result = await client.dispatch(
                tool=tool_name,
                params=params,
                request_id=request_id,
                timeout_seconds=timeout_seconds or self.timeout_seconds,
            )
            
            # Store result in context
            ctx = self.get_context()
            ctx.last_tool_results.append({
                "tool": tool_name,
                "params": params,
                "result": result,
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            # Keep only last 20 results
            if len(ctx.last_tool_results) > 20:
                ctx.last_tool_results = ctx.last_tool_results[-20:]
            ctx.step_count += 1
            self._save_context()
            
            return result
            
        except Exception as exc:
            logger.exception("Tool call failed: %s", tool_name)
            # Store error in context
            ctx = self.get_context()
            ctx.last_tool_results.append({
                "tool": tool_name,
                "params": params,
                "error": str(exc),
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self._save_context()
            raise

    def execute_task(self, task: dict) -> dict:
        """
        Synchronous execute method for backward compatibility.
        
        Expected task format (same as async execute):
        {
            "tool": "qgis.layers.load",
            "params": {"path": "/data/roads.shp"},
            "request_id": "optional-request-id",
            "timeout_seconds": 300
        }
        
        Or for multi-tool tasks:
        {
            "tools": [
                {"tool": "qgis.system.inspect", "params": {}},
                {"tool": "qgis.layers.inspect", "params": {}}
            ]
        }
        
        Note: This runs the async execute() via asyncio.run().
        For async contexts, use await agent.execute(task) instead.
        """
        try:
            return asyncio.run(self.execute(task))
        except RuntimeError as exc:
            # Handle case where event loop is already running
            if "cannot be called from a running event loop" in str(exc):
                logger.warning("execute_task called from running event loop; use await agent.execute() instead")
                return {
                    "agent_id": self.agent_id,
                    "task": task,
                    "status": "failed",
                    "error": "Cannot call sync execute_task from async context; use await agent.execute()",
                    "error_type": "RuntimeError",
                }
            raise

    async def execute(self, task: dict) -> dict:
        """
        Async execute method that actually calls MCP tools via the bridge.
        
        Expected task format:
        {
            "tool": "qgis.layers.load",           # Tool name to call
            "params": {"path": "/data/roads.shp"}, # Tool parameters
            "request_id": "optional-request-id",   # Optional request ID
            "timeout_seconds": 300                 # Optional timeout override
        }
        
        Or for multi-tool tasks:
        {
            "tools": [
                {"tool": "qgis.system.inspect", "params": {}},
                {"tool": "qgis.layers.inspect", "params": {}}
            ]
        }
        """
        # Check emergency stop at the start of execution
        if is_emergency_stop_active():
            logger.warning("Agent %s execution blocked: emergency stop active", self.agent_id)
            return {
                "agent_id": self.agent_id,
                "task": task,
                "status": "failed",
                "error": "Emergency stop is active - execution blocked",
                "error_type": "EmergencyStopActiveError",
            }

        # Single tool execution
        if "tool" in task:
            tool_name = task["tool"]
            params = task.get("params", {})
            request_id = task.get("request_id")
            timeout_seconds = task.get("timeout_seconds")
            
            try:
                result = await self.call_tool(
                    tool_name=tool_name,
                    params=params,
                    request_id=request_id,
                    timeout_seconds=timeout_seconds,
                )
                return {
                    "agent_id": self.agent_id,
                    "task": task,
                    "status": "completed",
                    "result": result,
                }
            except Exception as exc:
                logger.exception("Tool execution failed: %s", tool_name)
                return {
                    "agent_id": self.agent_id,
                    "task": task,
                    "status": "failed",
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
        
        # Multi-tool execution (sequential)
        elif "tools" in task:
            tools = task["tools"]
            results = []
            
            for i, tool_task in enumerate(tools):
                tool_name = tool_task.get("tool")
                params = tool_task.get("params", {})
                request_id = tool_task.get("request_id", f"req_{self.agent_id}_multi_{i}")
                timeout_seconds = tool_task.get("timeout_seconds")
                
                try:
                    result = await self.call_tool(
                        tool_name=tool_name,
                        params=params,
                        request_id=request_id,
                        timeout_seconds=timeout_seconds,
                    )
                    results.append({
                        "tool": tool_name,
                        "status": "completed",
                        "result": result,
                    })
                except Exception as exc:
                    logger.exception("Multi-tool execution failed at step %d: %s", i, tool_name)
                    results.append({
                        "tool": tool_name,
                        "status": "failed",
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    })
                    # Stop on first failure unless continue_on_error is set
                    if not task.get("continue_on_error", False):
                        break
            
            all_completed = all(r["status"] == "completed" for r in results)
            return {
                "agent_id": self.agent_id,
                "task": task,
                "status": "completed" if all_completed else "partial_failure",
                "results": results,
            }
        
        # Delegate to specialized implementation (for custom agents)
        else:
            return self.execute_task(task)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "permission_level": self.permission_level,
            "max_steps": self.max_steps,
            "timeout_seconds": self.timeout_seconds,
            "enabled": self.enabled,
        }


class SpecializedAgent(BaseAgent):
    """Base class for specialized GIS agents with domain-specific tools."""
    
    def __init__(self, *args, domain: str = "", tool_namespace: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self.domain = domain
        self.tool_namespace = tool_namespace  # e.g., "qgis.vector", "qgis.raster"
    
    def get_domain_tools(self) -> List[str]:
        """Get list of tool names in this agent's domain namespace."""
        from mcp_server.registry import build_registry
        registry = build_registry()
        if self.tool_namespace:
            return [
                t.name for t in registry.all() 
                if t.namespace == self.tool_namespace or t.name.startswith(self.tool_namespace + ".")
            ]
        return []