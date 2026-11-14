"""Universal AI GIS Studio — Universal MCP Server (low-level MCP Server).

Uses mcp.server.lowlevel.Server so every tool has a strict inputSchema
(declared in ToolRegistry). Exposes stdio and Streamable HTTP transports.
All tools call the QGIS Bridge and return verified, structured results.

Also exposes MCP Resources (qgis:// URIs) and Prompts (GIS workflow templates).
"""

import json
import uuid
import os
import anyio
import base64
import time
from typing import Optional, List, Dict, Any, Set

from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool, TextContent, Resource, ResourceTemplate, Prompt,
    LoggingLevel, SubscribeRequest, UnsubscribeRequest, SetLevelRequest,
    AnyUrl,
)

# JSON Schema validation
try:
    from jsonschema import Draft202012Validator, ValidationError as JSONSchemaValidationError
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False
    Draft202012Validator = None
    JSONSchemaValidationError = Exception

from mcp_server.registry import build_registry, ToolSpec
from mcp_server.qgis_client import AsyncQgisBridgeClient
from mcp_server.resources.registry import get_registry as get_resource_registry
from mcp_server.prompts.registry import get_registry as get_prompt_registry
from mcp_server.verification import get_verification_engine
from mcp_server.approval import get_approval_manager, check_approval_required, ApprovalRequest
from core.logging import get_logger
from core.exceptions import MCPError, BridgeError, ValidationError, UAGISPermissionError
from core.emergency_stop import is_emergency_stop_active, EmergencyStopActiveError
from security.rate_limiter import get_rate_limiter, RateLimitResult

logger = get_logger("mcp.server")


# ---- Permission System ----

class PermissionManager:
    """Manages permission checks for MCP tools."""

    def __init__(self):
        # In a real system, this would come from auth context / session
        # For now, we grant all permissions by default (can be overridden)
        self._granted_permissions: Set[str] = set()
        self._permission_hierarchy = {
            "qgis:read": [
                "qgis:system:read", "qgis:project:read", "qgis:canvas:read",
                "qgis:layers:read", "qgis:screen:read", "qgis:window:read",
                "qgis:dialog:read", "qgis:algorithms:read", "qgis:georeference:read",
                "qgis:gcp:read", "qgis:raster:read", "qgis:vector:read",
                "qgis:spatial:read", "qgis:database:read", "qgis:layout:read",
                "qgis:workflow:read", "qgis:agents:read", "qgis:skills:read",
                "qgis:verify:read", "qgis:history:read", "qgis:plugins:read",
            ],
            "qgis:write": [
                "qgis:project:write", "qgis:layer:write", "qgis:cursor:write",
                "qgis:keyboard:write", "qgis:mouse:write", "qgis:algorithm:execute",
                "qgis:gcp:write", "qgis:workflow:execute", "qgis:jobs:write",
            ],
            "qgis:admin": ["*"],
        }

    def grant_permission(self, permission: str):
        """Grant a permission (for testing/admin)."""
        self._granted_permissions.add(permission)

    def check_permission(self, required: str, context: Dict[str, Any] = None) -> bool:
        """Check if a permission is granted."""
        # Check direct grant
        if required in self._granted_permissions:
            return True
        # Check wildcard
        if "*" in self._granted_permissions:
            return True
        # Check hierarchy - if parent is granted
        for parent, children in self._permission_hierarchy.items():
            if parent in self._granted_permissions and required in children:
                return True
        # Default: deny if no explicit grants (secure by default)
        # In production, this would check auth token / session
        return False  # Deny by default

    def check_permissions(self, required: List[str], context: Dict[str, Any] = None) -> List[str]:
        """Check multiple permissions, return list of missing ones."""
        missing = []
        for perm in required:
            if not self.check_permission(perm, context):
                missing.append(perm)
        return missing


# Global permission manager
_permission_manager: Optional[PermissionManager] = None


def get_permission_manager() -> PermissionManager:
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager()
    return _permission_manager


