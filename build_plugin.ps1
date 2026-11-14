<#
.SYNOPSIS
    Build script for Universal AI GIS Studio QGIS Plugin (PowerShell version).

.DESCRIPTION
    Creates a proper QGIS plugin zip file with all necessary files.
    Includes backend modules since the plugin adds project root to sys.path.

.NOTES
    Run from the Universal-AI-GIS-Studio directory.
#>

param(
    [string]$Version = "1.0.0",
    [string]$OutputDir = "dist"
)

$ErrorActionPreference = "Stop"

# Project paths
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PluginSource = Join-Path $ProjectRoot "plugin\universal_ai_gis"
$DistDir = Join-Path $ProjectRoot $OutputDir
$PluginName = "universal_ai_gis_studio"
$BuildDir = Join-Path (Join-Path $ProjectRoot "build") $PluginName

Write-Host "=" * 60
Write-Host "Building $PluginName v$Version"
Write-Host "=" * 60

# Get git info
try {
    $CommitHash = (git rev-parse --short HEAD 2>$null).Trim()
    if (-not $CommitHash) { $CommitHash = "unknown" }
    $Dirty = if (git status --porcelain 2>$null) { "-dirty" } else { "" }
} catch {
    $CommitHash = "unknown"
    $Dirty = ""
}
Write-Host "Git commit: $CommitHash$Dirty"

# Clean and create build directory
if (Test-Path $BuildDir) {
    Remove-Item $BuildDir -Recurse -Force
}
New-Item -ItemType Directory -Path $BuildDir | Out-Null

# Plugin build directory (inside build dir)
$PluginBuildDir = Join-Path $BuildDir $PluginName
New-Item -ItemType Directory -Path $PluginBuildDir | Out-Null

# Files and directories to EXCLUDE
$ExcludePatterns = @(
    "__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "tests", "docs", "requirements", "migrations", "engines", "clusters",
    "integrations", "agents", "skills", "workflows", "extensions",
    "monitoring", "security", ".venv", "venv", ".env", "dist", "build",
    "*.pyc", "*.pyo", "*.pyd", ".DS_Store", "Thumbs.db", "*.log",
    "*.sqlite", "*.db", "node_modules", ".idea", ".vscode",
    "*.egg-info", "*.dist-info"
)

# Backend modules that MUST be included
$BackendModules = @("bridge", "core", "database")

# Plugin-specific files that must be included
$PluginRequiredFiles = @(
    "metadata.txt", "__init__.py", "plugin.py", "main_window.py"
)

function Should-Exclude($Path, $Root) {
    $RelPath = $Path.Substring($Root.Length + 1)
    $Parts = $RelPath -split '[\\/]'
    
    foreach ($Part in $Parts) {
        if ($ExcludePatterns -contains $Part) {
            return $true
        }
        foreach ($Pattern in $ExcludePatterns) {
            if ($Pattern -like "*" + $Part) { return $true }
            if ($Part -like $Pattern) { return $true }
        }
    }
    return $false
}

function Copy-Directory($Src, $Dst) {
    if (-not (Test-Path $Dst)) {
        New-Item -ItemType Directory -Path $Dst | Out-Null
    }
    
    Get-ChildItem $Src -Recurse -File | ForEach-Object {
        if (-not (Should-Exclude $_.FullName $Src)) {
            $RelPath = $_.FullName.Substring($Src.Length + 1)
            $DstFile = Join-Path $Dst $RelPath
            $DstDir = Split-Path -Parent $DstFile
            if (-not (Test-Path $DstDir)) {
                New-Item -ItemType Directory -Path $DstDir | Out-Null
            }
            Copy-Item $_.FullName -Destination $DstFile -Force
        }
    }
}

# Copy plugin source
Write-Host "`nCopying plugin source..."
foreach ($File in $PluginRequiredFiles) {
    $Src = Join-Path $PluginSource $File
    $Dst = Join-Path $PluginBuildDir $File
    if (Test-Path $Src) {
        Copy-Item $Src -Destination $Dst -Force
        Write-Host "  Copied: $File"
    } else {
        Write-Warning "Required file not found: $Src"
    }
}

# Copy backend modules
Write-Host "`nCopying backend modules..."
foreach ($Module in $BackendModules) {
    $Src = Join-Path $ProjectRoot $Module
    $Dst = Join-Path (Split-Path -Parent $PluginBuildDir) $Module
    if (Test-Path $Src) {
        Copy-Directory $Src $Dst
        Write-Host "  Copied: $Module/"
    } else {
        Write-Warning "Backend module not found: $Src"
    }
}

# Create resources
Write-Host "`nCreating resources..."

