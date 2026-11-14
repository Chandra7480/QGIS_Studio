"""Universal AI GIS Studio — Prometheus Metrics for Bridge Server.

Provides metrics for monitoring bridge health, request latency, and throughput.
"""

from typing import Optional, Any

try:
    from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = Histogram = Gauge = CollectorRegistry = generate_latest = None  # type: ignore

from core.logging import get_logger

logger = get_logger("bridge.metrics")


class BridgeMetrics:
    """Prometheus metrics for bridge server."""

    def __init__(self, registry: Optional[Any] = None):
        self._enabled = PROMETHEUS_AVAILABLE
        self._registry = registry

        if not self._enabled:
            logger.warning("prometheus-client not available, metrics disabled")
            return

        # Request counters
        self.requests_total = Counter(
            "bridge_requests_total",
            "Total number of bridge requests",
            ["tool", "status"],
            registry=registry,
        )

        # Request latency histogram
        self.request_latency_seconds = Histogram(
            "bridge_request_latency_seconds",
            "Bridge request latency in seconds",
            ["tool"],
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
            registry=registry,
        )

        # Bridge up/down gauge
        self.bridge_up = Gauge(
            "bridge_up",
            "Bridge server availability (1=up, 0=down)",
            registry=registry,
        )

        # Active requests gauge
        self.active_requests = Gauge(
            "bridge_active_requests",
            "Number of currently active requests",
            registry=registry,
        )

        # Circuit breaker state gauge
        self.circuit_breaker_state = Gauge(
            "bridge_circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=half_open, 2=open)",
            registry=registry,
        )

        # Job queue metrics
        self.jobs_queued = Gauge(
            "bridge_jobs_queued",
            "Number of jobs currently queued",
            registry=registry,
        )

        self.jobs_running = Gauge(
            "bridge_jobs_running",
            "Number of jobs currently running",
            registry=registry,
        )

        self.jobs_completed = Counter(
            "bridge_jobs_completed_total",
            "Total number of completed jobs",
            ["status"],  # success, failed, cancelled
            registry=registry,
        )

        # Request queue metrics (NEW for task-7)
        self.queue_depth = Gauge(
            "bridge_queue_depth",
            "Current request queue depth",
            registry=registry,
        )

        self.queue_wait_seconds = Histogram(
            "bridge_queue_wait_seconds",
            "Time requests spend waiting in queue",
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=registry,
        )

        self.rejected_total = Counter(
            "bridge_rejected_total",
            "Total number of rejected requests (queue full)",
            registry=registry,
        )

        self.batch_requests_total = Counter(
            "bridge_batch_requests_total",
            "Total number of batch dispatch requests",
            ["status"],
            registry=registry,
        )

        # QGIS project metrics
        self.qgis_project_loaded = Gauge(
            "bridge_qgis_project_loaded",
            "Whether a QGIS project is loaded (1=yes, 0=no)",
            registry=registry,
        )

        self.qgis_layer_count = Gauge(
            "bridge_qgis_layer_count",
            "Number of layers in the current QGIS project",
            registry=registry,
        )

        # Set initial bridge up
        self.bridge_up.set(1)

    def record_request(self, tool: str, status: str, latency: float):
        """Record a request completion."""
        if not self._enabled:
            return
        self.requests_total.labels(tool=tool, status=status).inc()
        self.request_latency_seconds.labels(tool=tool).observe(latency)

    def set_bridge_up(self, up: bool):
        """Set bridge availability."""
        if not self._enabled:
            return
        self.bridge_up.set(1 if up else 0)

    def set_active_requests(self, count: int):
        """Set number of active requests."""
        if not self._enabled:
            return
        self.active_requests.set(count)

    def set_circuit_breaker_state(self, state: str):
        """Set circuit breaker state."""
        if not self._enabled:
            return
        state_map = {"closed": 0, "half_open": 1, "open": 2}
        self.circuit_breaker_state.set(state_map.get(state, 0))

    def set_jobs_queued(self, count: int):
        """Set queued jobs count."""
        if not self._enabled:
            return
        self.jobs_queued.set(count)

    def set_jobs_running(self, count: int):
        """Set running jobs count."""
        if not self._enabled:
            return
        self.jobs_running.set(count)

    def record_job_completed(self, status: str):
        """Record job completion."""
        if not self._enabled:
            return
        self.jobs_completed.labels(status=status).inc()

    def set_queue_depth(self, depth: int):
        """Set request queue depth."""
        if not self._enabled:
            return
        self.queue_depth.set(depth)

    def record_queue_wait(self, wait_time: float):
        """Record queue wait time."""
        if not self._enabled:
            return
        self.queue_wait_seconds.observe(wait_time)

    def record_rejected(self):
        """Record a rejected request."""
        if not self._enabled:
            return
        self.rejected_total.inc()

    def record_batch_request(self, status: str):
        """Record a batch dispatch request."""
        if not self._enabled:
            return
        self.batch_requests_total.labels(status=status).inc()

    def set_qgis_project_loaded(self, loaded: bool):
        """Set QGIS project loaded state."""
        if not self._enabled:
            return
        self.qgis_project_loaded.set(1 if loaded else 0)

    def set_qgis_layer_count(self, count: int):
        """Set QGIS layer count."""
        if not self._enabled:
            return
        self.qgis_layer_count.set(count)

    def get_metrics_output(self) -> bytes:
        """Get Prometheus metrics in text format."""
        if not self._enabled or self._registry is None:
            return b"# Prometheus client not available\n"
        return generate_latest(self._registry)

    def is_enabled(self) -> bool:
        return self._enabled


# Global metrics instance (initialized in bridge_server.py)
_global_metrics: Optional[BridgeMetrics] = None


def get_metrics() -> BridgeMetrics:
    """Get global metrics instance."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = BridgeMetrics()
    return _global_metrics


def init_metrics(registry: Optional[Any] = None) -> BridgeMetrics:
    """Initialize global metrics."""
    global _global_metrics
    _global_metrics = BridgeMetrics(registry)
    return _global_metrics