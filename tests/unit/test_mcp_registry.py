"""Unit tests for Universal MCP Server registry + tool registration."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.registry import build_registry, ToolSpec


def test_registry_has_all_namespaces():
    r = build_registry()
    expected = {
        "qgis.system", "qgis.project", "qgis.layers", "qgis.canvas",
        "qgis.screen", "qgis.cursor", "qgis.keyboard", "qgis.mouse",
        "qgis.window", "qgis.dialog", "qgis.algorithms", "qgis.plugins",
        "qgis.georeference", "qgis.gcp", "qgis.raster", "qgis.vector",
        "qgis.spatial", "qgis.database", "qgis.layout", "qgis.workflow",
        "qgis.agents", "qgis.skills", "qgis.verify", "qgis.jobs", "qgis.history",
    }
    found = set(r.namespaces())
    missing = expected - found
    assert not missing, f"Missing namespaces: {missing}"


def test_key_tools_registered():
    r = build_registry()
    for name in [
        "qgis.system.inspect", "qgis.system.health",
        "qgis.project.open", "qgis.project.save", "qgis.project.inspect",
        "qgis.layers.inspect", "qgis.layers.load", "qgis.layers.remove",
        "qgis.canvas.inspect",
        "qgis.screen.capture",
        "qgis.cursor.move", "qgis.cursor.click", "qgis.cursor.drag",
        "qgis.keyboard.type", "qgis.keyboard.hotkey",
        "qgis.mouse.scroll",
        "qgis.window.inspect", "qgis.dialog.inspect",
        "qgis.algorithms.discover", "qgis.algorithms.execute",
        "qgis.georeference.analyze",
        "qgis.gcp.generate", "qgis.gcp.validate",
        "qgis.workflow.execute",
        "qgis.jobs.cancel",
        "qgis.history.inspect",
    ]:
        spec = r.get(name)
        assert spec is not None, f"Missing tool: {name}"
        assert spec.description, f"No description for {name}"
        assert spec.input_schema, f"No input schema for {name}"
        assert spec.output_schema, f"No output schema for {name}"
        assert spec.timeout_seconds > 0


def test_tool_schemas_strict():
    r = build_registry()
    spec = r.get("qgis.layers.load")
    assert spec.input_schema["required"] == ["path"]
    assert spec.input_schema["additionalProperties"] is False
    assert "path" in spec.input_schema["properties"]


def test_tool_permissions_present():
    r = build_registry()
    for spec in r.all():
        assert isinstance(spec.permissions, list)


def test_mcp_server_instantiates_and_lists_tools():
    from mcp_server.server import UniversalMCPServer
    s = UniversalMCPServer(bridge_url="http://127.0.0.1:9999")
    specs = s.registry.all()
    assert len(specs) > 20
    names = {sp.name for sp in specs}
    assert "qgis.system.inspect" in names
    assert "qgis.layers.load" in names
    # Every tool has inputSchema and outputSchema
    for sp in specs:
        assert sp.input_schema is not None
        assert sp.output_schema is not None
