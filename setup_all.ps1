# Universal AI GIS Studio - Complete Windows Setup Script
# Run as Administrator in PowerShell

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Universal AI GIS Studio - Full Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$ErrorActionPreference = "Stop"
$ProjectRoot = "D:\1 2 3 QGIS\Universal-AI-GIS-Studio"

# --------------------------------------------------
# 1. Check Prerequisites
# --------------------------------------------------
Write-Host "`n[1/7] Checking prerequisites..." -ForegroundColor Yellow

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  ✅ Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Python not found. Install from python.org" -ForegroundColor Red
    exit 1
}

# Check QGIS
$qgisPaths = @(
    "C:\Program Files\QGIS 3.34.0\bin\qgis-bin.exe",
    "C:\Program Files\QGIS 3.38.0\bin\qgis-bin.exe",
    "C:\OSGeo4W\bin\qgis-bin.exe"
)
$qgisFound = $false
foreach ($path in $qgisPaths) {
    if (Test-Path $path) {
        Write-Host "  ✅ QGIS found: $path" -ForegroundColor Green
        $qgisFound = $true
        break
    }
}
if (-not $qgisFound) {
    Write-Host "  ⚠️  QGIS not found in standard locations." -ForegroundColor Yellow
    Write-Host "     Install QGIS 3.34+ from qgis.org or OSGeo4W" -ForegroundColor Yellow
}

# Check pip
try {
    pip --version | Out-Null
    Write-Host "  ✅ pip available" -ForegroundColor Green
} catch {
    Write-Host "  ❌ pip not found" -ForegroundColor Red
    exit 1
}

# --------------------------------------------------
# 2. Install Python Dependencies
# --------------------------------------------------
Write-Host "`n[2/7] Installing Python dependencies..." -ForegroundColor Yellow

cd $ProjectRoot

$packages = @(
    "httpx>=0.27.0",
    "prometheus-client>=0.19.0", 
    "pybreaker>=0.8.1",
    "jsonschema>=4.20.0",
    "mcp>=1.2.0",
    "imagehash>=4.3.1",
    "Pillow>=10.0.0",
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
    "hypothesis>=6.82.0",
    "aiohttp>=3.9.0"
)

foreach ($pkg in $packages) {
    Write-Host "  Installing $pkg..." -NoNewline
    try {
        pip install $pkg -q 2>&1 | Out-Null
        Write-Host " ✅" -ForegroundColor Green
    } catch {
        Write-Host " ❌ Failed: $pkg" -ForegroundColor Red
    }
}

# Install package in development mode
Write-Host "  Installing universal-ai-gis-studio in development mode..." -NoNewline
try {
    pip install -e . -q 2>&1 | Out-Null
    Write-Host " ✅" -ForegroundColor Green
} catch {
    Write-Host " ⚠️  (may already be installed)" -ForegroundColor Yellow
}

# --------------------------------------------------
# 3. Generate Test Data
# --------------------------------------------------
Write-Host "`n[3/7] Generating test data..." -ForegroundColor Yellow
try {
    python scripts/generate_test_data.py 2>&1
    Write-Host "  ✅ Test data generated" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  Test data generation skipped (may need QGIS)" -ForegroundColor Yellow
}

# --------------------------------------------------
# 4. Setup QGIS Plugin
# --------------------------------------------------
Write-Host "`n[4/7] Setting up QGIS Plugin..." -ForegroundColor Yellow

$pluginSource = "$ProjectRoot\plugin\universal_ai_gis"
$qgisPluginDir = "$env:APPDATA\QGIS\QGIS3\profiles\default\python\plugins\universal_ai_gis"

if (Test-Path $pluginSource) {
    # Remove old plugin if exists
    if (Test-Path $qgisPluginDir) {
        Write-Host "  Removing old plugin..." -NoNewline
        Remove-Item -Recurse -Force $qgisPluginDir -ErrorAction SilentlyContinue
        Write-Host " ✅" -ForegroundColor Green
    }
    
    # Copy plugin
    Write-Host "  Copying plugin to QGIS profile..." -NoNewline
    Copy-Item -Path $pluginSource -Destination $qgisPluginDir -Recurse -Force
    Write-Host " ✅" -ForegroundColor Green
    
    # Verify metadata.txt
    if (Test-Path "$qgisPluginDir\metadata.txt") {
        Write-Host "  ✅ metadata.txt found" -ForegroundColor Green
    }
} else {
    Write-Host "  ❌ Plugin source not found at $pluginSource" -ForegroundColor Red
}

# --------------------------------------------------
# 5. Create Launch Scripts
# --------------------------------------------------
Write-Host "`n[5/7] Creating launch scripts..." -ForegroundColor Yellow

