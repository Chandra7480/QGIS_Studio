"""Universal AI GIS Studio — Temp File Cleanup and Cache Management.

Automatic cleanup of temp files older than 24h, disk quota enforcement (500MB max),
LRU cache eviction (256MB limit), and low disk alerts.
"""

import logging
import os
import shutil
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("uagis.monitoring.temp_cleanup")


@dataclass
class TempFileEntry:
    """Tracks a temporary file for cleanup."""
    path: Path
    job_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    size_bytes: int = 0
    description: str = ""

    def age_hours(self) -> float:
        return (datetime.utcnow() - self.created_at).total_seconds() / 3600

    def exists(self) -> bool:
        return self.path.exists()

    def get_size(self) -> int:
        if self.exists():
            try:
                self.size_bytes = self.path.stat().st_size
            except Exception:
                pass
        return self.size_bytes


@dataclass
class CacheEntry:
    """LRU cache entry."""
    key: str
    value: any
    size_bytes: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: datetime = field(default_factory=datetime.utcnow)
    access_count: int = 0

    def touch(self):
        self.last_accessed = datetime.utcnow()
        self.access_count += 1


class LRUCache:
    """Thread-safe LRU cache with size limit."""

    def __init__(self, max_size_mb: int = 256):
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._current_size = 0
        self._lock = threading.RLock()

    def get(self, key: str) -> any | None:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            entry.touch()
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return entry.value

    def put(self, key: str, value: any, size_bytes: int | None = None) -> None:
        with self._lock:
            # Remove existing if present
            if key in self._cache:
                old_entry = self._cache[key]
                self._current_size -= old_entry.size_bytes
                del self._cache[key]

            # Estimate size if not provided
            if size_bytes is None:
                size_bytes = self._estimate_size(value)

            # Evict LRU entries if needed
            while self._current_size + size_bytes > self.max_size_bytes and self._cache:
                self._evict_lru()

            entry = CacheEntry(key=key, value=value, size_bytes=size_bytes)
            self._cache[key] = entry
            self._current_size += size_bytes

    def _evict_lru(self) -> bool:
        """Evict least recently used entry. Returns True if evicted."""
        if not self._cache:
            return False
        key, entry = self._cache.popitem(last=False)  # FIFO = LRU
        self._current_size -= entry.size_bytes
        logger.debug("LRU evicted: %s (size=%.1f MB)", key, entry.size_bytes / 1024 / 1024)
        return True

    def _estimate_size(self, value: any) -> int:
        """Rough size estimation for common types."""
        try:
            import sys
            return sys.getsizeof(value)
        except Exception:
            return 1024  # Default 1KB

    def remove(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                entry = self._cache.pop(key)
                self._current_size -= entry.size_bytes
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._current_size = 0

    def stats(self) -> dict:
        with self._lock:
            return {
                "entries": len(self._cache),
                "size_mb": self._current_size / 1024 / 1024,
                "max_size_mb": self.max_size_bytes / 1024 / 1024,
                "utilization": self._current_size / self.max_size_bytes if self.max_size_bytes > 0 else 0,
            }


class TempFileManager:
    """Manages temporary files per job with automatic cleanup."""

    def __init__(
        self,
        temp_dir: str | None = None,
        max_age_hours: float = 24.0,
        max_total_size_mb: int = 500,
        cleanup_interval: float = 3600.0,  # 1 hour
        low_disk_threshold_mb: int = 1024,  # Alert when < 1GB free
    ):
        self.temp_dir = Path(temp_dir) if temp_dir else Path(os.environ.get("TEMP", "/tmp")) / "uagis"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.max_age_hours = max_age_hours
        self.max_total_size_bytes = max_total_size_mb * 1024 * 1024
        self.cleanup_interval = cleanup_interval
        self.low_disk_threshold_bytes = low_disk_threshold_mb * 1024 * 1024

        self._files: dict[str, list[TempFileEntry]] = {}  # job_id -> list of files
        self._lock = threading.RLock()
        self._cleanup_thread: threading.Thread | None = None
        self._stop_cleanup = threading.Event()
        self._alert_callback: Optional[callable] = None

    def set_alert_callback(self, callback: callable) -> None:
        """Set callback for low disk alerts."""
        self._alert_callback = callback

    def register_temp_file(
        self,
        job_id: str,
        file_path: str | Path,
        description: str = "",
    ) -> Path:
        """Register a temp file for tracking and cleanup."""
        path = Path(file_path)
        if not path.is_absolute():
            path = self.temp_dir / path

        entry = TempFileEntry(
            path=path,
            job_id=job_id,
            description=description,
        )

        with self._lock:
            if job_id not in self._files:
                self._files[job_id] = []
            self._files[job_id].append(entry)

        logger.debug("Registered temp file for job %s: %s", job_id, path)
        return path

    def create_temp_file(
        self,
        job_id: str,
        prefix: str = "uagis_",
        suffix: str = ".tmp",
        description: str = "",
    ) -> Path:
        """Create a new tracked temp file."""
        import tempfile
        fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=self.temp_dir)
        os.close(fd)
        return self.register_temp_file(job_id, path, description)

    def get_job_files(self, job_id: str) -> list[TempFileEntry]:
        """Get all temp files for a job."""
        with self._lock:
            return list(self._files.get(job_id, []))

    def cleanup_job(self, job_id: str) -> dict:
        """Clean up all temp files for a specific job."""
        with self._lock:
            files = self._files.pop(job_id, [])

        cleaned = 0
        failed = 0
        freed_bytes = 0

        for entry in files:
            try:
                if entry.exists():
                    freed_bytes += entry.get_size()
                    entry.path.unlink()
                    cleaned += 1
            except Exception as exc:
                logger.warning("Failed to delete temp file %s: %s", entry.path, exc)
                failed += 1

        logger.info("Cleaned up job %s: %d files, %.1f MB freed, %d failed",
                    job_id, cleaned, freed_bytes / 1024 / 1024, failed)
        return {"cleaned": cleaned, "failed": failed, "freed_mb": freed_bytes / 1024 / 1024}

    def cleanup_all(self, older_than_hours: float | None = None) -> dict:
        """Clean up all temp files older than threshold."""
        max_age = older_than_hours or self.max_age_hours
        now = datetime.utcnow()
        total_cleaned = 0
        total_failed = 0
        total_freed = 0

        with self._lock:
            all_entries = []
            for job_files in self._files.values():
                all_entries.extend(job_files)

        for entry in all_entries:
            age_hours = (now - entry.created_at).total_seconds() / 3600
            if age_hours >= max_age:
                try:
                    if entry.exists():
                        total_freed += entry.get_size()
                        entry.path.unlink()
                        total_cleaned += 1
                except Exception as exc:
                    logger.warning("Failed to delete temp file %s: %s", entry.path, exc)
                    total_failed += 1

        # Remove cleaned entries from tracking
        with self._lock:
            for job_id in list(self._files.keys()):
                self._files[job_id] = [
                    e for e in self._files[job_id]
                    if e.exists() and (now - e.created_at).total_seconds() / 3600 < max_age
                ]
                if not self._files[job_id]:
                    del self._files[job_id]

        logger.info("Global cleanup: %d files, %.1f MB freed, %d failed (age >= %.1fh)",
                    total_cleaned, total_freed / 1024 / 1024, total_failed, max_age)
        return {"cleaned": total_cleaned, "failed": total_failed, "freed_mb": total_freed / 1024 / 1024}

    def enforce_disk_quota(self) -> dict:
        """Enforce total disk quota by removing oldest files."""
        total_size = 0
        all_entries = []

        with self._lock:
            for job_files in self._files.values():
                for entry in job_files:
                    if entry.exists():
                        size = entry.get_size()
                        total_size += size
                        all_entries.append((entry, size))

        if total_size <= self.max_total_size_bytes:
            return {"enforced": False, "total_mb": total_size / 1024 / 1024}

        # Sort by age (oldest first)
        all_entries.sort(key=lambda x: x[0].created_at)

        freed = 0
        removed = 0
        for entry, size in all_entries:
            if total_size - freed <= self.max_total_size_bytes:
                break
            try:
                if entry.exists():
                    entry.path.unlink()
                    freed += size
                    removed += 1
                    logger.warning("Quota enforcement: deleted %s (%.1f MB)", entry.path, size / 1024 / 1024)
            except Exception as exc:
                logger.error("Failed to delete during quota enforcement: %s", exc)

        # Update tracking
        with self._lock:
            for job_id in list(self._files.keys()):
                self._files[job_id] = [e for e in self._files[job_id] if e.exists()]
                if not self._files[job_id]:
                    del self._files[job_id]

        return {
            "enforced": True,
            "removed": removed,
            "freed_mb": freed / 1024 / 1024,
            "remaining_mb": (total_size - freed) / 1024 / 1024,
        }

    def check_disk_space(self) -> dict:
        """Check available disk space and alert if low."""
        try:
            total, used, free = shutil.disk_usage(self.temp_dir)
            free_mb = free / 1024 / 1024
            total_mb = total / 1024 / 1024
            used_percent = (used / total) * 100

            is_low = free < self.low_disk_threshold_bytes

            result = {
                "total_mb": total_mb,
                "free_mb": free_mb,
                "used_percent": used_percent,
                "low_disk": is_low,
                "threshold_mb": self.low_disk_threshold_bytes / 1024 / 1024,
            }

            if is_low and self._alert_callback:
                try:
                    self._alert_callback(f"Low disk space: {free_mb:.0f} MB free on {self.temp_dir}")
                except Exception:
                    pass

            return result
        except Exception as exc:
            logger.error("Failed to check disk space: %s", exc)
            return {"error": str(exc)}

    def get_stats(self) -> dict:
        """Get temp file statistics."""
        with self._lock:
            total_files = sum(len(files) for files in self._files.values())
            total_size = 0
            jobs_with_files = len(self._files)

            for job_files in self._files.values():
                for entry in job_files:
                    if entry.exists():
                        total_size += entry.get_size()

        disk = self.check_disk_space()

        return {
            "tracked_files": total_files,
            "tracked_size_mb": total_size / 1024 / 1024,
            "jobs_with_files": jobs_with_files,
            "temp_dir": str(self.temp_dir),
            "max_age_hours": self.max_age_hours,
            "max_total_size_mb": self.max_total_size_bytes / 1024 / 1024,
            "disk": disk,
        }

    def start_cleanup(self) -> None:
        """Start background cleanup thread."""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        self._stop_cleanup.clear()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop, daemon=True, name="uagis-temp-cleanup"
        )
        self._cleanup_thread.start()
        logger.info("Temp file cleanup started (interval=%.0fs)", self.cleanup_interval)

    def stop_cleanup(self) -> None:
        """Stop background cleanup thread."""
        self._stop_cleanup.set()
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=10)
        logger.info("Temp file cleanup stopped")

    def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while not self._stop_cleanup.is_set():
            try:
                # Clean old files
                self.cleanup_all()
                # Enforce quota
                self.enforce_disk_quota()
                # Check disk space
                self.check_disk_space()
            except Exception as exc:
                logger.exception("Error in temp cleanup loop")
            self._stop_cleanup.wait(self.cleanup_interval)


