# Database Folder Analysis — Universal AI GIS Studio

**Task:** task-5  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent  
**Context:** core/ (task-1), clusters/ (task-2), engines/ (task-3), agents/ (task-4) analyses read prior

---

## 1. Folder Structure

```
database/
├── __init__.py                      # Exports Database, SCHEMA
├── db.py                            # Database (sync) + DatabasePool (514 lines)
├── async_db.py                      # AsyncDatabase + AsyncDatabasePool (285 lines)
├── schema.sql                       # Full DDL schema (314 lines)
├── schema.py                        # Schema loader + migration runner (108 lines)
├── migrations/
│   ├── __init__.py
│   ├── 001_initial_indexes.sql      # Additional indexes (6 lines)
│   └── 002_audit_hash_chain.sql     # Audit hash chain + anchors (23 lines)
├── repositories/
│   ├── __init__.py
│   ├── settings_repository.py       # SettingsRepository (19 lines)
│   ├── job_repository.py            # JobRepository (91 lines)
│   └── audit_repository.py          # AuditRepository with hash chain (166 lines)
└── __pycache__/
```

**Total:** ~1,500 lines of database code across 11 Python files + 2 migrations

---

## 2. Architecture & Components

### Core Database Classes

| Class | File | Purpose |
|-------|------|---------|
| **`Database`** | `db.py:306` | Main sync SQLite wrapper with thread-safe connection, WAL mode, transactions |
| **`DatabasePool`** | `db.py:34` | Multi-reader, single-writer connection pool with dedicated writer thread |
| **`AsyncDatabase`** | `async_db.py:19` | Async SQLite wrapper using `aiosqlite` with connection pool |
| **`AsyncDatabasePool`** | `async_db.py:120` | Async read/write separated pools for high concurrency |

### Repository Pattern
| Repository | Table(s) | Key Methods |
|------------|----------|-------------|
| **`SettingsRepository`** | `app_settings` | `get()`, `set()`, `get_all()` |
| **`JobRepository`** | `jobs`, `job_events` | `create()`, `get()`, `update_status()`, `set_output()`, `cancel()`, `list()`, `add_event()`, `get_events()`, `update_progress()`, `get_progress()` |
| **`AuditRepository`** | `audit_logs`, `audit_anchors` | `log()`, `list()`, `get_all_ordered()`, `get_last_hash()`, `add_anchor()`, `get_anchors()`, `verify_chain()` |

### Schema (25 Tables)
| Category | Tables |
|----------|--------|
| **Settings** | `app_settings` |
| **AI/Integration** | `ai_hosts`, `api_providers`, `api_profiles`, `mcp_servers`, `mcp_tools` |
| **Agents** | `agents`, `agent_tools`, `agent_skills`, `agent_contexts` |
| **Skills** | `skills` |
| **Workflows** | `workflows`, `workflow_steps`, `workflow_states` |
| **Jobs/Execution** | `jobs`, `job_events`, `tool_runs` |
| **Approvals** | `approvals` |
| **Project/Context** | `project_context` |
| **Capabilities** | `capability_registry` |
| **Georeferencing** | `gcp_records` |
| **Data** | `datasets` |
| **Audit/Security** | `audit_logs`, `audit_anchors` |
| **Migrations** | `schema_migrations` |

### Key Indexes (14 defined)
- `idx_jobs_status`, `idx_jobs_agent`, `idx_job_events_job`, `idx_tool_runs_job`
- `idx_mcp_tools_server`, `idx_mcp_tools_enabled`, `idx_agents_enabled`, `idx_skills_enabled`
- `idx_agent_tools_agent`, `idx_agent_skills_agent`, `idx_workflow_steps_workflow`
- `idx_gcp_job`, `idx_audit_timestamp`, `idx_audit_hash`, `idx_audit_anchors_log`, `idx_capability_category`, `idx_datasets_type`, `idx_approvals_status`

---

## 3. Key Design Decisions & Patterns

### ✅ Strong Patterns

1. **WAL Mode + Foreign Keys** — All connections enable `journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON` for concurrency and integrity

2. **Thread-Safe Sync Database** — `Database` uses `RLock` for write serialization; `DatabasePool` provides multi-reader/single-writer via dedicated writer thread with queue

3. **Async Support** — `AsyncDatabase`/`AsyncDatabasePool` using `aiosqlite.Pool` for non-blocking access in AgentOrchestrator, workflows

4. **Migration System** — `schema.py` applies base `schema.sql` + versioned migrations from `migrations/` tracked in `schema_migrations` table

5. **Repository Pattern** — All SQL encapsulated in repository classes; UI/business logic never writes raw SQL

