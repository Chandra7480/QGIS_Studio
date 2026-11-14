"""Quality Control Agent — Geometry, topology, CRS, attribute validation."""

from agents.base_agent import SpecializedAgent


class QualityControlAgent(SpecializedAgent):
    """Agent for quality control: geometry validation, topology, CRS, attributes."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_quality_control",
            name="Quality Control Agent",
            description="Geometry, topology, CRS, attribute validation.",
            instructions=(
                "You validate GIS data: geometry validity, topology rules, CRS consistency, "
                "attribute completeness, duplicate detection, and data quality reports. "
                "Use qgis.algorithms.execute with validation algorithms."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="quality_control",
            tool_namespace="qgis.algorithms",
        )
        
        self.qc_algorithms = {
            "check_validity": "native:checkvalidity",
            "fix_geometries": "native:fixgeometries",
            "topology_check": "native:topologychecker",
            "duplicate_geoms": "native:deleteduplicategeometries",
            "duplicate_attrs": "native:removeduplicates",
            "crs_check": "native:reprojectlayer",
            "field_check": "native:fieldcalculator",
            "null_check": "native:fieldcalculator",
            "statistics": "native:basicstatisticsforfields",
            "uniqueness": "native:fieldcalculator",
        }

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "validate")
        params = task.get("params", {})

        self.add_to_history("user", f"Quality Control: {action}", {"action": action})

        if action == "validate":
            result = await self._validate(params)
        elif action == "geometry":
            result = await self._geometry_check(params)
        elif action == "topology":
            result = await self._topology_check(params)
        elif action == "attributes":
            result = await self._attribute_check(params)
        elif action == "crs":
            result = await self._crs_check(params)
        elif action == "report":
            result = await self._report(params)
        elif action == "list_operations":
            result = {"operations": list(self.qc_algorithms.keys())}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _validate(self, params: dict) -> dict:
        """Full validation suite."""
        layer = params.get("layer")
        if not layer:
            return {"error": "Missing layer"}
        
        results = {}
        # Geometry validity
        results["geometry"] = await self._run_algorithm("native:checkvalidity", {"INPUT": layer})
        # Statistics
        results["statistics"] = await self._run_algorithm("native:basicstatisticsforfields", {"INPUT": layer})
        # Duplicates
        results["duplicates"] = await self._run_algorithm("native:deleteduplicategeometries", {"INPUT": layer})
        
        return {"layer": layer, "checks": results}

    async def _geometry_check(self, params: dict) -> dict:
        """Check geometry validity."""
        layer = params.get("layer")
        if not layer:
            return {"error": "Missing layer"}
        return await self._run_algorithm("native:checkvalidity", {"INPUT": layer})

    async def _topology_check(self, params: dict) -> dict:
        """Topology validation."""
        layer = params.get("layer")
        rules = params.get("rules", [])  # List of topology rules
        if not layer:
            return {"error": "Missing layer"}
        return await self._run_algorithm("native:topologychecker", {"INPUT": layer, "RULES": rules})

    async def _attribute_check(self, params: dict) -> dict:
        """Attribute validation."""
        layer = params.get("layer")
        checks = params.get("checks", {})  # field -> check_type
        if not layer:
            return {"error": "Missing layer"}
        
        results = {}
        for field, check in checks.items():
            if check == "null":
                results[field] = await self._run_algorithm("native:fieldcalculator", {
                    "INPUT": layer, "FIELD_NAME": f"{field}_null", "FORMULA": f"\"{field}\" IS NULL",
                    "FIELD_TYPE": 1, "OUTPUT": "memory:"
                })
            elif check == "unique":
                results[field] = await self._run_algorithm("native:fieldcalculator", {
                    "INPUT": layer, "FIELD_NAME": f"{field}_dup", 
                    "FORMULA": f"count(\"{field}\", \"{field}\") > 1",
                    "FIELD_TYPE": 1, "OUTPUT": "memory:"
                })
        return {"layer": layer, "attribute_checks": results}

    async def _crs_check(self, params: dict) -> dict:
        """CRS consistency check."""
        layers = params.get("layers", [])
        if not layers:
            return {"error": "Missing layers"}
        
        crs_list = []
        for layer in layers:
            info = await self.call_tool("qgis.vector.info", {"layer_id": layer})
            crs = info.get("result", {}).get("crs")
            crs_list.append({"layer": layer, "crs": crs})
        
        unique_crs = set(c["crs"] for c in crs_list)
        return {
            "layers": crs_list,
            "consistent": len(unique_crs) == 1,
            "unique_crs": list(unique_crs),
        }

    async def _report(self, params: dict) -> dict:
        """Generate quality report."""
        layer = params.get("layer")
        if not layer:
            return {"error": "Missing layer"}
        
        validation = await self._validate({"layer": layer})
        return {
            "layer": layer,
            "report": validation,
            "summary": "Quality control report generated",
        }

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": params}
        )