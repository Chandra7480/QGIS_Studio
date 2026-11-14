# .github/ Folder Analysis — Universal AI GIS Studio

**Task:** task-26  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector-2 agent  
**Context:** plugin/ (task-25) analysis read prior

---

## 1. Folder Structure

```
.github/
└── workflows/
    └── ci.yml              (425 lines) — Comprehensive CI/CD pipeline
```

---

## 2. CI/CD Pipeline Analysis (ci.yml)

### Pipeline Overview
| Job | OS | Trigger | Timeout | Dependencies |
|-----|----|---------|---------|--------------|
| `lint-and-type` | ubuntu-latest | All | 10 min | — |
| `unit-tests` | ubuntu-latest | All | 15 min | — |
| `contract-tests` | ubuntu-latest | All | 10 min | — |
| `integration-tests` | windows-latest | All | 45 min | lint, unit, contract |
| `property-tests` | ubuntu-latest | All | 20 min | lint, unit |
| `error-injection-tests` | ubuntu-latest | All | 15 min | lint, unit |
| `load-tests` | ubuntu-latest | schedule/dispatch | 30 min | lint, unit, integration |
| `build-package` | ubuntu-latest | Non-draft PRs | 10 min | All test jobs |
| `notify-failure` | ubuntu-latest | On failure | 5 min | All test jobs |

### Concurrency Control
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```
**Excellent:** Cancels in-progress runs on new pushes to same branch.

---

## 3. Job-by-Job Assessment

### 3.1 Lint & Type Check ✅
- **Tools:** Ruff (lint + format), MyPy (strict mode)
- **Scope:** `core`, `bridge`, `engines`, `mcp_server`, `clusters`
- **Ignores:** Missing imports (pragmatic for QGIS deps)
- **Cache:** Pip cache keyed on requirements files + pyproject.toml

### 3.2 Unit Tests ✅
- **Framework:** pytest with coverage
- **Coverage Targets:** core, bridge, engines, mcp_server, clusters
- **Reports:** JUnit XML + Codecov integration
- **Extras:** pytest-asyncio, hypothesis, jsonschema, imagehash, pillow

### 3.3 Contract Tests ✅
- **Purpose:** Schema validation (JSON Schema, hypothesis, snapshot testing)
- **Scope:** `tests/contract`
- **Good Practice:** Separate from unit tests for API contract enforcement

### 3.4 Integration Tests (QGIS) ⚠️ **HIGH COMPLEXITY**
- **OS:** windows-latest (QGIS requirement)
- **QGIS Setup:** Dual approach — apt cache + Chocolatey fallback
- **Python:** 3.9 (QGIS 3.34 bundled Python)
- **Bridge Startup:** Background process with health check
- **Test Filtering:** `-k "not visual"` + separate visual regression job
- **Risk:** QGIS installation on GitHub Actions Windows is fragile

### 3.5 Property-Based Tests ✅
- **Framework:** Hypothesis
- **Show Statistics:** Enabled for debugging
- **Good Practice:** Separate job for fuzzing

### 3.6 Error Injection Tests ✅
- **Framework:** pytest-mock
- **Purpose:** Fault tolerance validation
- **Good Practice:** Dedicated job for chaos testing

### 3.7 Load Tests ⏰ **SCHEDULED ONLY**
- **Trigger:** Weekly (Sunday 02:00 UTC) + manual dispatch
- **Dependencies:** Requires integration-tests to pass
- **Framework:** aiohttp + pytest-asyncio
- **Good Practice:** Not blocking regular PRs

### 3.8 Build & Package ✅
- **Tools:** `build` + `twine check`
- **Trigger:** After all tests pass, non-draft PRs
- **Artifacts:** Uploaded to GitHub Actions (30-day retention)

### 3.9 Notify Failure ⚠️ **PLACEHOLDER**
- **Current:** Echo only
- **Missing:** Slack/Discord/Email integration

---

## 4. Environment & Configuration

### Global Env Vars
```yaml
env:
  PYTHON_VERSION: "3.11"
  QGIS_VERSION: "3.34"
  PIP_CACHE_DIR: ~/.cache/pip
