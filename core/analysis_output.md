# Core Folder Analysis — Universal AI GIS Studio

**Task:** task-1  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent

---

## 1. Folder Structure

```
core/
├── __init__.py              # Package exports (exception classes)
├── config.py                # Configuration system with defaults + persistent storage
├── exceptions.py            # Base exception hierarchy (14 exception types)
├── event_bus.py             # In-process pub/sub event bus
├── logging.py               # Structured logging with sensitive data filtering
├── capability_registry.py   # GIS capability discovery engine
├── emergency_stop.py        # Global emergency stop singleton
├── keyring_backend.py       # OS credential manager (Windows/macOS/Linux + fallback)
├── resource_quota.py        # Per-job resource quota management & enforcement
├── job_manager.py           # Job lifecycle management (create/start/complete/fail/cancel)
├── circuit_breaker.py       # Unified circuit breaker (sync + async) with registry
└── __pycache__/             # Compiled bytecode (ignored)
```

**Total:** 10 Python modules + `__init__.py` (~1,500 lines of code)

---

## 2. Module Purposes & Architecture

| Module | Purpose | Key Patterns |
|--------|---------|--------------|
| **exceptions.py** | Unified error hierarchy with error codes, HTTP status codes, structured context | Exception inheritance, `to_dict()` for MCP/JSON serialization |
| **config.py** | In-memory config cache backed by SQLite `app_settings` table; 70+ typed defaults | Singleton-ish pattern, type coercion, JSON serialization for complex values |
| **event_bus.py** | Decoupled pub/sub for cross-module communication | Observer pattern, thread-safe dict of callback lists |
| **logging.py** | Structured logging with rotating files, console, sensitive field filtering | `SensitiveFilter` (strips API keys), `SafeFormatter` (request_id/job_id), `LogContext` context manager |
| **capability_registry.py** | Dynamic discovery of QGIS/GDAL/Processing algorithms; persists to DB | Registry pattern, lazy discovery, DB persistence |
| **emergency_stop.py** | Global singleton coordinating immediate cessation across all subsystems | Singleton with thread-safe registration, priority-ordered callbacks, audit logging |
| **keyring_backend.py** | Secure credential storage using OS native managers (Win CredMgr, macOS Keychain, Linux Secret Service) + encrypted file fallback | Abstract base + platform implementations, factory function `get_keyring_backend()` |
| **resource_quota.py** | Per-job limits (memory, CPU, disk, duration) with background monitor & kill callback | Dataclasses, enum for actions, background thread monitor, system memory pause |
| **job_manager.py** | Job lifecycle (queued→running→completed/failed/cancelled) with events & quota integration | Repository pattern, integrates `ResourceQuotaManager` & `EmergencyStop` |
| **circuit_breaker.py** | Failure isolation for Bridge/MCP with CLOSED/OPEN/HALF_OPEN states, sync + async | State machine, thread/async locks, fallback support, global registry |

---

## 3. Dependencies

### Internal (within core/)
- `exceptions.py` → imported by all modules
- `logging.py` → `get_logger()` used by all modules
- `config.py` → used by `capability_registry.py`, `emergency_stop.py`
- `event_bus.py` → not directly used yet (designed for future decoupling)
- `emergency_stop.py` → registered by `job_manager.py`
- `resource_quota.py` → used by `job_manager.py` (kill callback)
- `job_manager.py` → depends on `database.repositories.job_repository`

### External
- **stdlib:** `json`, `os`, `sys`, `logging`, `threading`, `asyncio`, `dataclasses`, `enum`, `datetime`, `uuid`, `ctypes`, `subprocess`, `platform`, `pathlib`
- **third-party:** `psutil` (optional, for system memory), `cryptography` (for fallback keyring encryption)
- **QGIS/GDAL:** `qgis`, `processing`, `osgeo.gdal` (dynamic imports in capability_registry)
- **Database:** `database.db.Database`, `database.repositories.*`

---

## 4. Patterns & Design Decisions

