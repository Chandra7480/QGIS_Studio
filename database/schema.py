"""Universal AI GIS Studio — Schema loader and migration runner.

Loads schema.sql and applies versioned migrations from database/migrations/.
Tracks applied migrations in a `schema_migrations` table.
"""

import os
from typing import List

from .db import Database
from core.logging import get_logger
from core.exceptions import DatabaseError

logger = get_logger("database.schema")

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


def _read_schema() -> str:
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        return f.read()


def _ensure_migrations_table(db: Database) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def _applied_versions(db: Database) -> List[int]:
    rows = db.fetchall("SELECT version FROM schema_migrations ORDER BY version")
    return [row["version"] for row in rows]


def _migration_files() -> List[int]:
    versions = []
    if not os.path.isdir(MIGRATIONS_DIR):
        return versions
    for fname in os.listdir(MIGRATIONS_DIR):
        if fname.endswith(".sql"):
            try:
                versions.append(int(fname.split("_")[0]))
            except ValueError:
                continue
    return sorted(versions)


def _apply_migration(db: Database, version: int) -> None:
    path = os.path.join(MIGRATIONS_DIR, f"{version}_*.sql")
    matches = [f for f in os.listdir(MIGRATIONS_DIR) if f.startswith(f"{version}_") and f.endswith(".sql")]
    if not matches:
        return
    with open(os.path.join(MIGRATIONS_DIR, matches[0]), "r", encoding="utf-8") as f:
        sql = f.read()
    db.execute_script(sql)
    with db.transaction() as conn:
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES(?, datetime('now'))",
            (version,),
        )
    logger.info("Applied migration %d", version)


def initialize(db: Database) -> None:
    """Create schema (if not exists) and apply pending migrations."""
    db.connect()
    # Base schema
    try:
        db.execute_script(_read_schema())
        logger.info("Base schema created/verified")
    except Exception as exc:
        raise DatabaseError(f"Failed to apply base schema: {exc}") from exc

    # Migration 002: Ensure audit_hash column exists in audit_logs
    _ensure_audit_hash_column(db)

    # Migrations
    _ensure_migrations_table(db)
    applied = set(_applied_versions(db))
    pending = [v for v in _migration_files() if v not in applied]
    for version in pending:
        _apply_migration(db, version)

    db.mark_initialized()
    logger.info("Database initialized (migrations pending: %d)", len(pending))


def _ensure_audit_hash_column(db: Database) -> None:
    """Ensure audit_hash column exists in audit_logs table."""
    try:
        # Check if column exists
        columns = db.fetchall("PRAGMA table_info(audit_logs)")
        column_names = [row["name"] for row in columns] if columns else []
        
        if "audit_hash" not in column_names:
            logger.info("Adding audit_hash column to audit_logs table")
            db.execute("ALTER TABLE audit_logs ADD COLUMN audit_hash TEXT NOT NULL DEFAULT ''")
            logger.info("Added audit_hash column to audit_logs")
        else:
            logger.debug("audit_hash column already exists in audit_logs")
    except Exception as exc:
        logger.warning("Could not verify/add audit_hash column: %s", exc)
