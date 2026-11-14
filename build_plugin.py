#!/usr/bin/env python3
"""
Build script for Universal AI GIS Studio QGIS Plugin.

Creates a proper QGIS plugin zip file with all necessary files.
Includes backend modules since the plugin adds project root to sys.path.
"""

import os
import sys
import zipfile
import subprocess
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Set, Tuple

# Project paths
PROJECT_ROOT = Path(__file__).parent.resolve()
PLUGIN_SOURCE = PROJECT_ROOT / "plugin" / "universal_ai_gis"
DIST_DIR = PROJECT_ROOT / "dist"
PLUGIN_NAME = "universal_ai_gis"
VERSION = "1.0.0"

# Files and directories to EXCLUDE from the zip
EXCLUDE_PATTERNS: Set[str] = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "tests",
    "docs",
    "requirements",
    "migrations",
    "clusters",
    "agents",
    "skills",
    "workflows",
    "extensions",
    ".venv",
    "venv",
    ".env",
    "dist",
    "build",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".DS_Store",
    "Thumbs.db",
    "*.log",
    "*.sqlite",
    "*.db",
    "node_modules",
    ".idea",
    ".vscode",
    "*.egg-info",
    "*.dist-info",
}

# Backend modules that MUST be included (referenced via sys.path)
BACKEND_MODULES: List[str] = [
    "bridge",
    "core",
    "database",
    "integrations",
    "security",
    "monitoring",
    "engines",
    # Note: clusters, agents, etc. are excluded per requirements
    # but the plugin may need some of them - we'll include only what's directly imported
]

# Plugin-specific files that must be included
PLUGIN_REQUIRED_FILES: List[str] = [
    "metadata.txt",
    "__init__.py",
    "plugin.py",
    "main_window.py",
    "configurator.py",
    "compat.py",
    "constants.py",
    "resources/icon.png",      # Will be created if missing
    "about.html",              # Will be created if missing
]

def should_exclude(path: Path, root: Path) -> bool:
    """Check if a path should be excluded from the zip."""
    rel_path = path.relative_to(root)
    parts = rel_path.parts
    
    # Check each part against exclude patterns
    for part in parts:
        if part in EXCLUDE_PATTERNS:
            return True
        # Check glob patterns
        for pattern in EXCLUDE_PATTERNS:
            if pattern.startswith("*") and part.endswith(pattern[1:]):
                return True
    
    return False


def get_git_version() -> str:
    """Get version from git tags, fallback to commit hash."""
    try:
        # Try to get version from git tags (like v1.0.0 -> 1.0.0)
        result = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            # Remove leading 'v' if present (e.g., v1.0.0 -> 1.0.0)
            if version.startswith('v'):
                version = version[1:]
            return version
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return "1.0.0"


def get_git_info() -> Tuple[str, str]:
    """Get git commit hash and status."""
    try:
        # Get short commit hash
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5
        )
        commit_hash = result.stdout.strip() if result.returncode == 0 else "unknown"
        
        # Check if working tree is dirty
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5
        )
        dirty = "-dirty" if result.stdout.strip() else ""
        
        return commit_hash, dirty
    except (subprocess.SubprocessError, FileNotFoundError):
        return "unknown", ""


def create_version_file(build_dir: Path, version: str, commit_hash: str, dirty: str) -> Path:
    """Create version.json with build metadata."""
    version_data = {
        "version": version,
        "commit_hash": commit_hash,
        "dirty": bool(dirty),
        "build_date": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "build_date_local": datetime.now().isoformat(),
        "plugin_name": PLUGIN_NAME,
    }
    
    version_file = build_dir / "version.json"
    version_file.write_text(json.dumps(version_data, indent=2), encoding="utf-8")
    return version_file


def create_icon(build_dir: Path) -> Path:
    """Create a default icon.png if it doesn't exist."""
    icon_path = build_dir / "resources" / "icon.png"
    icon_path.parent.mkdir(parents=True, exist_ok=True)
    
    if icon_path.exists():
        return icon_path
    
    # Create a simple 32x32 PNG icon using pure Python (no PIL dependency)
    # This creates a minimal valid PNG with a blue square
    png_data = bytes.fromhex(
        "89504e470d0a1a0a"  # PNG signature
        "0000000d49484452"  # IHDR chunk header
        "00000020000000200802000000"  # 32x32, 8-bit, truecolor
        "fc18eda3"  # CRC
        "0000000173524742"  # sRGB chunk
        "00aece1ce9"  # CRC
        "0000000467414d41"  # gAMA chunk
        "0000b18f0bfc6105"  # CRC
        "0000000970485973"  # pHYs chunk
        "00000ec300000ec301c76fa864"  # CRC
        "0000001d49444154"  # IDAT chunk header
        "789c63606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "606060606060606060606060606060606060606060606060606060606060606060606060"
        "0000000000000000"
        "ffffffff"  # CRC (placeholder)
        "0000000049454e44ae426082"  # IEND chunk
    )
    
    # Note: The above is a placeholder. In reality, we'd use PIL or similar.
    # For now, let's create a minimal valid PNG using a simpler approach
    try:
        from qgis.PyQt.QtGui import QPixmap, QColor, QPainter
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 100, 200))  # Blue background
        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(painter.font())
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "AI")
        painter.end()
        pixmap.save(str(icon_path), "PNG")
    except ImportError:
        # Fallback: write a minimal valid PNG manually
        # 32x32 blue square PNG
        import zlib
        import struct
        
        width = 32
        height = 32
        # Create raw image data (RGBA, blue)
        raw_data = bytearray()
        for y in range(height):
            raw_data.append(0)  # Filter type
            for x in range(width):
                raw_data.extend([0, 100, 200, 255])  # RGBA Blue
        
        compressed = zlib.compress(bytes(raw_data))
        
        def chunk(chunk_type, data):
            return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xffffffff)
        
        png = (
            b"\x89PNG\r\n\x1a\n" +
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", compressed) +
            chunk(b"IEND", b"")
        )
        
        icon_path.write_bytes(png)
    
    return icon_path