6. **Tamper-Proof Audit Log** — `AuditRepository` implements SHA-256 hash chain: `SHA256(prev_hash || current_data)` with external anchoring support

7. **Dual Access Modes** — `Database` supports both single-connection (`use_pool=False`) and pooled (`enable_pool()`) modes

8. **Context Manager Transactions** — Both sync (`Database.transaction()`) and async (`AsyncDatabase.transaction()`) provide BEGIN/COMMIT/ROLLBACK

### ⚠️ Areas of Concern

1. **Duplicate `fetchone`/`fetchall` Methods** — `Database` class defines `fetchone`/`fetchall` at lines 414-420 AND again at 457-467 (pool-aware versions) — the second pair shadows the first

2. **Duplicate `enable_pool`/`disable_pool`** — Defined at lines 349-364 AND again at 496-510

3. **Schema Hardcoded in `schema.sql`** — No programmatic schema definition; migrations are separate SQL files

4. **Migration 002 Partial in SQL** — `002_audit_hash_chain.sql` has comment "handled in Python code" for column addition — split responsibility

5. **No Connection Pool Health Checks** — No `ping()` or health verification for pooled connections

6. **Audit Hash Default** — `audit_hash` column default `''` in schema but Python code expects 64-char hash

---

## 4. Dependencies

### Internal
```
database.db                  → core.logging, core.exceptions
database.async_db            → core.logging, core.exceptions, aiosqlite
database.schema              → database.db, core.logging, core.exceptions
database.repositories.*      → database.db, core.exceptions
database.migrations/*.sql    → (raw SQL)
```

### External
- **SQLite** — Built-in `sqlite3` (sync), `aiosqlite` (async)
- **threading/queue** — Writer thread pool implementation

### Consumers (from prior analyses)
| Consumer | Uses |
|----------|------|
| `core.config.Config` | `Database.get_all_settings()`, `set_setting()` |
| `core.capability_registry.CapabilityRegistry` | `Database` for `capability_registry` table |
| `core.job_manager.JobManager` | `JobRepository` for job lifecycle |
| `core.emergency_stop.EmergencyStop` | `AuditRepository` for emergency stop audit |
| `agents.base_agent.BaseAgent` | `Database` for `agent_contexts` persistence |
| `agents.agent_manager.AgentManager` | `Database` for `agents`, `agent_tools` tables |
| `agents.orchestrator.AgentOrchestrator` | `JobManager` → `JobRepository` |
| `agents.custom.custom_builder.CustomAgentBuilder` | `Database` for `agents` table |

---

## 5. Issues Found

### 🔴 REMOVE (Dead Code / Bugs / Duplicates)
| Item | Location | Issue |
|------|----------|-------|
| `__pycache__/` | `database/`, `database/repositories/`, `database/migrations/` | Compiled bytecode committed — gitignore |
| **Duplicate `fetchone`/`fetchall`** | `db.py:414-420` and `457-467` | Second pair shadows first; pool-aware versions should replace, not duplicate |
| **Duplicate `enable_pool`/`disable_pool`** | `db.py:349-364` and `496-510` | Identical methods defined twice |
| **Empty `repositories/__init__.py`** | `repositories/__init__.py` | Should export repository classes |

### 🟡 ADD (Missing Features / Tests / Docs)
| Gap | Scope | Recommendation |
|-----|-------|----------------|
| **Repository for each table** | `repositories/` | Missing: `AiHostRepository`, `AgentRepository`, `WorkflowRepository`, `McpServerRepository`, `CapabilityRepository`, `DatasetRepository`, `GcpRepository`, `ProjectContextRepository`, `ApprovalRepository`, `ToolRunRepository` |
| **Async repositories** | `repositories/` | All repositories are sync-only; need async variants for `AgentOrchestrator` |
| **Unit tests** | `repositories/` | Only `JobRepository` tested (3 tests); zero tests for `SettingsRepository`, `AuditRepository` |
| **Migration tests** | `schema.py` | No tests for migration runner, schema initialization |
| **Pool health checks** | `DatabasePool`, `AsyncDatabasePool` | No `ping()` / `is_healthy()` method |
| **Connection pooling metrics** | `DatabasePool` | No stats: active connections, queue depth, wait times |
| **Audit log pagination** | `AuditRepository` | `list()` only supports LIMIT; no offset/cursor pagination |
| **Backup/restore** | `Database` | No `backup()` / `restore()` methods |
| **Schema documentation** | `schema.sql` | No ER diagram or table documentation |

