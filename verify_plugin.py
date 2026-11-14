#!/usr/bin/env python3
"""
Verification script for Universal AI GIS Studio QGIS Plugin zip.

Inspects the generated zip for correctness:
- Validates metadata.txt format
- Checks icon.png exists and is valid
- Checks about.html exists
- Verifies __init__.py has classFactory
- Verifies plugin.py has UniversalAIGISPlugin class
- Validates overall zip structure
"""

import zipfile
import sys
import json
from pathlib import Path
from typing import List, Tuple, Optional


def verify_zip(zip_path: Path) -> Tuple[bool, List[str], List[str]]:
    """
    Verify the plugin zip file.
    
    Returns:
        Tuple of (success, errors, warnings)
    """
    errors = []
    warnings = []
    
    if not zip_path.exists():
        errors.append(f"Zip file not found: {zip_path}")
        return False, errors, warnings
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        namelist = zf.namelist()
        
        # Determine the plugin root directory in the zip
        # Should be the first directory entry
        plugin_root = None
        for name in namelist:
            if name.endswith('/') and 'universal_ai_gis' in name:
                plugin_root = name.rstrip('/')
                break
        
        if not plugin_root:
            # Try to find it from file paths
            for name in namelist:
                if 'metadata.txt' in name:
                    plugin_root = name.rsplit('/', 1)[0]
                    break
        
        if not plugin_root:
            errors.append("Could not determine plugin root directory in zip")
            return False, errors, warnings
        
        print(f"Plugin root in zip: {plugin_root}")
        
        # 1. Check required files exist
        required_files = [
            "metadata.txt",
            "__init__.py",
            "plugin.py",
            "resources/icon.png",
            "about.html",
        ]
        
        print("\n[1] Checking required files...")
        for req in required_files:
            full_path = f"{plugin_root}/{req}"
            if full_path in namelist:
                print(f"  [OK] {req}")
            else:
                errors.append(f"Missing required file: {req}")
                print(f"  [MISSING] {req}")
        
        # 2. Validate metadata.txt
        print("\n[2] Validating metadata.txt...")
        metadata_path = f"{plugin_root}/metadata.txt"
        if metadata_path in namelist:
            try:
                content = zf.read(metadata_path).decode('utf-8')
                required_fields = [
                    'name=', 'version=', 'description=', 
                    'qgisMinimumVersion=', 'author=', 'icon=', 'about='
                ]
                for field in required_fields:
                    if field not in content:
                        errors.append(f"metadata.txt missing required field: {field.rstrip('=')}")
                        print(f"  [ERROR] Missing field: {field.rstrip('=')}")
                    else:
                        # Extract value
                        for line in content.split('\n'):
                            if line.startswith(field):
                                print(f"  [OK] {line.strip()}")
                                break
                
                # Check icon path matches
                if 'icon=resources/icon.png' not in content:
                    warnings.append("metadata.txt icon path may not match actual location")
                if 'about=about.html' not in content:
                    warnings.append("metadata.txt about path may not match actual location")
                    
            except UnicodeDecodeError:
                errors.append("metadata.txt is not valid UTF-8")
        else:
            errors.append("metadata.txt not found in zip")
        
        # 3. Check icon.png
        print("\n[3] Checking icon.png...")
        icon_path = f"{plugin_root}/resources/icon.png"
        if icon_path in namelist:
            icon_data = zf.read(icon_path)
            if icon_data.startswith(b'\x89PNG\r\n\x1a\n'):
                print(f"  [OK] Valid PNG file ({len(icon_data)} bytes)")
                if len(icon_data) < 100:
                    warnings.append("icon.png is very small, may be a placeholder")
            else:
                errors.append("icon.png is not a valid PNG file (missing PNG signature)")
                print(f"  [ERROR] Invalid PNG signature")
        else:
            errors.append("resources/icon.png not found in zip")
        
        # 4. Check about.html
        print("\n[4] Checking about.html...")
        about_path = f"{plugin_root}/about.html"
        if about_path in namelist:
            try:
                content = zf.read(about_path).decode('utf-8')
                if '<html' in content.lower() or '<!doctype html' in content.lower():
                    print(f"  [OK] Valid HTML file ({len(content)} bytes)")
                    if 'Universal AI GIS Studio' in content:
                        print(f"  [OK] Contains plugin name")
                    else:
                        warnings.append("about.html doesn't contain plugin name")
                else:
                    warnings.append("about.html doesn't appear to be valid HTML")
            except UnicodeDecodeError:
                errors.append("about.html is not valid UTF-8")
        else:
            errors.append("about.html not found in zip")
        
        # 5. Check __init__.py has classFactory
        print("\n[5] Checking __init__.py...")
        init_path = f"{plugin_root}/__init__.py"
        if init_path in namelist:
            try:
                content = zf.read(init_path).decode('utf-8')
                if 'def classFactory' in content:
                    print(f"  [OK] Contains classFactory function")
                else:
                    errors.append("__init__.py missing classFactory function")
                
                if 'UniversalAIGISPlugin' in content:
                    print(f"  [OK] Imports UniversalAIGISPlugin")
                else:
                    errors.append("__init__.py doesn't import UniversalAIGISPlugin")
                    
            except UnicodeDecodeError:
                errors.append("__init__.py is not valid UTF-8")
        else:
            errors.append("__init__.py not found in zip")
        
        # 6. Check plugin.py has UniversalAIGISPlugin class
        print("\n[6] Checking plugin.py...")
        plugin_path = f"{plugin_root}/plugin.py"
        if plugin_path in namelist:
            try:
                content = zf.read(plugin_path).decode('utf-8')
                if 'class UniversalAIGISPlugin' in content:
                    print(f"  [OK] Contains UniversalAIGISPlugin class")
                else:
                    errors.append("plugin.py missing UniversalAIGISPlugin class")
                
                # Check for key methods
                key_methods = ['initGui', 'unload', '_init_core', '_start_bridge', '_create_ui']
                for method in key_methods:
                    if f'def {method}' in content:
                        print(f"  [OK] Contains {method} method")
                    else:
                        warnings.append(f"plugin.py missing {method} method")
                        
            except UnicodeDecodeError:
                errors.append("plugin.py is not valid UTF-8")
        else:
            errors.append("plugin.py not found in zip")
        
        # 7. Check backend modules
        print("\n[7] Checking backend modules...")
        backend_modules = ['bridge', 'core', 'database']
        for module in backend_modules:
            module_files = [n for n in namelist if n.startswith(f"{module}/")]
            if module_files:
                print(f"  [OK] {module}/ ({len(module_files)} files)")
            else:
                errors.append(f"Missing backend module: {module}/")
        
        # 8. Check version.json
        print("\n[8] Checking version.json...")
        version_path = f"{plugin_root}/version.json"
        if version_path in namelist:
            try:
                content = zf.read(version_path).decode('utf-8')
                version_data = json.loads(content)
                required_version_fields = ['version', 'commit_hash', 'build_date', 'plugin_name']
                for field in required_version_fields:
                    if field in version_data:
                        print(f"  [OK] version.json has {field}: {version_data[field]}")
                    else:
                        warnings.append(f"version.json missing field: {field}")
            except (UnicodeDecodeError, json.JSONDecodeError):
                errors.append("version.json is not valid JSON")
        else:
            warnings.append("version.json not found in zip")
        
        # 9. Check for excluded directories
        print("\n[9] Checking excluded directories are not present...")
        excluded = ['tests', 'docs', 'requirements', 'engines', 'clusters', 
                    'integrations', 'agents', 'skills', 'workflows', 
                    'extensions', 'monitoring', 'security', '__pycache__', 
                    '.git', '.pytest_cache']
        for excl in excluded:
            found = [n for n in namelist if f"/{excl}/" in n or n.startswith(f"{excl}/")]
            if found:
                warnings.append(f"Excluded directory '{excl}' found in zip: {found[:3]}")
            else:
                print(f"  [OK] {excl}/ not present")
        
        # 10. Overall structure check
        print("\n[10] Overall structure...")
        print(f"  Total files in zip: {len(namelist)}")
        total_size = sum(zf.getinfo(n).file_size for n in namelist)
        print(f"  Total uncompressed size: {total_size / 1024:.1f} KB")
    
    return len(errors) == 0, errors, warnings


