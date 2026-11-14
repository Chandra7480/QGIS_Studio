# Security Folder Analysis — Universal AI GIS Studio

**Task:** task-13  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent  
**Context:** monitoring/ (task-12) analysis read prior

---

## 1. Folder Structure

```
security/
├── __init__.py                          # Empty package marker
├── permission_manager.py                # PermissionManager: tool allowlists (36 lines)
├── approval_manager.py                  # ApprovalManager: user consent gates (43 lines)
├── api_key_manager.py                   # APIKeyManager: rotation, testing, fallback, notifications (661 lines)
├── auth.py                              # BridgeAuth: token validation + API key proxy (45 lines)
├── rate_limiter.py                      # RateLimiter: token bucket (in-memory + Redis) (293 lines)
└── __pycache__/
```

**Total:** ~1,100 lines across 6 Python modules

---

## 2. Component Architecture

| Module | Class(es) | Purpose |
|--------|-----------|---------|
| **permission_manager.py** | `PermissionManager` | Agent-tool allowlist via `agent_tools` DB table |
| **approval_manager.py** | `ApprovalManager` | User consent for destructive ops; pending/approved/denied states |
| **api_key_manager.py** | `APIKeyManager`, `KeyTester`, `NotificationHandler` | Full API key lifecycle: rotation, testing, fallback, notifications, timers |
| **auth.py** | `BridgeAuth` | Bridge token validation + API key manager proxy |
| **rate_limiter.py** | `RateLimiter`, `InMemoryRateLimiterBackend`, `RedisRateLimiterBackend` | Token bucket per (agent, tool) with in-memory + Redis backends |

---

## 3. Detailed Component Analysis

### 3.1 Permission Manager (`permission_manager.py`)

**Features:**
- `check_tool(agent_id, tool_id)` → queries `agent_tools` table
- `require(agent_id, tool_id)` → raises `UAGISPermissionError` if denied
- `destructive_approval_required(action_type)` → hardcoded set of 6 action types

**Strengths:**
- Simple, direct DB-backed allowlist
- Used by `BaseAgent.call_tool()` and `UniversalMCPServer._execute_tool()`

**Issues:**
- No permission hierarchy (only flat allowlist)
- `destructive_approval_required` hardcoded — not configurable
- No time-limited permissions or scopes
- No audit logging of permission checks

### 3.2 Approval Manager (`approval_manager.py`)

**Features:**
- `request(action_type, target, requested_by)` → creates `approval_{id}` with `pending` status
- `decide(approval_id, decision, decided_by)` → `approved`/`denied` with timestamp
- `is_approved(approval_id)` → boolean check

**Integration:**
- Used by `WorkflowEngine._approval_handler()` and `UniversalMCPServer._execute_tool()`
- `mcp_server.approval.ApprovalManager` (different class) has TTL + `check_and_consume()`

**Issues:**
- Two `ApprovalManager` classes: `security.approval_manager` (simple) vs `mcp_server.approval.ApprovalManager` (with TTL, consume) — **duplication**
- No expiration/TTL for pending approvals (unlike MCP version)
- No notification to requester on decision

### 3.3 API Key Manager (`api_key_manager.py`) — **Largest Module**

**Core Features:**
| Feature | Description |
|---------|-------------|
| **Key Registration** | `register_key(provider, key_value, rotation_interval, strategy, ...)` |
| **Active Key Retrieval** | `get_active_key(provider)` / `get_active_key_id(provider)` |
| **Key Rotation** | `rotate_key(provider, new_key_value)` with validation test |
| **Automatic Fallback** | `fallback_to_previous(provider)` on failure threshold |
| **Failure Tracking** | `record_failure()` / `record_success()` with configurable threshold |
| **Scheduled Rotation** | `threading.Timer` at expiry; `_rotate_async()` callback |
| **Expiration Notifications** | `threading.Timer` at configurable days-before-expiry |
| **Key Validation** | `DefaultKeyTester` with provider-specific HTTP endpoints |
| **Notifications** | `LoggingNotificationHandler`, `WebhookNotificationHandler`, `EmailNotificationHandler` |
| **Key Revocation** | `revoke_key()` with automatic fallback |
| **Storage** | OS credential manager via `core.keyring_backend` (Windows/macOS/Linux + encrypted file fallback) |