# ---- Server Configuration ----

SERVER_INSTRUCTIONS = """Universal AI GIS Studio MCP Server

This server provides programmatic access to QGIS Desktop through the Model Context Protocol.
It exposes tools for GIS operations, resources for layer/project metadata, and prompts for common workflows.

Key capabilities:
- Tools: 45+ tools across 15 namespaces (qgis.system, qgis.project, qgis.layers, qgis.algorithms, etc.)
- Resources: qgis:// URIs for layer info, project metadata, canvas state, processing algorithms
- Prompts: GIS workflow templates for georeferencing, spatial analysis, cartography, etc.
- Logging: Structured log messages at debug/info/warning/error levels

Authentication: Configure UAGIS_BRIDGE_TOKEN environment variable for bridge authentication.
Transport: stdio (default) or Streamable HTTP (--transport streamable-http)

For tool details, use tools/list. For resource URIs, use resources/list.
For prompt templates, use prompts/list.
"""


# ---- JSON Schema Validators Cache ----

_validator_cache: Dict[str, Draft202012Validator] = {}


def get_validator(schema: Dict[str, Any]) -> Optional[Draft202012Validator]:
    """Get or create a cached JSON Schema validator."""
    if not JSONSCHEMA_AVAILABLE:
        return None
    # Use schema id or hash as cache key
    cache_key = json.dumps(schema, sort_keys=True)
    if cache_key not in _validator_cache:
        _validator_cache[cache_key] = Draft202012Validator(schema)
    return _validator_cache[cache_key]


def validate_input(spec: ToolSpec, params: dict) -> None:
    """Validate input parameters against tool's input schema.
    Raises ValidationError on failure with detailed error info.
    """
    if not JSONSCHEMA_AVAILABLE:
        logger.warning("jsonschema not available, skipping input validation")
        return

    validator = get_validator(spec.input_schema)
    if validator is None:
        return

    try:
        validator.validate(params)
    except JSONSchemaValidationError as exc:
        # Build detailed error path
        path = " -> ".join(str(p) for p in exc.absolute_path) if exc.absolute_path else "root"
        raise ValidationError(
            f"Invalid parameters for {spec.name}: {exc.message}",
            error_code="INVALID_PARAMS",
            context={
                "tool": spec.name,
                "schema_path": path,
                "failed_field": path,
                "expected": str(exc.schema),
                "received": str(exc.instance),
                "validator": exc.validator,
                "validator_value": str(exc.validator_value),
            },
        ) from exc


def validate_output(spec: ToolSpec, result: dict) -> None:
    """Validate output result against tool's output schema.
    Logs warning on mismatch but does not fail (bridge may return extra fields).
    """
    if not JSONSCHEMA_AVAILABLE:
        return

    validator = get_validator(spec.output_schema)
    if validator is None:
        return

    output_data = result.get("result", {})
    try:
        validator.validate(output_data)
    except JSONSchemaValidationError as exc:
        path = " -> ".join(str(p) for p in exc.absolute_path) if exc.absolute_path else "root"
        logger.warning(
            "Output validation warning for %s: %s at %s",
            spec.name, exc.message, path
        )


