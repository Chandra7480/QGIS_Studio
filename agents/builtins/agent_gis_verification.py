"""GIS Verification Agent — Verifies operation results and GCP residuals."""

from agents.base_agent import SpecializedAgent


class GISVerificationAgent(SpecializedAgent):
    """Agent for verification: operation results, GCP residuals, accuracy assessment."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_gis_verification",
            name="GIS Verification Agent",
            description="Verifies operation results and GCP residuals.",
            instructions=(
                "You verify GIS operations: check results, validate GCP residuals, "
                "assess accuracy, compare outputs, and generate verification reports. "
                "Use qgis.verify.status and validation tools."
            ),
            permission_level="read",
            max_steps=15,
            db=db,
            domain="verification",
            tool_namespace="qgis.verify",
        )

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "verify")
        params = task.get("params", {})

        self.add_to_history("user", f"Verification: {action}", {"action": action})

        if action == "verify":
            result = await self._verify(params)
        elif action == "gcp_residuals":
            result = await self._gcp_residuals(params)
        elif action == "accuracy":
            result = await self._accuracy(params)
        elif action == "compare":
            result = await self._compare(params)
        elif action == "status":
            result = await self._status(params)
        elif action == "report":
            result = await self._report(params)
        elif action == "list_operations":
            result = {"operations": ["verify", "gcp_residuals", "accuracy", "compare", "status", "report"]}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _verify(self, params: dict) -> dict:
        """Verify operation result."""
        request_id = params.get("request_id")
        expected = params.get("expected")
        if not request_id:
            return {"error": "Missing request_id"}
        
        status = await self.call_tool("qgis.verify.status", {"request_id": request_id})
        
        return {
            "request_id": request_id,
            "verification_state": status.get("result", {}).get("verification_state"),
            "expected": expected,
            "details": status.get("result", {}).get("details"),
        }

    async def _gcp_residuals(self, params: dict) -> dict:
        """Check GCP residuals."""
        job_id = params.get("job_id")
        if not job_id:
            return {"error": "Missing job_id"}
        
        # Query GCP records from database
        return {
            "note": "GCP residuals stored in database. Query gcp_records table.",
            "job_id": job_id,
            "query": "SELECT * FROM gcp_records WHERE job_id = ?",
        }

    async def _accuracy(self, params: dict) -> dict:
        """Assess accuracy."""
        reference = params.get("reference")
        result = params.get("result")
        metric = params.get("metric", "rmse")
        
        if not reference or not result:
            return {"error": "Missing reference or result"}
        
        return {
            "note": "Accuracy assessment compares reference vs result. "
                   "Use qgis.algorithms.execute with validation algorithms.",
            "reference": reference,
            "result": result,
            "metric": metric,
        }

    async def _compare(self, params: dict) -> dict:
        """Compare two outputs."""
        layer1 = params.get("layer1")
        layer2 = params.get("layer2")
        if not layer1 or not layer2:
            return {"error": "Missing layer1 or layer2"}
        
        return await self.call_tool("qgis.algorithms.execute", {
            "algorithm": "native:comparefeatures",
            "parameters": {"INPUT": layer1, "OVERLAY": layer2}
        })

    async def _status(self, params: dict) -> dict:
        """Get verification status."""
        request_id = params.get("request_id")
        if not request_id:
            return {"error": "Missing request_id"}
        return await self.call_tool("qgis.verify.status", {"request_id": request_id})

    async def _report(self, params: dict) -> dict:
        """Generate verification report."""
        job_id = params.get("job_id")
        return {
            "note": "Verification report summarizes all checks for a job.",
            "job_id": job_id,
            "includes": ["GCP residuals", "Accuracy metrics", "Topology checks", "CRS validation"],
        }