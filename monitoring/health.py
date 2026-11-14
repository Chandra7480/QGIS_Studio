"""Universal AI GIS Studio — Unified Health Check.

Single /healthz endpoint with all subsystem checks:
- Bridge server
- QGIS connection
- Database
- MCP server
- Disk space
- Memory
- Agents
- Jobs
- Circuit breaker
- Resource quotas
- Temp file cleanup
- Rate limiter

k8s-ready: liveness and readiness probes.
"""

import logging
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Callable

logger = logging.getLogger("uagis.monitoring.health")


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a single health check."""
    name: str
    status: HealthStatus
    message: str = ""
    details: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() + "Z",
            "duration_ms": round(self.duration_ms, 2),
        }


@dataclass
class SystemHealth:
    """Overall system health status."""
    status: HealthStatus
    checks: list[HealthCheckResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0.0"
    uptime_seconds: float = 0.0

    def to_dict(self) -> dict:
        # Overall status is the worst of all checks
        status_order = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 1,
            HealthStatus.UNHEALTHY: 2,
            HealthStatus.UNKNOWN: 3,
        }
        worst = max((status_order.get(c.status, 3) for c in self.checks), default=0)
        overall = list(status_order.keys())[worst] if self.checks else HealthStatus.UNKNOWN

        return {
            "status": overall.value,
            "version": self.version,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "timestamp": self.timestamp.isoformat() + "Z",
            "checks": [c.to_dict() for c in self.checks],
        }

    def is_healthy(self) -> bool:
        """Check if system is healthy (for liveness probe)."""
        return all(c.status == HealthStatus.HEALTHY for c in self.checks)

    def is_ready(self) -> bool:
        """Check if system is ready to serve traffic (for readiness probe)."""
        # Ready if no UNHEALTHY checks (DEGRADED is OK for readiness)
        return not any(c.status == HealthStatus.UNHEALTHY for c in self.checks)


class HealthCheck(ABC):
    """Abstract base for health checks."""

    def __init__(self, name: str, timeout: float = 5.0):
        self.name = name
        self.timeout = timeout

    @abstractmethod
    def check(self) -> HealthCheckResult:
        """Perform the health check."""
        pass

    def _run_with_timeout(self, func: Callable) -> HealthCheckResult:
        """Run check function with timeout."""
        start = time.perf_counter()
        result_container = {"result": None, "exception": None}

        def target():
            try:
                result_container["result"] = func()
            except Exception as exc:
                result_container["exception"] = exc

        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout=self.timeout)

        duration = (time.perf_counter() - start) * 1000

        if thread.is_alive():
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check timed out after {self.timeout}s",
                duration_ms=duration,
            )

        if result_container["exception"]:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {result_container['exception']}",
                duration_ms=duration,
            )

        result = result_container["result"]
        if isinstance(result, HealthCheckResult):
            result.duration_ms = duration
            return result
        else:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="Check returned invalid result",
                duration_ms=duration,
            )


class BridgeHealthCheck(HealthCheck):
    """Check bridge server health."""

    def __init__(self, bridge_server=None):
        super().__init__("bridge", timeout=3.0)
        self.bridge_server = bridge_server

    def check(self) -> HealthCheckResult:
        if self.bridge_server is None:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="Bridge server not configured",
            )

        if not self.bridge_server.running:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="Bridge server not running",
            )

        # Check if we can reach the executor
        try:
            if hasattr(self.bridge_server, 'dispatcher') and self.bridge_server.dispatcher:
                executor = self.bridge_server.dispatcher.executor
                health = executor.health()
                if not health.get("qgis_connected", False):
                    return HealthCheckResult(
                        name=self.name,
                        status=HealthStatus.DEGRADED,
                        message="QGIS not connected",
                        details=health,
                    )
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="Bridge server running",
                details={"port": self.bridge_server.port},
            )
        except Exception as exc:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Bridge health check failed: {exc}",
            )


class QGISHealthCheck(HealthCheck):
    """Check QGIS connection and status."""

    def __init__(self, executor=None):
        super().__init__("qgis", timeout=5.0)
        self.executor = executor

    def check(self) -> HealthCheckResult:
        if self.executor is None:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="QGIS executor not configured",
            )

        try:
            health = self.executor.health()
            if not health.get("qgis_connected", False):
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="QGIS not connected",
                    details=health,
                )

            # Check project loaded
            project = self.executor.inspect_project()
            project_loaded = bool(project.get("project_file"))

            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY if project_loaded else HealthStatus.DEGRADED,
                message="QGIS connected" + (" (no project)" if not project_loaded else ""),
                details={
                    "qgis_connected": True,
                    "project_loaded": project_loaded,
                    "layer_count": health.get("layer_count", 0),
                },
            )
        except Exception as exc:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"QGIS check failed: {exc}",
            )


class DatabaseHealthCheck(HealthCheck):
    """Check database connectivity."""

    def __init__(self, db=None):
        super().__init__("database", timeout=3.0)
        self.db = db

    def check(self) -> HealthCheckResult:
        if self.db is None:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="Database not configured",
            )

        try:
            # Simple query to verify connection
            row = self.db.fetchone("SELECT 1 as test")
            if row and row["test"] == 1:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="Database connection OK",
                )
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="Database query returned unexpected result",
            )
        except Exception as exc:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Database check failed: {exc}",
            )


class MCPHealthCheck(HealthCheck):
    """Check MCP server status."""

    def __init__(self, mcp_server=None):
        super().__init__("mcp", timeout=3.0)
        self.mcp_server = mcp_server

    def check(self) -> HealthCheckResult:
        if self.mcp_server is None:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="MCP server not configured",
            )

        try:
            # Check if server has tools registered
            tool_count = len(self.mcp_server.registry.all()) if hasattr(self.mcp_server, 'registry') else 0
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY if tool_count > 0 else HealthStatus.DEGRADED,
                message=f"MCP server OK ({tool_count} tools)",
                details={"tool_count": tool_count},
            )
        except Exception as exc:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"MCP check failed: {exc}",
            )


class DiskHealthCheck(HealthCheck):
    """Check disk space."""

    def __init__(self, path: str = ".", warning_threshold: float = 0.85, critical_threshold: float = 0.95):
        super().__init__("disk", timeout=2.0)
        self.path = path
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def check(self) -> HealthCheckResult:
        try:
            import shutil
            total, used, free = shutil.disk_usage(self.path)
            used_percent = used / total if total > 0 else 0

            details = {
                "total_mb": total / 1024 / 1024,
                "used_mb": used / 1024 / 1024,
                "free_mb": free / 1024 / 1024,
                "used_percent": round(used_percent * 100, 1),
            }

            if used_percent >= self.critical_threshold:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Disk critical: {used_percent*100:.1f}% used",
                    details=details,
                )
            elif used_percent >= self.warning_threshold:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message=f"Disk warning: {used_percent*100:.1f}% used",
                    details=details,
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message=f"Disk OK: {used_percent*100:.1f}% used",
                    details=details,
                )
        except Exception as exc:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Disk check failed: {exc}",
            )


class MemoryHealthCheck(HealthCheck):
    """Check memory usage."""

    def __init__(self, warning_threshold: float = 0.75, critical_threshold: float = 0.90):
        super().__init__("memory", timeout=2.0)
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold

    def check(self) -> HealthCheckResult:
        try:
            import psutil
            mem = psutil.virtual_memory()
            details = {
                "total_mb": mem.total / 1024 / 1024,
                "available_mb": mem.available / 1024 / 1024,
                "used_mb": mem.used / 1024 / 1024,
                "used_percent": mem.percent,
            }

            if mem.percent / 100 >= self.critical_threshold:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Memory critical: {mem.percent:.1f}% used",
                    details=details,
                )
            elif mem.percent / 100 >= self.warning_threshold:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message=f"Memory warning: {mem.percent:.1f}% used",
                    details=details,
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message=f"Memory OK: {mem.percent:.1f}% used",
                    details=details,
                )
        except ImportError:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="psutil not available",
            )
        except Exception as exc:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Memory check failed: {exc}",
            )


class AgentsHealthCheck(HealthCheck):
    """Check agent system status."""

    def __init__(self, orchestrator=None):
        super().__init__("agents", timeout=3.0)
        self.orchestrator = orchestrator

    def check(self) -> HealthCheckResult:
        if self.orchestrator is None:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="Agent orchestrator not configured",
            )

        try:
            agents = self.orchestrator.list_agents()
            active_count = sum(1 for a in agents if a.get("enabled", True))
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY if active_count > 0 else HealthStatus.DEGRADED,
                message=f"Agents OK ({active_count} active)",
                details={"total": len(agents), "active": active_count},
            )
        except Exception as exc:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Agents check failed: {exc}",
            )


class JobsHealthCheck(HealthCheck):
    """Check job system status."""

    def __init__(self, job_manager=None):
        super().__init__("jobs", timeout=3.0)
        self.job_manager = job_manager

    def check(self) -> HealthCheckResult:
        if self.job_manager is None:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="Job manager not configured",
            )

        try:
            queued = len(self.job_manager.list_jobs(status="queued"))
            running = len(self.job_manager.list_jobs(status="running"))
            failed = len(self.job_manager.list_jobs(status="failed"))

            # Degraded if too many queued or failed
            if running > 50 or queued > 100:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.HEALTHY

            return HealthCheckResult(
                name=self.name,
                status=status,
                message=f"Jobs: {running} running, {queued} queued, {failed} failed",
                details={"running": running, "queued": queued, "failed": failed},
            )
        except Exception as exc:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Jobs check failed: {exc}",
            )


class CircuitBreakerHealthCheck(HealthCheck):
    """Check circuit breaker status."""

    def __init__(self, circuit_breaker=None):
        super().__init__("circuit_breaker", timeout=2.0)
        self.circuit_breaker = circuit_breaker

    def check(self) -> HealthCheckResult:
        if self.circuit_breaker is None:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="Circuit breaker not configured",
            )

        try:
            state = self.circuit_breaker.get_state() if hasattr(self.circuit_breaker, 'get_state') else "unknown"
            if state == "open":
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="Circuit breaker OPEN",
                    details={"state": state},
                )
            elif state == "half_open":
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message="Circuit breaker HALF_OPEN",
                    details={"state": state},
                )
            else:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.HEALTHY,
                    message=f"Circuit breaker {state}",
                    details={"state": state},
                )
        except Exception as exc:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Circuit breaker check failed: {exc}",
            )


class ResourceQuotaHealthCheck(HealthCheck):
    """Check resource quota manager."""

    def __init__(self, quota_manager=None):
        super().__init__("resource_quota", timeout=2.0)
        self.quota_manager = quota_manager

    def check(self) -> HealthCheckResult:
        if self.quota_manager is None:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="Resource quota manager not configured",
            )

        try:
            stats = self.quota_manager.get_system_stats()
            if "error" in stats:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message=f"Resource stats error: {stats['error']}",
                )

            if self.quota_manager.is_system_paused():
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message="System paused due to high memory",
                    details=stats,
                )

            mem = stats.get("memory", {})
            if mem.get("used_percent", 0) > 90:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message=f"High memory: {mem.get('used_percent', 0):.1f}%",
                    details=stats,
                )

            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message="Resource quotas OK",
                details=stats,
            )
        except Exception as exc:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Resource quota check failed: {exc}",
            )


class TempCleanupHealthCheck(HealthCheck):
    """Check temp file cleanup system."""

    def __init__(self, temp_manager=None):
        super().__init__("temp_cleanup", timeout=2.0)
        self.temp_manager = temp_manager

    def check(self) -> HealthCheckResult:
        if self.temp_manager is None:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="Temp cleanup not configured",
            )

        try:
            stats = self.temp_manager.get_stats()
            disk = stats.get("disk", {})
            if disk.get("low_disk", False):
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Low disk: {disk.get('free_mb', 0):.0f} MB free",
                    details=stats,
                )

            tracked_mb = stats.get("tracked_size_mb", 0)
            max_mb = stats.get("max_total_size_mb", 500)
            if tracked_mb > max_mb * 0.9:
                return HealthCheckResult(
                    name=self.name,
                    status=HealthStatus.DEGRADED,
                    message=f"Temp quota near limit: {tracked_mb:.1f}/{max_mb} MB",
                    details=stats,
                )

            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message=f"Temp cleanup OK ({tracked_mb:.1f} MB tracked)",
                details=stats,
            )
        except Exception as exc:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Temp cleanup check failed: {exc}",
            )


class RateLimiterHealthCheck(HealthCheck):
    """Check rate limiter status."""

    def __init__(self, rate_limiter=None):
        super().__init__("rate_limiter", timeout=2.0)
        self.rate_limiter = rate_limiter

    def check(self) -> HealthCheckResult:
        if self.rate_limiter is None:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNKNOWN,
                message="Rate limiter not configured",
            )

        try:
            # Check if backend is responsive
            backend = self.rate_limiter.backend
            if hasattr(backend, '_redis') and backend._redis is not None:
                try:
                    backend._redis.ping()
                    backend_status = "redis_connected"
                except Exception:
                    backend_status = "redis_disconnected_fallback"
            else:
                backend_status = "in_memory"

            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.HEALTHY,
                message=f"Rate limiter OK ({backend_status})",
                details={"backend": backend_status, "tool_configs": len(self.rate_limiter.tool_configs)},
            )
        except Exception as exc:
            return HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Rate limiter check failed: {exc}",
            )


class HealthChecker:
    """Main health checker orchestrating all checks."""

    def __init__(self, version: str = "1.0.0", start_time: float | None = None):
        self.version = version
        self.start_time = start_time or time.time()
        self._checks: list[HealthCheck] = []
        self._lock = threading.RLock()

    def add_check(self, check: HealthCheck) -> None:
        """Add a health check."""
        with self._lock:
            self._checks.append(check)

    def remove_check(self, name: str) -> bool:
        """Remove a health check by name."""
        with self._lock:
            for i, check in enumerate(self._checks):
                if check.name == name:
                    self._checks.pop(i)
                    return True
            return False

    def run_checks(self, check_names: list[str] | None = None) -> SystemHealth:
        """Run all checks (or subset) and return system health."""
        with self._lock:
            checks_to_run = self._checks
            if check_names:
                checks_to_run = [c for c in self._checks if c.name in check_names]

        results = []
        for check in checks_to_run:
            try:
                result = check._run_with_timeout(check.check)
                results.append(result)
            except Exception as exc:
                logger.exception("Health check %s raised exception", check.name)
                results.append(HealthCheckResult(
                    name=check.name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check crashed: {exc}",
                ))

        uptime = time.time() - self.start_time
        health = SystemHealth(
            status=HealthStatus.HEALTHY,  # Will be computed in to_dict
            checks=results,
            timestamp=datetime.utcnow(),
            version=self.version,
            uptime_seconds=uptime,
        )
        return health

    def run_liveness(self) -> SystemHealth:
        """Run liveness probe checks (critical only)."""
        # For liveness, we only care if the process is alive
        # Run a minimal set of critical checks
        return self.run_checks(["bridge", "database"])

    def run_readiness(self) -> SystemHealth:
        """Run readiness probe checks (all subsystems)."""
        return self.run_checks()


# Global health checker
_health_checker: HealthChecker | None = None


def get_health_checker() -> HealthChecker:
    """Get global health checker."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker


