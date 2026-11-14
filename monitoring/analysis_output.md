# Monitoring Folder Analysis — Universal AI GIS Studio

**Task:** task-12  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent  
**Context:** extensions/ (task-11) analysis read prior

---

## 1. Folder Structure

```
monitoring/
├── __init__.py                          # Empty package marker
├── audit.py                             # AuditService: tamper-proof hash chain + external anchoring (128 lines)
├── verify_audit.py                      # CLI for audit chain verification (201 lines)
├── resource_monitor.py                  # ResourceMonitor: system/process metrics + quota enforcement (228 lines)
├── temp_cleanup.py                      # TempFileManager + LRUCache: temp files, disk quota, cache (444 lines)
├── health.py                            # HealthChecker + 12 health checks (798 lines)
└── __pycache__/
```

**Total:** ~1,800 lines across 5 Python modules

---

## 2. Component Architecture

| Module | Class(es) | Purpose |
|--------|-----------|---------|
| **audit.py** | `AuditService` | Tamper-proof audit log with SHA-256 hash chain, external anchoring (file + syslog/Event Log), periodic anchors |
| **verify_audit.py** | CLI | Verifies audit hash chain integrity; optional external anchor verification |
| **resource_monitor.py** | `ResourceMonitor` | System/process metrics (psutil + Windows fallback), quota enforcement integration |
| **temp_cleanup.py** | `TempFileManager`, `LRUCache` | Temp file tracking per job, age/size cleanup, disk quota enforcement, LRU cache |
| **health.py** | `HealthChecker` + 12 `HealthCheck` subclasses | Unified health system with liveness/readiness probes, 12 subsystem checks |

---

## 3. Detailed Component Analysis

### 3.1 Audit Service (`audit.py`)

**Features:**
- SHA-256 hash chain: `SHA256(prev_hash || JSON(entry))`
- External anchoring every N entries (default 100) to file + Windows Event Log / Unix syslog
- `AuditRepository` integration for DB persistence
- `force_anchor()` for manual anchoring

**Strengths:**
- Cryptographic integrity via hash chain
- Multi-target anchoring (file + syslog + Windows Event Log)
- Thread-safe with lock

**Issues:**
- Anchor interval hardcoded to 100 (configurable via constructor but not exposed)
- `_write_syslog_anchor` uses `ctypes.windll.advapi32.ReportEventW` with `GetCurrentProcessId()` as event source — incorrect API usage (needs registered event source)
- No anchor rotation/cleanup policy

### 3.2 Verify Audit CLI (`verify_audit.py`)

**Features:**
- Full chain or range verification (`--start`, `--end`)
- External anchor verification (`--anchors`)
- JSON output for automation
- Exit codes for CI/CD integration

**Strengths:**
- Comprehensive CLI with good defaults
- JSON output for automation

**Issues:**
- Duplicate anchor verification logic (also in `AuditRepository.verify_chain()`)
- No `--config` for default DB path

### 3.3 Resource Monitor (`resource_monitor.py`)

**Features:**
- System snapshot: disk, memory (psutil + Windows ctypes fallback), CPU
- Per-process usage (RSS, VMS, CPU times, I/O)
- Quota enforcement integration via `ResourceQuotaManager`
- System health assessment with warnings/critical thresholds

**Strengths:**
- Graceful psutil fallback on Windows
- Integrates with quota manager for enforcement
- Health status with actionable thresholds

**Issues:**
- `psutil.cpu_percent(interval=0.1)` blocks for 100ms per call
- Windows memory fallback uses `GlobalMemoryStatusEx` — deprecated; should use `GlobalMemoryStatusEx` (already correct) but no 64-bit handling
- No async variant for high-frequency monitoring

### 3.4 Temp Cleanup (`temp_cleanup.py`)

**Components:**
| Class | Purpose |
|-------|---------|
| `TempFileManager` | Tracks temp files per job, age-based cleanup (24h), disk quota (500MB), low-disk alerts, background cleanup thread |
| `LRUCache` | Thread-safe LRU with size limit (256MB), `OrderedDict` backend |

**Strengths:**
- Per-job file tracking with auto-cleanup on job completion
- Disk quota enforcement with LRU eviction
- Low-disk alert callback
- Background thread with configurable interval
- LRU cache with size estimation

**Issues:**
- `sys.getsizeof()` for cache size estimation is inaccurate for nested objects
- Background thread uses `threading.Event.wait()` — no graceful shutdown on exceptions
- `enforce_disk_quota()` deletes oldest files globally — may delete active job files
- No temp file compression/archival before deletion
- No integration with `ResourceQuotaManager` for coordinated quota enforcement