def create_about_html(build_dir: Path) -> Path:
    """Create about.html if it doesn't exist."""
    about_path = build_dir / "about.html"
    
    if about_path.exists():
        return about_path
    
    html_content = """<!DOCTYPE html>
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
    <p class="version">Version 1.0.0</p>
    
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
</html>"""
    
    about_path.write_text(html_content, encoding="utf-8")
    return about_path


def copy_plugin_source(build_dir: Path) -> None:
    """Copy plugin source files to build directory."""
    plugin_build_dir = build_dir / PLUGIN_NAME
    plugin_build_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy required plugin files
    for file_name in PLUGIN_REQUIRED_FILES:
        src = PLUGIN_SOURCE / file_name
        dst = plugin_build_dir / file_name
        
        if file_name in ("resources/icon.png", "about.html"):
            # These are created, not copied
            continue
            
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
        else:
            print(f"WARNING: Required file not found: {src}")


def copy_backend_modules(build_dir: Path) -> None:
    """Copy backend modules that the plugin imports via sys.path.
    
    Structure in zip:
    universal_ai_gis/       <- plugin package (at zip root)
      metadata.txt
      __init__.py
      plugin.py
      ...
      bridge/               <- backend module INSIDE plugin package
        bridge_server.py
        ...
      core/                 <- backend module inside plugin package
        config.py
        ...
      database/
      integrations/
    
    The plugin adds _PLUGIN_DIR to sys.path, so backend modules
    inside the plugin package are importable as bridge.executor, core.config, etc.
    """
    
    plugin_build_dir = build_dir / PLUGIN_NAME
    
    for module in BACKEND_MODULES:
        src = PROJECT_ROOT / module
        dst = plugin_build_dir / module
        
        if src.exists() and src.is_dir():
            copy_directory(src, dst)
        else:
            print(f"WARNING: Backend module not found: {src}")


def copy_directory(src: Path, dst: Path) -> None:
    """Copy directory recursively, respecting exclude patterns."""
    dst.mkdir(parents=True, exist_ok=True)
    
    for item in src.rglob("*"):
        if item.is_file():
            # Check if we should exclude this file
            rel = item.relative_to(src)
            if should_exclude(item, src):
                continue
            
            dst_file = dst / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            dst_file.write_bytes(item.read_bytes())


