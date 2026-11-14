"""Universal AI GIS Studio — Universal MCP Server entry point.

Usage:
    python -m mcp_server.main --transport stdio
    python -m mcp_server.main --transport streamable-http --port 8766

Configured via environment variables:
    UAGIS_BRIDGE_URL   (default http://127.0.0.1:8765)
    UAGIS_BRIDGE_TOKEN (optional auth token)
    UAGIS_MCP_TRANSPORT (stdio|streamable-http, default stdio)
    UAGIS_MCP_PORT     (default 8766)
"""

import argparse
import os
import sys

from mcp_server.server import UniversalMCPServer


def main():
    parser = argparse.ArgumentParser(description="Universal AI GIS Studio MCP Server")
    parser.add_argument("--transport", choices=["stdio", "streamable-http"],
                        default=os.environ.get("UAGIS_MCP_TRANSPORT", "stdio"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("UAGIS_MCP_PORT", "8766")))
    parser.add_argument("--bridge-url", default=os.environ.get("UAGIS_BRIDGE_URL",
                        "http://127.0.0.1:8765"))
    parser.add_argument("--bridge-token", default=os.environ.get("UAGIS_BRIDGE_TOKEN"))
    args = parser.parse_args()

    server = UniversalMCPServer(bridge_url=args.bridge_url,
                                auth_token=args.bridge_token)

    if args.transport == "stdio":
        print(f"[uagis] MCP server '{server.name}' starting on stdio", file=sys.stderr)
        server.run_stdio()
    else:
        print(f"[uagis] MCP server '{server.name}' starting on Streamable HTTP "
              f"http://{args.host}:{args.port}", file=sys.stderr)
        server.run_streamable_http(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