### 3.5 Health System (`health.py`)

**Health Checks (12):**
| Check | Subsystem | Key Metrics |
|-------|-----------|-------------|
| `BridgeHealthCheck` | Bridge server | Running status, QGIS connection |
| `QGISHealthCheck` | QGIS | Connection, project loaded, layer count |
| `DatabaseHealthCheck` | SQLite | Connectivity, query test |
| `MCPHealthCheck` | MCP server | Tool count |
| `DiskHealthCheck` | Disk space | Used % (warn 85%, critical 95%) |
| `MemoryHealthCheck` | RAM | Used % (warn 75%, critical 90%) |
| `AgentsHealthCheck` | Agent system | Active agent count |
| `JobsHealthCheck` | Job manager | Running/queued/failed counts |
| `CircuitBreakerHealthCheck` | Circuit breaker | State (closed/half-open/open) |
| `ResourceQuotaHealthCheck` | Quota manager | System pause, memory % |
| `TempCleanupHealthCheck` | Temp files | Disk space, quota utilization |
| `RateLimiterHealthCheck` | Rate limiter | Backend status, config count |

**Architecture:**
- `HealthCheck` ABC with timeout-protected execution via thread
- `HealthChecker` orchestrates checks, computes overall status
- `SystemHealth` aggregates results, provides `is_healthy()` (liveness) and `is_ready()` (readiness)
- Global `init_health_checker()` wires all subsystems

**Strengths:**
- k8s-ready liveness/readiness probes
- Timeout protection per check
- Extensible check registration
- Proper status aggregation (worst status wins)

**Issues:**
- Thread-per-check for timeout adds overhead
- `BridgeHealthCheck`/`QGISHealthCheck` duplicate executor health logic
- `RateLimiterHealthCheck` accesses private `_redis` attribute
- No async health checks (all sync with thread timeout)
- No check dependencies/ordering
- No historical health trend storage

---

## 4. Dependencies

### Internal
```
monitoring.audit            → database.repositories.audit_repository
monitoring.verify_audit     → database.db, database.repositories.audit_repository
monitoring.resource_monitor → core.resource_quota (ResourceQuotaManager)
monitoring.temp_cleanup     → (standalone, optional quota_manager)
monitoring.health           → bridge, database, mcp_server, agents, core.job_manager, core.circuit_breaker, core.resource_quota, temp_cleanup, security.rate_limiter
```

### External
| Module | Dependencies |
|--------|--------------|
| audit | hashlib, json, threading, ctypes (Windows), syslog (Unix) |
| verify_audit | argparse, json, pathlib |
| resource_monitor | psutil (optional), shutil, ctypes (Windows) |
| temp_cleanup | threading, OrderedDict, tempfile, shutil |
| health | psutil (optional), shutil, threading, abc, dataclasses |

---

## 5. Issues Found

### 🔴 REMOVE (Security Risks / Bugs)
| Item | Location | Issue |
|------|----------|-------|
| `__pycache__/` | `monitoring/__pycache__/` | Compiled bytecode committed — gitignore |
| **Windows Event Log API misuse** | `audit.py:92-100` | `ReportEventW` called with `GetCurrentProcessId()` as event source — requires registered source via `RegisterEventSourceW` |
| **Blocking `cpu_percent`** | `resource_monitor.py:47` | `psutil.cpu_percent(interval=0.1)` blocks 100ms — bad for health checks |
| **Inaccurate cache sizing** | `temp_cleanup.py:108-114` | `sys.getsizeof()` doesn't measure nested object sizes |
| **Quota enforcement deletes active files** | `temp_cleanup.py:272-317` | `enforce_disk_quota()` deletes oldest files globally without checking job status |

### 🟡 ADD (Missing Features)
| Gap | Scope | Recommendation |
|-----|-------|----------------|
| **Async health checks** | `health.py` | All checks sync; add async variant for non-blocking |
| **Health history/trends** | `health.py` | Store health snapshots for trend analysis |
| **Distributed tracing** | All | No correlation IDs across monitoring components |
| **Alerting/notification** | `audit.py`, `temp_cleanup.py` | Only logging; no webhook/email/pager integration |
| **Audit log retention** | `audit.py` | No rotation/purge policy for old audit logs |
| **Anchor rotation** | `audit.py` | Anchor file grows unbounded |
| **Temp file compression** | `temp_cleanup.py` | No archival before deletion |
| **Metrics export** | `resource_monitor.py`, `health.py` | No Prometheus/OpenTelemetry export |
| **Unit tests** | All | Zero tests for monitoring modules |