def init_health_checker(
    version: str = "1.0.0",
    start_time: float | None = None,
    bridge_server=None,
    executor=None,
    db=None,
    mcp_server=None,
    orchestrator=None,
    job_manager=None,
    circuit_breaker=None,
    quota_manager=None,
    temp_manager=None,
    rate_limiter=None,
) -> HealthChecker:
    """Initialize global health checker with all subsystems."""
    global _health_checker
    _health_checker = HealthChecker(version=version, start_time=start_time)

    # Add all checks
    _health_checker.add_check(BridgeHealthCheck(bridge_server))
    _health_checker.add_check(QGISHealthCheck(executor))
    _health_checker.add_check(DatabaseHealthCheck(db))
    _health_checker.add_check(MCPHealthCheck(mcp_server))
    _health_checker.add_check(DiskHealthCheck())
    _health_checker.add_check(MemoryHealthCheck())
    _health_checker.add_check(AgentsHealthCheck(orchestrator))
    _health_checker.add_check(JobsHealthCheck(job_manager))
    _health_checker.add_check(CircuitBreakerHealthCheck(circuit_breaker))
    _health_checker.add_check(ResourceQuotaHealthCheck(quota_manager))
    _health_checker.add_check(TempCleanupHealthCheck(temp_manager))
    _health_checker.add_check(RateLimiterHealthCheck(rate_limiter))

    return _health_checker