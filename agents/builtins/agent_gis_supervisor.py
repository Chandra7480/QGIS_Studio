"""GIS Supervisor Agent — Plans and delegates GIS tasks to specialist workers."""

from agents.base_agent import BaseAgent
from agents.orchestrator import AgentOrchestrator


class AGISSupervisorAgent(BaseAgent):
    """Top-level supervisor that decomposes requests and delegates to workers."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_gis_supervisor",
            name="GIS Supervisor Agent",
            description="Plans and delegates GIS tasks to specialist workers.",
            instructions=(
                "You are the GIS Supervisor. Break down complex GIS requests into "
                "concrete steps and delegate them to appropriate specialist agents. "
                "Use the orchestrator to chain agents together. Always verify results "
                "before returning to the user."
            ),
            permission_level="elevated",
            max_steps=20,
            db=db,
        )
        self._orchestrator: AgentOrchestrator | None = None

    def set_orchestrator(self, orchestrator: AgentOrchestrator):
        """Set the orchestrator for delegation."""
        self._orchestrator = orchestrator

    async def execute(self, task: dict) -> dict:
        """
        Execute a supervisory task: plan, delegate, and verify.
        
        Task format:
        {
            "request": "User's natural language request",
            "context": {"project_path": "...", "layers": [...]},
            "preferred_agents": ["agent_id1", "agent_id2"],
            "max_parallel": 3
        }
        """
        request = task.get("request", "")
        context = task.get("context", {})
        preferred_agents = task.get("preferred_agents", [])
        max_parallel = task.get("max_parallel", 3)

        # Load context
        self.add_to_history("user", request, {"type": "supervisor_request"})

        # Step 1: Analyze request and create execution plan
        plan = await self._create_plan(request, context, preferred_agents)
        
        # Step 2: Execute plan via orchestrator
        if self._orchestrator:
            results = await self._orchestrator.chain(plan, max_parallel=max_parallel)
        else:
            results = {"error": "No orchestrator available", "plan": plan}

        # Step 3: Verify and summarize results
        summary = self._summarize_results(plan, results)
        
        self.add_to_history("assistant", summary, {"type": "supervisor_response"})
        
        return {
            "agent_id": self.agent_id,
            "status": "completed" if not results.get("error") else "failed",
            "plan": plan,
            "results": results,
            "summary": summary,
        }

    async def _create_plan(self, request: str, context: dict, preferred_agents: list) -> list:
        """Create an execution plan from the request."""
        # This is a simplified planner - in production, this would use an LLM
        plan = []
        request_lower = request.lower()
        
        # Simple keyword-based routing (replace with LLM-based planning)
        if any(kw in request_lower for kw in ["import", "load", "download", "acquire", "fetch"]):
            plan.append({
                "step": 1,
                "agent": "agent_data_acquisition",
                "task": {"action": "import_data", "request": request, "context": context},
                "depends_on": [],
            })
        
        if any(kw in request_lower for kw in ["georeferenc", "georeference", "scan", "map image"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_georeferencing",
                "task": {"action": "georeference", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["vector", "buffer", "clip", "dissolve", "intersect", "overlay"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_vector_processing",
                "task": {"action": "process_vector", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["raster", "calculate", "reclass", "mosaic", "ndvi", "index"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_raster_processing",
                "task": {"action": "process_raster", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["spatial", "join", "proximity", "interpolat", "kriging", "idw"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_spatial_analysis",
                "task": {"action": "spatial_analysis", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["terrain", "slope", "aspect", "hillshade", "contour", "dem"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_terrain",
                "task": {"action": "terrain_analysis", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["hydrolog", "watershed", "stream", "flow", "drainage"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_hydrology",
                "task": {"action": "hydrology_analysis", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["network", "route", "shortest path", "service area", "routing"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_network",
                "task": {"action": "network_analysis", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["remote sens", "satellite", "landsat", "sentinel", "band", "index"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_remote_sensing",
                "task": {"action": "remote_sensing", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["classif", "supervised", "unsupervised", "random forest", "svm"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_classification",
                "task": {"action": "classification", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["change", "temporal", "time series", "before after", "land cover change"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_change_detection",
                "task": {"action": "change_detection", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["3d", "three.d", "terrain model", "dem 3d", "visualization"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_3d_gis",
                "task": {"action": "3d_gis", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["lidar", "point cloud", "las", "laz"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_lidar",
                "task": {"action": "lidar_processing", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["survey", "gps", "gnss", "coordinate", "traverse"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_survey_gps",
                "task": {"action": "survey_gps", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["cadastral", "parcel", "boundary", "lot", "cadastre"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_cadastral",
                "task": {"action": "cadastral", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["cartograph", "map", "layout", "symbolog", "label", "export map"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_cartography",
                "task": {"action": "cartography", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["temporal", "time", "animation", "time series"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_temporal_gis",
                "task": {"action": "temporal_analysis", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["database", "postgis", "geopackage", "spatial sql", "query"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_database",
                "task": {"action": "database_ops", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["web gis", "wms", "wfs", "wmts", "xyz", "tile"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_web_gis",
                "task": {"action": "web_gis", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["automat", "model", "batch", "workflow", "process chain"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_automation",
                "task": {"action": "automation", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["quality", "validat", "topology", "geometry check", "crs check"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_quality_control",
                "task": {"action": "quality_control", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["report", "export", "pdf", "document", "atlas"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_reporting",
                "task": {"action": "reporting", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["visual", "desktop", "gui", "click", "screen", "cursor"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_visual_desktop_control",
                "task": {"action": "visual_control", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["computer vision", "landmark", "detect", "match", "registration"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_computer_vision",
                "task": {"action": "computer_vision", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })
        
        if any(kw in request_lower for kw in ["verify", "verify", "residual", "gcp", "accuracy", "validate"]):
            plan.append({
                "step": len(plan) + 1,
                "agent": "agent_gis_verification",
                "task": {"action": "verification", "request": request, "context": context},
                "depends_on": [s["step"] for s in plan] if plan else [],
            })

        # If no specific agents matched, default to research
        if not plan:
            plan.append({
                "step": 1,
                "agent": "agent_gis_research",
                "task": {"action": "research", "request": request, "context": context},
                "depends_on": [],
            })

        # Add preferred agents if specified
        for agent_id in preferred_agents:
            if not any(s["agent"] == agent_id for s in plan):
                plan.append({
                    "step": len(plan) + 1,
                    "agent": agent_id,
                    "task": {"action": "execute", "request": request, "context": context},
                    "depends_on": [s["step"] for s in plan] if plan else [],
                })

        return plan

    def _summarize_results(self, plan: list, results: dict) -> str:
        """Create a human-readable summary of execution results."""
        if "error" in results:
            return f"Execution failed: {results['error']}"
        
        completed = results.get("completed", [])
        failed = results.get("failed", [])
        
        lines = [f"Supervisor executed {len(plan)} step(s):"]
        for step_result in completed:
            lines.append(f"  ✓ Step {step_result['step']} ({step_result['agent']}): {step_result.get('status', 'completed')}")
        for step_result in failed:
            lines.append(f"  ✗ Step {step_result['step']} ({step_result['agent']}): {step_result.get('error', 'failed')}")
        
        return "\n".join(lines)