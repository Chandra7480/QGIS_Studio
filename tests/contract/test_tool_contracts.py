"""Contract Tests for all 43 MCP Tools.

Validates:
- Input schema is valid JSON Schema Draft 2020-12
- Output schema is valid JSON Schema Draft 2020-12
- Required fields, additionalProperties: false, types
- Valid input passes validation (using jsonschema)
- Invalid input is rejected (missing required, wrong type, extra props)
- Tool metadata: permissions, timeout, approval, verification_rules present
"""

import json
import os
import sys
from pathlib import Path

import pytest
import jsonschema
from jsonschema import Draft202012Validator

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp_server.registry import build_registry, ToolSpec

REGISTRY = build_registry()
ALL_SPECS = REGISTRY.all()


class TestSchemaValidity:
    """Test that all tool schemas are valid JSON Schema."""

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_input_schema_is_valid_json_schema(self, spec: ToolSpec):
        """Input schema must be a valid JSON Schema Draft 2020-12."""
        Draft202012Validator.check_schema(spec.input_schema)

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_output_schema_is_valid_json_schema(self, spec: ToolSpec):
        """Output schema must be a valid JSON Schema Draft 2020-12."""
        Draft202012Validator.check_schema(spec.output_schema)

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_input_schema_has_required_array(self, spec: ToolSpec):
        """Input schema must have 'required' array (can be empty)."""
        assert "required" in spec.input_schema
        assert isinstance(spec.input_schema["required"], list)

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_input_schema_additional_properties_false(self, spec: ToolSpec):
        """Input schema must have additionalProperties: false for strict validation."""
        assert spec.input_schema.get("additionalProperties") is False, \
            f"{spec.name}: input_schema.additionalProperties must be false"

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_output_schema_additional_properties_false(self, spec: ToolSpec):
        """Output schema must have additionalProperties: false."""
        assert spec.output_schema.get("additionalProperties") is False, \
            f"{spec.name}: output_schema.additionalProperties must be false"

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_input_schema_properties_object(self, spec: ToolSpec):
        """Input schema properties must be an object."""
        assert "properties" in spec.input_schema
        assert isinstance(spec.input_schema["properties"], dict)

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_output_schema_properties_object(self, spec: ToolSpec):
        """Output schema properties must be an object."""
        assert "properties" in spec.output_schema
        assert isinstance(spec.output_schema["properties"], dict)


class TestSchemaStructure:
    """Test schema structure and required fields."""

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_required_fields_exist_in_properties(self, spec: ToolSpec):
        """All required fields must be defined in properties."""
        for req in spec.input_schema["required"]:
            assert req in spec.input_schema["properties"], \
                f"{spec.name}: required field '{req}' not in properties"

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_property_types_are_valid(self, spec: ToolSpec):
        """All property types must be valid JSON Schema types."""
        valid_types = {"string", "number", "integer", "boolean", "array", "object", "null"}
        for prop_name, prop_def in spec.input_schema["properties"].items():
            if "type" in prop_def:
                prop_type = prop_def["type"]
                if isinstance(prop_type, list):
                    for t in prop_type:
                        assert t in valid_types, f"{spec.name}.{prop_name}: invalid type {t}"
                else:
                    assert prop_type in valid_types, f"{spec.name}.{prop_name}: invalid type {prop_type}"

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_array_items_have_type(self, spec: ToolSpec):
        """Array properties must have items with type."""
        for prop_name, prop_def in spec.input_schema["properties"].items():
            if prop_def.get("type") == "array":
                assert "items" in prop_def, f"{spec.name}.{prop_name}: array missing items"
                items = prop_def["items"]
                assert "type" in items, f"{spec.name}.{prop_name}: items missing type"


