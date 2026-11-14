# Skills Folder Analysis — Universal AI GIS Studio

**Task:** task-9  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent  
**Context:** integrations/ (task-8) analysis read prior

---

## 1. Folder Structure

```
skills/
├── __init__.py                          # Empty package marker
├── skill_manager.py                     # SkillManager: CRUD + agent assignment (89 lines)
├── skill_loader.py                      # SkillLoader: manifest loading/validation (61 lines)
├── skill_validator.py                   # SkillValidator: security validation (92 lines)
├── builtin/
│   ├── __init__.py
│   └── automatic-georeferencing/        # Only builtin skill implemented
│       ├── manifest.yaml                # Skill definition (90 lines)
│       └── SKILL.md                     # Documentation (84 lines)
├── custom/
│   └── __init__.py
└── __pycache__/
```

**Total:** ~415 lines across 6 Python modules + 1 skill definition

---

## 2. Architecture & Components

### Core Classes

| Class | File | Purpose |
|-------|------|---------|
| **`SkillManager`** | `skill_manager.py` | CRUD for skills, agent assignment, builtin skill registry |
| **`SkillLoader`** | `skill_loader.py` | Loads skill manifests from directories (YAML/JSON), validates |
| **`SkillValidator`** | `skill_validator.py` | Security validation: forbidden patterns, permission checks, coordinate policy |

### Skill Manifest Structure (from `automatic-georeferencing/manifest.yaml`)
```yaml
name: string
version: semver string
description: string
category: string
author: string
license: string
entrypoint: Python class path (e.g., engines.georeferencing.georeferencing_engine.GeoreferencingEngine)
permissions: list of {name, description}
capabilities: list of operation names
input_schema: JSON Schema
output_schema: JSON Schema
security:
  no_shell_access: true
  no_network_access: true
  file_access: read_only_inputs
  coordinate_policy: never_invent_coordinates
```

### Builtin Skills Registry (`skill_manager.py:23-59`)
| Skill ID | Name | Description |
|----------|------|-------------|
| `automatic-georeferencing` | Automatic Georeferencing | Detect GCPs and georeference scanned maps |
| `raster-processing` | Raster Processing | Raster calculation, reclassify, mosaic, clip |
| `vector-analysis` | Vector Analysis | Buffer, clip, dissolve, overlay, repair |
| `watershed-analysis` | Watershed Analysis | Flow direction, accumulation, watershed delineation |
| `map-layout` | Map Layout | Create cartographic map layouts and export |
| `topology-validation` | Topology Validation | Validate geometry and topology of vector layers |
| `cadastral-digitization` | Cadastral Digitization | Digitize parcel boundaries and compute areas |

**Only `automatic-georeferencing` is actually implemented** (has directory with manifest.yaml + SKILL.md). The other 6 are registered in code but lack directories.

---

## 3. Security Model

### Validation Rules (`skill_validator.py`)
1. **Required Fields**: `name`, `version`, `description`
2. **Version Format**: Semver (major.minor.patch)
3. **Forbidden Code Patterns**: `shell`, `exec`, `eval`, `subprocess`, `os.system`, `urllib`, `requests`, `socket`, `ftplib`
4. **Permission Restrictions**: Blocks `shell:*`, `filesystem:*`, `network:*`, `*`
5. **Security Section**:
   - `shell_access` must be `false`
   - `network_access` must be `false`
   - `file_access` must not be `unrestricted`
   - `coordinate_policy` must be `never_invent_coordinates`
6. **Entrypoint Safety**: Blocks `os.system`, `subprocess`, `eval(`, `exec(`

### Security Policy (from `automatic-georeferencing`)
- **No shell access** — Cannot execute shell commands
- **No network access** — Cannot make HTTP/other network requests
- **File access: read_only_inputs** — Only reads declared input files
- **Coordinate policy: never_invent_coordinates** — All coordinates must come from trusted reference data

---

## 4. Dependencies

### Internal
```
skills.skill_manager      → database.db.Database, core.exceptions, skills.skill_loader
skills.skill_loader       → skills.skill_validator, core.exceptions
skills.skill_validator    → core.exceptions
skills.builtin.*          → (manifest files only)
```

### External
- **PyYAML** (optional, for YAML manifests) — `skill_loader.py` requires it for `.yaml` files
- **json** (stdlib)

### Database Tables
- `skills` — skill_id, name, version, description, manifest (JSON), enabled, trusted, installed_at, updated_at
- `agent_skills` — agent_id, skill_id (many-to-many)

---

## 5. Issues Found

### 🔴 REMOVE (Dead Code / Security Risks / Duplicates)
| Item | Location | Issue |
|------|----------|-------|
| `__pycache__/` | `skills/`, `skills/builtin/`, `skills/custom/` | Compiled bytecode committed — gitignore |
| **6 placeholder builtin skills** | `skill_manager.py:23-59` | Registered in `_builtin_skills` but **no directories exist** for `raster-processing`, `vector-analysis`, `watershed-analysis`, `map-layout`, `topology-validation`, `cadastral-digitization` |
| `custom/__init__.py` | `skills/custom/__init__.py` | Empty file — no custom skill framework implemented |

