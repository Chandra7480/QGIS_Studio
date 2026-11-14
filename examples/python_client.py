#!/usr/bin/env python3
"""
Universal AI GIS Studio — Python MCP Client Examples

Requirements:
    pip install mcp httpx

Usage:
    python examples/python_client.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("Install MCP SDK: pip install mcp")
    sys.exit(1)


# =============================================================================
# Example 1: Stdio Transport (for OpenCode/Codex-style local MCP servers)
# =============================================================================

async def example_stdio_transport():
    """Connect to MCP server via stdio transport."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Stdio Transport")
    print("="*60)
    
    # Server parameters - launches the MCP server as subprocess
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "mcp_server.main", "--transport", "stdio"],
        cwd=str(Path(__file__).parent.parent),  # Universal-AI-GIS-Studio root
        env={
            **os.environ,
            "UAGIS_BRIDGE_URL": "http://127.0.0.1:8765",
            # "UAGIS_BRIDGE_TOKEN": "your-token-if-configured",
        }
    )
    
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the connection
            await session.initialize()
            print("✓ MCP session initialized")
            
            # List available tools
            tools_result = await session.list_tools()
            print(f"✓ Discovered {len(tools_result.tools)} tools")
            
            # Show first 5 tools
            for tool in tools_result.tools[:5]:
                print(f"  - {tool.name}: {tool.description[:60]}...")
            
            # Call a simple tool: qgis.system.inspect
            print("\n→ Calling qgis.system.inspect...")
            result = await session.call_tool("qgis.system.inspect", {})
            print_result(result)
            
            # Call qgis.system.health
            print("\n→ Calling qgis.system.health...")
            result = await session.call_tool("qgis.system.health", {})
            print_result(result)


# =============================================================================
# Example 2: Streamable HTTP Transport (for web/remote clients)
# =============================================================================

async def example_http_transport():
    """Connect to MCP server via Streamable HTTP transport."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Streamable HTTP Transport")
    print("="*60)
    
    try:
        import httpx
    except ImportError:
        print("Install httpx: pip install httpx")
        return
    
    base_url = "http://127.0.0.1:8766"  # Default MCP HTTP port
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Initialize MCP session
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "uagis-python-example", "version": "1.0.0"}
            }
        }
        
        response = await client.post(f"{base_url}/mcp", json=init_request)
        init_result = response.json()
        print(f"✓ Initialized: {init_result.get('result', {}).get('serverInfo', {})}")
        
        # 2. Send initialized notification
        await client.post(f"{base_url}/mcp", json={
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {}
        })
        
        # 3. List tools
        list_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        response = await client.post(f"{base_url}/mcp", json=list_request)
        tools_result = response.json()
        tools = tools_result.get("result", {}).get("tools", [])
        print(f"✓ Discovered {len(tools)} tools")
        
        # 4. Call qgis.system.inspect
        call_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "qgis.system.inspect", "arguments": {}}
        }
        response = await client.post(f"{base_url}/mcp", json=call_request)
        result = response.json()
        print_result(result)


# =============================================================================
# Example 3: Complete GIS Workflow
# =============================================================================

async def example_gis_workflow():
    """Complete workflow: load layer → buffer → inspect result."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Complete GIS Workflow")
    print("="*60)
    
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "mcp_server.main", "--transport", "stdio"],
        cwd=str(Path(__file__).parent.parent),
        env={
            **os.environ,
            "UAGIS_BRIDGE_URL": "http://127.0.0.1:8765",
        }
    )
    
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            
            # Step 1: Check system
            print("→ Step 1: System inspection")
            result = await session.call_tool("qgis.system.inspect", {})
            print_result(result)
            
            # Step 2: Inspect current project
            print("\n→ Step 2: Project inspection")
            result = await session.call_tool("qgis.project.inspect", {})
            print_result(result)
            
            # Step 3: Load a layer (update path to your data)
            print("\n→ Step 3: Load layer")
            layer_path = "D:/data/parcels.gpkg"  # CHANGE THIS
            if not os.path.exists(layer_path):
                print(f"  ⚠ File not found: {layer_path}")
                print("  Skipping layer load. Update path in example.")
            else:
                result = await session.call_tool("qgis.layers.load", {
                    "path": layer_path,
                    "layer_name": "Parcels Example"
                })
                print_result(result)
                
                # Extract layer ID for next step
                layer_id = None
                try:
                    result_data = json.loads(result.content[0].text)
                    layer_id = result_data.get("result", {}).get("id")
                except:
                    pass
                
                # Step 4: Run buffer algorithm
                if layer_id:
                    print(f"\n→ Step 4: Buffer layer {layer_id} by 100m")
                    result = await session.call_tool("qgis.algorithms.execute", {
                        "algorithm": "native:buffer",
                        "parameters": {
                            "INPUT": layer_id,
                            "DISTANCE": 100,
                            "SEGMENTS": 5,
                            "END_CAP_STYLE": 0,
                            "JOIN_STYLE": 0,
                            "MITER_LIMIT": 2,
                            "DISSOLVE": False,
                            "OUTPUT": "memory:"
                        }
                    })
                    print_result(result)
            
            # Step 5: List algorithms
            print("\n→ Step 5: Discover algorithms")
            result = await session.call_tool("qgis.algorithms.discover", {})
            try:
                result_data = json.loads(result.content[0].text)
                algos = result_data.get("result", {}).get("algorithms", [])
                print(f"  Found {len(algos)} algorithms")
                for algo in algos[:5]:
                    print(f"  - {algo.get('id')}: {algo.get('name')}")
            except:
                print_result(result)