# MCP Server - Stdio
$stdioScript = @"
@echo off
cd /d "$ProjectRoot"
python -m mcp_server.main --transport stdio
"@
$stdioScript | Out-File -FilePath "$ProjectRoot\run_mcp_stdio.bat" -Encoding ASCII
Write-Host "  ✅ run_mcp_stdio.bat created" -ForegroundColor Green

# MCP Server - HTTP
$httpScript = @"
@echo off
cd /d "$ProjectRoot"
python -m mcp_server.main --transport streamable-http --port 8766
"@
$httpScript | Out-File -FilePath "$ProjectRoot\run_mcp_http.bat" -Encoding ASCII
Write-Host "  ✅ run_mcp_http.bat created" -ForegroundColor Green

# Test Client
$testScript = @"
@echo off
cd /d "$ProjectRoot"
python examples/python_client.py
"@
$testScript | Out-File -FilePath "$ProjectRoot\run_test_client.bat" -Encoding ASCII
Write-Host "  ✅ run_test_client.bat created" -ForegroundColor Green

# Full stack (bridge + mcp) - requires manual QGIS start
$fullScript = @"
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
"@
$fullScript | Out-File -FilePath "$ProjectRoot\run_full_stack.bat" -Encoding ASCII
Write-Host "  ✅ run_full_stack.bat created" -ForegroundColor Green

# --------------------------------------------------
# 6. Verify Installation
# --------------------------------------------------
Write-Host "`n[6/7] Verifying installation..." -ForegroundColor Yellow

# Test imports
$importTest = @"
import sys
sys.path.insert(0, r'$ProjectRoot')
try:
    import mcp_server.server
    import mcp_server.registry
    import mcp_server.qgis_client
    import mcp_server.verification
    import mcp_server.approval
    import mcp_server.resources.registry
    import mcp_server.prompts.registry
    print('ALL_IMPORTS_OK')
except Exception as e:
    print(f'IMPORT_ERROR: {e}')
    sys.exit(1)
"@

$result = python -c $importTest 2>&1
if ($result -like "*ALL_IMPORTS_OK*") {
    Write-Host "  ✅ All core modules import successfully" -ForegroundColor Green
} else {
    Write-Host "  ❌ Import failed: $result" -ForegroundColor Red
}

# Test registry builds
$registryTest = @"
import sys
sys.path.insert(0, r'$ProjectRoot')
from mcp_server.registry import build_registry
r = build_registry()
print(f'TOOLS: {len(r.all())}')
print(f'NAMESPACES: {r.namespaces()}')
"@
$result = python -c $registryTest 2>&1
Write-Host "  $result" -ForegroundColor Cyan

# --------------------------------------------------
# 7. Summary
# --------------------------------------------------
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "Setup complete! Press any key to exit..." -ForegroundColor Green
Read-Host
Write-Host "SETUP COMPLETE!" -ForegroundColor Green
Write-Host "============================================`n" -ForegroundColor Cyan

Write-Host "FILES CREATED:" -ForegroundColor Yellow
Write-Host "  $ProjectRoot\run_mcp_stdio.bat     - Start MCP server (stdio for OpenCode/Codex)"
Write-Host "  $ProjectRoot\run_mcp_http.bat      - Start MCP server (HTTP on port 8766)"
Write-Host "  $ProjectRoot\run_test_client.bat   - Run Python test client"
Write-Host "  $ProjectRoot\run_full_stack.bat    - Guided full stack launcher`n"

Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. Open QGIS" -ForegroundColor White
Write-Host "  2. Plugins > Manage and Install Plugins" -ForegroundColor White
Write-Host "  3. Enable 'Universal AI GIS Studio'" -ForegroundColor White
Write-Host "  4. Click Bridge toolbar button (chain icon) to start bridge on port 8765" -ForegroundColor White
Write-Host "  5. Run one of:" -ForegroundColor White
Write-Host "     .\run_mcp_stdio.bat    (for OpenCode/Codex/Claude Desktop)" -ForegroundColor Cyan
Write-Host "     .\run_mcp_http.bat     (for HTTP/curl/custom clients)" -ForegroundColor Cyan
Write-Host "     .\run_test_client.bat  (to test the connection)" -ForegroundColor Cyan

Write-Host "`nDOCUMENTATION:" -ForegroundColor Yellow
Write-Host "  $ProjectRoot\docs\GETTING_STARTED.md" -ForegroundColor White
Write-Host "  $ProjectRoot\docs\TOOL_REFERENCE.md" -ForegroundColor White
Write-Host "  $ProjectRoot\examples\python_client.py" -ForegroundColor White

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "Setup complete! Press any key to exit..." -ForegroundColor Green
Read-Host