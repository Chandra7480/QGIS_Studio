"""Unit tests for Screen Capture Engine (Stage 5). Captures real screen."""

import sys
import os
import base64

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.screen_capture.screen_capture import ScreenCaptureEngine


def test_screen_size():
    eng = ScreenCaptureEngine()
    w, h = eng.screen_size()
    assert isinstance(w, int) and w > 0
    assert isinstance(h, int) and h > 0


def test_capture_returns_valid_png_base64():
    eng = ScreenCaptureEngine()
    result = eng.capture()
    assert result["format"] == "png"
    assert isinstance(result["width"], int) and result["width"] > 0
    assert isinstance(result["height"], int) and result["height"] > 0
    base64.b64decode(result["image_base64"])  # must decode


def test_capture_region():
    eng = ScreenCaptureEngine()
    w, h = eng.screen_size()
    region = (0, 0, min(200, w), min(200, h))
    result = eng.capture(region=region)
    assert result["region"] == region
