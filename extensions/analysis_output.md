# Extensions Folder Analysis — Universal AI GIS Studio

**Task:** task-11  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent  
**Context:** workflows/ (task-10) analysis read prior

---

## 1. Folder Structure

```
extensions/
├── __init__.py                          # Empty package marker
├── extension_manager.py                 # ExtensionManager: install/uninstall/enable (98 lines)
└── __pycache__/
```

**Total:** 1 Python module (~100 lines)

---

## 2. Architecture & Components

### `ExtensionManager` (`extension_manager.py`)

| Method | Purpose |
|--------|---------|
| `install_from_zip(zip_path, extension_id?)` | Extracts ZIP to `extensions_dir/{ext_id}`, loads manifest, validates, stores in `skills` table |
| `install_from_directory(dir_path, extension_id?)` | Copies directory, same validation/storage |
| `uninstall(extension_id)` | Removes directory, deletes from `skills` table |
| `set_enabled(extension_id, enabled)` | Toggles `enabled` column in `skills` table |
| `list_extensions()` | Queries `skills` table for `id LIKE 'ext_%'` |

### Manifest Validation (`_validate_manifest`)
- Required: `name` field
- Blocks permissions: `shell:*`, `*` (wildcard)
- No version format validation
- No dependency checking

### Storage
- **Filesystem**: `extensions_dir/{extension_id}/` (extracted ZIP or copied directory)
- **Database**: `skills` table with `id`, `name`, `version`, `description`, `manifest` (JSON), `enabled`, `trusted`, `installed_at`, `updated_at`
- **Note**: Extensions stored in same `skills` table as skills — uses `ext_` prefix for distinction

### Extension Manifest (expected)
```json
{
  "name": "string",
  "version": "string",
  "description": "string",
  "permissions": ["qgis:layer:write", "qgis:algorithm:execute"]
}
```

---

## 3. Dependencies

### Internal
```
extensions.extension_manager.ExtensionManager
    → database.db.Database
    → core.exceptions.ExtensionError
    → (stdlib: zipfile, shutil, uuid, json, yaml optional)
```

### External
- **PyYAML** (optional, for YAML manifests)
- **zipfile, shutil** (stdlib)

---

## 4. Issues Found

### 🔴 REMOVE (Dead Code / Security Risks)
| Item | Location | Issue |
|------|----------|-------|
| `__pycache__/` | `extensions/__pycache__/` | Compiled bytecode committed — gitignore |
| **Manifest validation gaps** | `_validate_manifest()` | No validation of `version` format, `entrypoint`, `security` section, `coordinate_policy` |
| **Trust model missing** | `uninstall()` / `set_enabled()` | No trust verification — any extension can be enabled without review |
| **Skill/Extension conflation** | Database storage | Extensions stored in `skills` table with `ext_` prefix — confusing, no separation |

### 🟡 ADD (Missing Features)
| Gap | Scope | Recommendation |
|-----|-------|----------------|
| **Extension sandbox** | Runtime | No execution isolation — extensions run with full Python privileges |
| **Dependency resolution** | Manifest | No `dependencies` field for extension-to-extension requires |
| **Version compatibility** | Install | No check against platform version (`engines.dsh` equivalent) |
| **Marketplace integration** | Install | No remote registry, no signed packages, no update checking |
| **Extension UI hooks** | Manifest | No `ui_panels`, `menu_items`, `toolbar_buttons` declarations |
| **Uninstall hooks** | Lifecycle | No `on_uninstall` cleanup (temp files, DB cleanup) |
| **Enable/disable hooks** | Lifecycle | No `on_enable`/`on_disable` for runtime registration |
| **Permission review UI** | Install | No prompt showing requested permissions before install |
| **Extension signing** | Security | No signature verification for ZIP packages |
| **Rollback on failure** | Install | Partial install not cleaned up on validation failure |

### 🔵 IMPROVE (Refactoring)
| Opportunity | Details |
|-------------|---------|
| **Separate extensions table** | Create `extensions` table distinct from `skills` |
| **Extension entrypoint interface** | Define ABC with `initialize()`, `shutdown()`, `get_tools()`, `get_skills()` |
| **Sandbox execution** | Use `RestrictedPython` or subprocess isolation for untrusted extensions |
| **Signed packages** | Require cryptographic signatures for marketplace packages |
| **Dependency graph** | Topological install/order for dependent extensions |
| **Health checks** | `health_check()` method per extension |
| **Metrics** | Track install/enable/disable events, errors |

---

## 5. Cross-Module Integration (from workflows/ context)

### Current Integration
```
ExtensionManager
    → Database (skills table)
    → Skills system (reuses skills table, SkillValidator logic partially)
```

### Missing Integration
| Service | Should Integrate | Current State |
|---------|-----------------|---------------|
| `EventBus` | Install/enable/disable events | **Not used** |
| `CapabilityRegistry` | Register extension capabilities | **Not used** |
| `SkillManager` | Extensions can provide skills | **Partial** (stores in same table) |
| `WorkflowEngine` | Custom node types from extensions | **Not used** |
| `AgentManager` | Extensions can provide agents | **Not used** |
| `ClusterRegistry` | Extensions can provide clusters | **Not used** |
| `AuditRepository` | Log extension installs/changes | **Not used** |
| `Security` | Trust verification, signatures | **Not used** |

---

## 6. Test Coverage

| Test File | Coverage |
|-----------|----------|
| **None** | Zero tests for extension manager |

**Total: 0 tests for 1 module (0%)**

---

## 7. Recommendations Summary

### Priority 1 (Immediate)
1. **Add `extensions/__pycache__/` to `.gitignore`**
2. **Create separate `extensions` table** — don't conflate with `skills`
3. **Add manifest validation** for `version` (semver), `entrypoint`, `security.coordinate_policy`

### Priority 2 (Short-term)
4. **Add unit tests** for install/uninstall/enable/disable/validation
5. **Add extension entrypoint interface** (ABC with `initialize`/`shutdown`)
6. **Add lifecycle hooks** (`on_install`, `on_enable`, `on_disable`, `on_uninstall`)
6. **Add permission review** before install (show requested permissions)
7. **Add trust model** — require explicit trust grant for `shell:*` or wildcard permissions

### Priority 3 (Medium-term)
8. **Implement extension sandbox** (RestrictedPython or subprocess)
9. **Add signed package verification** for marketplace
10. **Add dependency resolution** and topological install
11. **Create `extensions` marketplace registry** (remote + local)
12. **Add UI hooks** in manifest (`panels`, `menus`, `toolbar`)
13. **Integrate with `EventBus`, `CapabilityRegistry`, `AuditRepository`**
14. **Add health check endpoint** per extension

---

## 8. Output for Next Task (monitoring/)

**Context to pass forward:**
- Extensions system: install/uninstall/enable from ZIP/directory, manifest validation, stored in `skills` table (conflated with skills)
- Security gaps: no sandbox, no trust model, no signature verification, no dependency resolution
- Monitoring folder contains: `__init__.py` only (no implementation yet)
- Monitoring likely should: track metrics, health checks, alerting, logging aggregation
- Key integration: `ExtensionManager` should emit events to monitoring
- Watch for: Circular imports between monitoring and extensions; monitoring should not import extension internals

---

*End of extensions/ folder analysis*