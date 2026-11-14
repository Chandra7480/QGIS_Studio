# Integrations Folder Analysis — Universal AI GIS Studio

**Task:** task-8  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent  
**Context:** mcp_server/ (task-7) analysis read prior

---

## 1. Folder Structure

```
integrations/
├── __init__.py                              # Package overview
├── ai_hosts/
│   ├── __init__.py
│   └── ai_host_manager.py                   # OpenCode/Codex host management (56 lines)
├── api_providers/
│   ├── __init__.py
│   └── api_manager.py                       # OpenAI/Gemini/Anthropic/OpenRouter config (80 lines)
├── external_mcp/
│   ├── __init__.py
│   └── mcp_manager.py                       # External MCP server manager (66 lines)
├── llm_providers/
│   ├── __init__.py                          # Provider registry + factory (117 lines)
│   ├── base.py                              # Base classes, data structures, errors (347 lines)
│   └── providers/
│       ├── __init__.py
│       ├── openai.py                        # OpenAI provider (196 lines)
│       ├── anthropic.py                     # Anthropic provider (273 lines)
│       ├── gemini.py                        # Google Gemini provider (333 lines)
│       ├── openrouter.py                    # OpenRouter provider (85 lines)
│       └── custom.py                        # Custom/OpenAI-compatible (109 lines)
├── fastmcp_server/
│   ├── main.py                              # External MCP server via TCP socket (366 lines)
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── README.md
└── __pycache__/
```

**Total:** ~2,000 lines across 14 Python modules

---

## 2. Component Purposes & Architecture

### AI Host Manager (`ai_hosts/ai_host_manager.py`)
- **Purpose**: Manage external AI host configurations (OpenCode, Codex, MCP clients)
- **Storage**: `ai_hosts` table (id, name, host_type, transport, endpoint, enabled, image_capable)
- **Operations**: add, list, enable/disable, test_connection, get_default
- **Transports**: stdio, http, websocket
- **Integration**: Used by agents for AI host selection

### API Manager (`api_providers/api_manager.py`)
- **Purpose**: Configure optional direct API integrations
- **Supported Providers**: openai, gemini, anthropic, openrouter, openai_compatible, custom
- **Security**: API keys stored in OS credential manager (Windows Credential Manager, macOS Keychain, Linux Secret Service) via `credential_store`; fallback stores reference only
- **Operations**: add_provider, set_api_key, set_enabled, test_connection, get_default, list_providers
- **Configuration**: base_url, model_id, timeout, retry_count, image_capable

### External MCP Manager (`external_mcp/mcp_manager.py`)
- **Purpose**: Manage external MCP server connections
- **Storage**: `mcp_servers` table (id, name, transport, command, args, url, enabled, connected, trust_level)
- **Trust Levels**: `trusted` / `untrusted` (default: untrusted)
- **Operations**: add_server, set_enabled, set_trust, test_connection, discover_tools, set_tool_enabled
- **Tool Discovery**: Queries `mcp_tools` table for server's tools

### LLM Providers (`llm_providers/`)
| Provider | Class | Key Features |
|----------|-------|--------------|
| **OpenAI** | `OpenAIProvider` | GPT-4o, GPT-4o-mini, o1-preview, streaming, tools, vision |
| **Anthropic** | `AnthropicProvider` | Claude 3.5 Sonnet/Opus/Haiku, streaming, tools, vision |
| **Gemini** | `GeminiProvider` | Gemini 1.5 Pro/Flash, streaming, tools, vision, API key as query param |
| **OpenRouter** | `OpenRouterProvider` (extends OpenAI) | 100+ models via unified API, adds HTTP-Referer/X-Title headers |
| **Custom** | `CustomProvider` (extends OpenAI) | Ollama/LM Studio/vLLM, optional API key, Ollama /api/tags fallback |

**Base Architecture** (`base.py`):
- **`LLMMessage`**: role (system/user/assistant/tool), content, tool_calls, tool_call_id
- **`LLMTool`**: name, description, parameters (JSON Schema), namespace; converts to OpenAI/Anthropic/Gemini formats
- **`LLMResponse`**: content, tool_calls, model, usage, finish_reason, raw_response, provider
- **`LLMProviderConfig`**: api_key, base_url, model, temperature, max_tokens, top_p, penalties, timeout, retries, extra_headers/params
- **`LLMProvider` (ABC)**: `chat()`, `chat_stream()`, `list_models()`, `validate_key()`, error hierarchy (Auth, RateLimit, ContextLength, Connection, Server)