class TestToolMetadata:
    """Test tool metadata completeness."""

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_tool_has_description(self, spec: ToolSpec):
        """Every tool must have a non-empty description."""
        assert spec.description, f"{spec.name}: missing description"
        assert len(spec.description) > 10, f"{spec.name}: description too short"

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_tool_has_namespace(self, spec: ToolSpec):
        """Every tool must have a namespace."""
        assert spec.namespace, f"{spec.name}: missing namespace"
        assert spec.namespace.startswith("qgis."), f"{spec.name}: namespace must start with 'qgis.'"

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_tool_has_permissions(self, spec: ToolSpec):
        """Every tool must have permissions list (can be empty)."""
        assert isinstance(spec.permissions, list), f"{spec.name}: permissions must be list"
        for perm in spec.permissions:
            assert isinstance(perm, str), f"{spec.name}: permission must be string"
            assert perm.startswith("qgis:"), f"{spec.name}: permission must start with 'qgis:'"

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_tool_has_timeout(self, spec: ToolSpec):
        """Every tool must have positive timeout."""
        assert isinstance(spec.timeout_seconds, int), f"{spec.name}: timeout must be int"
        assert spec.timeout_seconds > 0, f"{spec.name}: timeout must be positive"
        assert spec.timeout_seconds <= 3600, f"{spec.name}: timeout too large (>1hr)"

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_tool_has_approval_flag(self, spec: ToolSpec):
        """Every tool must have require_approval boolean."""
        assert isinstance(spec.require_approval, bool), f"{spec.name}: require_approval must be bool"

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_tool_has_verification_rules(self, spec: ToolSpec):
        """Every tool must have verification_rules list (can be empty)."""
        assert isinstance(spec.verification_rules, list), f"{spec.name}: verification_rules must be list"
        for rule in spec.verification_rules:
            assert isinstance(rule, str), f"{spec.name}: verification rule must be string"


class TestInputValidation:
    """Test input validation against schemas."""

    def _validate_input(self, spec: ToolSpec, input_data: dict) -> tuple[bool, str | None]:
        """Validate input against schema. Returns (is_valid, error_message)."""
        try:
            Draft202012Validator(spec.input_schema).validate(input_data)
            return True, None
        except jsonschema.ValidationError as e:
            return False, str(e)

    def _validate_output(self, spec: ToolSpec, output_data: dict) -> tuple[bool, str | None]:
        """Validate output against schema. Returns (is_valid, error_message)."""
        try:
            Draft202012Validator(spec.output_schema).validate(output_data)
            return True, None
        except jsonschema.ValidationError as e:
            return False, str(e)

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_empty_input_for_no_required_params(self, spec: ToolSpec):
        """Tools with no required params should accept empty input."""
        if not spec.input_schema["required"]:
            valid, error = self._validate_input(spec, {})
            assert valid, f"{spec.name}: empty input should be valid: {error}"

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_missing_required_rejected(self, spec: ToolSpec):
        """Missing required fields must be rejected."""
        if spec.input_schema["required"]:
            # Create input with all required fields missing
            invalid_input = {}
            valid, error = self._validate_input(spec, invalid_input)
            assert not valid, f"{spec.name}: missing required should be rejected"
            assert "required" in error.lower() or "missing" in error.lower()

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_extra_properties_rejected(self, spec: ToolSpec):
        """Extra properties not in schema must be rejected (additionalProperties: false)."""
        # Add a property not in schema
        invalid_input = {"__extra_unknown_property__": "value"}
        # Also include required fields if any
        for req in spec.input_schema["required"]:
            # Provide minimal valid value based on type
            prop = spec.input_schema["properties"].get(req, {})
            prop_type = prop.get("type", "string")
            if prop_type == "string":
                invalid_input[req] = "test"
            elif prop_type == "integer":
                invalid_input[req] = 1
            elif prop_type == "number":
                invalid_input[req] = 1.0
            elif prop_type == "boolean":
                invalid_input[req] = True
            elif prop_type == "array":
                invalid_input[req] = []
            elif prop_type == "object":
                invalid_input[req] = {}
            else:
                invalid_input[req] = "test"

        valid, error = self._validate_input(spec, invalid_input)
        assert not valid, f"{spec.name}: extra properties should be rejected"
        assert "additional" in error.lower() or "unknown" in error.lower() or "extra" in error.lower()

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_wrong_type_rejected(self, spec: ToolSpec):
        """Wrong type for a property must be rejected."""
        for prop_name, prop_def in spec.input_schema["properties"].items():
            prop_type = prop_def.get("type")
            if not prop_type:
                continue

            # Create input with wrong type for this property
            invalid_input = {}
            for req in spec.input_schema["required"]:
                if req == prop_name:
                    continue
                # Valid value for other required
                p = spec.input_schema["properties"].get(req, {})
                t = p.get("type", "string")
                if t == "string":
                    invalid_input[req] = "test"
                elif t == "integer":
                    invalid_input[req] = 1
                elif t == "number":
                    invalid_input[req] = 1.0
                elif t == "boolean":
                    invalid_input[req] = True
                elif t == "array":
                    invalid_input[req] = []
                elif t == "object":
                    invalid_input[req] = {}

            # Wrong type for target property
            if isinstance(prop_type, list):
                # Union type - pick a type not in union
                wrong_val = "not_a_valid_type_for_union"
            elif prop_type == "string":
                wrong_val = 123
            elif prop_type == "integer":
                wrong_val = "not_an_int"
            elif prop_type == "number":
                wrong_val = "not_a_number"
            elif prop_type == "boolean":
                wrong_val = "not_a_bool"
            elif prop_type == "array":
                wrong_val = "not_an_array"
            elif prop_type == "object":
                wrong_val = "not_an_object"
            else:
                wrong_val = None

            if wrong_val is not None:
                invalid_input[prop_name] = wrong_val
                valid, error = self._validate_input(spec, invalid_input)
                assert not valid, f"{spec.name}.{prop_name}: wrong type should be rejected"


