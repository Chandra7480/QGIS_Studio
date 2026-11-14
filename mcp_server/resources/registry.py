"""Universal AI GIS Studio — MCP Resource Registry.

Defines every MCP resource as a typed ResourceSpec: URI pattern, name, description,
MIME type, and metadata. The registry is the single source of truth for what
the MCP server exposes as resources.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict, Callable
from enum import Enum
import re


class ResourceType(Enum):
    """Type of resource for categorization."""
    STATIC = "static"           # Fixed URI, e.g., qgis://project/info
    DYNAMIC = "dynamic"         # Parameterized, e.g., qgis://layer/{layer_id}/features
    TEMPLATE = "template"       # URI template with variables


@dataclass
class ResourceSpec:
    """Specification for an MCP resource or resource template."""
    uri_pattern: str              # e.g., "qgis://layer/{layer_id}" or "qgis://project/info"
    name: str                     # Human-readable name
    description: str
    mime_type: str = "application/json"  # Default MIME type
    resource_type: ResourceType = ResourceType.STATIC
    variables: Dict[str, str] = field(default_factory=dict)  # Variable name -> description for templates
    permissions: List[str] = field(default_factory=list)
    # Handler function: (variables: dict) -> dict (resource content)
    handler: Optional[Callable[[Dict[str, Any]], Any]] = None

    def matches(self, uri: str) -> Optional[Dict[str, str]]:
        """Check if URI matches this pattern, return extracted variables or None."""
        # Convert pattern to regex
        pattern = self.uri_pattern
        # Escape special regex chars except {}
        pattern = re.escape(pattern)
        # Replace \{var\} with named capture groups
        pattern = re.sub(r'\\\{([^}]+)\\\}', r'(?P<\1>[^/]+)', pattern)
        pattern = f"^{pattern}$"

        match = re.match(pattern, uri)
        if match:
            return match.groupdict()
        return None

    def to_mcp_resource(self, uri: str = None) -> dict:
        """Convert to MCP resource format."""
        return {
            "uri": uri or self.uri_pattern,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }

    def to_mcp_template(self) -> dict:
        """Convert to MCP resource template format."""
        return {
            "uriTemplate": self.uri_pattern,
            "name": self.name,
            "description": self.description,
            "mimeType": self.mime_type,
        }


class ResourceRegistry:
    """Registry of all MCP resources and resource templates."""

    def __init__(self):
        self._resources: Dict[str, ResourceSpec] = {}  # uri_pattern -> spec
        self._templates: Dict[str, ResourceSpec] = {}  # uri_pattern -> spec (for templates)

    def register(self, spec: ResourceSpec) -> None:
        """Register a resource or resource template."""
        if spec.resource_type == ResourceType.TEMPLATE:
            self._templates[spec.uri_pattern] = spec
        else:
            self._resources[spec.uri_pattern] = spec

    def get(self, uri: str) -> Optional[ResourceSpec]:
        """Get resource spec by exact URI match (for static resources)."""
        return self._resources.get(uri)

    def get_by_pattern(self, uri: str) -> Optional[tuple[ResourceSpec, Dict[str, str]]]:
        """Find a resource/template matching the URI, return spec and extracted variables."""
        # First check static resources (exact match)
        if uri in self._resources:
            spec = self._resources[uri]
            if spec.resource_type == ResourceType.STATIC:
                return spec, {}

        # Then check templates FIRST (more specific patterns like /search?q=, /transform?...)
        for pattern, spec in self._templates.items():
            vars_dict = spec.matches(uri)
            if vars_dict is not None:
                return spec, vars_dict

        # Then check dynamic resources (parameterized paths like /{id})
        for pattern, spec in self._resources.items():
            if spec.resource_type == ResourceType.DYNAMIC:
                vars_dict = spec.matches(uri)
                if vars_dict is not None:
                    return spec, vars_dict
        return None

    def all_resources(self) -> List[ResourceSpec]:
        """Get all static resources."""
        return list(self._resources.values())

    def all_templates(self) -> List[ResourceSpec]:
        """All resource templates (dynamic resources)."""
        return list(self._templates.values())

    def list_uris(self) -> List[str]:
        """List all static resource URIs."""
        return sorted(self._resources.keys())


# Global registry instance
_registry: Optional[ResourceRegistry] = None


def get_registry() -> ResourceRegistry:
    """Get or create the global resource registry."""
    global _registry
    if _registry is None:
        _registry = build_registry()
    return _registry


def build_registry() -> ResourceRegistry:
    """Build the resource registry with all QGIS resources."""
    from .layers import register_layer_resources
    from .project import register_project_resources
    from .algorithms import register_algorithm_resources
    from .crs import register_crs_resources
    from .layouts import register_layout_resources
    from .database import register_database_resources
    from .styles import register_style_resources

    r = ResourceRegistry()

    # Register all resource groups
    register_layer_resources(r)
    register_project_resources(r)
    register_algorithm_resources(r)
    register_crs_resources(r)
    register_layout_resources(r)
    register_database_resources(r)
    register_style_resources(r)

    return r