### FastMCP Server (`fastmcp_server/main.py`)
- **Purpose**: External MCP server connecting to QGIS via TCP socket (port 9876)
- **Transport**: stdio (for MCP clients like Claude Code, Codex, Cursor)
- **Protocol**: Length-prefixed JSON over TCP
- **Tools**: 14 tools (ping, diagnose, project, layers, features, processing, SQL, render, execute_code)
- **Auth**: Shared token via `QGIS_MCP_TOKEN` env var
- **Architecture**: `QGISClient` async TCP client + MCP `Server` with `list_tools`/`call_tool` handlers

---

## 3. Dependencies

### Internal
```
integrations.ai_hosts.ai_host_manager     → database.db.Database
integrations.api_providers.api_manager    → database.db.Database, core.exceptions
integrations.external_mcp.mcp_manager     → database.db.Database, core.exceptions
integrations.llm_providers.base           → (standalone ABC + dataclasses)
integrations.llm_providers.providers.*    → llm_providers.base, httpx
integrations.fastmcp_server.main          → mcp.server, httpx, asyncio, pydantic
```

### External
| Component | Dependencies |
|-----------|--------------|
| LLM Providers | `httpx` (sync + async), `json` |
| FastMCP Server | `mcp.server`, `mcp.types`, `httpx`, `pydantic`, `asyncio` |
| All | `core.exceptions` (ConfigurationError, NotFoundError) |

### Database Tables Used
| Manager | Tables |
|---------|--------|
| AIHostManager | `ai_hosts` |
| APIManager | `api_providers`, `api_profiles` |
| MCPManager | `mcp_servers`, `mcp_tools` |

---

## 4. Security Analysis

