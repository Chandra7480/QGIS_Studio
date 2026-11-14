"""Universal AI GIS Studio — Async Database Layer.

Provides async SQLite operations using aiosqlite for non-blocking database
access in async contexts (WorkflowEngine, AgentOrchestrator, JobManager).
"""

import os
import aiosqlite
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple, Union

from core.logging import get_logger
from core.exceptions import DatabaseError

logger = get_logger("database.async")


class AsyncDatabase:
    """Async SQLite database manager using aiosqlite.
    
    Provides async methods for database operations without blocking the event loop.
    Uses WAL mode for concurrent access.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._pool: Optional[aiosqlite.Pool] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the database connection pool."""
        if self._initialized:
            return
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Create pool with WAL mode
        self._pool = await aiosqlite.create_pool(
            self.db_path,
            maxsize=10,
            timeout=30.0,
        )
        
        # Initialize pragmas
        async with self._pool.acquire() as conn:
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA foreign_keys=ON")
            await conn.execute("PRAGMA temp_store=MEMORY")
            await conn.execute("PRAGMA busy_timeout=30000")
        
        self._initialized = True
        logger.info("Async database initialized: %s", self.db_path)
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool."""
        if not self._initialized:
            await self.initialize()
        async with self._pool.acquire() as conn:
            yield conn
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for a transactional block."""
        async with self.acquire() as conn:
            await conn.execute("BEGIN")
            try:
                yield conn
                await conn.execute("COMMIT")
            except Exception:
                try:
                    await conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise
    
    async def execute(self, sql: str, params: Tuple = ()) -> aiosqlite.Cursor:
        """Execute a SQL statement."""
        async with self.acquire() as conn:
            return await conn.execute(sql, params)
    
    async def executemany(self, sql: str, params: List[Tuple]) -> aiosqlite.Cursor:
        """Execute many statements."""
        async with self.acquire() as conn:
            return await conn.executemany(sql, params)
    
    async def execute_script(self, sql: str) -> None:
        """Execute a multi-statement SQL script."""
        async with self.acquire() as conn:
            await conn.executescript(sql)
    
    async def fetchone(self, sql: str, params: Tuple = ()) -> Optional[aiosqlite.Row]:
        """Fetch a single row."""
        async with self.acquire() as conn:
            cur = await conn.execute(sql, params)
            return await cur.fetchone()
    
    async def fetchall(self, sql: str, params: Tuple = ()) -> List[aiosqlite.Row]:
        """Fetch all rows."""
        async with self.acquire() as conn:
            cur = await conn.execute(sql, params)
            return await cur.fetchall()
    
    async def fetchall_as_dict(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows as dictionaries."""
        rows = await self.fetchall(sql, params)
        return [dict(row) for row in rows]
    
    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self._initialized = False
            logger.info("Async database closed")


class AsyncDatabasePool:
    """High-level async database pool with read/write separation.
    
    Uses separate read and write pools for better concurrency.
    """
    
    def __init__(self, db_path: str, read_pool_size: int = 10, write_pool_size: int = 1):
        self.db_path = db_path
        self.read_pool_size = read_pool_size
        self.write_pool_size = write_pool_size
        self._read_pool: Optional[aiosqlite.Pool] = None
        self._write_pool: Optional[aiosqlite.Pool] = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize read and write pools."""
        if self._initialized:
            return
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Create read pool (larger)
        self._read_pool = await aiosqlite.create_pool(
            self.db_path,
            maxsize=10,
            timeout=30.0,
        )
        
        # Create write pool (single writer for SQLite)
        self._write_pool = await aiosqlite.create_pool(
            self.db_path,
            maxsize=1,
            timeout=30.0,
        )
        
        # Initialize pragmas for both pools
        async with self._read_pool.acquire() as conn:
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA foreign_keys=ON")
            await conn.execute("PRAGMA temp_store=MEMORY")
            await conn.execute("PRAGMA busy_timeout=30000")
        
        async with self._write_pool.acquire() as conn:
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")
            await conn.execute("PRAGMA foreign_keys=ON")
            await conn.execute("PRAGMA temp_store=MEMORY")
            await conn.execute("PRAGMA busy_timeout=30000")
        
        self._initialized = True
        logger.info("Async database pool initialized: %s", self.db_path)
    
    @asynccontextmanager
    async def read_connection(self):
        """Get a read connection."""
        if not self._initialized:
            await self.initialize()
        async with self._read_pool.acquire() as conn:
            yield conn
    
    @asynccontextmanager
    async def write_connection(self):
        """Get a write connection."""
        if not self._initialized:
            await self.initialize()
        async with self._write_pool.acquire() as conn:
            yield conn
    
    @asynccontextmanager
    async def transaction(self):
        """Transaction context manager using write pool."""
        async with self.write_connection() as conn:
            await conn.execute("BEGIN")
            try:
                yield conn
                await conn.execute("COMMIT")
            except Exception:
                try:
                    await conn.execute("ROLLBACK")
                except Exception:
                    pass
                raise
    
    # Read operations
    async def fetchone(self, sql: str, params: Tuple = ()) -> Optional[aiosqlite.Row]:
        async with self.read_connection() as conn:
            cur = await conn.execute(sql, params)
            return await cur.fetchone()
    
    async def fetchall(self, sql: str, params: Tuple = ()) -> List[aiosqlite.Row]:
        async with self.read_connection() as conn:
            cur = await conn.execute(sql, params)
            return await cur.fetchall()
    
    async def fetchall_as_dict(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        rows = await self.fetchall(sql, params)
        return [dict(row) for row in rows]
    
    # Write operations
    async def execute(self, sql: str, params: Tuple = ()) -> aiosqlite.Cursor:
        async with self.write_connection() as conn:
            return await conn.execute(sql, params)
    
    async def executemany(self, sql: str, params: List[Tuple]) -> aiosqlite.Cursor:
        async with self.write_connection() as conn:
            return await conn.executemany(sql, params)
    
    async def execute_script(self, sql: str) -> None:
        async with self.write_connection() as conn:
            await conn.executescript(sql)
    
    async def fetchone_write(self, sql: str, params: Tuple = ()) -> Optional[aiosqlite.Row]:
        async with self.write_connection() as conn:
            cur = await conn.execute(sql, params)
            return await cur.fetchone()
    
    async def fetchall_write(self, sql: str, params: Tuple = ()) -> List[aiosqlite.Row]:
        async with self.write_connection() as conn:
            cur = await conn.execute(sql, params)
            return await cur.fetchall()
    
    async def close(self) -> None:
        """Close both pools."""
        if self._read_pool:
            await self._read_pool.close()
        if self._write_pool:
            await self._write_pool.close()
        self._read_pool = None
        self._write_pool = None
        self._initialized = False
        logger.info("Async database pool closed")


# Global instances for convenience
_async_db: Optional[AsyncDatabase] = None
_async_db_pool: Optional[AsyncDatabasePool] = None


async def get_async_db(db_path: str) -> AsyncDatabase:
    """Get or create global async database instance."""
    global _async_db
    if _async_db is None or _async_db.db_path != db_path:
        _async_db = AsyncDatabase(db_path)
        await _async_db.initialize()
    return _async_db


async def get_async_db_pool(db_path: str) -> AsyncDatabasePool:
    """Get or create global async database pool instance."""
    global _async_db_pool
    if _async_db_pool is None or _async_db_pool.db_path != db_path:
        _async_db_pool = AsyncDatabasePool(db_path)
        await _async_db_pool.initialize()
    return _async_db_pool


async def close_async_db() -> None:
    """Close global async database instances."""
    global _async_db, _async_db_pool
    if _async_db:
        await _async_db.close()
        _async_db = None
    if _async_db_pool:
        await _async_db_pool.close()
        _async_db_pool = None