def create_zip(build_dir: Path, output_path: Path) -> None:
    """Create the final plugin zip file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path in build_dir.rglob("*"):
            if file_path.is_file():
                # Archive path relative to build_dir
                arcname = file_path.relative_to(build_dir)
                zf.write(file_path, arcname)
                print(f"  Added: {arcname}")


def validate_zip(zip_path: Path) -> List[str]:
    """Validate the generated zip file structure."""
    errors = []
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        namelist = zf.namelist()
        
        # Check required files exist
        required_in_zip = [
            f"{PLUGIN_NAME}/metadata.txt",
            f"{PLUGIN_NAME}/__init__.py",
            f"{PLUGIN_NAME}/plugin.py",
            f"{PLUGIN_NAME}/resources/icon.png",
            f"{PLUGIN_NAME}/about.html",
        ]
        
        for req in required_in_zip:
            if req not in namelist:
                errors.append(f"Missing required file in zip: {req}")
        
        # Check backend modules (inside plugin package)
        for module in BACKEND_MODULES:
            module_files = [n for n in namelist if n.startswith(f"{PLUGIN_NAME}/{module}/")]
            if not module_files:
                errors.append(f"Missing backend module: {PLUGIN_NAME}/{module}/")
        
        # Validate metadata.txt format
        try:
            metadata_content = zf.read(f"{PLUGIN_NAME}/metadata.txt").decode('utf-8')
            required_fields = ['name', 'version', 'description', 'qgisMinimumVersion', 'author']
            for field in required_fields:
                if f"{field}=" not in metadata_content:
                    errors.append(f"metadata.txt missing required field: {field}")
        except KeyError:
            errors.append("metadata.txt not found in zip")
        except UnicodeDecodeError:
            errors.append("metadata.txt is not valid UTF-8")
        
        # Check __init__.py has classFactory
        try:
            init_content = zf.read(f"{PLUGIN_NAME}/__init__.py").decode('utf-8')
            if "def classFactory" not in init_content:
                errors.append("__init__.py missing classFactory function")
            if "UniversalAIGISPlugin" not in init_content:
                errors.append("__init__.py doesn't import UniversalAIGISPlugin")
        except KeyError:
            errors.append("__init__.py not found in zip")
        
        # Check plugin.py has UniversalAIGISPlugin class
        try:
            plugin_content = zf.read(f"{PLUGIN_NAME}/plugin.py").decode('utf-8')
            if "class UniversalAIGISPlugin" not in plugin_content:
                errors.append("plugin.py missing UniversalAIGISPlugin class")
        except KeyError:
            errors.append("plugin.py not found in zip")
        
        # Check icon.png is valid (basic check)
        try:
            icon_data = zf.read(f"{PLUGIN_NAME}/resources/icon.png")
            if not icon_data.startswith(b'\x89PNG\r\n\x1a\n'):
                errors.append("icon.png is not a valid PNG file")
            if len(icon_data) < 100:
                errors.append("icon.png seems too small (possibly corrupt)")
        except KeyError:
            errors.append("icon.png not found in zip")
        
        # Check about.html exists
        try:
            about_content = zf.read(f"{PLUGIN_NAME}/about.html").decode('utf-8')
            if "<html" not in about_content.lower() and "<!doctype html" not in about_content.lower():
                errors.append("about.html doesn't appear to be valid HTML")
        except KeyError:
            errors.append("about.html not found in zip")
    
    return errors


def main():
    """Main build function."""
    # Get git version (from tags or commit)
    git_version = get_git_version()
    commit_hash, dirty = get_git_info()
    version_with_hash = f"{git_version}+{commit_hash}{dirty}"
    print("=" * 60)
    print(f"Building {PLUGIN_NAME} v{git_version}")
    print("=" * 60)
    print(f"Git version: {git_version}")
    print(f"Git commit: {commit_hash}{dirty}")
    
    # Create build directory
    build_dir = PROJECT_ROOT / "build" / PLUGIN_NAME
    if build_dir.exists():
        import shutil
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)
    
    print(f"\nBuild directory: {build_dir}")
    
    # Copy plugin source
    print("\nCopying plugin source...")
    copy_plugin_source(build_dir)
    
    # Copy backend modules
    print("\nCopying backend modules...")
    copy_backend_modules(build_dir)
    
    # Update metadata.txt with git version
    print("\nUpdating metadata.txt with git version...")
    metadata_path = build_dir / PLUGIN_NAME / "metadata.txt"
    if metadata_path.exists():
        content = metadata_path.read_text(encoding="utf-8")
        # Replace version line
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("version="):
                lines[i] = f"version={git_version}"
                break
        metadata_path.write_text("\n".join(lines), encoding="utf-8")
    
    # Update constants.py with git version
    print("Updating constants.py with git version...")
    constants_path = build_dir / PLUGIN_NAME / "constants.py"
    if constants_path.exists():
        content = constants_path.read_text(encoding="utf-8")
        # Replace plugin_version line
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("plugin_version"):
                lines[i] = f'plugin_version = "{git_version}"'
                break
        constants_path.write_text("\n".join(lines), encoding="utf-8")
    
    # Create resources
    print("\nCreating resources...")
    create_icon(build_dir / PLUGIN_NAME)
    create_about_html(build_dir / PLUGIN_NAME)
    
    # Create version file
    print("\nCreating version file...")
    create_version_file(build_dir / PLUGIN_NAME, git_version, commit_hash, dirty)
    
    # Create zip
    print("\nCreating zip archive...")
    zip_name = f"{PLUGIN_NAME}-{git_version}.zip"
    zip_path = DIST_DIR / zip_name
    create_zip(build_dir, zip_path)
    
    # Validate zip
    print("\nValidating zip...")
    errors = validate_zip(zip_path)
    
    if errors:
        print("\n[ERROR] VALIDATION ERRORS:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("\n[OK] Validation passed!")
    
    # Print summary
    version_with_hash = f"{git_version}+{commit_hash}{dirty}"
    print("\n" + "=" * 60)
    print("BUILD SUCCESSFUL")
    print("=" * 60)
    print(f"Output: {zip_path}")
    print(f"Size: {zip_path.stat().st_size / 1024:.1f} KB")
    print(f"Version: {version_with_hash}")
    print("=" * 60)


if __name__ == "__main__":
    main()