### 🔵 IMPROVE (Refactoring)
| Opportunity | Details |
|-------------|---------|
| **Fix Windows Event Log** | Use `win32evtlog` / `pywin32` proper API with registered source |
| **Non-blocking CPU check** | Use `psutil.cpu_percent(interval=None)` with cached value |
| **Accurate cache sizing** | Use `pympler.asizeof` or recursive `sys.getsizeof` |
| **Job-aware quota enforcement** | Check job status before deleting temp files |
| **Unified quota system** | Merge `ResourceQuotaManager` + `TempFileManager` quota logic |
| **Async health checks** | Convert `HealthCheck` to async with `asyncio.wait_for()` |
| **Health check dependencies** | Allow checks to declare dependencies (e.g., QGIS needs Bridge) |
| **Structured logging** | Add correlation IDs (`request_id`, `job_id`) to all monitoring logs |

---

## 6. Cross-Module Integration (from extensions/ context)

### Current Integration
```
AuditService              → AuditRepository (DB) + file anchor + syslog/EventLog
ResourceMonitor           → ResourceQuotaManager (core) for enforcement
TempFileManager           → Optional quota_manager for coordinated enforcement
HealthChecker             → 12 subsystem checks wired via init_health_checker()
```

### Missing Integration
| Service | Should Integrate | Current State |
|---------|-----------------|---------------|
| `EventBus` | Audit events, health changes, quota violations | **Not used** |
| `CapabilityRegistry` | Register monitoring capabilities | **Not used** |
| `JobManager` | Track monitoring jobs (cleanup, verification) | **Not used** |
| `CircuitBreaker` | Wrap external calls (syslog, psutil) | **Not used** |
| `ExtensionManager` | Monitor extension health | **Not used** |

---

## 7. Test Coverage

| Test File | Coverage |
|-----------|----------|
| **None** | Zero tests for any monitoring module |

**Total: 0 tests for 5 modules (0%)**

---

## 8. Recommendations Summary

### Priority 1 (Immediate)
1. **Add `monitoring/__pycache__/` to `.gitignore`**
2. **Fix Windows Event Log anchoring** — use `pywin32` `win32evtlogutil.ReportEvent()` with registered source
3. **Fix blocking CPU check** — use non-blocking `psutil.cpu_percent(interval=None)` with cached value
4. **Fix quota enforcement** — check job status before deleting temp files

### Priority 2 (Short-term)
5. **Add unit tests** for all 5 modules (audit chain, resource snapshot, temp cleanup, health checks, CLI)
6. **Add async health check support** — convert `HealthCheck._run_with_timeout` to `asyncio.wait_for()`
7. **Add Prometheus metrics export** from `ResourceMonitor` and `HealthChecker`
8. **Implement accurate cache sizing** in `LRUCache` (recursive `getsizeof` or `pympler`)
9. **Add audit log retention policy** (auto-purge old entries with anchor preservation)

### Priority 3 (Medium-term)
10. **Unify quota systems** — merge `ResourceQuotaManager` + `TempFileManager` enforcement
11. **Add distributed tracing** — correlation IDs across monitoring components
12. **Implement alerting** — webhook/email/pager for critical health/audit events
13. **Add health history storage** — trend analysis, SLA reporting
14. **Convert CLI to library** — `verify_audit` as importable module
15. **Add temp file compression** — gzip/archive before deletion for recoverability

---

## 9. Output for Next Task (security/)

**Context to pass forward:**
- Monitoring provides: tamper-proof audit log with hash chain + external anchoring, resource monitoring with quota enforcement, temp file management with LRU cache, comprehensive health checks (12 subsystems) with liveness/readiness probes
- Security folder contains: `__init__.py`, `permission_manager.py`, `approval_manager.py`
- `PermissionManager` likely: permission system for agents/tools (used by `BaseAgent`, `UniversalMCPServer`)
- `ApprovalManager` likely: approval gates for destructive operations (used by `WorkflowEngine`, `UniversalMCPServer`)
- Key integration: `PermissionManager` used by `BaseAgent.can_use_tool()`, `ApprovalManager` used by `WorkflowEngine._approval_handler()` and `UniversalMCPServer._execute_tool()`
- Watch for: Circular imports between security and monitoring/agents; security should not import monitoring internals

---

*End of monitoring/ folder analysis*