class UniversalMCPServer:
    def __init__(self, bridge_url: Optional[str] = None,
                 auth_token: Optional[str] = None,
                 name: str = "universal-ai-gis-studio"):
        if bridge_url is None:
            bridge_url = os.environ.get("UAGIS_BRIDGE_URL", "http://127.0.0.1:8766")
        self.bridge_url = bridge_url
        self.auth_token = auth_token
        self.name = name
        self.client = AsyncQgisBridgeClient(base_url=bridge_url, auth_token=auth_token)
        self.registry = build_registry()
        self.resource_registry = get_resource_registry()
        self.prompt_registry = get_prompt_registry()
        self.verification_engine = get_verification_engine()
        self.approval_manager = get_approval_manager()
        self.permission_manager = get_permission_manager()

        self.server = Server(
            name=name,
            version="1.0.0",
            instructions=SERVER_INSTRUCTIONS,
            website_url="https://github.com/universal-ai-gis-studio",
            icons=None,
        )
        # Override create_initialization_options to always use notification options
        # This ensures both stdio and Streamable HTTP transports get correct capabilities
        original_create_init = self.server.create_initialization_options
        
        def _create_init_with_notifications(
            notification_options=None,
            experimental_capabilities=None,
        ):
            from mcp.server.lowlevel import NotificationOptions
            if notification_options is None:
                notification_options = NotificationOptions(
                    prompts_changed=True,
                    resources_changed=True,
                    tools_changed=True,
                )
            return original_create_init(notification_options, experimental_capabilities)
        
        self.server.create_initialization_options = _create_init_with_notifications
        self._setup_handlers()

    # ------------------------------------------------------------------ #
    # Handler setup
    # ------------------------------------------------------------------ #
    def _setup_handlers(self):
        server = self.server
        registry = self.registry
        resource_registry = self.resource_registry
        prompt_registry = self.prompt_registry

        # ---- Tools ----
        @server.list_tools()
        async def list_tools() -> List[Tool]:
            tools = []
            for spec in registry.all():
                tools.append(Tool(
                    name=spec.name,
                    description=spec.description,
                    inputSchema=spec.input_schema,
                ))
            logger.info("Listed %d MCP tools", len(tools))
            return tools

        @server.call_tool()
        async def call_tool(name: str, arguments: dict) -> List[TextContent]:
            spec = registry.get(name)
            if spec is None:
                raise MCPError(f"Unknown tool: {name}")
            return await self._execute_tool(spec, arguments or {})

        # ---- Resources ----
        @server.list_resources()
        async def list_resources() -> List[Resource]:
            resources = []
            for spec in resource_registry.all_resources():
                resources.append(Resource(
                    uri=spec.uri_pattern,
                    name=spec.name,
                    description=spec.description,
                    mimeType=spec.mime_type,
                ))
            logger.info("Listed %d MCP resources", len(resources))
            return resources

        @server.list_resource_templates()
        async def list_resource_templates() -> List[ResourceTemplate]:
            templates = []
            for spec in resource_registry.all_templates():
                templates.append(ResourceTemplate(
                    uriTemplate=spec.uri_pattern,
                    name=spec.name,
                    description=spec.description,
                    mimeType=spec.mime_type,
                ))
            logger.info("Listed %d MCP resource templates", len(templates))
            return templates

        @server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read a resource by URI, returning JSON content."""
            result = resource_registry.get_by_pattern(uri)
            if result is None:
                raise MCPError(f"Resource not found: {uri}")
            spec, variables = result
            if spec.handler is None:
                raise MCPError(f"Resource {uri} has no handler")
            try:
                content = await spec.handler(variables)
                return json.dumps(content, indent=2)
            except Exception as exc:
                logger.exception("Resource %s handler failed", uri)
                raise MCPError(f"Resource handler failed: {exc}") from exc

        # ---- Prompts ----
        @server.list_prompts()
        async def list_prompts() -> List[Prompt]:
            prompts = []
            for spec in prompt_registry.all():
                prompts.append(Prompt(
                    name=spec.name,
                    description=spec.description,
                    arguments=[
                        {
                            "name": arg.name,
                            "description": arg.description,
                            "required": arg.required,
                        }
                        for arg in spec.arguments
                    ],
                ))
            logger.info("Listed %d MCP prompts", len(prompts))
            return prompts

        @server.get_prompt()
        async def get_prompt(name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
            """Get a prompt by name with arguments, returning rendered template."""
            from mcp.types import GetPromptResult, PromptMessage
            spec = prompt_registry.get(name)
            if spec is None:
                raise MCPError(f"Prompt not found: {name}")
            try:
                rendered = spec.render(arguments or {})
                return GetPromptResult(
                    description=spec.description,
                    messages=[
                        PromptMessage(
                            role="user",
                            content=TextContent(type="text", text=rendered),
                        )
                    ],
                )
            except Exception as exc:
                logger.exception("Prompt %s render failed", name)
                raise MCPError(f"Prompt render failed: {exc}") from exc

        # ---- Logging ----
        @server.set_logging_level()
        async def set_logging_level(level: LoggingLevel) -> None:
            """Set the logging level for the server."""
            import logging
            logging.getLogger("mcp.server").setLevel(level.upper())
            logger.info("Log level set to %s", level)

        # ---- Resource Subscriptions ----
        @server.subscribe_resource()
        async def subscribe_resource(uri: AnyUrl) -> None:
            """Subscribe to resource updates."""
            # Check if resource exists
            result = resource_registry.get_by_pattern(str(uri))
            if result is None:
                raise MCPError(f"Resource not found: {uri}")
            # In a real implementation, track subscriptions per client session
            # For now, just acknowledge the subscription
            logger.info("Client subscribed to resource: %s", uri)

        @server.unsubscribe_resource()
        async def unsubscribe_resource(uri: AnyUrl) -> None:
            """Unsubscribe from resource updates."""
            logger.info("Client unsubscribed from resource: %s", uri)

    # ------------------------------------------------------------------ #
    # Tool execution with validation, permissions, approval, verification
    # ------------------------------------------------------------------ #
    async def _execute_tool(self, spec: ToolSpec, params: dict) -> List[TextContent]:
        request_id = f"req_{uuid.uuid4().hex[:12]}"

        # 1. INPUT VALIDATION
        try:
            validate_input(spec, params)
        except ValidationError:
            raise
        except Exception as exc:
            logger.exception("Input validation error for %s", spec.name)
            raise ValidationError(f"Validation failed: {exc}") from exc

        # 2. PERMISSION CHECK
        if spec.permissions:
            missing = self.permission_manager.check_permissions(spec.permissions, {"tool": spec.name})
            if missing:
                raise UAGISPermissionError(
                    f"Missing required permissions for {spec.name}: {', '.join(missing)}",
                    error_code="PERMISSION_DENIED",
                    context={"required": spec.permissions, "missing": missing, "tool": spec.name},
                )

        # 3. APPROVAL GATE
        approval_request = check_approval_required(spec, params, request_id)
        if approval_request is not None:
            # Approval required but not granted - return error with approval_id
            raise MCPError(
                f"Approval required for {spec.name}",
                error_code="APPROVAL_REQUIRED",
                context={
                    "approval_id": approval_request.approval_id,
                    "tool": spec.name,
                    "expires_at": approval_request.expires_at,
                    "message": f"Tool {spec.name} requires human approval. Use qgis.approval.grant with approval_id to proceed.",
                },
            )

        # 3.5. RATE LIMITING
        # Extract client identifier from context (would come from auth in production)
        client_id = getattr(self, '_current_client_id', 'mcp_anonymous')
        rate_limiter = get_rate_limiter()
        rate_result: RateLimitResult = rate_limiter.check_rate_limit(client_id, spec.name)

        if not rate_result.allowed:
            logger.warning("MCP Rate limit exceeded for %s:%s", client_id, spec.name)
            raise MCPError(
                f"Rate limit exceeded for tool {spec.name}. Try again in {rate_result.retry_after:.1f}s",
                error_code="RATE_LIMIT_EXCEEDED",
                context={
                    "tool": spec.name,
                    "retry_after": rate_result.retry_after,
                    "remaining_tokens": rate_result.remaining_tokens,
                    "capacity": rate_result.capacity,
                    "refill_rate": rate_result.refill_rate,
                },
            )

        # 3.6. EMERGENCY STOP CHECK
        if is_emergency_stop_active():
            logger.warning("MCP Tool %s rejected: emergency stop active", spec.name)
            raise MCPError(
                "Emergency stop is active - all tool executions are blocked",
                error_code="EMERGENCY_STOP_ACTIVE",
                context={"tool": spec.name},
            )

        # 4. EXECUTE TOOL
        try:
            result = await self.client.dispatch(
                tool=spec.name, params=params, request_id=request_id,
                timeout_seconds=spec.timeout_seconds,
            )

            status = result.get("status", "error")
            verification = result.get("verification_state", "UNKNOWN")

            if status == "error":
                err = result.get("error", {})
                raise MCPError(
                    f"Tool {spec.name} failed: {err.get('message', 'unknown error')}",
                    context={"code": err.get("code"), "request_id": request_id,
                             "verification_state": verification},
                )

            # 5. OUTPUT VALIDATION (warning only)
            validate_output(spec, result)

            # 6. VERIFICATION RULES
            verification_state = verification
            if spec.verification_rules:
                failed_rules = self.verification_engine.run_verification(spec, result)
                if failed_rules:
                    verification_state = "FAILED"
                    logger.warning(
                        "Verification FAILED for %s: rules failed: %s",
                        spec.name, failed_rules
                    )
                else:
                    verification_state = "SUCCESS"
                    logger.debug("Verification PASSED for %s", spec.name)

            out = {
                "request_id": request_id,
                "tool": spec.name,
                "status": status,
                "verification_state": verification_state,
                "result": result.get("result", {}),
                "job_id": result.get("job_id"),
                "timestamp": result.get("timestamp") or time.time(),
            }
            return [TextContent(type="text", text=json.dumps(out, indent=2))]

        except MCPError:
            raise
        except BridgeError:
            raise
        except Exception as exc:
            logger.exception("MCP tool %s failed", spec.name)
            raise MCPError(f"Tool {spec.name} error: {exc}") from exc

    # ------------------------------------------------------------------ #
    # Transports
    # ------------------------------------------------------------------ #
    def _create_init_options(self):
        """Create initialization options with proper notification options."""
        from mcp.server.lowlevel import NotificationOptions
        return self.server.create_initialization_options(
            notification_options=NotificationOptions(
                prompts_changed=True,
                resources_changed=True,
                tools_changed=True,
            ),
        )

    def run_stdio(self):
        """Run on stdio transport (OpenCode / local MCP clients)."""

        async def _run():
            async with stdio_server() as (read_stream, write_stream):
                await self.server.run(
                    read_stream, write_stream,
                    self._create_init_options(),
                )

        anyio.run(_run)

    def streamable_http_app(self):
        """Return an ASGI app serving Streamable HTTP transport."""
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
        from mcp.server.lowlevel.server import Server as MCPServer
        
        # Create manager as instance attribute so lifespan can use it
        if not hasattr(self, '_streamable_http_manager'):
            self._streamable_http_manager = StreamableHTTPSessionManager(
                app=self.server,
                stateless=False,
                json_response=False,
            )
        manager = self._streamable_http_manager
        
        # The manager already has an asgi_app attribute
        return manager.asgi_app

    def run_streamable_http(self, host: str = "127.0.0.1", port: int = 8766):
        """Run Streamable HTTP via uvicorn if available."""
        try:
            import uvicorn  # type: ignore
        except ImportError as exc:
            raise BridgeError(
                "uvicorn is required for Streamable HTTP transport. "
                "Install it or use stdio transport."
            ) from exc
        
        # Need to wrap with lifespan for StreamableHTTPSessionManager
        from starlette.applications import Starlette
        from starlette.routing import Mount
        from contextlib import asynccontextmanager
        
        @asynccontextmanager
        async def lifespan(app):
            # Start the session manager
            async with self._streamable_http_manager.run():
                yield
        
        # Create Starlette app with lifespan and mount the ASGI app
        app = Starlette(lifespan=lifespan, routes=[
            Mount("/", app=self.streamable_http_app()),
        ])
        
        uvicorn.run(app, host=host, port=port, log_level="info")