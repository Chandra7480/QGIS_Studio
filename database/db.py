"""Universal AI GIS Studio — SQLite database connection manager.

Provides a thread-safe SQLite connection with WAL mode, foreign keys,
migrations, and transaction support. All access goes through this
manager or repository classes — never direct SQL in UI components.

Also provides a connection pool for read scaling (multi-reader, single-writer).
"""

import os
import sqlite3
import threading
import queue
import logging
from contextlib import contextmanager
from typing import Any, Dict, Optional, List
from dataclasses import dataclass

from core.logging import get_logger
from core.exceptions import DatabaseError

logger = get_logger("database")


@dataclass
class PoolConfig:
    """Configuration for database connection pool."""
    max_read_connections: int = 10
    write_queue_maxsize: int = 1000
    connection_timeout: float = 30.0
    check_same_thread: bool = False


class DatabasePool:
    """SQLite connection pool with multi-reader, single-writer architecture.
    
    Uses WAL mode for concurrent reads. All writes go through a single
    writer connection with a queue. Read connections are pooled.
    """
    
    def __init__(self, db_path: str, config: Optional[PoolConfig] = None):
        self.db_path = db_path
        self.config = config or PoolConfig()
        self._write_lock = threading.Lock()
        self._read_connections: List[sqlite3.Connection] = []
        self._read_lock = threading.Lock()
        self._write_queue: queue.Queue = queue.Queue(maxsize=self.config.write_queue_maxsize)
        self._writer_thread: Optional[threading.Thread] = None
        self._writer_running = False
        self._writer_conn: Optional[sqlite3.Connection] = None
        self._closed = False
        self._init_db()
        self._start_writer()
    
    def _init_db(self):
        """Initialize the database with WAL mode and required pragmas."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # Initialize with a temporary connection to set up WAL mode
        init_conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30,
            isolation_level=None,
        )
        init_conn.execute("PRAGMA journal_mode=WAL")
        init_conn.execute("PRAGMA synchronous=NORMAL")
        init_conn.execute("PRAGMA foreign_keys=ON")
        init_conn.execute("PRAGMA temp_store=MEMORY")
        init_conn.execute("PRAGMA busy_timeout=30000")
        init_conn.close()
        logger.info("Database pool initialized: %s", self.db_path)
    
    def _start_writer(self):
        """Start the dedicated writer thread."""
        self._writer_running = True
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True, name="db-writer")
        self._writer_thread.start()
        
        # Initialize writer connection
        self._writer_conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30,
            isolation_level=None,
        )
        self._writer_conn.row_factory = sqlite3.Row
        self._writer_conn.execute("PRAGMA journal_mode=WAL")
        self._writer_conn.execute("PRAGMA synchronous=NORMAL")
        self._writer_conn.execute("PRAGMA foreign_keys=ON")
        self._writer_conn.execute("PRAGMA temp_store=MEMORY")
        self._writer_conn.execute("PRAGMA busy_timeout=30000")
        logger.info("Database writer thread started")
    
    def _writer_loop(self):
        """Writer thread loop - processes write operations from queue."""
        while self._writer_running:
            try:
                # Get next write operation with timeout
                try:
                    operation = self._write_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                if operation is None:  # Shutdown signal
                    break
                
                op_type, sql, params, result_future = operation
                try:
                    if op_type == "execute":
                        cursor = self._writer_conn.execute(sql, params)
                        result_future.set_result(cursor)
                    elif op_type == "executemany":
                        cursor = self._writer_conn.executemany(sql, params)
                        result_future.set_result(cursor)
                    elif op_type == "executescript":
                        self._writer_conn.executescript(sql)
                        result_future.set_result(None)
                    elif op_type == "execute_with_result":
                        # For operations that need to return results (fetchone, fetchall)
                        cursor = self._writer_conn.execute(sql, params)
                        result_future.set_result(cursor)
                    else:
                        result_future.set_exception(ValueError(f"Unknown operation: {op_type}"))
                except Exception as e:
                    result_future.set_exception(e)
                finally:
                    self._write_queue.task_done()
                    
            except Exception as e:
                logger.error("Writer loop error: %s", e)
    
    def _get_read_connection(self) -> sqlite3.Connection:
        """Get a read connection from pool or create new one."""
        with self._read_lock:
            if self._read_connections:
                return self._read_connections.pop()
        
        # Create new read connection
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30,
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn
    
    def _return_read_connection(self, conn: sqlite3.Connection):
        """Return a read connection to pool."""
        with self._read_lock:
            if len(self._read_connections) < self.config.max_read_connections:
                self._read_connections.append(conn)
            else:
                conn.close()
    
    @contextmanager
    def read_connection(self):
        """Context manager for read operations."""
        conn = self._get_read_connection()
        try:
            yield conn
        finally:
            self._return_read_connection(conn)
    
    def execute_read(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a read query."""
        with self.read_connection() as conn:
            return conn.execute(sql, params)
    
    def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        with self.read_connection() as conn:
            cur = conn.execute(sql, params)
            return cur.fetchone()
    
    def fetchall(self, sql: str, params: tuple = ()) -> list:
        with self.read_connection() as conn:
            cur = conn.execute(sql, params)
            return cur.fetchall()
    
    def execute_write(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a write operation (queued to writer thread)."""
        if self._closed:
            raise DatabaseError("Database pool is closed")
        
        future = queue.Queue(maxsize=1)
        self._write_queue.put(("execute", sql, params, future))
        return future.get()
    
    def fetchone_write(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Execute a write query that returns a single row (e.g., RETURNING clause)."""
        if self._closed:
            raise DatabaseError("Database pool is closed")
        
        future = queue.Queue(maxsize=1)
        self._write_queue.put(("execute_with_result", sql, params, future))
        cursor = future.get()
        return cursor.fetchone()
    
    def fetchall_write(self, sql: str, params: tuple = ()) -> list:
        """Execute a write query that returns all rows."""
        if self._closed:
            raise DatabaseError("Database pool is closed")
        
        future = queue.Queue(maxsize=1)
        self._write_queue.put(("execute_with_result", sql, params, future))
        cursor = future.get()
        return cursor.fetchall()
    
    def executemany_write(self, sql: str, params: list) -> sqlite3.Cursor:
        """Execute many write operations."""
        if self._closed:
            raise DatabaseError("Database pool is closed")
        
        future = queue.Queue(maxsize=1)
        self._write_queue.put(("executemany", sql, params, future))
        return future.get()
    
    def execute_script(self, sql: str) -> None:
        """Execute a multi-statement SQL script."""
        if self._closed:
            raise DatabaseError("Database pool is closed")
        
        future = queue.Queue(maxsize=1)
        self._write_queue.put(("executescript", sql, (), future))
        future.get()
    
    @contextmanager
    def transaction(self):
        """Context manager for a transactional write block."""
        if self._closed:
            raise DatabaseError("Database pool is closed")
        
        # Execute transaction in writer thread
        result_future = queue.Queue(maxsize=1)
        
        def run_transaction():
            conn = self._writer_conn
            try:
                conn.execute("BEGIN")
                # Create a generator that yields the connection
                def txn_gen():
                    try:
                        yield conn
                        conn.execute("COMMIT")
                        result_future.set_result(True)
                    except Exception as e:
                        try:
                            conn.execute("ROLLBACK")
                        except sqlite3.Error:
                            pass
                        result_future.set_exception(e)
                
                gen = txn_gen()
                next(gen)  # Start generator - executes BEGIN
                result_future.set_result(gen)  # Return generator
            except Exception as e:
                result_future.set_exception(e)
        
        future = queue.Queue(maxsize=1)
        self._write_queue.put(("transaction", "", (run_transaction,), future))
        gen = future.get()
        try:
            yield gen
        except Exception:
            # If exception during yield, generator will handle rollback
            raise
    
    def close(self):
        """Close the pool and all connections."""
        if self._closed:
            return
        
        self._closed = True
        self._writer_running = False
        
        # Signal writer to stop
        self._write_queue.put(None)
        if self._writer_thread and self._writer_thread.is_alive():
            self._writer_thread.join(timeout=5)
        
        # Close writer connection
        if self._writer_conn:
            try:
                self._writer_conn.close()
            except sqlite3.Error:
                pass
            self._writer_conn = None
        
        # Close read connections
        with self._read_lock:
            for conn in self._read_connections:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
            self._read_connections.clear()
        
        logger.info("Database pool closed")


class Database:
    """SQLite database manager.

    Uses check_same_thread=False with a lock to allow use across
    worker threads while serializing writes via the connection lock.
    Supports optional connection pool for high-concurrency scenarios.
    """

    def __init__(self, db_path: str, use_pool: bool = False, pool_config: Optional[PoolConfig] = None):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._initialized = False
        # Optional pool for high-concurrency scenarios
        self._pool: Optional[DatabasePool] = None
        self._use_pool = use_pool
        self._pool_config = pool_config or PoolConfig()

    def connect(self) -> sqlite3.Connection:
        """Open (or reuse) the database connection."""
        if self._use_pool and self._pool is not None:
            # Pool connections are managed internally
            pass
        if self._conn is not None:
            return self._conn
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        try:
            self._conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30,
                isolation_level=None,  # autocommit; we manage transactions explicitly
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.execute("PRAGMA temp_store=MEMORY")
            logger.info("Database connected: %s", self.db_path)
        except sqlite3.Error as exc:
            raise DatabaseError(f"Failed to open database {self.db_path}: {exc}") from exc
        return self._conn

    @contextmanager
    def transaction(self):
        """Context manager for a transactional block.

        Uses explicit BEGIN/COMMIT in autocommit mode (isolation_level=None)
        so callers can group multiple statements into one atomic unit.
        """
        conn = self.connect()
        with self._lock:
            conn.execute("BEGIN")
            try:
                yield conn
                conn.execute("COMMIT")
            except Exception:
                try:
                    conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise

    def execute_script(self, sql: str) -> None:
        """Execute a multi-statement SQL script (DDL) outside a transaction.

        Safe to call in autocommit mode; each statement commits independently.
        """
        conn = self.connect()
        with self._lock:
            try:
                conn.executescript(sql)
            except sqlite3.Error as exc:
                raise DatabaseError(f"SQL script execution failed: {exc}") from exc

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        conn = self.connect()
        with self._lock:
            try:
                return conn.execute(sql, params)
            except sqlite3.Error as exc:
                raise DatabaseError(f"SQL execution failed: {exc}\nSQL: {sql}") from exc

    def executemany(self, sql: str, params: list) -> sqlite3.Cursor:
        conn = self.connect()
        with self._lock:
            try:
                return conn.executemany(sql, params)
            except sqlite3.Error as exc:
                raise DatabaseError(f"SQL executemany failed: {exc}\nSQL: {sql}") from exc

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except sqlite3.Error:
                    pass
                self._conn = None
                logger.info("Database closed: %s", self.db_path)

    def get_all_settings(self) -> Dict[str, str]:
        """Return all app_settings as a dict (used by Config loader)."""
        rows = self.fetchall("SELECT key, value FROM app_settings")
        return {row["key"]: row["value"] for row in rows}

    def set_setting(self, key: str, value: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO app_settings(key, value, updated_at) VALUES(?, ?, datetime('now')) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
                (key, value),
            )

    def is_initialized(self) -> bool:
        return self._initialized

    def mark_initialized(self) -> None:
        self._initialized = True

    def enable_pool(self, config: Optional[PoolConfig] = None) -> None:
        """Enable connection pool for high-concurrency scenarios."""
        if self._pool is not None:
            return
        self._pool = DatabasePool(self.db_path, config or PoolConfig())
        self._use_pool = True
        logger.info("Database connection pool enabled")

    def disable_pool(self) -> None:
        """Disable connection pool and fall back to single connection."""
        if self._pool is not None:
            self._pool.close()
            self._pool = None
            self._use_pool = False
            logger.info("Database connection pool disabled")

    # Pool-aware methods
    def _get_pool(self) -> DatabasePool:
        if not self._use_pool or self._pool is None:
            raise DatabaseError("Connection pool not enabled. Call enable_pool() first.")
        return self._pool
    
    def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        if self._use_pool and self._pool:
            return self._pool.fetchone(sql, params)
        cur = self.execute(sql, params)
        return cur.fetchone()
    
    def fetchall(self, sql: str, params: tuple = ()) -> list:
        if self._use_pool and self._pool:
            return self._pool.fetchall(sql, params)
        cur = self.execute(sql, params)
        return cur.fetchall()
    
    def execute_write(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        if self._use_pool and self._pool:
            return self._pool.execute_write(sql, params)
        return self.execute(sql, params)
    
    def executemany_write(self, sql: str, params: list) -> sqlite3.Cursor:
        if self._use_pool and self._pool:
            return self._pool.executemany_write(sql, params)
        return self.executemany(sql, params)
    
    def execute_write_with_result(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        if self._use_pool and self._pool:
            return self._pool.execute_write(sql, params)
        return self.execute(sql, params)
    
    def fetchone_write(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        if self._use_pool and self._pool:
            return self._pool.fetchone_write(sql, params)
        cur = self.execute(sql, params)
        return cur.fetchone()
    
    def fetchall_write(self, sql: str, params: tuple = ()) -> list:
        if self._use_pool and self._pool:
            return self._pool.fetchall_write(sql, params)
        cur = self.execute(sql, params)
        return cur.fetchall()

    @property
    def pool(self) -> Optional[DatabasePool]:
        return self._pool
