"""Universal AI GIS Studio — GIS Supervisor Agent (top of supervisor-worker)."""

from agents.base_agent import BaseAgent


class AGISSupervisorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="agent_gis_supervisor",
            name="GIS Supervisor Agent",
            description="Plans and delegates GIS tasks to specialist workers.",
            instructions="You supervise GIS work. Break requests into steps and delegate.",
            permission_level="elevated",
            max_steps=20,
        )

    def execute_task(self, task: dict) -> dict:
        # Supervisor delegates; here we record the plan.
        steps = task.get("steps", [])
        return {
            "agent_id": self.agent_id,
            "status": "planned",
            "steps": steps,
            "note": "Supervisor created plan; workers execute via orchestrator",
        }
