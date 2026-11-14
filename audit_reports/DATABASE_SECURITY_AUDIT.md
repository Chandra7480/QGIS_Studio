# DATABASE AND SECURITY AUDIT — Universal AI GIS Studio

## 1. Database Schema

**File:** `database/schema.sql` — 18 tables

| Table | Purpose | FKs | Indexes |
|-------|---------|-----|---------|
| app_settings | Key/value settings | No | No |
| ai_hosts | AI host configurations | No | No |
| api_providers | API provider configurations | No | No |
| api_profiles | API key credential references | api_providers | No |
| mcp_servers | MCP server configurations | No | No |
| mcp_tools | Discovered MCP tools | mcp_servers | idx_mcp_tools_server |
| agents | Agent definitions | No | No |
| agent_tools | Agent-tool assignments | agents, mcp_tools | idx_agent_tools_agent |
| skills | Skill definitions | No | No |
| agent_skills | Agent-skill assignments | agents, skills | idx_agent_skills_agent |
| workflows | Workflow definitions | No | No |
| workflow_steps | Workflow step definitions | workflows | idx_workflow_steps_workflow |
| jobs | Job records | None (FKs removed) | idx_jobs_status, idx_jobs_agent |
| job_events | Job audit trail | jobs | idx_job_events_job |
| tool_runs | Tool execution records | jobs, mcp_tools | idx_tool_runs_job |
| approvals | Approval records | No | idx_approvals_status |
| project_context | Current project snapshot | No | No |
| capability_registry | Discovered GIS capabilities | No | idx_capability_category |
| gcp_records | Ground control points | jobs | idx_gcp_job |
| datasets | Registered data sources | No | idx_datasets_type |
| audit_logs | Security audit log | No | idx_audit_timestamp |

**WAL mode:** `PRAGMA journal_mode=WAL` ✅  
**Foreign keys:** `PRAGMA foreign_keys=ON` ✅  
**Transactions:** `BEGIN`/`COMMIT`/`ROLLBACK` in context manager ✅  
**Migrations:** `schema_migrations` table + migration files ✅

**FK Issue:** Jobs table FKs to agents and mcp_tools were removed (caused IntegrityError when builtin agents aren't persisted). This is noted as a design compromise.

## 2. Repository Layer

| Repository | File | Methods |
|------------|------|---------|
| SettingsRepository | settings_repository.py | get, set, get_all |
| JobRepository | job_repository.py | create, get, update_status, set_output, cancel, list, add_event, get_events |
| AuditRepository | audit_repository.py | log, list |

**SQL not in UI:** ✅ Repository pattern used, no direct SQL in UI components.

## 3. Security Analysis

### Credential Storage
**File:** `integrations/api_providers/api_manager.py`

| Practice | Implementation | Status |
|----------|---------------|--------|
| API keys in plaintext DB | ❌ NOT DONE | ✅ GOOD |
| API keys in logs | ❌ NOT DONE (SensitiveFilter strips them) | ✅ GOOD |
| OS credential manager | `keyring` referenced but optional fallback | PARTIAL |
| Credential reference only | `credential_ref` stored instead of key | ✅ GOOD |

**SensitiveFilter:** Strips `api_key`, `apikey`, `secret`, `password`, `token`, `credential` from log records ✅

### Authentication
**File:** `security/auth.py`

| Feature | Implementation | Status |
|---------|---------------|--------|
| Bridge auth token | Optional token-based | REAL |
| Token validation | `validate(provided)` compares to stored token | REAL |
| Auth not configured | token=None → allow all (dev mode) | ⚠️ Dev mode |

### Permission Management
**File:** `security/permission_manager.py`

| Feature | Implementation | Status |
|---------|---------------|--------|
| Tool allowlists | agent_tools table | REAL |
| Agent permissions | permission_level (read/standard/elevated) | REAL |
| Destructive approval | destructive_approval_required() | REAL |

### Approval Management
**File:** `security/approval_manager.py`

| Feature | Implementation | Status |
|---------|---------------|--------|
| Request approval | INSERT into approvals table | REAL |
| Decide (approve/deny) | UPDATE status | REAL |
| Check approved | SELECT status | REAL |

### Audit Logging
**File:** `monitoring/audit.py`

| Feature | Implementation | Status |
|---------|---------------|--------|
| Log security events | AuditRepository.log() | REAL |
| List recent logs | AuditRepository.list() | REAL |
| Actor, action, target, outcome, details, ip | All captured | REAL |

## 4. Security Vulnerability Scan

| Vulnerability | Check | Status |
|---------------|-------|--------|
| Plaintext credentials in DB | Searched | ✅ NOT FOUND |
| Exposed API keys in logs | SensitiveFilter | ✅ MITIGATED |
| Unsafe shell execution | Searched for subprocess, os.system | ✅ NOT IN PRODUCTION |
| Arbitrary file deletion | No file deletion in production | ✅ NOT FOUND |
| Path traversal | No file path manipulation in production | ✅ NOT FOUND |
| Unauthenticated local service | Bridge auth optional (dev mode) | ⚠️ WARNING |
| Unsafe deserialization | No pickle/eval in production | ✅ NOT FOUND |
| SQL injection | Parameterized queries everywhere | ✅ MITIGATED |
| Unrestricted plugin execution | Extension manifest validation | ✅ IMPLEMENTED |

## 5. Resource Monitoring

**File:** `monitoring/resource_monitor.py`

| Feature | Implementation | Status |
|---------|---------------|--------|
| Disk usage | shutil.disk_usage() | REAL |
| Memory usage | Windows GlobalMemoryStatusEx via ctypes | REAL |
| Temp file cleanup | Config option only (not implemented) | ❌ NOT IMPLEMENTED |
| Cache limits | Config option only | ❌ NOT IMPLEMENTED |

## 6. Emergency Stop

**File:** `engines/cursor_controller/cursor_controller.py`

| Feature | Implementation | Status |
|---------|---------------|--------|
| Emergency stop | _emergency_stopped flag | REAL (cursor only) |
| Job cancellation | JobManager.cancel_job() | REAL |
| System-wide emergency stop | ❌ NOT IMPLEMENTED | MISSING |

## 7. Verdict

| Component | Status |
|-----------|--------|
| Database schema (18 tables) | REAL, COMPLETE |
| WAL mode, FKs, transactions | REAL |
| Migrations | REAL |
| Repository layer | REAL |
| Credential storage (no plaintext) | REAL |
| Sensitive log filtering | REAL |
| Bridge authentication | REAL (optional) |
| Permission management | REAL |
| Approval workflow | REAL |
| Audit logging | REAL |
| SQL injection protection | REAL (parameterized) |
| Emergency stop (system-wide) | ❌ NOT IMPLEMENTED |
| Temp file cleanup | ❌ NOT IMPLEMENTED |
| Cache limits | ❌ NOT IMPLEMENTED |

**Overall:** Database and security foundation is solid. Missing: system-wide emergency stop, temp file cleanup, cache limits. Bridge auth is optional (dev mode allows all).