**Data Model (`APIKeyMetadata`):**
- Provider, key_id, status (ACTIVE/ROTATING/EXPIRED/REVOKED/FAILED)
- Timestamps: created_at, expires_at, rotated_at, last_notification
- Rotation: strategy (SCHEDULED/MANUAL/ON_FAILURE), interval_days, notification_days_before
- Test config: test_endpoint, test_method, test_headers
- Failure tracking: failure_count, max_failures_before_rotate

**Strengths:**
- Comprehensive key lifecycle management
- Multi-provider support (OpenAI, Anthropic, Gemini, OpenRouter, custom)
- Secure storage via OS credential manager
- Automatic fallback on validation failure
- Extensible notification handlers (log, webhook, email)
- Thread-safe with `RLock`

**Issues:**
- `threading.Timer` for rotation/notifications — not persistent across restarts
- `_rotate_async()` logs warning but **cannot auto-generate new keys** — requires manual intervention
- `list_keys(provider)` returns empty list — keyring backend `list_keys()` unimplemented
- `DefaultKeyTester` uses synchronous `requests` — blocks timer threads
- Hardcoded test endpoints for providers (not configurable per-key)
- `_cancel_timers()` uses hardcoded day intervals `[7, 1, 30, 60]`
- No cleanup of expired keys from keyring (only metadata status change)

### 3.4 Bridge Auth (`auth.py`)

**Features:**
- `validate(provided_token)` → simple string comparison
- `get_provider_key(provider)` → proxies to `APIKeyManager.get_active_key()`
- `record_provider_failure/success()` → proxies to key manager
- `rotate_provider_key()` / `fallback_provider_key()` → proxies to key manager

**Integration:**
- Used by `BridgeRequestHandler._check_auth()` and `AsyncQgisBridgeClient.check_auth()`
- `APIKeyManager` instantiated via `get_api_key_manager()`

### 3.5 Rate Limiter (`rate_limiter.py`)

**Architecture:**
```
RateLimiter
  ├── InMemoryRateLimiterBackend (RLock + dict)
  └── RedisRateLimiterBackend (Lua script for atomicity)
```

**Token Bucket Algorithm:**
- `capacity` = max tokens
- `refill_rate` = tokens/second
- `atomic_consume(key, capacity, refill_rate, tokens_requested)` → `RateLimitResult`

**Configuration:**
- `default_config` = 100 capacity, 10 tokens/sec
- `tool_configs` = dict of tool_id → `RateLimitConfig`
- `bridge.dispatcher.DEFAULT_RATE_LIMITS` defines 150+ tool-specific limits

**Backends:**
| Backend | Atomicity | Persistence | Multi-process |
|---------|-----------|-------------|---------------|
| InMemory | RLock | Process memory | No |
| Redis | Lua script | Redis (24h TTL) | Yes |

**Strengths:**
- Atomic Redis operations via Lua script
- Fail-open on Redis errors (allows request, logs error)
- Per-(identifier, tool) buckets
- Configurable per-tool limits

**Issues:**
- Fail-open on Redis errors — **security risk** (allows unlimited requests during Redis outage)
- InMemory backend not shared across processes
- `get_remaining()` not atomic (read-then-calculate)
- No distributed lock for InMemory backend
- Redis connection lazy-initialized; no reconnection logic

---

## 4. Dependencies

### Internal
```
security.permission_manager     → database.db.Database, core.exceptions
security.approval_manager       → database.db.Database, core.exceptions
security.api_key_manager        → core.keyring_backend, core.logging
security.auth                   → security.api_key_manager
security.rate_limiter           → core.logging, (redis optional)
```

