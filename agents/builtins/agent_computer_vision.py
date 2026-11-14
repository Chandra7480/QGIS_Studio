"""Computer Vision Agent — Landmark detection and image registration."""

from agents.base_agent import SpecializedAgent


class ComputerVisionAgent(SpecializedAgent):
    """Agent for computer vision: landmark detection, image registration, feature matching."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_computer_vision",
            name="Computer Vision Agent",
            description="Landmark detection and image registration.",
            instructions=(
                "You apply computer vision: landmark detection, feature matching, "
                "image registration, object detection, and visual inspection. "
                "Use qgis.georeference.analyze, qgis.gcp.generate, and CV algorithms."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="computer_vision",
            tool_namespace="qgis.georeference",
        )

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "analyze")
        params = task.get("params", {})

        self.add_to_history("user", f"Computer Vision: {action}", {"action": action})

        if action == "analyze":
            result = await self._analyze(params)
        elif action == "landmarks":
            result = await self._landmarks(params)
        elif action == "register":
            result = await self._register(params)
        elif action == "match":
            result = await self._match(params)
        elif action == "detect":
            result = await self._detect(params)
        elif action == "list_operations":
            result = {"operations": ["analyze", "landmarks", "register", "match", "detect"]}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _analyze(self, params: dict) -> dict:
        """Analyze image for CV features."""
        image_path = params.get("image_path")
        if not image_path:
            return {"error": "Missing image_path"}
        return await self.call_tool("qgis.georeference.analyze", {"image_path": image_path})

    async def _landmarks(self, params: dict) -> dict:
        """Detect/generate landmarks."""
        image_path = params.get("image_path")
        reference = params.get("reference_source")
        if not image_path or not reference:
            return {"error": "Missing image_path or reference_source"}
        return await self.call_tool("qgis.gcp.generate", {"image_path": image_path, "reference_source": reference})

    async def _register(self, params: dict) -> dict:
        """Register image to reference."""
        image_path = params.get("image_path")
        gcps = params.get("gcps", [])
        if not image_path:
            return {"error": "Missing image_path"}
        return {
            "note": "Image registration uses GCPs. Apply transformation via gdal:georeference algorithm.",
            "image_path": image_path,
            "gcps": gcps,
        }

    async def _match(self, params: dict) -> dict:
        """Feature matching between images."""
        return {"note": "Feature matching requires OpenCV integration. Use qgis.gcp.generate for landmark-based matching."}

    async def _detect(self, params: dict) -> dict:
        """Object detection (requires ML model)."""
        return {"note": "Object detection requires trained ML models. Use agent_ai_ml for AI-based detection."}