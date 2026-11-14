#!/bin/bash
# Universal AI GIS Studio — Installation Script
# Usage: ./install.sh [base|mcp|opencv|dev|all]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MODE="${1:-base}"

echo "========================================="
echo "Universal AI GIS Studio — Installation"
echo "Mode: $MODE"
echo "========================================="

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.11"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"; then
    echo "ERROR: Python 3.11+ required. Found: $PYTHON_VERSION"
    exit 1
fi

echo "Python version: $PYTHON_VERSION ✓"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install base dependencies
echo "Installing base dependencies..."
pip install -r requirements/base.txt

case "$MODE" in
    base)
        echo "Base installation complete."
        ;;
    mcp)
        echo "Installing MCP server dependencies..."
        pip install -r requirements/mcp.txt
        ;;
    opencv)
        echo "Installing OpenCV dependencies..."
        pip install -r requirements/opencv.txt
        ;;
    dev)
        echo "Installing development dependencies..."
        pip install -r requirements/dev.txt
        ;;
    all)
        echo "Installing all dependencies..."
        pip install -r requirements.txt
        ;;
    *)
        echo "ERROR: Unknown mode: $MODE"
        echo "Usage: ./install.sh [base|mcp|opencv|dev|all]"
        exit 1
        ;;
esac

echo "========================================="
echo "Installation complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Set environment variables (optional):"
echo "     export UAGIS_BRIDGE_URL=http://127.0.0.1:8765"
echo "     export UAGIS_BRIDGE_AUTH_TOKEN=your-token"
echo ""
echo "  2. Run MCP server:"
echo "     python -m mcp_server.main --transport stdio"
echo "     # or: python -m mcp_server.main --transport streamable-http --port 8766"
echo ""
echo "  3. Install QGIS plugin:"
echo "     Copy plugin/universal_ai_gis/ to your QGIS profile plugins folder"
echo ""
echo "  4. Connect OpenCode:"
echo "     opencode mcp add uagis --global --command python --args -m mcp_server.main --transport stdio"
echo ""
echo "Documentation: docs/"