# =============================================================================
# Example 4: Error Handling & Verification States
# =============================================================================

async def example_error_handling():
    """Demonstrate proper error handling with verification states."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Error Handling & Verification States")
    print("="*60)
    
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "mcp_server.main", "--transport", "stdio"],
        cwd=str(Path(__file__).parent.parent),
        env={**os.environ, "UAGIS_BRIDGE_URL": "http://127.0.0.1:8765"}
    )
    
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            
            # Test 1: Valid tool call
            print("→ Test 1: Valid tool call")
            result = await session.call_tool("qgis.system.inspect", {})
            verification = extract_verification(result)
            print(f"  Verification: {verification}")
            
            # Test 2: Invalid tool (should error)
            print("\n→ Test 2: Invalid tool name")
            try:
                result = await session.call_tool("qgis.nonexistent.tool", {})
                verification = extract_verification(result)
                print(f"  Verification: {verification}")
            except Exception as e:
                print(f"  Exception (expected): {e}")
            
            # Test 3: Invalid parameters (should error)
            print("\n→ Test 3: Invalid parameters")
            try:
                result = await session.call_tool("qgis.layers.load", {
                    "path": "/nonexistent/path.shp"
                })
                verification = extract_verification(result)
                print(f"  Verification: {verification}")
            except Exception as e:
                print(f"  Exception: {e}")


def extract_verification(result) -> str:
    """Extract verification_state from tool result."""
    try:
        text = result.content[0].text
        data = json.loads(text)
        return data.get("verification_state", "UNKNOWN")
    except:
        return "PARSE_ERROR"


def print_result(result):
    """Pretty print tool result."""
    try:
        text = result.content[0].text
        data = json.loads(text)
        status = data.get("status", "unknown")
        verification = data.get("verification_state", "unknown")
        
        if status == "ok":
            print(f"  ✓ Status: {status} | Verification: {verification}")
            result_data = data.get("result", {})
            if result_data:
                # Print key fields
                for key, value in list(result_data.items())[:5]:
                    print(f"    {key}: {value}")
        else:
            error = data.get("error", {})
            print(f"  ✗ Status: {status} | Verification: {verification}")
            print(f"    Error: {error.get('code')}: {error.get('message')}")
    except Exception as e:
        print(f"  Parse error: {e}")
        print(f"  Raw: {result}")


# =============================================================================
# Example 5: Direct Bridge HTTP Client (bypass MCP)
# =============================================================================

async def example_direct_bridge():
    """Call QGIS Bridge directly via HTTP (useful for debugging)."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Direct Bridge HTTP Client")
    print("="*60)
    
    import httpx
    import uuid
    
    bridge_url = "http://127.0.0.1:8765"
    auth_token = os.environ.get("UAGIS_BRIDGE_TOKEN")  # Optional
    
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Health check
        print("→ Health check")
        resp = await client.get(f"{bridge_url}/health", headers=headers)
        print(f"  {resp.status_code}: {resp.json()}")
        
        # Direct tool dispatch
        print("\n→ Direct dispatch: qgis.system.inspect")
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        payload = {
            "request_id": request_id,
            "tool": "qgis.system.inspect",
            "params": {},
            "timeout_seconds": 30
        }
        resp = await client.post(f"{bridge_url}/dispatch", headers=headers, json=payload)
        print(f"  {resp.status_code}: {resp.json()}")
        
        # Load layer
        print("\n→ Direct dispatch: qgis.layers.load")
        request_id = f"req_{uuid.uuid4().hex[:12]}"
        payload = {
            "request_id": request_id,
            "tool": "qgis.layers.load",
            "params": {"path": "D:/data/parcels.gpkg"},  # CHANGE THIS
            "timeout_seconds": 60
        }
        resp = await client.post(f"{bridge_url}/dispatch", headers=headers, json=payload)
        print(f"  {resp.status_code}: {resp.json()}")


# =============================================================================
# Main
# =============================================================================

async def main():
    print("Universal AI GIS Studio — Python Client Examples")
    print("="*60)
    print("Prerequisites:")
    print("  1. QGIS 4.2.3 running with Universal AI GIS Studio plugin enabled")
    print("  2. Bridge started (Plugins → Universal AI GIS Studio → Start Bridge)")
    print("  3. MCP server dependencies installed (pip install -e .[mcp])")
    print()
    
    # Run examples (comment/uncomment as needed)
    try:
        await example_stdio_transport()
    except Exception as e:
        print(f"Stdio example failed: {e}")
        print("  Make sure QGIS Bridge is running on port 8765")
    
    # Uncomment to run HTTP example (requires MCP server running on HTTP)
    # try:
    #     await example_http_transport()
    # except Exception as e:
    #     print(f"HTTP example failed: {e}")
    
    # Uncomment for workflow example (requires data file)
    # try:
    #     await example_gis_workflow()
    # except Exception as e:
    #     print(f"Workflow example failed: {e}")
    
    try:
        await example_error_handling()
    except Exception as e:
        print(f"Error handling example failed: {e}")
    
    # Uncomment for direct bridge example
    # try:
    #     await example_direct_bridge()
    # except Exception as e:
    #     print(f"Direct bridge example failed: {e}")
    
    print("\n" + "="*60)
    print("Examples complete!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())