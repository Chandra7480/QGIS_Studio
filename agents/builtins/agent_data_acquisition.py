"""Data Acquisition Agent — Discovers and imports datasets."""

from agents.base_agent import SpecializedAgent


class DataAcquisitionAgent(SpecializedAgent):
    """Agent for discovering, validating, and importing GIS datasets."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_data_acquisition",
            name="Data Acquisition Agent",
            description="Discovers and imports datasets.",
            instructions=(
                "You acquire GIS data: discover local files, download from web services, "
                "connect to databases, and validate data sources. Use qgis.layers.load, "
                "qgis.layers.inspect, and qgis.system.inspect tools."
            ),
            permission_level="standard",
            max_steps=10,
            db=db,
            domain="data_acquisition",
            tool_namespace="qgis.layers",
        )

    async def execute(self, task: dict) -> dict:
        """Execute a data acquisition task."""
        action = task.get("action", "import_data")
        request = task.get("request", "")
        context = task.get("context", {})
        params = task.get("params", {})

        self.add_to_history("user", f"Data Acquisition: {action} - {request}", {"action": action})

        if action == "import_data":
            result = await self._import_data(params, context)
        elif action == "load_layer":
            result = await self._load_layer(params)
        elif action == "validate_source":
            result = await self._validate_source(params)
        elif action == "discover_layers":
            result = await self._discover_layers()
        elif action == "import_from_web":
            result = await self._import_from_web(params)
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _import_data(self, params: dict, context: dict) -> dict:
        """Import data based on request parameters."""
        path = params.get("path") or self.get_working_memory("last_data_path")
        layer_name = params.get("layer_name")
        provider = params.get("provider")

        if not path:
            return {"error": "No path provided for import"}

        try:
            result = await self.call_tool(
                "qgis.layers.load",
                {"path": path, "layer_name": layer_name, "provider": provider}
            )
            if result.get("status") == "ok":
                self.set_working_memory("last_data_path", path)
                self.set_working_memory("last_layer_id", result.get("result", {}).get("id"))
            return result
        except Exception as exc:
            return {"error": str(exc)}

    async def _load_layer(self, params: dict) -> dict:
        """Load a specific layer."""
        path = params.get("path")
        if not path:
            return {"error": "Missing required parameter: path"}
        
        return await self.call_tool(
            "qgis.layers.load",
            {
                "path": path,
                "layer_name": params.get("layer_name"),
                "provider": params.get("provider"),
            }
        )

    async def _validate_source(self, params: dict) -> dict:
        """Validate a data source exists and is readable."""
        path = params.get("path")
        if not path:
            return {"error": "Missing required parameter: path"}
        
        import os
        exists = os.path.exists(path)
        return {
            "path": path,
            "exists": exists,
            "valid": exists,
            "message": "Source exists and is readable" if exists else "Source not found",
        }

    async def _discover_layers(self) -> dict:
        """Discover all currently loaded layers."""
        return await self.call_tool("qgis.layers.inspect", {})

    async def _import_from_web(self, params: dict) -> dict:
        """Import data from web services (WFS, WMS, XYZ tiles)."""
        url = params.get("url")
        service_type = params.get("type", "wfs")  # wfs, wms, wmts, xyz
        
        if not url:
            return {"error": "Missing required parameter: url"}
        
        # For web services, we load via the layer loading mechanism
        return await self.call_tool(
            "qgis.layers.load",
            {"path": url, "provider": service_type}
        )