### ✅ Strong Patterns
1. **Structured Error Hierarchy** — Every exception has `error_code`, `http_status`, `context`, `cause`, and `to_dict()` for MCP compliance.
2. **Sensitive Data Protection** — `SensitiveFilter` automatically redacts keys containing `api_key`, `secret`, `password`, `token`, `credential` from logs.
3. **Singleton with Thread Safety** — `EmergencyStop`, `ResourceQuotaManager`, `CircuitBreakerRegistry` use double-checked locking.
4. **Priority-Ordered Callbacks** — Emergency stop executes highest-priority callbacks first (job manager = 100).
5. **Graceful Degradation** — Keyring falls back through Windows → macOS → Linux → encrypted file; circuit breaker has fallback callable.
6. **Configuration Coercion** — `_coerce()` handles int/float/bool conversion from string storage.
7. **Audit Trail Integration** — Emergency stop attempts to write to `AuditRepository` (best-effort).

### ⚠️ Areas of Concern
1. **Hardcoded QGIS Path** — `config.py:24-25` defaults to `C:\Program Files\QGIS 4.2.3` — not portable, version-specific.
2. **No Event Bus Usage** — `event_bus.py` exists but isn't wired into job_manager, emergency_stop, or other modules yet.
3. **Capability Registry DB Coupling** — Direct import of `database.db.Database` creates circular dependency risk.
4. **Fallback Keyring Imports at Module Level** — `cryptography` imports in `FallbackKeyring.__init__` could fail on systems without it.
5. **Circuit Breaker Dual Locks** — Both `threading.RLock` and `asyncio.Lock` maintained; sync/async paths could diverge.
6. **Missing Type Hints** — Some methods lack return type annotations (e.g., `JobManager.db()`).
7. **`__pycache__` in Source Tree** — Should be in `.gitignore`.

---

## 5. Issues Found

### 🔴 REMOVE (Dead Code / Security Risks / Duplicates)
| Item | Location | Issue |
|------|----------|-------|
| `__pycache__/` | `core/__pycache__/` | Compiled bytecode committed — should be gitignored |
| Hardcoded QGIS 4.2.3 path | `config.py:24-25` | Security/maintenance risk — version lock-in, not portable |
| `list_keys()` stubs | `keyring_backend.py:183, 272, 334` | All three platform backends return `[]` — incomplete implementation |
| `AuditRepository` import inside method | `emergency_stop.py:166` | Runtime import hides circular dependency; should be dependency-injected |

### 🟡 ADD (Missing Features / Tests / Docs)
| Gap | Module | Recommendation |
|-----|--------|----------------|
| Unit tests | `capability_registry.py`, `emergency_stop.py`, `keyring_backend.py`, `resource_quota.py`, `job_manager.py`, `circuit_breaker.py` | Only `exceptions`, `event_bus`, `config`, `logging` have tests (4/10 modules) |
| Integration tests | All | No cross-module integration tests |
| Config validation | `config.py` | No schema validation on `set()` — invalid types persist silently |
| Event bus wiring | `event_bus.py` | Publish job status changes, emergency stop, quota violations |
| Health check endpoint | All | No `/health` or `status()` aggregation across core services |
| Structured logging context | `logging.py` | `LogContext` uses global `setLogRecordFactory` — not thread-safe for concurrent requests |
| Keyring `list_keys` | `keyring_backend.py` | Implement `CredEnumerateW` (Windows), `security dump-keychain` (macOS), `secret-tool search` (Linux) |
| Circuit breaker metrics export | `circuit_breaker.py` | Add Prometheus/OpenTelemetry export |

