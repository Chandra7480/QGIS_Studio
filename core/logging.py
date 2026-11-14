"""Universal AI GIS Studio — Structured logging.

Provides a configured logger with rotating file output, console output,
and structured record enrichment. Never logs API keys or credentials.
"""

import logging
import logging.handlers
import os
import sys
from typing import Optional

from .exceptions import ConfigurationError

_LOGGER_NAME = "uagis"
_SENSITIVE_KEYS = {"api_key", "apikey", "secret", "password", "token", "credential"}


def _is_sensitive(key: str) -> bool:
    return any(s in key.lower() for s in _SENSITIVE_KEYS)


def _sanitize(value):
    if isinstance(value, dict):
        return {k: ("***" if _is_sensitive(k) else _sanitize(v)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    return value


class SensitiveFilter(logging.Filter):
    """Strip sensitive fields from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, "context") and record.context:
            record.context = _sanitize(record.context)
        if hasattr(record, "extra") and record.extra:
            record.extra = _sanitize(record.extra)
        # Ensure request_id/job_id always exist for formatters
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        if not hasattr(record, "job_id"):
            record.job_id = "-"
        return True


class SafeFormatter(logging.Formatter):
    """Formatter that always provides request_id and job_id."""

    def formatMessage(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        if not hasattr(record, "job_id"):
            record.job_id = "-"
        return super().formatMessage(record)


def setup_logging(
    log_dir: str,
    level: int = logging.INFO,
    console: bool = True,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
) -> logging.Logger:
    """Initialize the platform logger."""

    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False  # Don't propagate to QGIS root logger

    formatter = SafeFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(request_id)s %(job_id)s | %(module)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    fh = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "uagis.log"),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    fh.setFormatter(formatter)
    fh.addFilter(SensitiveFilter())
    logger.addHandler(fh)

    if console:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        sh.addFilter(SensitiveFilter())
        logger.addHandler(sh)

    return logger


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    """Return a child logger for the given module name."""
    return logging.getLogger(f"{_LOGGER_NAME}.{name}" if name != _LOGGER_NAME else name)


class LogContext:
    """Context manager to attach request_id/job_id to log records within a block."""

    def __init__(self, logger: logging.Logger, request_id: Optional[str] = None, job_id: Optional[str] = None):
        self.logger = logger
        self.request_id = request_id
        self.job_id = job_id
        self._old_factory = logging.getLogRecordFactory()

    def _factory(self, *args, **kwargs):
        record = self._old_factory(*args, **kwargs)
        record.request_id = self.request_id or "-"
        record.job_id = self.job_id or "-"
        return record

    def __enter__(self):
        logging.setLogRecordFactory(self._factory)
        return self

    def __exit__(self, exc_type, exc, tb):
        logging.setLogRecordFactory(self._old_factory)
        return False
