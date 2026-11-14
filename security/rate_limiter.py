"""Universal AI GIS Studio — Token Bucket Rate Limiter.

Per-(agent, tool) or per-(IP, tool) rate limiting with Redis backend for multi-process support.
"""

import logging
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("uagis.security.rate_limiter")


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit bucket."""
    capacity: int           # Maximum tokens in bucket
    refill_rate: float      # Tokens added per second
    key_prefix: str = "ratelimit"


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining_tokens: float
    retry_after: float | None = None  # Seconds until next token available
    capacity: int = 0
    refill_rate: float = 0.0


class RateLimiterBackend(ABC):
    """Abstract backend for token bucket storage."""

    @abstractmethod
    def get_bucket(self, key: str) -> tuple[float, float]:
        """Get (tokens, last_refill_time) for a bucket. Returns (capacity, now) if not exists."""
        pass

    @abstractmethod
    def set_bucket(self, key: str, tokens: float, last_refill: float) -> None:
        """Set bucket state."""
        pass

    @abstractmethod
    def atomic_consume(self, key: str, capacity: int, refill_rate: float, tokens_requested: int = 1) -> RateLimitResult:
        """Atomically consume tokens. Returns RateLimitResult."""
        pass


class InMemoryRateLimiterBackend(RateLimiterBackend):
    """In-memory token bucket (single process only)."""

    def __init__(self):
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.RLock()

    def get_bucket(self, key: str) -> tuple[float, float]:
        with self._lock:
            return self._buckets.get(key, (0, 0))

    def set_bucket(self, key: str, tokens: float, last_refill: float) -> None:
        with self._lock:
            self._buckets[key] = (tokens, last_refill)

    def atomic_consume(self, key: str, capacity: int, refill_rate: float, tokens_requested: int = 1) -> RateLimitResult:
        with self._lock:
            now = time.monotonic()
            tokens, last_refill = self._buckets.get(key, (float(capacity), now))

            # Refill tokens based on elapsed time
            elapsed = now - last_refill
            tokens = min(capacity, tokens + elapsed * refill_rate)

            if tokens >= tokens_requested:
                tokens -= tokens_requested
                self._buckets[key] = (tokens, now)
                return RateLimitResult(
                    allowed=True,
                    remaining_tokens=tokens,
                    capacity=capacity,
                    refill_rate=refill_rate,
                )
            else:
                # Calculate retry-after
                needed = tokens_requested - tokens
                retry_after = needed / refill_rate
                self._buckets[key] = (tokens, now)
                return RateLimitResult(
                    allowed=False,
                    remaining_tokens=tokens,
                    retry_after=retry_after,
                    capacity=capacity,
                    refill_rate=refill_rate,
                )


class RedisRateLimiterBackend(RateLimiterBackend):
    """Redis-backed token bucket for multi-process/multi-instance deployments."""

    def __init__(self, redis_url: str = "redis://localhost:6379", key_prefix: str = "uagis:ratelimit:"):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self._redis = None
        self._connect()

    def _connect(self):
        try:
            import redis
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
            self._redis.ping()
            logger.info("Connected to Redis for rate limiting: %s", self.redis_url)
        except ImportError:
            logger.warning("redis-py not installed, falling back to in-memory")
            self._redis = None
        except Exception as exc:
            logger.warning("Failed to connect to Redis: %s, falling back to in-memory", exc)
            self._redis = None

    def _key(self, key: str) -> str:
        return f"{self.key_prefix}{key}"

    def get_bucket(self, key: str) -> tuple[float, float]:
        if self._redis is None:
            return (0, 0)
        try:
            data = self._redis.hmget(self._key(key), "tokens", "last_refill")
            if data[0] is None:
                return (0, 0)
            return (float(data[0]), float(data[1]))
        except Exception as exc:
            logger.error("Redis get_bucket failed: %s", exc)
            return (0, 0)

    def set_bucket(self, key: str, tokens: float, last_refill: float) -> None:
        if self._redis is None:
            return
        try:
            self._redis.hset(self._key(key), mapping={
                "tokens": tokens,
                "last_refill": last_refill,
            })
            # Expire after 24 hours of inactivity
            self._redis.expire(self._key(key), 86400)
        except Exception as exc:
            logger.error("Redis set_bucket failed: %s", exc)

    def atomic_consume(self, key: str, capacity: int, refill_rate: float, tokens_requested: int = 1) -> RateLimitResult:
        if self._redis is None:
            # Fallback to in-memory behavior
            return InMemoryRateLimiterBackend().atomic_consume(key, capacity, refill_rate, tokens_requested)

        try:
            # Lua script for atomic token bucket consumption
            lua_script = """
            local key = KEYS[1]
            local capacity = tonumber(ARGV[1])
            local refill_rate = tonumber(ARGV[2])
            local tokens_requested = tonumber(ARGV[3])
            local now = tonumber(ARGV[4])

            local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
            local tokens = tonumber(bucket[1])
            local last_refill = tonumber(bucket[2])

            if tokens == nil then
                tokens = capacity
                last_refill = now
            end

            local elapsed = now - last_refill
            tokens = math.min(capacity, tokens + elapsed * refill_rate)

            if tokens >= tokens_requested then
                tokens = tokens - tokens_requested
                redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
                redis.call('EXPIRE', key, 86400)
                return {1, tokens, 0}
            else
                local needed = tokens_requested - tokens
                local retry_after = needed / refill_rate
                redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
                redis.call('EXPIRE', key, 86400)
                return {0, tokens, retry_after}
            end
            """

            script = self._redis.register_script(lua_script)
            now = time.monotonic()
            result = script(keys=[self._key(key)], args=[capacity, refill_rate, tokens_requested, now])

            allowed = bool(result[0])
            remaining = float(result[1])
            retry_after = float(result[2]) if result[2] > 0 else None

            return RateLimitResult(
                allowed=allowed,
                remaining_tokens=remaining,
                retry_after=retry_after,
                capacity=capacity,
                refill_rate=refill_rate,
            )
        except Exception as exc:
            logger.error("Redis atomic_consume failed: %s - denying request (fail-closed)", exc)
            # Fail closed - deny request on Redis error
            return RateLimitResult(
                allowed=False,
                remaining_tokens=0,
                retry_after=1.0,
                capacity=capacity,
                refill_rate=refill_rate,
            )


class RateLimiter:
    """Token bucket rate limiter with configurable backends."""

    def __init__(
        self,
        backend: RateLimiterBackend | None = None,
        default_config: RateLimitConfig | None = None,
        tool_configs: dict[str, RateLimitConfig] | None = None,
    ):
        self.backend = backend or InMemoryRateLimiterBackend()
        self.default_config = default_config or RateLimitConfig(capacity=100, refill_rate=10.0)
        self.tool_configs = tool_configs or {}
        self._lock = threading.RLock()

    def get_config(self, tool_id: str) -> RateLimitConfig:
        """Get rate limit config for a tool."""
        return self.tool_configs.get(tool_id, self.default_config)

    def set_tool_config(self, tool_id: str, config: RateLimitConfig) -> None:
        """Set rate limit config for a specific tool."""
        with self._lock:
            self.tool_configs[tool_id] = config

    def check_rate_limit(
        self,
        identifier: str,  # agent_id or IP
        tool_id: str,
        tokens: int = 1,
    ) -> RateLimitResult:
        """Check and consume rate limit for (identifier, tool_id)."""
        config = self.get_config(tool_id)
        key = f"{identifier}:{tool_id}"
        return self.backend.atomic_consume(key, config.capacity, config.refill_rate, tokens)

    def get_remaining(self, identifier: str, tool_id: str) -> float:
        """Get remaining tokens without consuming."""
        config = self.get_config(tool_id)
        key = f"{identifier}:{tool_id}"
        tokens, last_refill = self.backend.get_bucket(key)
        if tokens == 0 and last_refill == 0:
            return float(config.capacity)
        now = time.monotonic()
        elapsed = now - last_refill
        return min(config.capacity, tokens + elapsed * config.refill_rate)

    def reset(self, identifier: str, tool_id: str) -> None:
        """Reset rate limit for an identifier/tool pair."""
        key = f"{identifier}:{tool_id}"
        config = self.get_config(tool_id)
        self.backend.set_bucket(key, float(config.capacity), time.monotonic())


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def init_rate_limiter(
    backend: RateLimiterBackend | None = None,
    default_config: RateLimitConfig | None = None,
    tool_configs: dict[str, RateLimitConfig] | None = None,
    redis_url: str | None = None,
) -> RateLimiter:
    """Initialize global rate limiter."""
    global _rate_limiter

    if backend is None and redis_url:
        backend = RedisRateLimiterBackend(redis_url)

    _rate_limiter = RateLimiter(backend, default_config, tool_configs)
    return _rate_limiter