### 🟡 ADD (Missing Features / Tests / Docs)
| Gap | Scope | Recommendation |
|-----|-------|----------------|
| **Actual skill implementations** | `builtin/` | Only 1 of 7 builtin skills has directory + manifest; implement remaining 6 |
| **Custom skill framework** | `custom/` | No skill template, no sandbox execution, no marketplace |
| **Unit tests** | All modules | Zero tests for skill_manager, skill_loader, skill_validator |
| **Skill versioning** | `skill_manager.py` | No upgrade/downgrade logic; `version` field unused |
| **Skill dependencies** | Manifest | No `dependencies` field for skill-to-skill requires |
| **Skill marketplace** | `skill_manager.py` | No `search_skills()`, `install_from_registry()`, `publish()` |
| **Agent skill execution** | `skill_manager.py` | `assign_to_agent()` only writes DB; no runtime skill invocation |
| **Skill sandbox** | `skill_validator.py` | Validation only; no actual sandbox (no exec isolation) |
| **Documentation** | `builtin/*/SKILL.md` | Only 1 skill has docs; need for all |
| **Skill validation caching** | `skill_loader.py` | Re-validates on every load; no cache |

### 🔵 IMPROVE (Refactoring / Performance / Patterns)
| Opportunity | Details |
|-------------|---------|
| **Remove placeholder skills** | Delete 6 entries from `_builtin_skills` or implement them |
| **Add skill dependency resolution** | Topological sort for skill loading order |
| **Implement skill sandbox** | Use `RestrictedPython` or subprocess isolation for untrusted skills |
| **Async skill loading** | `SkillLoader.load_from_directory()` is sync; add async variant |
| **Manifest schema** | Add JSON Schema for manifest validation (beyond Python checks) |
| **Skill categories/tags** | Add `tags` field for discoverability |
| **Skill lifecycle hooks** | `on_install`, `on_enable`, `on_disable`, `on_uninstall` |
| **Skill metrics** | Track usage count, success rate, latency per skill |
| **Entrypoint interface** | Define ABC for skill entrypoints (required methods) |
| **Custom skill directory** | Define standard structure: `manifest.yaml`, `code.py`, `requirements.txt`, `README.md` |

---

## 6. Cross-Module Integration (with integrations/ context)

### Current Integration
```
skills.skill_manager.SkillManager
    → database.db.Database (skills, agent_skills tables)
    → skills.skill_loader.SkillLoader
        → skills.skill_validator.validator
    → _builtin_skills (hardcoded dict)

agents.base_agent.BaseAgent
    → (no direct skill integration yet)

mcp_server.server.UniversalMCPServer
    → (skills listed via list_prompts? no — prompts are separate)
```

### Missing Integration
| Service | Should Integrate | Current State |
|---------|-----------------|---------------|
| `EventBus` | Skill install/enable/disable events | **Not used** |
| `CapabilityRegistry` | Register skill capabilities | **Not used** |
| `JobManager` | Track long-running skill operations | **Not used** |
| `AgentManager` | `assign_to_agent()` should verify agent exists | **Partial** (writes DB only) |
| `LLM Providers` | Skills could use AI for analysis | **Not used** |

---

## 7. Test Coverage

| Test File | Coverage |
|-----------|----------|
| **None** | Zero tests for any skills module |

**Total: 0 tests for 6 modules (0%)**

---

## 8. Recommendations Summary

### Priority 1 (Immediate)
1. **Add all `skills/**/__pycache__/` to `.gitignore`**
2. **Remove 6 placeholder builtin skills** from `skill_manager.py` OR implement them
3. **Delete empty `skills/custom/__init__.py`** or implement custom skill framework

### Priority 2 (Short-term)
4. **Implement the 6 missing builtin skills** with manifests + entrypoints
5. **Add unit tests** for `SkillManager`, `SkillLoader`, `SkillValidator`
6. **Add skill sandbox execution** (RestrictedPython or subprocess isolation)
7. **Wire `assign_to_agent()`** to verify agent exists via `AgentManager`

### Priority 3 (Medium-term)
8. **Implement custom skill framework** with template, sandbox, marketplace
9. **Add skill dependencies** and topological loading
10. **Add skill lifecycle hooks** and metrics
11. **Integrate with `CapabilityRegistry`** and `EventBus`
12. **Create skill entrypoint ABC** with required methods (`execute`, `validate`, etc.)
13. **Add JSON Schema validation** for manifests
14. **Implement skill versioning/upgrade** logic

---

## 9. Output for Next Task (workflows/)

**Context to pass forward:**
- Skills system provides: skill registration, validation (security-focused), agent assignment, manifest loading
- Only 1 builtin skill implemented (`automatic-georeferencing`) with entrypoint to `engines.georeferencing.GeoreferencingEngine`
- Security model: no shell, no network, read-only file access, never invent coordinates
- Workflows folder contains: `__init__.py` only (no implementation yet)
- Workflows likely should: compose skills + agents + tools into executable pipelines
- Key integration: `skill_manager.SkillManager.assign_to_agent()` writes to `agent_skills` table
- Watch for: Circular imports between workflows and skills/agents; workflows should orchestrate, not duplicate skill logic

---

*End of skills/ folder analysis*