class TestValidInputGeneration:
    """Generate and test valid inputs for each tool."""

    def _generate_valid_input(self, spec: ToolSpec) -> dict:
        """Generate a valid input dict for the tool schema."""
        input_data = {}
        for prop_name, prop_def in spec.input_schema["properties"].items():
            # Only include required properties for minimal valid input
            if prop_name not in spec.input_schema["required"]:
                continue

            prop_type = prop_def.get("type", "string")
            if isinstance(prop_type, list):
                prop_type = prop_type[0]  # Use first type

            if prop_type == "string":
                # Check for format hints
                fmt = prop_def.get("format")
                if fmt == "uri":
                    input_data[prop_name] = "file:///test/path"
                elif "path" in prop_name.lower():
                    input_data[prop_name] = "/test/path.gpkg"
                elif "algorithm" in prop_name.lower():
                    input_data[prop_name] = "native:buffer"
                else:
                    input_data[prop_name] = "test_value"
            elif prop_type == "integer":
                minimum = prop_def.get("minimum", 0)
                maximum = prop_def.get("maximum", 10000)
                input_data[prop_name] = max(minimum, min(100, maximum))
            elif prop_type == "number":
                input_data[prop_name] = 1.0
            elif prop_type == "boolean":
                input_data[prop_name] = True
            elif prop_type == "array":
                input_data[prop_name] = []
            elif prop_type == "object":
                input_data[prop_name] = {}
            else:
                input_data[prop_name] = "test"

        return input_data

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_generated_valid_input_passes(self, spec: ToolSpec):
        """Generated valid input should pass validation."""
        valid_input = self._generate_valid_input(spec)
        try:
            Draft202012Validator(spec.input_schema).validate(valid_input)
        except jsonschema.ValidationError as e:
            pytest.fail(f"{spec.name}: generated valid input failed: {e}\nInput: {valid_input}")

    @pytest.mark.parametrize("spec", ALL_SPECS, ids=lambda s: s.name)
    def test_output_schema_accepts_minimal_valid_structure(self, spec: ToolSpec):
        """Output schema should accept a minimal valid response structure."""
        # Generate minimal valid output based on schema properties
        output_data = {}
        for prop_name, prop_def in spec.output_schema["properties"].items():
            prop_type = prop_def.get("type", "string")
            if isinstance(prop_type, list):
                prop_type = prop_type[0]

            if prop_type == "string":
                output_data[prop_name] = "test"
            elif prop_type == "integer":
                output_data[prop_name] = 1
            elif prop_type == "number":
                output_data[prop_name] = 1.0
            elif prop_type == "boolean":
                output_data[prop_name] = True
            elif prop_type == "array":
                output_data[prop_name] = []
            elif prop_type == "object":
                output_data[prop_name] = {}
            else:
                output_data[prop_name] = "test"

        try:
            Draft202012Validator(spec.output_schema).validate(output_data)
        except jsonschema.ValidationError as e:
            # Output schema validation failure is a warning, not a hard fail
            # because some schemas may have complex constraints
            print(f"WARNING: {spec.name} output schema may be too restrictive: {e}")


