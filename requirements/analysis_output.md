# Requirements Folder Analysis — Universal AI GIS Studio

**Task:** task-17  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent  
**Context:** docs/ (task-16) analysis read prior

---

## 1. Folder Structure

```
requirements/
├── base.txt       # Core runtime dependencies (5 lines)
├── dev.txt        # Development dependencies (4 lines)
├── mcp.txt        # MCP server dependencies (2 lines)
├── opencv.txt     # Computer vision dependencies (3 lines)
├── keyring.txt    # Secure credential storage (2 lines)
└── pyproject.toml (at root) — Single source of truth for optional deps
```

**Total:** 5 requirement files + pyproject.toml (~50 lines total)

---

## 2. Dependency Analysis

### Core Dependencies (`base.txt`)
| Package | Version | Purpose |
|---------|---------|---------|
| pydantic | >=2.5.0 | Data validation, settings management |
| pytest | >=7.0.0 | Testing framework (also in dev) |
| aiosqlite | >=0.20.0 | Async SQLite for MCP server |

**Note:** `pytest` appears in both `base.txt` and `dev.txt` — duplication.

### Development Dependencies (`dev.txt`)
| Package | Version | Purpose |
|---------|---------|---------|
| pytest | >=7.0.0 | Testing (duplicated in base) |
| pytest-qt | >=4.0.0 | Qt testing support |
| aiohttp | >=3.9.0 | Async HTTP client |

**Note:** `aiohttp` not listed as optional dependency in pyproject.toml — missing.

### MCP Server Dependencies (`mcp.txt`)
| Package | Version | Purpose |
|---------|---------|---------|
| mcp | >=1.2.0 | Model Context Protocol SDK |

**Note:** Version 1.2.0+ required for Streamable HTTP support.

### Computer Vision Dependencies (`opencv.txt`)
| Package | Version | Purpose |
|---------|---------|---------|
| opencv-python-headless | >=4.8.0 | OpenCV without GUI (for CV engine) |
| numpy | >=1.24.0 | Numerical computing (OpenCV dependency) |

**Note:** Marked as "optional" but used by CV engine — should be explicit optional dependency.

### Secure Credential Storage (`keyring.txt`)
| Package | Version | Purpose |
|---------|---------|---------|
| keyring | >=24.0.0 | Cross-platform credential storage |

---

## 3. pyproject.toml Analysis

### Optional Dependencies (Extras)
```toml
[project.optional-dependencies]
mcp = ["mcp>=1.2.0"]
pydantic = ["pydantic>=2.5.0"]
opencv = ["opencv-python-headless>=4.8.0"]
keyring = ["keyring>=24.0.0"]
pytest = ["pytest>=7.0.0", "pytest-qt>=4.0.0"]
aiohttp = ["aiohttp>=3.9.0"]
httpx = ["httpx>=0.27.0"]
prometheus = ["prometheus-client>=0.19.0"]
pybreaker = ["pybreaker>=0.8.1"]
```

### Observations
| Extra | Matches requirements/ | Notes |
|-------|----------------------|-------|
| mcp | mcp.txt ✅ | |
| pydantic | base.txt ✅ | base.txt has pydantic |
| opencv | opencv.txt ✅ | |
| keyring | keyring.txt ✅ | |
| pytest | dev.txt ✅ | dev.txt has pytest + pytest-qt |
| aiohttp | dev.txt ✅ | dev.txt has aiohttp |
| httpx | ❌ Missing from requirements/ | Used by MCP client |
| prometheus | ❌ Missing from requirements/ | Used by metrics |
| pybreaker | ❌ Missing from requirements/ | Used by circuit breaker |

---

## 4. Dependency Issues

### 🔴 Critical Issues

| Issue | Location | Impact |
|-------|----------|--------|
| **Missing httpx** | pyproject.toml has `httpx` extra but not in requirements/ | MCP client uses httpx — install fails without it |
| **Missing prometheus-client** | pyproject.toml has `prometheus` extra but not in requirements/ | Metrics module fails |
| **Missing pybreaker** | pyproject.toml has `pybreaker` extra but not in requirements/ | Circuit breaker fails |
| **Missing aiohttp in pyproject.toml** | dev.txt has aiohttp but not as extra | Bridge server may fail |
| **pytest duplication** | base.txt + dev.txt both have pytest | Unnecessary duplication |