### 🔵 IMPROVE (Refactoring / Performance / Patterns)
| Opportunity | Module | Details |
|-------------|--------|---------|
| Dependency injection | `capability_registry.py`, `job_manager.py` | Pass `db`/`repo` instead of importing `database.db.Database` |
| Config path resolution | `config.py` | Auto-detect QGIS install via registry (Windows) or `which qgis` (Unix) |
| Event-driven architecture | `job_manager.py`, `emergency_stop.py`, `resource_quota.py` | Emit events on `EventBus` for job state changes, quota violations, emergency stop |
| Async-first design | `circuit_breaker.py`, `job_manager.py` | Consider making `JobManager` methods async; circuit breaker already supports both |
| Quota monitor efficiency | `resource_quota.py` | Polling every 5s; consider event-driven updates from job manager |
| Keyring backend selection | `keyring_backend.py` | Cache backend instance; add health check for each backend |
| Circuit breaker registry | `circuit_breaker.py` | Add `get_all_stats()` returning typed models, not raw dicts |
| Logging performance | `logging.py` | `SensitiveFilter` deep-copies entire context dict on every log call — optimize with shallow copy |

---

## 6. Cross-Module Integration Assessment

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Config     │────▶│  CapabilityReg   │────▶│  JobManager      │
│  (defaults, │     │  (QGIS discovery)│     │  (lifecycle,     │
│   storage)  │     └──────────────────┘     │   quota, events) │
└─────────────┘              ▲               └────────┬─────────┘
       ▲                     │                        │
       │                     │                        ▼
       │            ┌──────────────────┐     ┌──────────────────┐
       │            │  EmergencyStop   │◀────│ ResourceQuotaMgr │
       │            │  (singleton,     │     │  (monitor, kill  │
       └────────────│   callbacks)     │     │   callback)      │
                    └──────────────────┘     └──────────────────┘
                           ▲                        ▲
                           │                        │
                    ┌──────────────────┐     ┌──────────────────┐
                    │ CircuitBreaker   │     │   Keyring        │
                    │ (Bridge, MCP)    │     │   (credentials)  │
                    └──────────────────┘     └──────────────────┘
                           ▲
                           │
                    ┌──────────────────┐
                    │   EventBus       │  ← NOT YET WIRED
                    │  (decoupling)    │
                    └──────────────────┘
```

**Key Integration Gaps:**
1. `EventBus` is defined but **not used** by any module — missed opportunity for decoupling.
2. `JobManager` directly calls `ResourceQuotaManager` and `EmergencyStop` — tight coupling.
3. `CapabilityRegistry` imports `Database` directly — hard to test/mock.
4. No central "Core Services" facade to initialize/wire all singletons.

---

## 7. Recommendations Summary

### Priority 1 (Immediate)
1. **Add `core/__pycache__/` to `.gitignore`** — remove from repo.
2. **Replace hardcoded QGIS path** with auto-detection logic.
3. **Wire `EventBus`** into `JobManager`, `EmergencyStop`, `ResourceQuotaManager` for decoupled notifications.
4. **Add unit tests** for 6 untested modules (target: 80%+ coverage).

### Priority 2 (Short-term)
5. **Implement `list_keys()`** for all keyring backends.
6. **Dependency-inject `Database`/`AuditRepository`** into `CapabilityRegistry` and `EmergencyStop`.
7. **Add config validation** on `set()` with schema (Pydantic or custom).
8. **Create `CoreServices` facade** for unified initialization/shutdown.

### Priority 3 (Medium-term)
9. **Make `JobManager` async-compatible** for better integration with MCP/Bridge.
10. **Add Prometheus metrics** to `CircuitBreaker`, `ResourceQuotaManager`, `JobManager`.
11. **Optimize `SensitiveFilter`** to avoid deep copy on every log record.
12. **Implement health check aggregation** across all core services.

---

## 8. Output for Next Task (clusters/)

**Context to pass forward:**
- Core provides: config, exceptions, logging, event bus, job management, resource quotas, emergency stop, circuit breaker, keyring, capability discovery.
- Clusters will likely depend on: `Config` (for settings), `JobManager` (for async operations), `EventBus` (for progress events), `CapabilityRegistry` (for algorithm availability), `exceptions` (for error handling).
- Key integration points: `clusters/registry.py` should register cluster capabilities with `CapabilityRegistry`; cluster handlers should use `JobManager` for long-running operations.
- Watch for: Circular imports between `clusters` and `core` (avoid `from core import *` in cluster `__init__.py`).

---

*End of core/ folder analysis*