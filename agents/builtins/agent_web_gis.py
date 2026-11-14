"""Web GIS Agent — WMS, WFS, WMTS, XYZ tiles."""

from agents.base_agent import SpecializedAgent


class WebGISAgent(SpecializedAgent):
    """Agent for web GIS: WMS, WFS, WMTS, XYZ tiles, OGC services."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_web_gis",
            name="Web GIS Agent",
            description="WMS, WFS, WMTS, XYZ tiles.",
            instructions=(
                "You connect to web services: WMS, WFS, WMTS, WCS, XYZ tiles, "
                "OGC API Features, STAC, and cloud services. Use qgis.layers.load "
                "and qgis.web_gis tools."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="web_gis",
            tool_namespace="qgis.layers",
        )

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "connect")
        params = task.get("params", {})

        self.add_to_history("user", f"Web GIS: {action}", {"action": action})

        if action == "connect":
            result = await self._connect(params)
        elif action == "wms":
            result = await self._wms(params)
        elif action == "wfs":
            result = await self._wfs(params)
        elif action == "wmts":
            result = await self._wmts(params)
        elif action == "xyz":
            result = await self._xyz(params)
        elif action == "stac":
            result = await self._stac(params)
        elif action == "list_operations":
            result = {"operations": ["connect", "wms", "wfs", "wmts", "xyz", "stac"]}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _connect(self, params: dict) -> dict:
        """Connect to web service."""
        url = params.get("url")
        service_type = params.get("type", "wms")
        if not url:
            return {"error": "Missing URL"}
        return await self.call_tool("qgis.layers.load", {"path": url, "provider": service_type})

    async def _wms(self, params: dict) -> dict:
        """Add WMS layer."""
        url = params.get("url")
        layers = params.get("layers")
        if not url:
            return {"error": "Missing URL"}
        return await self.call_tool("qgis.layers.load", {"path": f"{url}?layers={layers}", "provider": "wms"})

    async def _wfs(self, params: dict) -> dict:
        """Add WFS layer."""
        url = params.get("url")
        typename = params.get("typename")
        if not url:
            return {"error": "Missing URL"}
        return await self.call_tool("qgis.layers.load", {"path": f"{url}?typename={typename}", "provider": "wfs"})

    async def _wmts(self, params: dict) -> dict:
        """Add WMTS layer."""
        url = params.get("url")
        layer = params.get("layer")
        if not url:
            return {"error": "Missing URL"}
        return await self.call_tool("qgis.layers.load", {"path": f"{url}?layer={layer}", "provider": "wmts"})

    async def _xyz(self, params: dict) -> dict:
        """Add XYZ tile layer."""
        url = params.get("url")
        if not url:
            return {"error": "Missing URL"}
        return await self.call_tool("qgis.layers.load", {"path": url, "provider": "xyz"})

    async def _stac(self, params: dict) -> dict:
        """Connect to STAC catalog."""
        url = params.get("url")
        if not url:
            return {"error": "Missing STAC catalog URL"}
        return {
            "note": "STAC support requires QGIS STAC plugin or external tools. "
                   "Use qgis.layers.load with STAC API endpoints.",
            "catalog_url": url,
        }