### External
| Module | Dependencies |
|--------|--------------|
| api_key_manager | requests, smtplib, email, threading, uuid, json, datetime |
| rate_limiter | redis (optional), threading, time |
| auth | security.api_key_manager |

### Consumers
| Consumer | Uses |
|----------|------|
| `agents.base_agent.BaseAgent` | `PermissionManager.check_tool()`, `require()` |
| `mcp_server.server.UniversalMCPServer` | `PermissionManager`, `ApprovalManager`, `RateLimiter` |
| `agents.orchestrator.AgentOrchestrator` | `ApprovalManager` |
| `bridge.request_handler.BridgeRequestHandler` | `BridgeAuth.validate()` |
| `bridge.dispatcher.BridgeDispatcher` | `RateLimiter` |
| `bridge.bridge_server_async` | `RateLimiter` (dependency injection) |

---

## 5. Issues Found

### 🔴 REMOVE (Security Risks / Bugs)
| Item | Location | Issue |
|------|----------|-------|
| `__pycache__/` | `security/__pycache__/` | Compiled bytecode committed — gitignore |
| **Fail-open Redis rate limiter** | `rate_limiter.py:205-213` | On Redis error, `atomic_consume` returns `allowed=True` — **allows unlimited requests during Redis outage** |
| **Duplicate ApprovalManager** | `security/aproval_manager.py` vs `mcp_server/approval.py` | Two implementations with different features; `security` version lacks TTL, consume, notification |
| **Blocking HTTP in timer threads** | `api_key_manager.py:115-125` | `DefaultKeyTester.test_key()` uses synchronous `requests` in `threading.Timer` callback — blocks timer thread |
| **Timer persistence** | `api_key_manager.py:528-552` | `threading.Timer` not persistent across restarts; missed rotations on downtime |
| **Fail-open rate limiter** | `rate_limiter.py:207-213` | Redis errors return `allowed=True` — should fail-closed or at least log critically |
| **Insecure default in PermissionManager** | `mcp_server/server.py:93` | `check_permission` returns `True` if no grants configured — **allows all by default** |

### 🟡 ADD (Missing Features)
| Gap | Scope | Recommendation |
|-----|-------|----------------|
| **Async key testing** | `api_key_manager.py` | Use `aiohttp` in async context; don't block timer threads |
| **Persistent scheduled jobs** | `api_key_manager.py` | Replace `threading.Timer` with APScheduler or DB-backed scheduler |
| **Key generation integration** | `api_key_manager.py` | Integrate with provider APIs for auto-rotation (OpenAI, Anthropic key generation) |
| **Key listing/indexing** | `api_key_manager.py` | Implement `list_keys()` via keyring backend or separate index |
| **Permission scopes/hierarchy** | `permission_manager.py` | Add resource-level permissions, time-limited grants |
| **Approval expiration** | `approval_manager.py` | Add TTL (like MCP version) and auto-deny on expiry |
| **Rate limiter fail-closed** | `rate_limiter.py` | On Redis error, should deny or queue, not allow |
| **Distributed in-memory limiter** | `rate_limiter.py` | Add Redis-only mode or etcd/consul backend for multi-instance |
| **Audit logging** | All | Log permission checks, approval decisions, rate limit hits |
| **Unit tests** | All | Zero tests for any security module |