# Create icon.png
$IconPath = Join-Path $PluginBuildDir "resources\icon.png"
$IconDir = Split-Path -Parent $IconPath
if (-not (Test-Path $IconDir)) {
    New-Item -ItemType Directory -Path $IconDir | Out-Null
}

if (-not (Test-Path $IconPath)) {
    # Create minimal valid PNG (32x32 blue square) using .NET
    Add-Type -AssemblyName System.Drawing
    $Bitmap = New-Object System.Drawing.Bitmap(32, 32)
    $Graphics = [System.Drawing.Graphics]::FromImage($Bitmap)
    $Graphics.Clear([System.Drawing.Color]::FromArgb(0, 100, 200))
    $Bitmap.Save($IconPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $Graphics.Dispose()
    $Bitmap.Dispose()
    Write-Host "  Created: resources/icon.png"
}

# Create about.html
$AboutPath = Join-Path $PluginBuildDir "about.html"
if (-not (Test-Path $AboutPath)) {
    $HtmlContent = @"
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Universal AI GIS Studio - About</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }
        h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; margin-top: 25px; }
        .version { color: #7f8c8d; font-size: 0.9em; }
        .feature { margin: 10px 0; padding-left: 20px; }
        .feature::before { content: "▸ "; color: #3498db; }
        a { color: #3498db; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .footer { margin-top: 30px; padding-top: 15px; border-top: 1px solid #ecf0f1; color: #95a5a6; font-size: 0.85em; }
    </style>
</head>
<body>
    <h1>Universal AI GIS Studio</h1>
    <p class="version">Version $Version</p>
    
    <p>MCP-first AI-controlled QGIS automation platform. Provides a QGIS Bridge, 
    MCP server integration, visual automation, AI cursor, georeferencing, and 25 GIS functional clusters.</p>
    
    <h2>Key Features</h2>
    <div class="feature">QGIS Bridge — Localhost HTTP server for PyQGIS execution</div>
    <div class="feature">MCP Server Integration — Model Context Protocol for AI agents</div>
    <div class="feature">Visual Automation — Screen capture, cursor control, window detection</div>
    <div class="feature">AI Cursor — Visual overlay with smooth movement, highlighting, trails</div>
    <div class="feature">Georeferencing Engine — Auto georeference scanned maps using CV</div>
    <div class="feature">25 GIS Functional Clusters — M01 through M25 covering all GIS domains</div>
    <div class="feature">Agent Manager — 29 built-in specialized GIS agents</div>
    <div class="feature">Skill Manager — Import and validate custom skills</div>
    <div class="feature">Workflow Builder — Visual GIS workflow creation</div>
    <div class="feature">Macro Recorder — Record and replay GIS operations</div>
    <div class="feature">Visual Verification — SSIM-based image comparison</div>
    <div class="feature">Security & Permissions — Audit logs, approval workflows</div>
    
    <h2>Architecture</h2>
    <p>The plugin runs inside QGIS Desktop and starts a local Bridge Server (HTTP + WebSocket) 
    that external AI agents connect to via MCP. All PyQGIS operations execute on the QGIS main thread.</p>
    
    <h2>Links</h2>
    <ul>
        <li><a href="https://example.com/universal-ai-gis-studio">Homepage</a></li>
        <li><a href="https://example.com/universal-ai-gis-studio">Repository</a></li>
    </ul>
    
    <div class="footer">
        &copy; 2024 Universal AI GIS Studio. Licensed under MIT.
        <br>Built with Python, PyQt6, and QGIS.
    </div>
</body>
</html>
"@
    Set-Content -Path $AboutPath -Value $HtmlContent -Encoding UTF8
    Write-Host "  Created: about.html"
}

# Create version.json
Write-Host "`nCreating version file..."
$VersionData = @{
    version = $Version
    commit_hash = $CommitHash
    dirty = ($Dirty -ne "")
    build_date = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
    build_date_local = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss.fff")
    plugin_name = $PluginName
} | ConvertTo-Json -Depth 3

$VersionPath = Join-Path $PluginBuildDir "version.json"
Set-Content -Path $VersionPath -Value $VersionData -Encoding UTF8
Write-Host "  Created: version.json"

# Create zip
Write-Host "`nCreating zip archive..."
if (-not (Test-Path $DistDir)) {
    New-Item -ItemType Directory -Path $DistDir | Out-Null
}

$ZipName = "$PluginName-$Version.zip"
$ZipPath = Join-Path $DistDir $ZipName

# Remove existing zip
if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}

# Use .NET to create zip - need to zip from the parent of $PluginBuildDir so plugin is at root
$ZipRoot = Split-Path -Parent $PluginBuildDir
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($ZipRoot, $ZipPath, [System.IO.Compression.CompressionLevel]::Optimal, $false)

Write-Host "  Created: $ZipPath"

# Validate zip
Write-Host "`nValidating zip..."
$Errors = @()

# Open zip and check contents
$Zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
$Entries = $Zip.Entries

# Debug: list all entries
# $Entries | ForEach-Object { Write-Host "Entry: $($_.FullName)" }

# Check required files
$RequiredInZip = @(
    "$PluginName/metadata.txt",
    "$PluginName/__init__.py",
    "$PluginName/plugin.py",
    "$PluginName/resources/icon.png",
    "$PluginName/about.html"
)

foreach ($Req in $RequiredInZip) {
    $Found = $false
    foreach ($Entry in $Entries) {
        # Fix: use double backslash for single literal backslash in regex
        $EntryPath = [string]$Entry.FullName -replace '\\', '/'
        if ($EntryPath -eq $Req) {
            $Found = $true
            break
        }
    }
    if (-not $Found) {
        $Errors += "Missing required file in zip: $Req"
    }
}

# Check backend modules
foreach ($Module in $BackendModules) {
    $Found = $false
    foreach ($Entry in $Entries) {
        $EntryPath = [string]$Entry.FullName -replace '\\', '/'
        if ($EntryPath -like "$Module/*") {
            $Found = $true
            break
        }
    }
    if (-not $Found) {
        $Errors += "Missing backend module: $Module/"
    }
}

# Validate metadata.txt
$MetadataEntry = $Entries | Where-Object { ([string]$_.FullName -replace '\\', '/') -eq "$PluginName/metadata.txt" }
if ($MetadataEntry) {
    $Stream = $MetadataEntry.Open()
    $Reader = New-Object System.IO.StreamReader($Stream, [System.Text.Encoding]::UTF8)
    $Content = $Reader.ReadToEnd()
    $Reader.Close()
    $Stream.Close()
    
    $RequiredFields = @('name=', 'version=', 'description=', 'qgisMinimumVersion=', 'author=')
    foreach ($Field in $RequiredFields) {
        if ($Content -notmatch [regex]::Escape($Field)) {
            $Errors += "metadata.txt missing required field: $($Field.TrimEnd('='))"
        }
    }
}

# Check __init__.py
$InitEntry = $Entries | Where-Object { ([string]$_.FullName -replace '\\', '/') -eq "$PluginName/__init__.py" }
if ($InitEntry) {
    $Stream = $InitEntry.Open()
    $Reader = New-Object System.IO.StreamReader($Stream, [System.Text.Encoding]::UTF8)
    $Content = $Reader.ReadToEnd()
    $Reader.Close()
    $Stream.Close()
    
    if ($Content -notmatch "def classFactory") {
        $Errors += "__init__.py missing classFactory function"
    }
    if ($Content -notmatch "UniversalAIGISPlugin") {
        $Errors += "__init__.py doesn't import UniversalAIGISPlugin"
    }
}

# Check plugin.py
$PluginEntry = $Entries | Where-Object { ([string]$_.FullName -replace '\\', '/') -eq "$PluginName/plugin.py" }
if ($PluginEntry) {
    $Stream = $PluginEntry.Open()
    $Reader = New-Object System.IO.StreamReader($Stream, [System.Text.Encoding]::UTF8)
    $Content = $Reader.ReadToEnd()
    $Reader.Close()
    $Stream.Close()
    
    if ($Content -notmatch "class UniversalAIGISPlugin") {
        $Errors += "plugin.py missing UniversalAIGISPlugin class"
    }
}

# Check icon.png
$IconEntry = $Entries | Where-Object { $_.FullName -eq "$PluginName/resources/icon.png" }
if ($IconEntry) {
    $Stream = $IconEntry.Open()
    $Bytes = New-Object byte[] 8
    $Stream.Read($Bytes, 0, 8) | Out-Null
    $Stream.Close()
    $PngSignature = [byte[]]@(0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A)
    if (-not ($Bytes -ceq $PngSignature)) {
        $Errors += "icon.png is not a valid PNG file"
    }
}

$Zip.Dispose()

if ($Errors.Count -gt 0) {
    Write-Host "`n[ERROR] VALIDATION ERRORS:" -ForegroundColor Red
    foreach ($Err in $Errors) {
        Write-Host "  - $Err" -ForegroundColor Red
    }
    exit 1
} else {
    Write-Host "`n[OK] Validation passed!" -ForegroundColor Green
}

# Print summary
Write-Host "`n" + "=" * 60
Write-Host "BUILD SUCCESSFUL" -ForegroundColor Green
Write-Host "=" * 60
Write-Host "Output: $ZipPath"
$ZipSize = (Get-Item $ZipPath).Length / 1KB
Write-Host "Size: $([math]::Round($ZipSize, 1)) KB"
Write-Host "Version: $Version+$CommitHash$Dirty"
Write-Host "=" * 60