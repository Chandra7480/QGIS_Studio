"""Universal AI GIS Studio — MCP Prompt Registry.

Defines every MCP prompt as a typed PromptSpec: name, description, arguments,
and the prompt template with argument placeholders.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict, Callable
from enum import Enum


class PromptCategory(Enum):
    """Category for organizing prompts."""
    VECTOR = "vector"
    RASTER = "raster"
    ANALYSIS = "analysis"
    CARTOGRAPHY = "cartography"
    DATA = "data"
    REMOTE_SENSING = "remote_sensing"
    AUTOMATION = "automation"
    TERRAIN = "terrain"
    HYDROLOGY = "hydrology"
    NETWORK = "network"
    GEOREFERENCING = "georeferencing"
    CLASSIFICATION = "classification"
    CHANGE_DETECTION = "change_detection"
    THREE_D = "3d"
    LIDAR = "lidar"
    SURVEY = "survey"
    CADASTRAL = "cadastral"
    TEMPORAL = "temporal"
    DATABASE = "database"
    FIELD_DATA = "field_data"


@dataclass
class PromptArgument:
    """Argument definition for a prompt."""
    name: str
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[str]] = None  # Allowed values if applicable


@dataclass
class PromptSpec:
    """Specification for an MCP prompt."""
    name: str                      # e.g., "create_buffer"
    description: str               # Human-readable description
    category: PromptCategory
    arguments: List[PromptArgument] = field(default_factory=list)
    # Template with {arg_name} placeholders
    template: str = ""
    # Optional handler for dynamic prompt generation
    handler: Optional[Callable[[Dict[str, Any]], str]] = None
    permissions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def to_mcp_prompt(self) -> dict:
        """Convert to MCP prompt format."""
        return {
            "name": self.name,
            "description": self.description,
            "arguments": [
                {
                    "name": arg.name,
                    "description": arg.description,
                    "required": arg.required,
                }
                for arg in self.arguments
            ],
        }

    def render(self, arguments: Dict[str, Any]) -> str:
        """Render the prompt template with provided arguments."""
        # Check required arguments
        for arg in self.arguments:
            if arg.required and arg.name not in arguments:
                if arg.default is not None:
                    arguments[arg.name] = arg.default
                else:
                    raise ValueError(f"Missing required argument: {arg.name}")

        if self.handler:
            return self.handler(arguments)

        # Simple template substitution
        result = self.template
        for arg in self.arguments:
            placeholder = f"{{{arg.name}}}"
            value = arguments.get(arg.name, arg.default)
            if value is not None:
                result = result.replace(placeholder, str(value))
            elif arg.required:
                raise ValueError(f"Required argument not provided: {arg.name}")
        return result


class PromptRegistry:
    """Registry of all MCP prompts."""

    def __init__(self):
        self._prompts: Dict[str, PromptSpec] = {}

    def register(self, spec: PromptSpec) -> None:
        """Register a prompt."""
        self._prompts[spec.name] = spec

    def get(self, name: str) -> Optional[PromptSpec]:
        """Get prompt by name."""
        return self._prompts.get(name)

    def all(self) -> List[PromptSpec]:
        """Get all prompts."""
        return list(self._prompts.values())

    def by_category(self, category: PromptCategory) -> List[PromptSpec]:
        """Get prompts by category."""
        return [p for p in self._prompts.values() if p.category == category]

    def names(self) -> List[str]:
        """Get all prompt names."""
        return sorted(self._prompts.keys())

    def categories(self) -> List[PromptCategory]:
        """Get all used categories."""
        cats = {p.category for p in self._prompts.values()}
        return sorted(cats, key=lambda c: c.value)


# Global registry instance
_registry: Optional[PromptRegistry] = None


def get_registry() -> PromptRegistry:
    """Get or create the global prompt registry."""
    global _registry
    if _registry is None:
        _registry = build_registry()
    return _registry


def build_registry() -> PromptRegistry:
    """Build the prompt registry with all GIS workflow prompts."""
    from .vector import register_vector_prompts
    from .raster import register_raster_prompts
    from .analysis import register_analysis_prompts
    from .cartography import register_cartography_prompts
    from .data import register_data_prompts
    from .remote_sensing import register_remote_sensing_prompts
    from .automation import register_automation_prompts
    from .terrain import register_terrain_prompts

    r = PromptRegistry()

    register_vector_prompts(r)
    register_raster_prompts(r)
    register_analysis_prompts(r)
    register_cartography_prompts(r)
    register_data_prompts(r)
    register_remote_sensing_prompts(r)
    register_automation_prompts(r)
    register_terrain_prompts(r)

    return r