def simulate_qgis_install(zip_path: Path) -> Tuple[bool, List[str]]:
    """
    Simulate QGIS plugin installation by extracting and checking structure.
    """
    errors = []
    
    import tempfile
    import shutil
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Extract zip
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(tmpdir)
        
        # Find plugin directory
        plugin_dirs = [d for d in tmpdir.iterdir() if d.is_dir() and 'universal_ai_gis' in d.name]
        if not plugin_dirs:
            errors.append("No plugin directory found after extraction")
            return False, errors
        
        plugin_dir = plugin_dirs[0]
        print(f"\n[Simulation] Extracted to: {plugin_dir}")
        
        # Check that __init__.py can be imported (syntax check)
        init_file = plugin_dir / "__init__.py"
        if init_file.exists():
            try:
                compile(init_file.read_text(encoding='utf-8'), str(init_file), 'exec')
                print(f"  [OK] __init__.py syntax valid")
            except SyntaxError as e:
                errors.append(f"__init__.py syntax error: {e}")
        
        # Check that plugin.py can be imported (syntax check)
        plugin_file = plugin_dir / "plugin.py"
        if plugin_file.exists():
            try:
                compile(plugin_file.read_text(encoding='utf-8'), str(plugin_file), 'exec')
                print(f"  [OK] plugin.py syntax valid")
            except SyntaxError as e:
                errors.append(f"plugin.py syntax error: {e}")
        
        # Check that backend modules are importable (syntax check)
        for module in ['bridge', 'core', 'database']:
            module_dir = tmpdir / module
            if module_dir.exists():
                for py_file in module_dir.rglob("*.py"):
                    try:
                        compile(py_file.read_text(encoding='utf-8'), str(py_file), 'exec')
                    except SyntaxError as e:
                        errors.append(f"{py_file.relative_to(tmpdir)} syntax error: {e}")
        
        if not errors:
            print(f"  [OK] All Python files have valid syntax")
    
    return len(errors) == 0, errors


def main():
    """Main verification function."""
    if len(sys.argv) < 2:
        # Default to dist folder
        zip_path = Path(__file__).parent / "dist" / "universal_ai_gis_studio-1.0.0.zip"
    else:
        zip_path = Path(sys.argv[1])
    
    print("=" * 60)
    print(f"Verifying: {zip_path}")
    print("=" * 60)
    
    # Verify zip structure
    success, errors, warnings = verify_zip(zip_path)
    
    # Simulate QGIS install
    print("\n" + "=" * 60)
    print("Simulating QGIS plugin installation...")
    print("=" * 60)
    sim_success, sim_errors = simulate_qgis_install(zip_path)
    errors.extend(sim_errors)
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  [WARN] {w}")
    
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  [ERROR] {e}")
        print("\n[FAIL] Verification failed!")
        return 1
    else:
        print("\n[PASS] All checks passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())