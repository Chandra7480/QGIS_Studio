"""Universal AI GIS Studio — Resource Quota Management.

Per-job resource limits: memory, CPU time, disk usage, and execution duration.
Background monitor enforces quotas and kills exceeding jobs.
"""

import logging
import threading
import time
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable
from collections import defaultdict

from core.event_bus import EventBus

logger = logging.getLogger("uagis.core.resource_quota")


class QuotaExceededAction(Enum):
    """Action to take when quota is exceeded."""
    KILL = "kill"              # Terminate the job immediately
    THROTTLE = "throttle"      # Reduce priority/pause
    WARN = "warn"              # Log warning only


@dataclass
class ResourceQuota:
    """Resource limits for a job."""
    max_memory_mb: int = 1024          # Max memory in MB
    max_cpu_seconds: int = 3600        # Max CPU time in seconds
    max_disk_mb: int = 512             # Max disk usage in MB
    max_duration_seconds: int = 3600   # Max wall-clock duration
    action: QuotaExceededAction = QuotaExceededAction.KILL


@dataclass
class JobResourceUsage:
    """Current resource usage for a job."""
    job_id: str
    memory_mb: float = 0.0
    cpu_seconds: float = 0.0
    disk_mb: float = 0.0
    duration_seconds: float = 0.0
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    peak_memory_mb: float = 0.0
    peak_cpu_seconds: float = 0.0


@dataclass
class QuotaViolation:
    """Record of a quota violation."""
    job_id: str
    quota_type: str          # 'memory', 'cpu', 'disk', 'duration'
    limit: float
    current: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    action_taken: str = ""