```

### Per-Job Overrides
- Integration tests: Python 3.9, QGIS-specific paths
- Load tests: Only on schedule/dispatch

---

## 5. Missing Workflows

| Missing Workflow | Purpose | Priority |
|------------------|---------|----------|
| **Release/Deploy** | Build release artifacts, create GitHub Release, publish to PyPI | 🔴 Critical |
| **Dependabot/Dependabot-auto-merge** | Automated dependency updates | 🟡 Medium |
| **Security Scan** | CodeQL, pip-audit, bandit | 🔴 Critical |
| **Documentation Build** | Build Sphinx/MkDocs, deploy to Pages | 🟢 Low |
| **Plugin Validation** | QGIS plugin metadata validation, ZIP structure check | 🔴 Critical |
| **Pre-commit CI** | Mirror local pre-commit hooks | 🟡 Medium |

---

## 6. Issues Found

### 🔴 Critical
| Issue | Description |
|-------|-------------|
| **No release workflow** | Release process documented in release/ analysis as manual; no automated release on tag |
| **No security scanning** | No CodeQL, no dependency vulnerability scanning (pip-audit/OSV) |
| **No plugin validation** | QGIS plugin metadata.txt not validated; no ZIP structure test |
| **QGIS CI fragility** | Chocolatey install on GitHub Actions Windows is unreliable; no fallback verification |
| **No PyPI publishing** | Build job creates artifacts but doesn't publish |

### 🟡 Medium
| Issue | Description |
|-------|-------------|
| **Notification placeholder** | `notify-failure` job only echoes; no real integration |
| **Python version mismatch** | Main jobs use 3.11, integration uses 3.9 (QGIS bundled) — could cause dependency resolution issues |
| **No branch protection config** | No `branch-protection.yml` or branch rules enforcement via Actions |
| **Hardcoded QGIS version** | `3.34` in multiple places; should be single source |
| **Missing dependabot** | No automated dependency updates |
| **No secrets scanning** | No trufflehog/gitguardian for credential leaks |

### 🟢 Low
| Issue | Description |
|-------|-------------|
| **Cache key could include OS** | Pip cache shared across Ubuntu/Windows may cause issues |
| **MyPy ignore-missing-imports** | Masks real type issues for QGIS deps; consider stubs |
| **No test matrix** | Single Python version per job; could test 3.10, 3.11, 3.12 |
| **Weekly schedule only** | No nightly or per-PR load tests option |

---

## 7. Recommendations

### Priority 1 (Immediate)
1. **Add Release Workflow** (`.github/workflows/release.yml`):
   - Trigger on version tag (`v*`)
   - Run full test suite
   - Build artifacts (reuse `build-package` job)
   - Generate checksums (SHA256)
   - Create GitHub Release with artifacts
   - Publish to PyPI (trusted publishing OIDC)

2. **Add Security Workflow** (`.github/workflows/security.yml`):
   - CodeQL analysis (Python)
   - pip-audit / osv-scanner for dependencies
   - Bandit for static security analysis
   - TruffleHog for secrets scanning

3. **Add Plugin Validation Workflow** (`.github/workflows/plugin-validation.yml`):
   - Validate `metadata.txt` schema
   - Test plugin ZIP structure matches QGIS requirements
   - Verify `__init__.py` has `classFactory`
   - Check icon/about.html references exist

### Priority 2 (Short-term)
4. **Improve QGIS CI Reliability**:
   - Use `qgis/actions-setup-qgis` action if available
   - Add retry logic for Chocolatey install
   - Consider self-hosted runner for QGIS tests
   - Cache QGIS installation

5. **Add Dependabot** (`.github/dependabot.yml`):
   - Weekly dependency updates
   - Auto-merge for patch/minor with passing tests
   - Security updates immediate

6. **Real Failure Notifications**:
   - Slack/Discord webhook integration
   - Email on critical failures

### Priority 3 (Medium-term)
7. **Test Matrix**: Add Python 3.10, 3.11, 3.12 matrix for unit/contract/property tests
8. **Documentation Workflow**: Build and deploy docs to GitHub Pages
9. **Single Source QGIS Version**: Define in one place (env var or variable)
10. **Pre-commit CI**: Add `pre-commit.ci` or local pre-commit mirror job

---

## 8. Output for Next Task (.pytest_cache/)

**Context to pass forward:**
- Single comprehensive CI workflow (ci.yml) with 9 jobs
- Tests: lint, unit, contract, integration (QGIS), property, error-injection, load
- Windows runner required for QGIS integration tests
- **Critical gaps:** No release workflow, no security scanning, no plugin validation, no PyPI publishing
- Notification job is placeholder only
- QGIS version hardcoded (3.34) in multiple places
- Next task: analyze `.pytest_cache/` folder for test cache insights

---

*End of .github/ folder analysis*