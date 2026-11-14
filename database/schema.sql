-- Universal AI GIS Studio — SQLite schema
-- All tables use WAL mode, foreign keys, indexes. Managed via migrations.

PRAGMA foreign_keys = ON;

-- Platform settings (typed, key/value)
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- AI host configurations (OpenCode, Codex, other MCP clients)
CREATE TABLE IF NOT EXISTS ai_hosts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    host_type TEXT NOT NULL,            -- 'opencode', 'codex', 'mcp_client', 'custom'
    transport TEXT NOT NULL,            -- 'stdio', 'http', 'websocket'
    endpoint TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    image_capable INTEGER NOT NULL DEFAULT 0,
    configured_at TEXT,
    last_tested TEXT,
    last_status TEXT
);

-- Optional direct API providers
CREATE TABLE IF NOT EXISTS api_providers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,                 -- 'openai', 'gemini', 'anthropic', 'openrouter', 'openai_compatible', 'custom'
    base_url TEXT,
    model_id TEXT,
    enabled INTEGER NOT NULL DEFAULT 0,
    image_capable INTEGER NOT NULL DEFAULT 0,
    timeout_seconds INTEGER DEFAULT 60,
    retry_count INTEGER DEFAULT 3,
    created_at TEXT,
    updated_at TEXT
);

-- API key profiles (credential references, not plaintext keys)
CREATE TABLE IF NOT EXISTS api_profiles (
    id TEXT PRIMARY KEY,
    provider_id TEXT NOT NULL,
    credential_ref TEXT NOT NULL,       -- OS credential manager reference
    is_default INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(provider_id) REFERENCES api_providers(id)
);

-- MCP servers (external + universal)
CREATE TABLE IF NOT EXISTS mcp_servers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    transport TEXT NOT NULL,            -- 'stdio', 'http'
    command TEXT,                       -- for stdio
    args TEXT,                          -- JSON array
    url TEXT,                           -- for http
    enabled INTEGER NOT NULL DEFAULT 1,
    connected INTEGER NOT NULL DEFAULT 0,
    last_connected TEXT,
    trust_level TEXT DEFAULT 'untrusted' -- 'trusted', 'untrusted'
);

-- MCP tools discovered from servers
CREATE TABLE IF NOT EXISTS mcp_tools (
    id TEXT PRIMARY KEY,
    server_id TEXT NOT NULL,
    name TEXT NOT NULL,
    namespace TEXT,
    description TEXT,
    input_schema TEXT,                  -- JSON schema
    output_schema TEXT,                 -- JSON schema
    enabled INTEGER NOT NULL DEFAULT 1,
    permissions TEXT,                   -- JSON array of required permissions
    FOREIGN KEY(server_id) REFERENCES mcp_servers(id)
);

-- Agents
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    agent_type TEXT NOT NULL,           -- 'builtin' or 'custom'
    instructions TEXT,
    ai_host_id TEXT,
    permission_level TEXT DEFAULT 'standard', -- 'read', 'standard', 'elevated'
    max_steps INTEGER DEFAULT 10,
    timeout_seconds INTEGER DEFAULT 300,
    output_format TEXT DEFAULT 'text',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);

-- Agent tool assignments
CREATE TABLE IF NOT EXISTS agent_tools (
    agent_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    PRIMARY KEY (agent_id, tool_id),
    FOREIGN KEY(agent_id) REFERENCES agents(id),
    FOREIGN KEY(tool_id) REFERENCES mcp_tools(id)
);

-- Skills
CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '1.0.0',
    description TEXT,
    manifest TEXT,                      -- JSON manifest
    enabled INTEGER NOT NULL DEFAULT 1,
    trusted INTEGER NOT NULL DEFAULT 0,
    installed_at TEXT,
    updated_at TEXT
);

-- Agent skill assignments
CREATE TABLE IF NOT EXISTS agent_skills (
    agent_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    PRIMARY KEY (agent_id, skill_id),
    FOREIGN KEY(agent_id) REFERENCES agents(id),
    FOREIGN KEY(skill_id) REFERENCES skills(id)
);

-- Workflows
CREATE TABLE IF NOT EXISTS workflows (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    definition TEXT,                    -- JSON workflow definition
    version INTEGER NOT NULL DEFAULT 1,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);

-- Workflow steps
CREATE TABLE IF NOT EXISTS workflow_steps (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    node_type TEXT NOT NULL,            -- 'start','end','gis_tool','agent','mcp_tool','api','condition','loop','input','output','approval','validation','report'
    config TEXT,                        -- JSON node config
    FOREIGN KEY(workflow_id) REFERENCES workflows(id)
);

-- Workflow execution states (for pause/resume/checkpoint)
CREATE TABLE IF NOT EXISTS workflow_states (
    job_id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL,
    step_index INTEGER NOT NULL DEFAULT 0,
    context TEXT,                       -- JSON: full execution context
    completed_steps TEXT,               -- JSON array of completed step IDs
    pending_steps TEXT,                 -- JSON array of pending step IDs
    status TEXT NOT NULL DEFAULT 'running', -- running, paused, completed, failed, cancelled
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(job_id) REFERENCES jobs(id),
    FOREIGN KEY(workflow_id) REFERENCES workflows(id)
);