### ✅ Strong Patterns
1. **Credential Isolation** — API keys never stored in database; `APIManager.set_api_key()` uses injected `credential_store` (OS credential manager via `core.keyring_backend`)
2. **Trust Levels** — External MCP servers default to `untrusted`; explicit opt-in required
3. **No Plaintext Secrets** — `api_profiles` table stores only `credential_ref` (pointer to OS credential manager)
4. **Fallback Logging** — Warning logged when credential store unavailable (doesn't fail silently)

### ⚠️ Concerns
1. **`APIManager` credential_store injection** — Optional; if `None`, falls back to reference-only storage (key not persisted)
2. **FastMCP token** — Shared secret in env var `QGIS_MCP_TOKEN`; no rotation, no per-client tokens
3. **Custom provider** — No API key validation by default; `SUPPORTS_VISION=False` but depends on endpoint
4. **OpenRouter headers** — `HTTP-Referer` and `X-Title` hardcoded; should be configurable
5. **`execute_code` tool** — FastMCP exposes arbitrary PyQGIS code execution (dangerous!)

---

## 5. Issues Found

### 🔴 REMOVE (Dead Code / Security Risks / Duplicates)
| Item | Location | Issue |
|------|----------|-------|
| `__pycache__/` | All subfolders | Compiled bytecode committed — gitignore |
| `execute_code` tool | `fastmcp_server/main.py:268` | **Arbitrary code execution** — high risk; should be removed or heavily restricted |
| `CustomProvider` DEFAULT_MODELS | `custom.py:24-34` | Hardcoded Ollama models; not dynamic |
| `OpenRouterProvider` headers | `openrouter.py:44-47` | Hardcoded referer/title; not configurable |

### 🟡 ADD (Missing Features / Tests / Docs)
| Gap | Scope | Recommendation |
|-----|-------|----------------|
| **Unit tests** | All 14 modules | Zero tests for any integration module |
| **Integration tests** | All | No tests with real OpenCode, Codex, OpenAI, Anthropic, etc. |
| **API key rotation** | `api_manager.py` | No `rotate_key()` or expiry tracking |
| **MCP server health monitoring** | `mcp_manager.py` | No periodic health checks / auto-reconnect |
| **Provider failover** | `llm_providers` | No automatic fallback between providers |
| **Streaming tool calls** | `llm_providers.base` | Tool calls in streaming not fully handled |
| **Rate limit handling** | `llm_providers.base` | Retry logic exists but no circuit breaker per provider |
| **FastMCP HTTP transport** | `fastmcp_server/main.py:360` | Marked "not yet implemented" |
| **Credential store integration** | `api_manager.py:29` | `credential_store` injection not documented/wired |
| **Model capability detection** | `llm_providers` | No automatic vision/tools support detection |

### 🔵 IMPROVE (Refactoring / Performance / Patterns)
| Opportunity | Details |
|-------------|---------|
| **Unify provider interface** | All providers extend `OpenAIProvider` except Anthropic/Gemini — consider adapter pattern |
| **Dynamic model discovery** | All providers have `list_models()` but not auto-called on init |
| **Async client support** | `OpenAIProvider` uses sync `httpx.Client`; add async variant for high concurrency |
| **Error standardization** | All providers have similar `_handle_error()` — extract to base class |
| **FastMCP security** | Remove `execute_code` or add approval gate; add per-session tokens |
| **Configuration validation** | Add Pydantic models for provider configs |
| **Observability** | Add structured logging with request_id correlation |
| **Connection pooling** | `httpx.Client` created per provider; share pool for same base_url |
| **Model registry** | Centralize model metadata (context length, pricing, capabilities) |

---

## 6. Cross-Module Integration (with mcp_server/ context)

### Current Integration Points
```
mcp_server.server.UniversalMCPServer
    → get_permission_manager() (from mcp_server.server)
    → AsyncQgisBridgeClient (from mcp_server.qgis_client)
    → build_registry() (from mcp_server.registry)
    → get_verification_engine() (from mcp_server.verification)
    → get_approval_manager() (from mcp_server.approval)
    → get_rate_limiter() (from security.rate_limiter)

agents.base_agent.BaseAgent
    → create_client(async_mode=True) → AsyncQgisBridgeClient
    → call_tool() → client.dispatch()

integrations.api_providers.APIManager
    → Uses credential_store (should be core.keyring_backend)
    → Stores in api_providers / api_profiles tables

integrations.external_mcp.MCPManager
    → Stores in mcp_servers / mcp_tools tables
    → discover_tools() reads mcp_tools table

integrations.ai_hosts.AIHostManager
    → Stores in ai_hosts table
    → get_default() used for default AI host
```

### Missing Integration
| Service | Should Integrate | Current State |
|---------|-----------------|---------------|
| `EventBus` | Tool execution, approval, host changes | **Not used** |
| `CapabilityRegistry` | Register provider capabilities | **Not used** |
| `JobManager` | Track async API calls | **Not used** |
| `CircuitBreaker` | Per-provider failure isolation | **Not used** (but `qgis_client` has one) |
| `AuditRepository` | Log API key changes, approvals | **Not used** |

---

## 7. Test Coverage

| Test File | Coverage |
|-----------|----------|
| **None** | Zero tests for any integration module |

**Total: 0 tests for 14 modules (0%)**

---

## 8. Recommendations Summary

### Priority 1 (Immediate)
1. **Add all `integrations/**/__pycache__/` to `.gitignore`**
2. **REMOVE `execute_code` tool** from `fastmcp_server/main.py` — arbitrary code execution is critical risk
3. **Wire `credential_store`** in `APIManager` to `core.keyring_backend.get_keyring()`

### Priority 2 (Short-term)
4. **Add unit tests** for all 4 managers + 5 LLM providers
5. **Add integration tests** with mock external services
6. **Implement FastMCP HTTP transport** (currently stubbed)
7. **Add circuit breaker** per LLM provider (reuse `qgis_client.CircuitBreaker`)
8. **Remove hardcoded headers** in OpenRouter; make configurable

### Priority 3 (Medium-term)
9. **Implement provider failover** (try next provider on failure)
10. **Add API key rotation/expiry** tracking
11. **Add MCP server health monitoring** with auto-reconnect
12. **Implement model capability registry** (context length, vision, tools per model)
13. **Add structured logging** with correlation IDs
14. **Create async variants** of LLM providers for high concurrency
15. **Document credential store integration** for `APIManager`

---

## 9. Output for Next Task (skills/)

**Context to pass forward:**
- Integrations provide: AI host management, API provider configs (5 LLM providers), external MCP server management, FastMCP socket server
- Key tables: `ai_hosts`, `api_providers`, `api_profiles`, `mcp_servers`, `mcp_tools`
- Security: OS credential manager for API keys; trust levels for MCP servers
- Skills folder contains: `builtin/` and `custom/` skills, `skill_manager.py`
- `skill_manager.py` likely uses `database.db.Database` for skill persistence
- LLM providers used by: agents (via `BaseAgent.ai_host_id`), potentially skills for AI-powered operations
- Watch for: Circular imports between skills and integrations; skills should not import LLM providers directly

---

*End of integrations/ folder analysis*