"""Unit tests for Stage 2 Core Foundation."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.exceptions import (
    UAGISError, ConfigurationError, VerificationError,
    SecurityError, UAGISPermissionError, NotFoundError,
    UAGISTimeoutError, ValidationError,
)
from core.event_bus import EventBus
from core.config import Config
from core.logging import get_logger


def test_exceptions_have_codes():
    err = VerificationError("boom", context={"k": "v"})
    d = err.to_dict()
    assert d["error"] == "VERIFICATION_ERROR"
    assert d["message"] == "boom"
    assert d["context"] == {"k": "v"}
    assert "VERIFICATION_ERROR" in str(err)


def test_event_bus_publish_subscribe():
    bus = EventBus()
    received = []
    bus.subscribe("topic", lambda p: received.append(p))
    bus.publish("topic", {"a": 1})
    assert received == [{"a": 1}]


def test_event_bus_unsubscribe():
    bus = EventBus()
    received = []
    cb = lambda p: received.append(p)
    bus.subscribe("topic", cb)
    bus.unsubscribe("topic", cb)
    bus.publish("topic", {"a": 1})
    assert received == []


def test_config_defaults():
    cfg = Config()
    cfg.load()
    assert cfg.get("app_name") == "Universal AI GIS Studio"
    assert cfg.get("max_background_workers") == 2
    assert cfg.get("mcp_stdio_enabled") is True


def test_config_set_get():
    cfg = Config()
    cfg.set("foo", "bar", persist=False)
    assert cfg.get("foo") == "bar"


def test_default_data_dir():
    d = Config.default_data_dir() if hasattr(Config, "default_data_dir") else None
    from core.config import default_data_dir
    assert default_data_dir().endswith("Universal AI GIS Studio")