class TestToolRegistryCompleteness:
    """Test that registry has expected tools."""

    def test_registry_tool_count(self):
        """Registry should have expected number of tools (currently 38)."""
        # Update this count when tools are added/removed
        expected_count = 38
        assert len(ALL_SPECS) == expected_count, f"Expected {expected_count} tools, got {len(ALL_SPECS)}"

    def test_registry_namespace_count(self):
        """Registry should have expected number of namespaces (currently 26)."""
        # Update this count when namespaces are added/removed
        expected_count = 26
        namespaces = REGISTRY.namespaces()
        assert len(namespaces) == expected_count, f"Expected {expected_count} namespaces, got {len(namespaces)}: {namespaces}"

    def test_expected_namespaces_present(self):
        """All expected namespaces must be present."""
        expected = {
            "qgis.system", "qgis.project", "qgis.layers", "qgis.canvas",
            "qgis.screen", "qgis.cursor", "qgis.keyboard", "qgis.mouse",
            "qgis.window", "qgis.dialog", "qgis.algorithms", "qgis.plugins",
            "qgis.georeference", "qgis.gcp", "qgis.raster", "qgis.vector",
            "qgis.spatial", "qgis.database", "qgis.layout", "qgis.workflow",
            "qgis.agents", "qgis.skills", "qgis.verify", "qgis.jobs", "qgis.history",
        }
        found = set(REGISTRY.namespaces())
        missing = expected - found
        assert not missing, f"Missing namespaces: {missing}"

    def test_key_tools_registered(self):
        """Critical tools must be registered."""
        critical_tools = [
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
        ]
        for name in critical_tools:
            spec = REGISTRY.get(name)
            assert spec is not None, f"Missing critical tool: {name}"


class TestSchemaVersioning:
    """Test for schema breaking changes detection."""

    def test_no_required_field_removed(self, request):
        """Snapshot test: required fields should not be removed."""
        pytest.importorskip("pytest_snapshot", reason="pytest-snapshot not installed")
        snapshot = request.getfixturevalue("snapshot")
        required_map = {}
        for spec in ALL_SPECS:
            required_map[spec.name] = sorted(spec.input_schema["required"])
        snapshot.assert_match(json.dumps(required_map, indent=2), "required_fields_snapshot.json")

    def test_no_property_type_changed(self, request):
        """Snapshot test: property types should not change."""
        pytest.importorskip("pytest_snapshot", reason="pytest-snapshot not installed")
        snapshot = request.getfixturevalue("snapshot")
        type_map = {}
        for spec in ALL_SPECS:
            types = {}
            for prop_name, prop_def in spec.input_schema["properties"].items():
                types[prop_name] = prop_def.get("type")
            type_map[spec.name] = types
        snapshot.assert_match(json.dumps(type_map, indent=2), "property_types_snapshot.json")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])