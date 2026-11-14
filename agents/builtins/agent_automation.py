"""Automation Agent — Processing models and batch workflows."""

from agents.base_agent import SpecializedAgent


class AutomationAgent(SpecializedAgent):
    """Agent for automation: processing models, batch workflows, scripts."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_automation",
            name="Automation Agent",
            description="Processing models and batch workflows.",
            instructions=(
                "You automate GIS workflows: create processing models, run batch processes, "
                "execute Python scripts, schedule tasks, and build workflow chains. "
                "Use qgis.workflow.execute and qgis.algorithms.execute."
            ),
            permission_level="standard",
            max_steps=20,
            db=db,
            domain="automation",
            tool_namespace="qgis.workflow",
        )

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "run")
        params = task.get("params", {})

        self.add_to_history("user", f"Automation: {action}", {"action": action})

        if action == "run":
            result = await self._run_workflow(params)
        elif action == "batch":
            result = await self._batch_process(params)
        elif action == "model":
            result = await self._run_model(params)
        elif action == "script":
            result = await self._run_script(params)
        elif action == "chain":
            result = await self._chain(params)
        elif action == "list_operations":
            result = {"operations": ["run", "batch", "model", "script", "chain"]}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _run_workflow(self, params: dict) -> dict:
        """Execute saved workflow."""
        workflow_id = params.get("workflow_id")
        if not workflow_id:
            return {"error": "Missing workflow_id"}
        return await self.call_tool("qgis.workflow.execute", {"workflow_id": workflow_id})

    async def _batch_process(self, params: dict) -> dict:
        """Run batch processing."""
        algorithm = params.get("algorithm")
        param_table = params.get("param_table")  # List of parameter dicts
        if not algorithm or not param_table:
            return {"error": "Missing algorithm or param_table"}
        return {
            "note": "Batch processing runs algorithm multiple times with different parameters. "
                   "Use qgis.algorithms.execute in a loop or Processing batch interface.",
            "algorithm": algorithm,
            "iterations": len(param_table),
        }

    async def _run_model(self, params: dict) -> dict:
        """Run processing model."""
        model = params.get("model")
        if not model:
            return {"error": "Missing model"}
        return await self.call_tool("qgis.algorithms.execute", {"algorithm": model, "parameters": params.get("parameters", {})})

    async def _run_script(self, params: dict) -> dict:
        """Run Python script (requires bridge support)."""
        return {"note": "Python script execution requires bridge support for PyQGIS. Use QGIS Python console or external scripts."}

    async def _chain(self, params: dict) -> dict:
        """Chain multiple operations."""
        steps = params.get("steps", [])
        results = []
        for i, step in enumerate(steps):
            algo = step.get("algorithm")
            alg_params = step.get("parameters", {})
            if algo:
                result = await self.call_tool("qgis.algorithms.execute", {"algorithm": algo, "parameters": alg_params})
                results.append({"step": i, "algorithm": algo, "result": result})
        return {"chained_results": results}