### 🔵 IMPROVE (Refactoring / Performance / Patterns)
| Opportunity | Details |
|-------------|---------|
| **Fix duplicate methods** | Remove first `fetchone`/`fetchall` (lines 414-420) and first `enable_pool`/`disable_pool` (349-364) |
| **Export repositories** | Add `__all__` to `repositories/__init__.py` |
| **Unify migration 002** | Move `audit_hash` column addition from Python `_ensure_audit_hash_column()` to SQL migration |
| **Programmatic schema** | Consider SQLAlchemy-style declarative or at least Python schema builder for type safety |
| **Repository base class** | Create `BaseRepository` with common CRUD patterns |
| **Async repository variants** | Add `AsyncJobRepository`, `AsyncAuditRepository` using `AsyncDatabase` |
| **Batch operations** | Add `executemany` support in repositories for bulk inserts |
| **Query builder** | Simple query builder for complex filters (e.g., `JobRepository.list()` with multiple filters) |
| **Transaction retry** | Add retry logic for `sqlite3.OperationalError: database is locked` |
| **Read replicas** | For high read load, support multiple read pool connections (already in `DatabasePool`) |

---

## 6. Cross-Module Integration (with prior analyses context)

### Current Integration Points
```
core.config.Config              ──uses──▶ Database.get_all_settings(), set_setting()
core.capability_registry        ──uses──▶ Database (capability_registry table)
core.job_manager.JobManager     ──uses──▶ JobRepository (jobs, job_events)
core.emergency_stop             ──uses──▶ AuditRepository (audit logging)
agents.base_agent.BaseAgent     ──uses──▶ Database (agent_contexts table)
agents.agent_manager.AgentManager ──uses──▶ Database (agents, agent_tools tables)
agents.orchestrator.AgentOrchestrator ──uses──▶ JobManager → JobRepository
agents.custom.custom_builder    ──uses──▶ Database (agents table)
```

### Missing Integration
| Core Service | Should Integrate With | Current State |
|--------------|----------------------|---------------|
| `EventBus` | Repository changes (job created, audit logged) | **Not used** |
| `CapabilityRegistry` | Register `Database` capabilities (pool status, migration version) | **Not used** |
| `CircuitBreaker` | Wrap database operations (especially async pool acquire) | **Not used** |
| `ResourceQuotaManager` | Track DB connection pool memory/CPU | **Not used** |

---

## 7. Test Coverage

| Test File | Coverage |
|-----------|----------|
| `test_database.py` | `Database` init + settings (1 test), `JobRepository` CRUD (2 tests), `JobRepository` not found (1 test) |
| **Missing** | `DatabasePool` tests, `AsyncDatabase` tests, `AsyncDatabasePool` tests, `SettingsRepository` tests, `AuditRepository` tests, migration tests, schema initialization tests |

**Total: 4 tests for 11 database modules (36%)**

---

## 8. Recommendations Summary

### Priority 1 (Immediate)
1. **Add all `database/**/__pycache__/` to `.gitignore`**
2. **Fix duplicate methods** in `Database` class — remove lines 414-420 and 349-364
3. **Export repositories** in `repositories/__init__.py`
4. **Unify migration 002** — move `audit_hash` column addition to SQL

### Priority 2 (Short-term)
5. **Add async repository variants** (`AsyncJobRepository`, `AsyncAuditRepository`, `AsyncSettingsRepository`)
6. **Add unit tests** for `SettingsRepository`, `AuditRepository`, `DatabasePool`, `AsyncDatabase`, migrations
7. **Add pool health checks** and metrics to `DatabasePool` and `AsyncDatabasePool`
8. **Create base repository class** for common CRUD patterns
9. **Add audit log pagination** (offset/cursor) to `AuditRepository.list()`

### Priority 3 (Medium-term)
10. **Implement missing repositories** for all schema tables
11. **Add backup/restore** functionality to `Database`
12. **Add transaction retry logic** for lock contention
13. **Create programmatic schema definition** (Python-based, generate SQL)
14. **Add query builder** for complex repository queries
15. **Document schema** with ER diagram and table descriptions

---

## 9. Output for Next Task (bridge/)

**Context to pass forward:**
- Database provides: SQLite with WAL, sync/async pools, migrations, repositories for settings/jobs/audit, tamper-proof audit log with hash chain
- Key tables used by other modules: `jobs`, `job_events`, `app_settings`, `agents`, `agent_tools`, `agent_contexts`, `audit_logs`, `capability_registry`, `gcp_records`, `mcp_servers`, `mcp_tools`, `workflows`, `workflow_states`
- Bridge folder contains: `protocol.py` (protocol definitions)
- Bridge likely uses: `jobs` table for async job tracking, `mcp_tools` for tool registry, protocol for serialization
- Watch for: Circular imports between bridge and database; bridge protocol should be independent of database implementation

---

*End of database/ folder analysis*