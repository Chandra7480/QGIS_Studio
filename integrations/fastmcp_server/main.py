#!/usr/bin/env python3
"""
Universal AI GIS Studio — FastMCP Server.

External MCP server that connects to QGIS via TCP socket.
Compatible with all MCP clients (Claude Code, Codex, Cursor, etc.).

Installation:
    uvx --from https://github.com/your-org/uagis-mcp/archive/refs/heads/main.zip uagis-mcp-server

Environment Variables:
    QGIS_MCP_HOST        - QGIS plugin host (default: localhost)
    QGIS_MCP_PORT        - QGIS plugin port (default: 9876)
    QGIS_MCP_TOKEN       - Shared secret for authentication
    QGIS_MCP_TRANSPORT   - Transport: stdio or streamable-http (default: stdio)
    QGIS_MCP_LOG_FILE    - Log file path
    QGIS_MCP_LOG_LEVEL   - Log level (default: INFO)
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    CallToolRequest,
    CallToolResult,
)
from pydantic import BaseModel

# Configure logging
log_level = os.environ.get("QGIS_MCP_LOG_LEVEL", "INFO").upper()
log_file = os.environ.get("QGIS_MCP_LOG_FILE", "")
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file) if log_file else logging.StreamHandler(sys.stderr)
    ],
)
logger = logging.getLogger("uagis-mcp")

# Configuration
QGIS_HOST = os.environ.get("QGIS_MCP_HOST", "localhost")
QGIS_PORT = int(os.environ.get("QGIS_MCP_PORT", "9876"))
QGIS_TOKEN = os.environ.get("QGIS_MCP_TOKEN", "").strip()
TRANSPORT = os.environ.get("QGIS_MCP_TRANSPORT", "stdio")

# Global HTTP client for socket communication
http_client: Optional[httpx.AsyncClient] = None


class QGISClient:
    """Async client for communicating with QGIS socket server."""
    
    def __init__(self, host: str, port: int, token: str = ""):
        self.host = host
        self.port = port
        self.token = token
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
    
    async def connect(self):
        """Establish TCP connection to QGIS plugin."""
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        logger.info(f"Connected to QGIS at {self.host}:{self.port}")
    
    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
    
    async def send_command(self, cmd_type: str, params: Dict = None) -> Dict:
        """Send a command to QGIS and return response."""
        if not self.writer:
            raise RuntimeError("Not connected to QGIS")
        
        command = {
            "type": cmd_type,
            "params": params or {},
        }
        if self.token:
            command["token"] = self.token
        
        # Length-prefixed JSON framing
        payload = json.dumps(command).encode("utf-8")
        length = len(payload).to_bytes(4, "big")
        self.writer.write(length + payload)
        await self.writer.drain()
        
        # Read response
        header = await self.reader.readexactly(4)
        if len(header) < 4:
            raise ConnectionError("Connection closed by QGIS")
        msg_len = int.from_bytes(header, "big")
        if msg_len > 10 * 1024 * 1024:
            raise ValueError(f"Message too large: {msg_len}")
        body = await self.reader.readexactly(msg_len)
        return json.loads(body.decode("utf-8"))


# Global QGIS client
qgis_client: Optional[QGISClient] = None


def get_qgis_client() -> QGISClient:
    global qgis_client
    if qgis_client is None:
        qgis_client = QGISClient(QGIS_HOST, QGIS_PORT, QGIS_TOKEN)
    return qgis_client


# MCP Server instance
server = Server("uagis-mcp")


# Define available tools
TOOLS = [
    Tool(
        name="ping",
        description="Test connection to QGIS",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="diagnose",
        description="Run diagnostic checks on QGIS connection and server",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_project_info",
        description="Get current QGIS project information",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="load_project",
        description="Load a QGIS project file",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to .qgz project file"},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="create_new_project",
        description="Create a new QGIS project",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="save_project",
        description="Save current QGIS project",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Optional path to save as"},
            },
        },
    ),
    Tool(
        name="get_layers",
        description="List all layers in current project",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="add_vector_layer",
        description="Add a vector layer to the project",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to vector file"},
                "name": {"type": "string", "description": "Layer name (optional)"},
                "provider": {"type": "string", "description": "Provider name (optional)"},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="add_raster_layer",
        description="Add a raster layer to the project",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to raster file"},
                "name": {"type": "string", "description": "Layer name (optional)"},
            },
            "required": ["path"],
        },
    ),
    Tool(
        name="remove_layer",
        description="Remove a layer from the project",
        inputSchema={
            "type": "object",
            "properties": {
                "layer_id": {"type": "string", "description": "Layer ID to remove"},
            },
            "required": ["layer_id"],
        },
    ),
    Tool(
        name="get_layer_features",
        description="Get features from a layer",
        inputSchema={
            "type": "object",
            "properties": {
                "layer_id": {"type": "string"},
                "limit": {"type": "integer", "default": 100},
            },
            "required": ["layer_id"],
        },
    ),
    Tool(
        name="add_features",
        description="Add features to a layer",
        inputSchema={
            "type": "object",
            "properties": {
                "layer_id": {"type": "string"},
                "features": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["layer_id", "features"],
        },
    ),
    Tool(
        name="execute_processing",
        description="Run a QGIS processing algorithm",
        inputSchema={
            "type": "object",
            "properties": {
                "algorithm": {"type": "string", "description": "Algorithm ID (e.g., native:buffer)"},
                "parameters": {"type": "object", "description": "Algorithm parameters"},
            },
            "required": ["algorithm"],
        },
    ),
    Tool(
        name="execute_sql",
        description="Execute SQL on a database connection",
        inputSchema={
            "type": "object",
            "properties": {
                "connection": {"type": "string", "description": "Connection name"},
                "sql": {"type": "string", "description": "SQL query"},
            },
            "required": ["connection", "sql"],
        },
    ),
    Tool(
        name="render_map",
        description="Render the map canvas to an image",
        inputSchema={
            "type": "object",
            "properties": {
                "width": {"type": "integer", "default": 800},
                "height": {"type": "integer", "default": 600},
            },
        },
    ),
    ]


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List all available tools."""
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Execute a tool call via QGIS socket."""
    client = get_qgis_client()
    
    # Ensure connection
    if not client.writer:
        try:
            await client.connect()
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Failed to connect to QGIS: {e}")],
                isError=True,
            )
    
    # Map tool name to QGIS command
    cmd_map = {
        "ping": "ping",
        "diagnose": "diagnose",
        "get_project_info": "get_project_info",
        "load_project": "load_project",
        "create_new_project": "create_new_project",
        "save_project": "save_project",
        "get_layers": "get_layers",
        "add_vector_layer": "add_vector_layer",
        "add_raster_layer": "add_raster_layer",
        "remove_layer": "remove_layer",
        "get_layer_features": "get_layer_features",
        "add_features": "add_features",
        "execute_processing": "execute_processing",
        "execute_sql": "execute_sql",
        "render_map": "render_map",
    }
    
    cmd_type = cmd_map.get(name, name)
    
    try:
        result = await client.send_command(cmd_type, arguments)
        
        if result.get("status") == "error":
            return CallToolResult(
                content=[TextContent(type="text", text=result.get("message", "Unknown error"))],
                isError=True,
            )
        
        result_data = result.get("result", result)
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(result_data, indent=2))],
        )
    except Exception as e:
        logger.exception(f"Error calling {name}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {e}")],
            isError=True,
        )


async def main():
    """Main entry point."""
    logger.info("Starting UAGIS MCP Server")
    logger.info(f"QGIS host: {QGIS_HOST}:{QGIS_PORT}")
    logger.info(f"Transport: {TRANSPORT}")
    logger.info(f"Auth: {'enabled' if QGIS_TOKEN else 'disabled'}")
    
    if TRANSPORT == "stdio":
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )
    else:
        # HTTP transport - not fully implemented here
        logger.error("HTTP transport not yet implemented")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())