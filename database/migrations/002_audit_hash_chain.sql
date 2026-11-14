-- Migration 002: Add audit hash chain and external anchors
-- Adds audit_hash column to audit_logs and creates audit_anchors table

PRAGMA foreign_keys = ON;

-- Add audit_hash column to existing audit_logs table (if not exists)
-- Use a workaround: try to add column, ignore error if already exists
-- This is handled in Python code, but keep SQL for reference

-- Create audit_anchors table for external anchoring
CREATE TABLE IF NOT EXISTS audit_anchors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_log_id INTEGER NOT NULL,
    anchor_hash TEXT NOT NULL,
    anchor_type TEXT NOT NULL,
    anchor_location TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY(audit_log_id) REFERENCES audit_logs(id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_audit_hash ON audit_logs(audit_hash);
CREATE INDEX IF NOT EXISTS idx_audit_anchors_log ON audit_anchors(audit_log_id);