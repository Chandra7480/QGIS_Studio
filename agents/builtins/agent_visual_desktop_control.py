"""Visual Desktop Control Agent — Controls QGIS GUI via screen/cursor/mouse/keyboard."""

from agents.base_agent import SpecializedAgent


class VisualDesktopControlAgent(SpecializedAgent):
    """Agent for visual desktop control: screen capture, cursor, mouse, keyboard, window/dialog."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_visual_desktop_control",
            name="Visual Desktop Control Agent",
            description="Controls QGIS GUI via screen/cursor/mouse/keyboard.",
            instructions=(
                "You control QGIS visually: screen capture, cursor movement, clicking, "
                "keyboard input, mouse actions, window/dialog inspection. "
                "Use qgis.screen, qgis.cursor, qgis.keyboard, qgis.mouse, qgis.window, qgis.dialog tools."
            ),
            permission_level="elevated",
            max_steps=20,
            db=db,
            domain="visual_desktop",
            tool_namespace="qgis.screen",
        )

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "control")
        params = task.get("params", {})

        self.add_to_history("user", f"Visual Desktop: {action}", {"action": action})

        if action == "control":
            result = await self._control(params)
        elif action == "capture":
            result = await self._capture(params)
        elif action == "cursor":
            result = await self._cursor(params)
        elif action == "click":
            result = await self._click(params)
        elif action == "keyboard":
            result = await self._keyboard(params)
        elif action == "mouse":
            result = await self._mouse(params)
        elif action == "window":
            result = await self._window(params)
        elif action == "dialog":
            result = await self._dialog(params)
        elif action == "workflow":
            result = await self._visual_workflow(params)
        elif action == "list_operations":
            result = {"operations": ["control", "capture", "cursor", "click", "keyboard", "mouse", "window", "dialog", "workflow"]}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _control(self, params: dict) -> dict:
        """General visual control."""
        return {
            "note": "Visual desktop control requires step-by-step operations. "
                   "Use specific actions: capture, cursor, click, keyboard, mouse.",
            "available_tools": [
                "qgis.screen.capture",
                "qgis.cursor.move", "qgis.cursor.click", "qgis.cursor.drag",
                "qgis.keyboard.type", "qgis.keyboard.hotkey",
                "qgis.mouse.scroll",
                "qgis.window.inspect", "qgis.dialog.inspect",
            ],
        }

    async def _capture(self, params: dict) -> dict:
        """Capture screen."""
        return await self.call_tool("qgis.screen.capture", {})

    async def _cursor(self, params: dict) -> dict:
        """Move cursor."""
        x = params.get("x")
        y = params.get("y")
        if x is None or y is None:
            return {"error": "Missing x, y coordinates"}
        return await self.call_tool("qgis.cursor.move", {"x": x, "y": y})

    async def _click(self, params: dict) -> dict:
        """Click at current cursor position."""
        return await self.call_tool("qgis.cursor.click", {})

    async def _keyboard(self, params: dict) -> dict:
        """Keyboard input."""
        action = params.get("keyboard_action", "type")
        if action == "type":
            text = params.get("text")
            if not text:
                return {"error": "Missing text"}
            return await self.call_tool("qgis.keyboard.type", {"text": text})
        elif action == "hotkey":
            keys = params.get("keys")
            if not keys:
                return {"error": "Missing keys"}
            return await self.call_tool("qgis.keyboard.hotkey", {"keys": keys})
        return {"error": f"Unknown keyboard action: {action}"}

    async def _mouse(self, params: dict) -> dict:
        """Mouse scroll."""
        delta = params.get("delta", 1)
        return await self.call_tool("qgis.mouse.scroll", {"delta": delta})

    async def _window(self, params: dict) -> dict:
        """Inspect window."""
        return await self.call_tool("qgis.window.inspect", {})

    async def _dialog(self, params: dict) -> dict:
        """Inspect dialogs."""
        return await self.call_tool("qgis.dialog.inspect", {})

    async def _visual_workflow(self, params: dict) -> dict:
        """Execute a visual workflow (sequence of actions)."""
        steps = params.get("steps", [])
        results = []
        for step in steps:
            action = step.get("action")
            step_params = step.get("params", {})
            if action == "capture":
                results.append(await self._capture(step_params))
            elif action == "cursor":
                results.append(await self._cursor(step_params))
            elif action == "click":
                results.append(await self._click(step_params))
            elif action == "keyboard":
                results.append(await self._keyboard(step_params))
            elif action == "mouse":
                results.append(await self._mouse(step_params))
            elif action == "wait":
                import asyncio
                await asyncio.sleep(step_params.get("seconds", 1))
                results.append({"action": "wait", "seconds": step_params.get("seconds", 1)})
        return {"workflow_results": results}