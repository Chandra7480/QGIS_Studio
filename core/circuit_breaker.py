"""Universal AI GIS Studio — Unified Circuit Breaker.

Provides a single circuit breaker implementation shared between the Bridge
server and MCP client for consistent failure handling and recovery.
"""

import asyncio
import logging
import time
import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Dict, List

from core.logging import get_logger

logger = get_logger("circuit_breaker")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing recovery, limited requests allowed


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 10          # Failures before opening
    success_threshold: int = 5           # Successes in half-open before closing
    recovery_timeout: float = 60.0       # Seconds before half-open
    half_open_max_calls: int = 3         # Max concurrent calls in half-open
    excluded_exceptions: tuple = ()      # Exception types that don't count as failures
    
    # Prometheus metric names
    metrics_prefix: str = "circuit_breaker"


@dataclass
class CircuitBreakerStats:
    """Statistics for monitoring."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    last_state_change: Optional[float] = None
    current_state: CircuitState = CircuitState.CLOSED


class CircuitBreaker:
    """Thread-safe circuit breaker with async support.
    
    Implements the circuit breaker pattern to prevent cascading failures
    and allow failing services time to recover.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests blocked immediately
    - HALF_OPEN: Testing recovery, limited requests allowed
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        fallback: Optional[Callable[..., Any]] = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.fallback = fallback
        
        # State management
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._last_state_change = time.time()
        self._last_failure_time: Optional[float] = None
        
        # Thread safety
        self._lock = threading.RLock()
        self._async_lock = asyncio.Lock()
        
        # Statistics
        self.stats = CircuitBreakerStats(current_state=CircuitState.CLOSED)
        
        # Callbacks for state changes
        self._state_change_callbacks: List[Callable[[str, CircuitState, CircuitState], None]] = []
        
        logger.info("Circuit breaker '%s' initialized: threshold=%d, timeout=%.1fs",
                    name, self.config.failure_threshold, self.config.recovery_timeout)
    
    @property
    def state(self) -> CircuitState:
        return self._state
    
    @property
    def is_closed(self) -> bool:
        return self._state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        return self._state == CircuitState.OPEN
    
    @property
    def is_half_open(self) -> bool:
        return self._state == CircuitState.HALF_OPEN
    
    def add_state_change_callback(self, callback: Callable[[str, CircuitState, CircuitState], None]) -> None:
        """Add callback for state changes."""
        self._state_change_callbacks.append(callback)
    
    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old_state = self._state
        if old_state == new_state:
            return
        
        self._state = new_state
        self._last_state_change = time.time()
        self.stats.current_state = new_state
        self.stats.state_changes += 1
        self.stats.last_state_change = time.time()
        
        logger.warning("Circuit breaker '%s' state change: %s -> %s",
                       self.name, old_state.value, new_state.value)
        
        # Notify callbacks
        for callback in self._state_change_callbacks:
            try:
                callback(self.name, old_state, new_state)
            except Exception as e:
                logger.error("Circuit breaker callback error: %s", e)
    
    def _should_open(self) -> bool:
        """Check if circuit should open."""
        return self._failure_count >= self.config.failure_threshold
    
    def _should_close(self) -> bool:
        """Check if circuit should close from half-open."""
        return self._success_count >= self.config.success_threshold
    
    def _can_execute_half_open(self) -> bool:
        """Check if a call can proceed in half-open state."""
        return self._half_open_calls < self.config.half_open_max_calls
    
    def can_execute(self) -> bool:
        """Check if a request can proceed (sync version)."""
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if time.time() - self._last_state_change >= self.config.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                    self._half_open_calls = 0
                    self._success_count = 0
                    return True
                return False
            
            # HALF_OPEN - allow limited calls
            return self._half_open_calls < self.config.half_open_max_calls
    
    async def can_execute_async(self) -> bool:
        """Check if a request can proceed (async version)."""
        async with self._async_lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_state_change >= self.config.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                    self._half_open_calls = 0
                    self._success_count = 0
                    return True
                return False
            
            return self._half_open_calls < self.config.half_open_max_calls
    
    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self.stats.successful_calls += 1
            self.stats.total_calls += 1
            self.stats.last_success_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                self._half_open_calls = max(0, self._half_open_calls - 1)
                if self._should_close():
                    self._transition_to(CircuitState.CLOSED)
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success in closed state
                self._failure_count = 0
    
    async def record_success_async(self) -> None:
        """Record a successful call (async version)."""
        async with self._async_lock:
            self.stats.successful_calls += 1
            self.stats.total_calls += 1
            self.stats.last_success_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                self._half_open_calls = max(0, self._half_open_calls - 1)
                if self._should_close():
                    self._transition_to(CircuitState.CLOSED)
                    self._failure_count = 0
                    self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0
    
    def record_failure(self, exception: Optional[Exception] = None) -> None:
        """Record a failed call."""
        with self._lock:
            # Check if this exception type should be excluded
            if exception and self.config.excluded_exceptions:
                if isinstance(exception, self.config.excluded_exceptions):
                    return  # Don't count as failure
            
            self.stats.failed_calls += 1
            self.stats.total_calls += 1
            self.stats.last_failure_time = time.time()
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens the circuit
                self._transition_to(CircuitState.OPEN)
                self._failure_count = 1
                self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._should_open():
                    self._transition_to(CircuitState.OPEN)
    
    async def record_failure_async(self, exception: Optional[Exception] = None) -> None:
        """Record a failed call (async version)."""
        async with self._async_lock:
            if exception and self.config.excluded_exceptions:
                if isinstance(exception, self.config.excluded_exceptions):
                    return
            
            self.stats.failed_calls += 1
            self.stats.total_calls += 1
            self.stats.last_failure_time = time.time()
            self._last_failure_time = time.time()
            
            if self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
                self._failure_count = 1
                self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._should_open():
                    self._transition_to(CircuitState.OPEN)
    
    @asynccontextmanager
    async def call(self, operation: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute an operation with circuit breaker protection."""
        # Check if we can execute
        if not await self.can_execute_async():
            self.stats.rejected_calls += 1
            if self.fallback:
                logger.debug("Circuit breaker '%s' open, using fallback", self.name)
                return await self.fallback(*args, **kwargs)
            raise CircuitBreakerOpenError(f"Circuit breaker '{self.name}' is OPEN")
        
        # Track half-open calls
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
        
        try:
            if asyncio.iscoroutinefunction(operation):
                result = await operation(*args, **kwargs)
            else:
                result = operation(*args, **kwargs)
            await self.record_success_async()
            return result
        except Exception as e:
            await self.record_failure_async(e)
            raise
    
    def execute(self, operation: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute an operation with circuit breaker protection (sync)."""
        if not self.can_execute():
            self.stats.rejected_calls += 1
            if self.fallback:
                logger.debug("Circuit breaker '%s' open, using fallback", self.name)
                return self.fallback(*args, **kwargs)
            raise CircuitBreakerOpenError(f"Circuit breaker '{self.name}' is OPEN")
        
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
        
        try:
            result = operation(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "half_open_calls": self._half_open_calls,
                "total_calls": self.stats.total_calls,
                "successful_calls": self.stats.successful_calls,
                "failed_calls": self.stats.failed_calls,
                "rejected_calls": self.stats.rejected_calls,
                "last_failure_time": self.stats.last_failure_time,
                "last_success_time": self.stats.last_success_time,
                "last_state_change": self.stats.last_state_change,
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
            }
    
    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._half_open_calls = 0
            self._last_state_change = time.time()
            self.stats = CircuitBreakerStats(current_state=CircuitState.CLOSED)
            logger.info("Circuit breaker '%s' reset", self.name)


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and request is rejected."""
    pass


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()
    
    def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
        fallback: Optional[Callable] = None,
    ) -> CircuitBreaker:
        """Get existing circuit breaker or create new one."""
        with self._lock:
            if name not in self._breakers:
                self._breakers[name] = CircuitBreaker(name, config, fallback)
            return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        with self._lock:
            return self._breakers.get(name)
    
    def remove(self, name: str) -> bool:
        """Remove a circuit breaker."""
        with self._lock:
            if name in self._breakers:
                del self._breakers[name]
                return True
            return False
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get stats for all circuit breakers."""
        with self._lock:
            return {name: cb.get_stats() for name, cb in self._breakers.items()}
    
    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        with self._lock:
            for cb in self._breakers.values():
                cb.reset()


# Global registry
_global_registry: Optional[CircuitBreakerRegistry] = None


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get global circuit breaker registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = CircuitBreakerRegistry()
    return _global_registry


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
    fallback: Optional[Callable] = None,
) -> CircuitBreaker:
    """Get or create a circuit breaker."""
    return get_circuit_breaker_registry().get_or_create(name, config, fallback)