### 🟡 Medium Issues

| Issue | Location | Recommendation |
|-------|----------|----------------|
| **No version upper bounds** | All requirements | Risk of breaking changes; add `<x.y.0` upper bounds |
| **No lock file** | No requirements.lock / poetry.lock / uv.lock | Reproducible builds not guaranteed |
| **opencv marked optional but required** | opencv.txt says "optional" but CV engine requires it | Misleading; make required or document clearly |
| **numpy not pinned** | opencv.txt has numpy>=1.24.0 | OpenCV 4.8+ requires specific numpy; pin to tested version |
| **mcp version not pinned** | mcp>=1.2.0 | MCP SDK has breaking changes; pin to tested minor version |
| **No security scanning** | No pip-audit / safety in dev deps | Supply chain risk |

### 🔵 Minor Issues

| Issue | Location |
|-------|----------|
| `requirements/` files not referenced by pyproject.toml | Two parallel systems |
| `keyring` extra in pyproject.toml but keyring.txt has no version upper bound | |
| `aiohttp` in dev.txt but used in production code (MCP client) | Should be core or explicit extra |
| No `build` extra for packaging | |

---

## 5. Environment-Specific Requirements

### QGIS Bridge (QGIS Python 3.12.15)
- Must install in QGIS bundled Python: `python -m pip install -e .`
- Requires: `pydantic`, `opencv` (for CV engine), `keyring`, `aiosqlite`
- **Cannot use system Python packages** — must be in QGIS environment

### MCP Server (System Python 3.11+)
- Install: `pip install -e ".[mcp]"` or `pip install -e ".[mcp,opencv,keyring,httpx,prometheus,pybreaker]"`
- Requires: `mcp`, `httpx`, `aiohttp`, `pydantic`, `pybreaker`, `prometheus-client`

### Development Environment
- Install: `pip install -e ".[pytest,aiohttp]"` + all extras
- Requires: `pytest`, `pytest-qt`, `aiohttp`, `httpx`

---

## 6. Missing Files

| Missing File | Purpose |
|--------------|---------|
| `requirements/httpx.txt` | HTTP client for MCP client |
| `requirements/prometheus.txt` | Metrics export |
| `requirements/pybreaker.txt` | Circuit breaker |
| `requirements/aiohttp.txt` | Async HTTP (production) |
| `requirements/numpy.txt` | Explicit numpy pinning |
| `requirements.lock` / `uv.lock` / `poetry.lock` | Lock file for reproducible builds |
| `constraints.txt` | Universal version constraints |

---

## 7. Recommendations

### Priority 1 (Immediate)
1. **Add missing requirement files**: `httpx.txt`, `prometheus.txt`, `pybreaker.txt`, `aiohttp.txt`
2. **Remove pytest duplication** — keep only in `dev.txt`
3. **Add upper bounds** to all versions (e.g., `httpx>=0.27.0,<0.28.0`)
4. **Pin mcp version** to tested minor: `mcp>=1.2.0,<1.3.0`

### Priority 2 (Short-term)
5. **Create lock file** using `uv pip compile` or `pip-tools`:
   ```bash
   uv pip compile pyproject.toml -o requirements.lock
   ```
6. **Add constraints.txt** for universal version caps
7. **Move aiohttp from dev to explicit extra** in pyproject.toml
8. **Pin numpy** to tested version with upper bound: `numpy>=1.24.0,<2.0.0`

### Priority 3 (Medium-term)
9. **Add security scanning** to CI: `pip-audit` or `safety`
10. **Document install commands per environment** in GETTING_STARTED.md
11. **Add `build` extra** for packaging: `build`, `twine`
12. **Consider uv for faster installs** — faster, better locking

---

## 8. Output for Next Task (examples/)

**Context to pass forward:**
- Requirements structure is split across 5 files + pyproject.toml with 9 extras
- Critical missing: httpx, prometheus-client, pybreaker, aiohttp (as explicit extra)
- Duplication: pytest in base.txt and dev.txt
- No lock file for reproducible builds
- Examples folder likely contains usage examples — should demonstrate proper dependency installation

---

*End of requirements/ folder analysis*