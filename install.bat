@echo off
REM Universal AI GIS Studio — Installation Script (Windows)
REM Usage: install.bat [base^|mcp^|opencv^|dev^|all]

setlocal enabledelayedexpansion

SET SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

SET MODE=%1
IF "%MODE%"=="" SET MODE=base

echo =========================================
echo Universal AI GIS Studio - Installation
echo Mode: %MODE%
echo =========================================

REM Check Python version
python --version 2>&1 | findstr /R "3\.1[1-9] 3\.1[2-9] 3\.[2-9][0-9]" >nul
IF ERRORLEVEL 1 (
    echo ERROR: Python 3.11+ required.
    exit /b 1
)

echo Python version check passed.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install base dependencies
echo Installing base dependencies...
pip install -r requirements\base.txt

IF "%MODE%"=="base" (
    echo Base installation complete.
    GOTO END
)

IF "%MODE%"=="mcp" (
    echo Installing MCP server dependencies...
    pip install -r requirements\mcp.txt
    GOTO END
)

IF "%MODE%"=="opencv" (
    echo Installing OpenCV dependencies...
    pip install -r requirements\opencv.txt
    GOTO END
)

IF "%MODE%"=="dev" (
    echo Installing development dependencies...
    pip install -r requirements\dev.txt
    GOTO END
)

IF "%MODE%"=="all" (
    echo Installing all dependencies...
    pip install -r requirements.txt
    GOTO END
)

echo ERROR: Unknown mode: %MODE%
echo Usage: install.bat [base^|mcp^|opencv^|dev^|all]
exit /b 1

:END
echo =========================================
echo Installation complete!
echo =========================================
echo.
echo Next steps:
echo   1. Set environment variables (optional):
echo      set UAGIS_BRIDGE_URL=http://127.0.0.1:8765
echo      set UAGIS_BRIDGE_AUTH_TOKEN=your-token
echo.
echo   2. Run MCP server:
echo      python -m mcp_server.main --transport stdio
echo      REM or: python -m mcp_server.main --transport streamable-http --port 8766
echo.
echo   3. Install QGIS plugin:
echo      Copy plugin\universal_ai_gis\ to your QGIS profile plugins folder
echo      (usually %APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\)
echo.
echo   4. Connect OpenCode:
echo      opencode mcp add uagis --global --command python --args -m mcp_server.main --transport stdio
echo.
echo Documentation: docs\