# Global instances
_temp_file_manager: TempFileManager | None = None
_lru_cache: LRUCache | None = None


def get_temp_file_manager() -> TempFileManager:
    """Get global temp file manager."""
    global _temp_file_manager
    if _temp_file_manager is None:
        _temp_file_manager = TempFileManager()
    return _temp_file_manager


def get_lru_cache() -> LRUCache:
    """Get global LRU cache."""
    global _lru_cache
    if _lru_cache is None:
        _lru_cache = LRUCache()
    return _lru_cache


def init_temp_cleanup(
    temp_dir: str | None = None,
    max_age_hours: float = 24.0,
    max_total_size_mb: int = 500,
    cleanup_interval: float = 3600.0,
    cache_size_mb: int = 256,
    low_disk_threshold_mb: int = 1024,
) -> tuple[TempFileManager, LRUCache]:
    """Initialize global temp cleanup and cache."""
    global _temp_file_manager, _lru_cache
    _temp_file_manager = TempFileManager(
        temp_dir=temp_dir,
        max_age_hours=max_age_hours,
        max_total_size_mb=max_total_size_mb,
        cleanup_interval=cleanup_interval,
        low_disk_threshold_mb=low_disk_threshold_mb,
    )
    _lru_cache = LRUCache(max_size_mb=cache_size_mb)
    return _temp_file_manager, _lru_cache