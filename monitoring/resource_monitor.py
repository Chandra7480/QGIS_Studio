"""Universal AI GIS Studio — Resource monitoring with quota enforcement.

Provides system resource snapshots and per-job resource tracking.
Integrates with ResourceQuotaManager for enforcement.
"""

import logging
import shutil
import threading
import time
import os
from typing import Optional

logger = logging.getLogger("uagis.monitoring.resources")


class ResourceMonitor:
    """System resource monitor with quota enforcement integration."""

    def __init__(self, quota_manager=None):
        self.quota_manager = quota_manager
        self._psutil_available = False
        self._init_psutil()

    def _init_psutil(self):
        try:
            import psutil
            self._psutil = psutil
            self._psutil_available = True
        except ImportError:
            self._psutil = None
            logger.warning("psutil not available, using fallback methods")

    def snapshot(self) -> dict:
        """Get current system resource snapshot."""
        total, used, free = shutil.disk_usage(".")

        # Memory info
        if self._psutil_available:
            mem = self._psutil.virtual_memory()
            mem_info = {
                "total": mem.total,
                "available": mem.available,
                "used": mem.used,
                "percent": mem.percent,
            }
            cpu_percent = self._psutil.cpu_percent(interval=0.1)
            cpu_info = {"percent": cpu_percent}
        else:
            mem_info = self._get_memory_fallback()
            cpu_info = {"percent": 0.0}

        return {
            "disk": {"total": total, "used": used, "free": free},
            "memory": mem_info,
            "cpu": cpu_info,
            "timestamp": time.time(),
        }

    def _get_memory_fallback(self) -> dict:
        """Fallback memory info using ctypes on Windows."""
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            class MEMORYSTATUS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("dwTotalPhys", ctypes.c_size_t),
                            ("dwAvailPhys", ctypes.c_size_t),
                            ("dwTotalPageFile", ctypes.c_size_t),
                            ("dwAvailPageFile", ctypes.c_size_t),
                            ("dwTotalVirtual", ctypes.c_size_t),
                            ("dwAvailVirtual", ctypes.c_size_t),
                            ("dwExtendedMemory", ctypes.c_size_t)]
            ms = MEMORYSTATUS()
            ms.dwLength = ctypes.sizeof(MEMORYSTATUS)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            return {
                "total": ms.dwTotalPhys,
                "available": ms.dwAvailPhys,
                "used": ms.dwTotalPhys - ms.dwAvailPhys,
                "percent": ms.dwMemoryLoad,
            }
        except Exception:
            return {"note": "memory info unavailable"}

    def get_process_usage(self, pid: int | None = None) -> dict:
        """Get resource usage for a specific process."""
        if not self._psutil_available:
            return {"error": "psutil not available"}

        if pid is None:
            pid = os.getpid()

        try:
            proc = self._psutil.Process(pid)
            mem_info = proc.memory_info()
            cpu_times = proc.cpu_times()
            io_counters = proc.io_counters() if hasattr(proc, 'io_counters') else None

            return {
                "pid": pid,
                "memory_rss_mb": mem_info.rss / 1024 / 1024,
                "memory_vms_mb": mem_info.vms / 1024 / 1024,
                "cpu_user_seconds": cpu_times.user,
                "cpu_system_seconds": cpu_times.system,
                "cpu_total_seconds": cpu_times.user + cpu_times.system,
                "num_threads": proc.num_threads(),
                "io_read_mb": io_counters.read_bytes / 1024 / 1024 if io_counters else 0,
                "io_write_mb": io_counters.write_bytes / 1024 / 1024 if io_counters else 0,
            }
        except self._psutil.NoSuchProcess:
            return {"error": "process not found"}
        except Exception as exc:
            return {"error": str(exc)}

    def check_job_resources(self, job_id: str, pid: int | None = None) -> dict:
        """Check resources for a specific job and enforce quotas."""
        result = {"job_id": job_id}

        if self.quota_manager:
            # Update quota manager with current usage
            if pid:
                usage = self.get_process_usage(pid)
                if "error" not in usage:
                    self.quota_manager.update_usage(
                        job_id,
                        memory_mb=usage.get("memory_rss_mb"),
                        cpu_seconds=usage.get("cpu_total_seconds"),
                    )

            # Check and enforce quotas
            violations = self.quota_manager.enforce_quotas(job_id)
            result["quota_violations"] = [
                {
                    "type": v.quota_type,
                    "limit": v.limit,
                    "current": v.current,
                    "action": v.action_taken,
                }
                for v in violations
            ]
            result["quota_exceeded"] = len(violations) > 0

            # Get current usage from quota manager
            usage = self.quota_manager.get_usage(job_id)
            if usage:
                result["usage"] = {
                    "memory_mb": usage.memory_mb,
                    "cpu_seconds": usage.cpu_seconds,
                    "disk_mb": usage.disk_mb,
                    "duration_seconds": usage.duration_seconds,
                    "peak_memory_mb": usage.peak_memory_mb,
                    "peak_cpu_seconds": usage.peak_cpu_seconds,
                }

        return result

    def get_system_health(self) -> dict:
        """Get overall system health status."""
        snap = self.snapshot()

        health = {
            "healthy": True,
            "warnings": [],
            "critical": [],
            "resources": snap,
        }

        # Check memory
        mem = snap.get("memory", {})
        if isinstance(mem, dict) and "percent" in mem:
            if mem["percent"] > 90:
                health["critical"].append(f"Memory critical: {mem['percent']:.1f}%")
                health["healthy"] = False
            elif mem["percent"] > 75:
                health["warnings"].append(f"Memory high: {mem['percent']:.1f}%")

        # Check disk
        disk = snap.get("disk", {})
        if disk.get("total", 0) > 0:
            disk_percent = (disk["used"] / disk["total"]) * 100
            if disk_percent > 95:
                health["critical"].append(f"Disk critical: {disk_percent:.1f}%")
                health["healthy"] = False
            elif disk_percent > 85:
                health["warnings"].append(f"Disk high: {disk_percent:.1f}%")

        # Check CPU
        cpu = snap.get("cpu", {})
        if cpu.get("percent", 0) > 90:
            health["warnings"].append(f"CPU high: {cpu['percent']:.1f}%")

        # Check quota manager system pause
        if self.quota_manager and self.quota_manager.is_system_paused():
            health["critical"].append("System paused due to high memory")
            health["healthy"] = False

        return health

    def start_quota_monitor(self):
        """Start the quota manager's background monitor."""
        if self.quota_manager:
            self.quota_manager.start_monitor()

    def stop_quota_monitor(self):
        """Stop the quota manager's background monitor."""
        if self.quota_manager:
            self.quota_manager.stop_monitor()


# Global instance
_resource_monitor: ResourceMonitor | None = None


def get_resource_monitor() -> ResourceMonitor:
    """Get global resource monitor instance."""
    global _resource_monitor
    if _resource_monitor is None:
        _resource_monitor = ResourceMonitor()
    return _resource_monitor


def init_resource_monitor(quota_manager=None) -> ResourceMonitor:
    """Initialize global resource monitor."""
    global _resource_monitor
    _resource_monitor = ResourceMonitor(quota_manager=quota_manager)
    return _resource_monitor