class ResourceQuotaManager:
    """Manages per-job resource quotas and enforcement."""

    def __init__(
        self,
        default_quota: ResourceQuota | None = None,
        check_interval: float = 5.0,
        system_memory_threshold: float = 0.9,  # 90%
    ):
        self.default_quota = default_quota or ResourceQuota()
        self.check_interval = check_interval
        self.system_memory_threshold = system_memory_threshold
        self._job_quotas: dict[str, ResourceQuota] = {}
        self._job_usage: dict[str, JobResourceUsage] = {}
        self._violations: list[QuotaViolation] = []
        self._lock = threading.RLock()
        self._monitor_thread: threading.Thread | None = None
        self._stop_monitor = threading.Event()
        self._kill_callback: Callable[[str], None] | None = None
        self._event_bus = EventBus()
        self._system_paused = False

    def set_kill_callback(self, callback: Callable[[str], None]) -> None:
        """Set callback to kill a job (e.g., job_manager.cancel_job)."""
        self._kill_callback = callback

    def set_quota(self, job_id: str, quota: ResourceQuota) -> None:
        """Set custom quota for a job."""
        with self._lock:
            self._job_quotas[job_id] = quota

    def get_quota(self, job_id: str) -> ResourceQuota:
        """Get quota for a job (default if not set)."""
        with self._lock:
            return self._job_quotas.get(job_id, self.default_quota)

    def start_tracking(self, job_id: str, quota: ResourceQuota | None = None) -> None:
        """Start tracking resources for a job."""
        with self._lock:
            if quota:
                self._job_quotas[job_id] = quota
            self._job_usage[job_id] = JobResourceUsage(job_id=job_id)
            logger.info("Started resource tracking for job %s", job_id)

    def stop_tracking(self, job_id: str) -> JobResourceUsage | None:
        """Stop tracking and return final usage."""
        with self._lock:
            usage = self._job_usage.pop(job_id, None)
            self._job_quotas.pop(job_id, None)
            if usage:
                logger.info("Stopped resource tracking for job %s: %s", job_id, usage)
            return usage

    def update_usage(
        self,
        job_id: str,
        memory_mb: float | None = None,
        cpu_seconds: float | None = None,
        disk_mb: float | None = None,
    ) -> None:
        """Update resource usage for a job."""
        with self._lock:
            usage = self._job_usage.get(job_id)
            if not usage:
                return

            now = datetime.utcnow()
            if memory_mb is not None:
                usage.memory_mb = memory_mb
                usage.peak_memory_mb = max(usage.peak_memory_mb, memory_mb)
            if cpu_seconds is not None:
                usage.cpu_seconds = cpu_seconds
                usage.peak_cpu_seconds = max(usage.peak_cpu_seconds, cpu_seconds)
            if disk_mb is not None:
                usage.disk_mb = disk_mb
            usage.duration_seconds = (now - usage.started_at).total_seconds()
            usage.last_updated = now

    def check_quotas(self, job_id: str) -> list[QuotaViolation]:
        """Check if job exceeds any quotas. Returns list of violations."""
        with self._lock:
            usage = self._job_usage.get(job_id)
            quota = self._job_quotas.get(job_id, self.default_quota)
            if not usage:
                return []

            violations = []

            # Check memory
            if usage.memory_mb > quota.max_memory_mb:
                violations.append(QuotaViolation(
                    job_id=job_id,
                    quota_type="memory",
                    limit=quota.max_memory_mb,
                    current=usage.memory_mb,
                    action_taken=quota.action.value,
                ))

            # Check CPU
            if usage.cpu_seconds > quota.max_cpu_seconds:
                violations.append(QuotaViolation(
                    job_id=job_id,
                    quota_type="cpu",
                    limit=quota.max_cpu_seconds,
                    current=usage.cpu_seconds,
                    action_taken=quota.action.value,
                ))

            # Check disk
            if usage.disk_mb > quota.max_disk_mb:
                violations.append(QuotaViolation(
                    job_id=job_id,
                    quota_type="disk",
                    limit=quota.max_disk_mb,
                    current=usage.disk_mb,
                    action_taken=quota.action.value,
                ))

            # Check duration
            if usage.duration_seconds > quota.max_duration_seconds:
                violations.append(QuotaViolation(
                    job_id=job_id,
                    quota_type="duration",
                    limit=quota.max_duration_seconds,
                    current=usage.duration_seconds,
                    action_taken=quota.action.value,
                ))

            return violations

    def enforce_quotas(self, job_id: str) -> list[QuotaViolation]:
        """Check and enforce quotas for a job. Returns violations."""
        violations = self.check_quotas(job_id)
        if not violations:
            return []

        with self._lock:
            for violation in violations:
                self._violations.append(violation)
                logger.warning(
                    "Quota exceeded for job %s: %s (limit=%.1f, current=%.1f)",
                    job_id, violation.quota_type, violation.limit, violation.current
                )

                # Publish EventBus event for quota exceeded
                self._event_bus.publish("quota.exceeded", {
                    "job_id": job_id,
                    "quota_type": violation.quota_type,
                    "limit": violation.limit,
                    "current": violation.current,
                    "action": violation.action_taken,
                })

                # Take action
                quota = self.get_quota(job_id)
                if quota.action == QuotaExceededAction.KILL and self._kill_callback:
                    try:
                        self._kill_callback(job_id)
                        violation.action_taken = "killed"
                        logger.error("Killed job %s due to %s quota exceeded",
                                     job_id, violation.quota_type)
                    except Exception as exc:
                        logger.error("Failed to kill job %s: %s", job_id, exc)
                        violation.action_taken = "kill_failed"

                # Also publish quota warning if approaching limit (80%)
                elif violation.current >= quota.max_memory_mb * 0.8:
                    self._event_bus.publish("quota.warning", {
                        "job_id": job_id,
                        "quota_type": violation.quota_type,
                        "limit": violation.limit,
                        "current": violation.current,
                        "percentage": (violation.current / violation.limit) * 100,
                    })

        return violations

    def get_usage(self, job_id: str) -> JobResourceUsage | None:
        """Get current usage for a job."""
        with self._lock:
            return self._job_usage.get(job_id)

    def get_all_usage(self) -> dict[str, JobResourceUsage]:
        """Get usage for all tracked jobs."""
        with self._lock:
            return dict(self._job_usage)

    def get_violations(self, job_id: str | None = None, since: datetime | None = None) -> list[QuotaViolation]:
        """Get quota violations."""
        with self._lock:
            result = self._violations
            if job_id:
                result = [v for v in result if v.job_id == job_id]
            if since:
                result = [v for v in result if v.timestamp >= since]
            return result

    def start_monitor(self) -> None:
        """Start background quota monitor."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._stop_monitor.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True, name="uagis-quota-monitor")
        self._monitor_thread.start()
        logger.info("Resource quota monitor started")

    def stop_monitor(self) -> None:
        """Stop background quota monitor."""
        self._stop_monitor.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=10)
        logger.info("Resource quota monitor stopped")

    def _monitor_loop(self) -> None:
        """Background loop to check all job quotas."""
        while not self._stop_monitor.is_set():
            try:
                self._check_all_jobs()
                self._check_system_memory()
            except Exception as exc:
                logger.exception("Error in quota monitor loop")
            self._stop_monitor.wait(self.check_interval)

    def _check_all_jobs(self) -> None:
        """Check quotas for all tracked jobs."""
        with self._lock:
            job_ids = list(self._job_usage.keys())

        for job_id in job_ids:
            try:
                self.enforce_quotas(job_id)
            except Exception as exc:
                logger.error("Error enforcing quotas for job %s: %s", job_id, exc)

    def _check_system_memory(self) -> None:
        """Check system memory and pause if over threshold."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            if mem.percent / 100.0 >= self.system_memory_threshold:
                if not self._system_paused:
                    self._system_paused = True
                    logger.critical("System memory at %.1f%% (threshold %.1f%%) - pausing new jobs",
                                    mem.percent, self.system_memory_threshold * 100)
            else:
                if self._system_paused:
                    self._system_paused = False
                    logger.info("System memory recovered: %.1f%%", mem.percent)
        except ImportError:
            pass  # psutil not available
        except Exception as exc:
            logger.error("Error checking system memory: %s", exc)

    def is_system_paused(self) -> bool:
        """Check if system is paused due to high memory."""
        return self._system_paused

    def get_system_stats(self) -> dict:
        """Get current system resource stats."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            cpu = psutil.cpu_percent(interval=0.1)
            return {
                "memory": {
                    "total_mb": mem.total / 1024 / 1024,
                    "available_mb": mem.available / 1024 / 1024,
                    "used_percent": mem.percent,
                },
                "disk": {
                    "total_mb": disk.total / 1024 / 1024,
                    "free_mb": disk.free / 1024 / 1024,
                    "used_percent": (disk.used / disk.total) * 100,
                },
                "cpu_percent": cpu,
                "paused": self._system_paused,
            }
        except ImportError:
            return {"error": "psutil not available"}
        except Exception as exc:
            return {"error": str(exc)}


# Global instance
_resource_quota_manager: ResourceQuotaManager | None = None


def get_resource_quota_manager() -> ResourceQuotaManager:
    """Get global resource quota manager."""
    global _resource_quota_manager
    if _resource_quota_manager is None:
        _resource_quota_manager = ResourceQuotaManager()
    return _resource_quota_manager


def init_resource_quota_manager(
    default_quota: ResourceQuota | None = None,
    check_interval: float = 5.0,
    system_memory_threshold: float = 0.9,
) -> ResourceQuotaManager:
    """Initialize global resource quota manager."""
    global _resource_quota_manager
    _resource_quota_manager = ResourceQuotaManager(
        default_quota=default_quota,
        check_interval=check_interval,
        system_memory_threshold=system_memory_threshold,
    )
    return _resource_quota_manager