-- Jobs (long-running task records)
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued', -- queued, running, completed, failed, cancelled
    agent_id TEXT,       -- informational; no FK (builtin agents may not be persisted)
    tool_id TEXT,        -- informational; no FK
    request_id TEXT,
    input_payload TEXT,                 -- JSON
    output_payload TEXT,                -- JSON
    verification_state TEXT,            -- SUCCESS, PARTIAL_SUCCESS, FAILED, NEEDS_REVIEW, CANCELLED
    started_at TEXT,
    completed_at TEXT,
    error_message TEXT
);

-- Job events (audit trail for jobs)
CREATE TABLE IF NOT EXISTS job_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    event_type TEXT NOT NULL,           -- 'created','started','progress','completed','failed','cancelled'
    message TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

-- Tool runs (individual tool execution records)
CREATE TABLE IF NOT EXISTS tool_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    tool_id TEXT NOT NULL,
    input_payload TEXT,
    output_payload TEXT,
    status TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    duration_ms INTEGER,
    error_message TEXT,
    FOREIGN KEY(job_id) REFERENCES jobs(id),
    FOREIGN KEY(tool_id) REFERENCES mcp_tools(id)
);

-- Approvals (user consent for destructive operations)
CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,
    target TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, approved, denied
    requested_at TEXT NOT NULL DEFAULT (datetime('now')),
    decided_at TEXT,
    decided_by TEXT
);

-- Project context (current QGIS project state snapshot)
CREATE TABLE IF NOT EXISTS project_context (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    project_path TEXT,
    project_title TEXT,
    crs TEXT,
    layer_count INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Capability registry (discovered GIS capabilities)
CREATE TABLE IF NOT EXISTS capability_registry (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,             -- 'qgis', 'gdal', 'ogr', 'processing_provider', 'algorithm', 'plugin'
    name TEXT NOT NULL,
    version TEXT,
    available INTEGER NOT NULL DEFAULT 1,
    details TEXT,                       -- JSON
    discovered_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- GCP records (georeferencing ground control points)
CREATE TABLE IF NOT EXISTS gcp_records (
    id TEXT PRIMARY KEY,
    job_id TEXT,
    source_pixel_x REAL NOT NULL,
    source_pixel_y REAL NOT NULL,
    dest_map_x REAL NOT NULL,
    dest_map_y REAL NOT NULL,
    crs TEXT,
    confidence REAL,
    landmark_description TEXT,
    validation_status TEXT DEFAULT 'pending', -- pending, accepted, rejected
    residual_error REAL,
    source_reference TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

-- Datasets (registered data sources)
CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT,
    type TEXT NOT NULL,                 -- 'vector', 'raster', 'database', 'web'
    crs TEXT,
    extent TEXT,                        -- JSON
    feature_count INTEGER,
    registered_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Audit logs (security-relevant events)
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT,
    outcome TEXT NOT NULL,              -- 'success', 'failure', 'denied'
    details TEXT,                       -- JSON
    ip TEXT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    audit_hash TEXT NOT NULL            -- SHA256 hash chain: SHA256(prev_hash || current_data)
);

-- Audit anchors (external tamper-proof anchors)
CREATE TABLE IF NOT EXISTS audit_anchors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_log_id INTEGER NOT NULL,
    anchor_hash TEXT NOT NULL,          -- Hash anchored externally
    anchor_type TEXT NOT NULL,          -- 'file', 'syslog', 'remote'
    anchor_location TEXT NOT NULL,      -- File path, syslog tag, remote URL
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(audit_log_id) REFERENCES audit_logs(id)
);

-- Agent context persistence (state between calls)
CREATE TABLE IF NOT EXISTS agent_contexts (
    agent_id TEXT PRIMARY KEY,
    context_data TEXT NOT NULL,         -- JSON: conversation_history, working_memory, last_tool_results, step_count
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(agent_id) REFERENCES agents(id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_agent ON jobs(agent_id);
CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events(job_id);
CREATE INDEX IF NOT EXISTS idx_tool_runs_job ON tool_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_mcp_tools_server ON mcp_tools(server_id);
CREATE INDEX IF NOT EXISTS idx_agent_tools_agent ON agent_tools(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_skills_agent ON agent_skills(agent_id);
CREATE INDEX IF NOT EXISTS idx_workflow_steps_workflow ON workflow_steps(workflow_id);
CREATE INDEX IF NOT EXISTS idx_gcp_job ON gcp_records(job_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_hash ON audit_logs(audit_hash);
CREATE INDEX IF NOT EXISTS idx_audit_anchors_log ON audit_anchors(audit_log_id);
CREATE INDEX IF NOT EXISTS idx_capability_category ON capability_registry(category);
