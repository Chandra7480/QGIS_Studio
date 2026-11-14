@echo off
echo ============================================
echo Universal AI GIS Studio - Full Stack Launcher
echo ============================================
echo.
echo STEP 1: Open QGIS and enable plugin
echo   - Plugins > Manage and Install Plugins
echo   - Search 'Universal AI GIS Studio' > Install/Enable
echo   - Click Bridge button (chain icon) to start bridge on port 8765
echo.
echo STEP 2: Press any key after bridge is running...
pause
echo.
echo STEP 3: Starting MCP Server on stdio...
python -m mcp_server.main --transport stdio
