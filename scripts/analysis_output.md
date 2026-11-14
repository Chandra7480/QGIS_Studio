# Scripts Folder Analysis — Universal AI GIS Studio

**Task:** task-18  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent  
**Context:** requirements/ (task-17) analysis read prior

---

## 1. Folder Structure

```
scripts/
├── build_release.py           # Release ZIP builder (66 lines)
├── generate_test_data.py      # Synthetic test data generator (343 lines)
└── __pycache__/
```

**Total:** 2 Python scripts, ~410 lines

---

## 2. Script Analysis

### 2.1 `build_release.py` — Release ZIP Builder

**Purpose:** Creates two distribution ZIPs for release:
1. **QGIS Plugin ZIP** — `universal_ai_gis_plugin.zip` for QGIS Plugin Manager
2. **Full Platform ZIP** — `universal-ai-gis-studio-1.0.0.zip` with complete source

**Key Features:**
- Excludes `__pycache__`, `.pytest_cache`, `.pyc`, `.pyo` files
- Plugin ZIP uses `plugin/universal_ai_gis` as source root
- Platform ZIP includes 14 directories + 4 root files
- Uses `zipfile.ZIP_DEFLATED` compression

**Strengths:**
- Clean, single-responsibility script
- Proper exclusion of cache/compiled files
- Hardcoded version `1.0.0` in filename (should be dynamic)
- Clear output messages

**Issues:**
| Issue | Severity | Description |
|-------|----------|-------------|
| **Hardcoded version** | Medium | `1.0.0` hardcoded in line 34; should read from pyproject.toml |
| **No verification** | Medium | No checksum generation, no size validation |
| **No manifest** | Low | No manifest.json with file list, sizes, hashes |
| **No cleanup on failure** | Low | Partial ZIPs left on error |
| **Hardcoded paths** | Low | Assumes specific directory structure; not configurable |
| **No compression level control** | Low | Uses default ZIP_DEFLATED; no option for compression level |

### 2.2 `generate_test_data.py` — Synthetic Test Data Generator

**Purpose:** Generates synthetic geospatial test data for integration tests:
- `sample.gpkg` — Vector data (points, lines, polygons, multipolygons)
- `dem.tif` — Single-band DEM (Float32) with synthetic terrain
- `rgb.tif` — 3-band RGB (Byte) with synthetic patterns
- `scan_map.tif` — Unreferenced TIFF for georeferencing tests
- `reference.tif` — Copy of DEM for GCP reference

**Strengths:**
- Comprehensive synthetic data generation using GDAL/OGR
- Realistic synthetic terrain with hills, valleys, ridges, valleys, noise
- Proper georeferencing (UTM zone 18N, EPSG:32618)
- Distinct patterns for feature matching (grid lines, diagonals)
- Reproducible (fixed random seeds)
- Clean CLI with `--output-dir`, `--clean` options
- Copies DEM as reference for georeferencing tests

**Code Quality:**
| Aspect | Assessment |
|--------|------------|
| **Modularity** | Good — separate functions per data type |
| **Documentation** | Excellent — docstrings, comments, CLI help |
| **Error Handling** | Good — deletes existing files, handles missing dirs |
| **Reproducibility** | Excellent — fixed random seeds (42, 123) |
| **GIS Correctness** | Excellent — proper CRS, geotransforms, no-data values |

**Issues:**
| Issue | Severity | Description |
|-------|----------|-------------|
| **No test** | Medium | No unit test for data generator itself |
| **Hardcoded output dir** | Low | Defaults to `tests/fixtures/data`; should be configurable via env var |
| **No size limits** | Low | No option to limit file sizes for CI |
| **No format options** | Low | Only GeoPackage/GeoTIFF; no Shapefile, GeoJSON options |
| **No metadata injection** | Low | No option to inject custom metadata into generated files |

---

## 3. Missing Scripts

| Missing Script | Purpose | Priority |
|----------------|---------|----------|
| `scripts/run_tests.py` | Unified test runner with coverage | High |
| `scripts/install_plugin.py` | Automated QGIS plugin installation | Medium |
| `scripts/validate_schemas.py` | Validate all JSON schemas in registry | Medium |
| `scripts/check_deps.py` | Verify dependency versions match pyproject.toml | Medium |
| `scripts/generate_docs.py` | Auto-generate docs from code | Low |
| `scripts/bump_version.py` | Version bump automation | Low |
| `scripts/docker_build.py` | Docker image build (if containerized) | Low |

---

## 4. Script Quality Standards

### Current State
| Script | Linting | Type Hints | Tests | Documentation |
|--------|---------|------------|-------|---------------|
| `build_release.py` | ❌ None | ❌ None | ❌ None | ⚠️ Inline comments only |
| `generate_test_data.py` | ❌ None | ✅ Good | ❌ None | ✅ Excellent |

### Recommended Standards
```python
# All scripts should have:
#!/usr/bin/env python3
"""Module docstring with purpose, usage, examples."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Optional

def main() -> int:
    """Main entry point. Returns exit code."""
    ...

if __name__ == "__main__":
    sys.exit(main())
```

---

## 5. Integration with Project

### Current Integration
| Script | Called By | Integration Point |
|--------|-----------|-------------------|
| `build_release.py` | Manual (CI/CD) | Produces `release/` artifacts |
| `generate_test_data.py` | Manual (dev) | Produces `tests/fixtures/data/` |

### Missing Integration
| Missing | Impact |
|---------|--------|
| **CI/CD integration** | No GitHub Actions / Azure Pipelines calling scripts |
| **Pre-commit hooks** | No automated formatting/linting |
| **Version synchronization** | `build_release.py` hardcoded version vs pyproject.toml |
| **Test data in CI** | `generate_test_data.py` not run in CI pipeline |

---

## 5. Recommendations

### Priority 1 (Immediate)
1. **Make version dynamic** — Read version from `pyproject.toml` in `build_release.py`
2. **Add exit codes** — Return proper exit codes (0=success, 1=error)
3. **Add error handling** — Try/except with meaningful error messages
3. **Add `--version` flag** to both scripts

### Priority 2 (Short-term)
4. **Add type hints** to all functions in both scripts
5. **Add unit tests** for `generate_test_data.py` (verify file creation, CRS, data integrity)
6. **Add validation** in `build_release.py` — verify ZIP contents, checksums
7. **Add `--check` mode** to `build_release.py` for dry-run validation

### Priority 3 (Medium-term)
8. **Add missing scripts** — `run_tests.py`, `validate_schemas.py`, `check_deps.py`
9. **Add CI/CD integration** — GitHub Actions workflow calling scripts
10. **Add pre-commit hooks** — ruff, black, mypy for scripts/
11. **Add Docker support** — `docker_build.py` for containerized builds
12. **Add schema validation script** — Verify all JSON schemas in registry

---

## 6. Output for Next Task (packaging/)

**Context to pass forward:**
- Scripts folder has 2 well-written but incomplete scripts
- `build_release.py` creates 2 ZIPs but version is hardcoded
- `generate_test_data.py` is excellent for test data generation but not run in CI
- Missing: test runner, schema validator, dependency checker, version bumper
- Packaging folder likely contains packaging configuration — should reference build script
- Version synchronization needed between pyproject.toml and build script

---

*End of scripts/ folder analysis*