### 🔵 IMPROVE (Refactoring)
| Opportunity | Details |
|-------------|---------|
| **Unify ApprovalManager** | Merge `security.approval_manager` + `mcp_server.approval` into single implementation with TTL, consume, notifications |
| **Async key validation** | Move `DefaultKeyTester` to async; use `aiohttp`; run in event loop not timer thread |
| **Persistent scheduler** | Replace `threading.Timer` with APScheduler (persistent job store) or DB-backed cron |
| **Keyring list_keys()** | Implement `list_keys()` in `core.keyring_backend` for `APIKeyManager.list_keys()` |
| **Atomic get_remaining** | Make `RateLimiter.get_remaining()` atomic (Lua script for Redis) |
| **Rate limit metrics** | Add Prometheus metrics for bucket depth, rejections, latency |
| **Redis connection resilience** | Add reconnection logic, connection pooling, sentinel support |
| **Configuration-driven limits** | Move `DEFAULT_RATE_LIMITS` from `bridge.dispatcher` to config file |
| **Permission inheritance** | Add role-based permissions with inheritance |

---

## 6. Cross-Module Integration (from monitoring/ context)

### Current Integration
```
PermissionManager         → agent_tools DB table; used by BaseAgent, UniversalMCPServer
ApprovalManager (security) → approvals DB table; used by WorkflowEngine
ApprovalManager (MCP)      → approvals DB table; used by UniversalMCPServer, WorkflowEngine
APIKeyManager             → OS credential manager; used by BridgeAuth, UniversalMCPServer
RateLimiter               → InMemory/Redis; used by BridgeDispatcher, BridgeServerAsync
BridgeAuth                → token validation + APIKeyManager proxy; used by BridgeRequestHandler, AsyncQgisBridgeClient
```

### Missing Integration
| Service | Should Integrate | Current State |
|---------|-----------------|---------------|
| `EventBus` | Permission denied, approval requested, rate limit hit | **Not used** |
| `AuditRepository` | Log permission checks, approvals, key rotations | **Not used** |
| `CapabilityRegistry` | Register security capabilities | **Not used** |
| `CircuitBreaker` | Wrap Redis/keyring/HTTP calls | **Not used** |
| `JobManager` | Track async key rotations | **Not used** |

---

## 7. Test Coverage

| Test File | Coverage |
|-----------|----------|
| **None** | Zero tests for any security module |

**Total: 0 tests for 6 modules (0%)**

---

## 8. Recommendations Summary

### Priority 1 (Immediate)
1. **Add `security/__pycache__/` to `.gitignore`**
2. **Fix fail-open rate limiter** — on Redis error, deny request or queue; never allow
3. **Fix fail-closed permission default** — `PermissionManager.check_permission()` should deny if no grants
4. **Unify ApprovalManager** — merge `security.approval_manager` + `mcp_server.approval` into single implementation

### Priority 2 (Short-term)
5. **Make key testing async** — move `DefaultKeyTester` to `aiohttp`; run in event loop
6. **Replace `threading.Timer`** with APScheduler (persistent job store) for rotations/notifications
7. **Add unit tests** for all 6 modules (permission, approval, API key, auth, rate limiter)
8. **Implement `list_keys()`** in keyring backend for `APIKeyManager.list_keys()`
9. **Add audit logging** for permission checks, approvals, key rotations, rate limit hits

### Priority 3 (Medium-term)
10. **Integrate provider key generation APIs** for auto-rotation (OpenAI, Anthropic, etc.)
11. **Add Redis reconnection logic** with exponential backoff
12. **Implement distributed in-memory limiter** (etcd/consul) or require Redis for multi-instance
13. **Add Prometheus metrics** for rate limiter, API key status, approval queue
14. **Add permission scopes/hierarchy** with time-limited grants
15. **Convert `threading.Timer` to async** — use `asyncio.create_task()` with `asyncio.sleep()` in event loop

---

## 9. Output for Next Task (utils/)

**Context to pass forward:**
- Security provides: permission allowlists, approval gates, API key lifecycle management, token bucket rate limiting
- Key integrations: `BaseAgent`, `UniversalMCPServer`, `WorkflowEngine`, `BridgeDispatcher`, `BridgeRequestHandler`
- Utils folder likely contains: utility functions, helpers, common code
- Watch for: Circular imports between utils and security/core/database; utils should be leaf dependencies

---

*End of security/ folder analysis*