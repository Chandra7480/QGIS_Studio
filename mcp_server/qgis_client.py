"""Universal AI GIS Studio — QGIS Bridge HTTP Client.

Async client with connection pooling, retry logic, circuit breaker,
and structured observability for reliable bridge communication.
"""

import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Optional, AsyncIterator

import httpx
from httpx import Limits, Timeout

from core.logging import get_logger
from core.exceptions import BridgeError, UAGISTimeoutError, MCPError

logger = get_logger("mcp.qgis_client")

# Circuit breaker states
CB_CLOSED = "closed"
CB_OPEN = "open"
CB_HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerState:
    """Circuit breaker state tracking."""
    state: str = CB_CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0
    last_state_change: float = field(default_factory=time.time)


class CircuitBreaker:
    """Simple circuit breaker for bridge failures.

    - Opens after 5 consecutive failures
    - Half-open after 30 seconds in open state
    - Closes after 3 consecutive successes in half-open
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_success_threshold: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_success_threshold = half_open_success_threshold
        self._state = CircuitBreakerState()
        self._lock = asyncio.Lock()

    @property
    def is_closed(self) -> bool:
        return self._state.state == CB_CLOSED

    @property
    def is_open(self) -> bool:
        return self._state.state == CB_OPEN

    @property
    def is_half_open(self) -> bool:
        return self._state.state == CB_HALF_OPEN

    async def can_execute(self) -> bool:
        """Check if request can proceed."""
        async with self._lock:
            if self._state.state == CB_CLOSED:
                return True
            if self._state.state == CB_OPEN:
                # Check if recovery timeout has passed
                if time.time() - self._state.last_state_change >= self.recovery_timeout:
                    self._state.state = CB_HALF_OPEN
                    self._state.success_count = 0
                    self._state.last_state_change = time.time()
                    logger.warning("Circuit breaker entering HALF_OPEN state")
                    return True
                return False
            # HALF_OPEN - allow one request through
            return True

    async def record_success(self):
        """Record a successful call."""
        async with self._lock:
            if self._state.state == CB_HALF_OPEN:
                self._state.success_count += 1
                if self._state.success_count >= self.half_open_success_threshold:
                    self._state.state = CB_CLOSED
                    self._state.failure_count = 0
                    self._state.success_count = 0
                    self._state.last_state_change = time.time()
                    logger.info("Circuit breaker CLOSED after recovery")
            elif self._state.state == CB_CLOSED:
                self._state.failure_count = 0

    async def record_failure(self):
        """Record a failed call."""
        async with self._lock:
            self._state.failure_count += 1
            self._state.last_failure_time = time.time()

            if self._state.state == CB_HALF_OPEN:
                # Any failure in half-open reopens the circuit
                self._state.state = CB_OPEN
                self._state.success_count = 0
                self._state.last_state_change = time.time()
                logger.warning("Circuit breaker OPEN after half-open failure")
            elif self._state.state == CB_CLOSED:
                if self._state.failure_count >= self.failure_threshold:
                    self._state.state = CB_OPEN
                    self._state.last_state_change = time.time()
                    logger.warning(
                        "Circuit breaker OPEN after %d consecutive failures",
                        self.failure_threshold,
                    )

    def get_state(self) -> dict:
        """Get current state for monitoring."""
        return {
            "state": self._state.state,
            "failure_count": self._state.failure_count,
            "success_count": self._state.success_count,
        }


class RetryPolicy:
    """Exponential backoff retry policy with jitter."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 10.0,
        jitter: float = 0.1,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Determine if request should be retried."""
        if attempt >= self.max_retries:
            return False
        # Retry on connection errors, timeouts, 5xx, 429
        if isinstance(exception, (httpx.ConnectError, httpx.TimeoutException)):
            return True
        if isinstance(exception, httpx.HTTPStatusError):
            return exception.response.status_code >= 500 or exception.response.status_code == 429
        return False

    def get_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        # Add jitter: ±jitter * delay
        import random
        jitter_range = delay * self.jitter
        return delay + random.uniform(-jitter_range, jitter_range)


@dataclass
class BridgeMetrics:
    """Prometheus-style metrics for bridge client."""
    requests_total: dict = field(default_factory=lambda: {"success": 0, "error": 0, "retry": 0})
    latency_seconds: list = field(default_factory=list)
    circuit_breaker_state: str = CB_CLOSED

    def record_request(self, success: bool, latency: float, retried: bool = False):
        if success:
            self.requests_total["success"] += 1
        else:
            self.requests_total["error"] += 1
        if retried:
            self.requests_total["retry"] += 1
        self.latency_seconds.append(latency)
        # Keep last 1000 latencies
        if len(self.latency_seconds) > 1000:
            self.latency_seconds = self.latency_seconds[-1000:]

    def get_summary(self) -> dict:
        latencies = self.latency_seconds
        if not latencies:
            return {"requests": self.requests_total, "latency_p50": 0, "latency_p95": 0, "latency_p99": 0}
        sorted_lat = sorted(latencies)
        return {
            "requests": self.requests_total,
            "latency_p50": sorted_lat[len(sorted_lat) // 2],
            "latency_p95": sorted_lat[int(len(sorted_lat) * 0.95)],
            "latency_p99": sorted_lat[int(len(sorted_lat) * 0.99)],
            "circuit_breaker": self.circuit_breaker_state,
        }


class AsyncQgisBridgeClient:
    """Async HTTP client for QGIS Bridge with connection pooling, retries, and circuit breaker."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout_seconds: int = 300,
        # Connection pool settings
        max_connections: int = 10,
        max_keepalive_connections: int = 5,
        # Timeout settings (connect, read, write, pool)
        connect_timeout: float = 5.0,
        read_timeout: float = 300.0,
        write_timeout: float = 30.0,
        pool_timeout: float = 10.0,
        # Retry settings
        max_retries: int = 3,
        retry_base_delay: float = 0.5,
        retry_max_delay: float = 10.0,
        # Circuit breaker settings
        cb_failure_threshold: int = 5,
        cb_recovery_timeout: float = 30.0,
        cb_half_open_success: int = 3,
    ):
        import os
        if base_url is None:
            base_url = os.environ.get("UAGIS_BRIDGE_URL", "http://127.0.0.1:8765")

        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout_seconds = timeout_seconds

        # Connection pool limits
        self._limits = Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
        )

        # Timeout configuration
        self._timeout = Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=write_timeout,
            pool=pool_timeout,
        )

        # Retry policy
        self._retry_policy = RetryPolicy(
            max_retries=max_retries,
            base_delay=retry_base_delay,
            max_delay=retry_max_delay,
        )

        # Circuit breaker
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=cb_failure_threshold,
            recovery_timeout=cb_recovery_timeout,
            half_open_success_threshold=cb_half_open_success,
        )

        # Metrics
        self._metrics = BridgeMetrics()

        # HTTP client (lazy initialization)
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    base_url=self.base_url,
                    limits=self._limits,
                    timeout=self._timeout,
                    headers=self._headers(),
                    follow_redirects=True,
                )
            return self._client

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def _generate_request_id(self) -> str:
        return f"req_{uuid.uuid4().hex[:12]}"

    async def dispatch(
        self,
        tool: str,
        params: dict,
        request_id: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> dict:
        """Dispatch a tool call to the bridge with retry and circuit breaker."""
        request_id = request_id or self._generate_request_id()
        start_time = time.perf_counter()
        retried = False

        # Check circuit breaker
        if not await self._circuit_breaker.can_execute():
            cb_state = self._circuit_breaker.get_state()
            raise BridgeError(
                f"Circuit breaker OPEN - bridge unavailable (state: {cb_state['state']})",
                context={"circuit_breaker": cb_state, "request_id": request_id},
            )

        client = await self._get_client()
        timeout = httpx.Timeout(timeout_seconds or self.timeout_seconds) if timeout_seconds else None

        payload = {
            "request_id": request_id,
            "tool": tool,
            "params": params,
            "timeout_seconds": timeout_seconds or self.timeout_seconds,
        }

        last_exception = None
        for attempt in range(self._retry_policy.max_retries + 1):
            try:
                logger.debug(
                    "Dispatching %s (attempt %d/%d) request_id=%s",
                    tool, attempt + 1, self._retry_policy.max_retries + 1, request_id
                )

                response = await client.post(
                    "/dispatch",
                    json=payload,
                    timeout=timeout,
                )
                response.raise_for_status()

                latency = time.perf_counter() - start_time
                await self._circuit_breaker.record_success()
                self._metrics.record_request(True, latency, retried)
                self._metrics.circuit_breaker_state = self._circuit_breaker.get_state()["state"]

                logger.debug(
                    "Dispatch %s succeeded in %.3fs request_id=%s",
                    tool, latency, request_id
                )
                return response.json()

            except httpx.HTTPStatusError as exc:
                last_exception = exc
                latency = time.perf_counter() - start_time

                # Don't retry 4xx (except 429)
                if 400 <= exc.response.status_code < 500 and exc.response.status_code != 429:
                    await self._circuit_breaker.record_failure()
                    self._metrics.record_request(False, latency, retried)
                    self._metrics.circuit_breaker_state = self._circuit_breaker.get_state()["state"]

                    try:
                        detail = exc.response.json()
                    except Exception:
                        detail = {"code": "HTTP_ERROR", "message": str(exc)}

                    raise BridgeError(
                        f"Bridge HTTP {exc.response.status_code} for {tool}: {detail.get('message', str(exc))}",
                        context={
                            "http_status": exc.response.status_code,
                            "detail": detail,
                            "request_id": request_id,
                            "circuit_breaker": self._circuit_breaker.get_state(),
                        },
                    ) from exc

            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exception = exc
                latency = time.perf_counter() - start_time

            except Exception as exc:
                last_exception = exc
                latency = time.perf_counter() - start_time

            # Check if we should retry
            if not self._retry_policy.should_retry(attempt, last_exception):
                break

            retried = True
            delay = self._retry_policy.get_delay(attempt)
            logger.warning(
                "Dispatch %s failed (attempt %d), retrying in %.2fs: %s request_id=%s",
                tool, attempt + 1, delay, last_exception, request_id
            )
            await asyncio.sleep(delay)

        # All retries exhausted
        latency = time.perf_counter() - start_time
        await self._circuit_breaker.record_failure()
        self._metrics.record_request(False, latency, retried)
        self._metrics.circuit_breaker_state = self._circuit_breaker.get_state()["state"]

        raise BridgeError(
            f"Bridge dispatch failed for {tool} after {self._retry_policy.max_retries + 1} attempts: {last_exception}",
            context={
                "request_id": request_id,
                "attempts": self._retry_policy.max_retries + 1,
                "last_error": str(last_exception),
                "circuit_breaker": self._circuit_breaker.get_state(),
            },
        ) from last_exception

    async def health(self) -> dict:
        """Health check with latency measurement."""
        start_time = time.perf_counter()
        client = await self._get_client()

        try:
            response = await client.get("/health", timeout=httpx.Timeout(10.0))
            response.raise_for_status()
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            data = response.json()
            data["bridge_latency_ms"] = latency_ms
            data["qgis_connected"] = data.get("qgis_connected", True)
            return data
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return {
                "qgis_connected": False,
                "bridge_latency_ms": latency_ms,
                "error": str(exc),
            }

    async def ready(self) -> dict:
        """Readiness check - verifies bridge can process requests."""
        start_time = time.perf_counter()
        client = await self._get_client()

        try:
            response = await client.get("/ready", timeout=httpx.Timeout(5.0))
            response.raise_for_status()
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            data = response.json()
            data["bridge_latency_ms"] = latency_ms
            return data
        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            if exc.response.status_code == 503:
                return {
                    "ready": False,
                    "bridge_latency_ms": latency_ms,
                    "error": exc.response.json().get("detail", "Service unavailable"),
                }
            raise
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            return {
                "ready": False,
                "bridge_latency_ms": latency_ms,
                "error": str(exc),
            }

    def get_metrics(self) -> dict:
        """Get client metrics for monitoring."""
        return self._metrics.get_summary()

    def get_circuit_breaker_state(self) -> dict:
        """Get circuit breaker state."""
        return self._circuit_breaker.get_state()

    async def close(self):
        """Close the HTTP client and clean up."""
        async with self._client_lock:
            if self._client and not self._client.is_closed:
                await self._client.aclose()
                self._client = None

    @asynccontextmanager
    async def session(self) -> AsyncIterator["AsyncQgisBridgeClient"]:
        """Context manager for client lifecycle."""
        try:
            yield self
        finally:
            await self.close()


# Backward compatibility: sync wrapper for existing code
class QgisBridgeClient:
    """Synchronous wrapper around AsyncQgisBridgeClient for backward compatibility.

    Uses asyncio.run() per call to avoid persistent event loop leaks.
    Each call creates a fresh event loop that is properly cleaned up.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout_seconds: int = 300,
    ):
        import os
        if base_url is None:
            base_url = os.environ.get("UAGIS_BRIDGE_URL", "http://127.0.0.1:8765")

        self._async_client = AsyncQgisBridgeClient(
            base_url=base_url,
            auth_token=auth_token,
            timeout_seconds=timeout_seconds,
        )
        self._closed = False

    def dispatch(
        self,
        tool: str,
        params: dict,
        request_id: str,
        timeout_seconds: Optional[int] = None,
    ) -> dict:
        """Sync dispatch - runs async version using asyncio.run()."""
        if self._closed:
            raise RuntimeError("QgisBridgeClient is closed")
        coro = self._async_client.dispatch(tool, params, request_id, timeout_seconds)
        return asyncio.run(coro)

    def health(self) -> dict:
        """Sync health check using asyncio.run()."""
        if self._closed:
            raise RuntimeError("QgisBridgeClient is closed")
        return asyncio.run(self._async_client.health())

    def close(self):
        """Close the async client."""
        if self._closed:
            return
        self._closed = True
        # Use asyncio.run to properly close the async client
        asyncio.run(self._async_client.close())


def create_client(
    base_url: Optional[str] = None,
    auth_token: Optional[str] = None,
    timeout_seconds: int = 300,
    async_mode: bool = False,
) -> AsyncQgisBridgeClient | QgisBridgeClient:
    """Factory to create sync or async client."""
    if async_mode:
        return AsyncQgisBridgeClient(
            base_url=base_url,
            auth_token=auth_token,
            timeout_seconds=timeout_seconds,
        )
    return QgisBridgeClient(
        base_url=base_url,
        auth_token=auth_token,
        timeout_seconds=timeout_seconds,
    )