"""Unit tests for Verification Engine (Stage 5)."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.verification.verification_engine import (
    VerificationEngine, SUCCESS, PARTIAL_SUCCESS, FAILED, NEEDS_REVIEW,
)


def test_verify_layer_loaded_success():
    v = VerificationEngine()
    r = v.verify_layer_loaded("lid1", valid=True, crs_ok=True,
                              extent_ok=True, feature_or_dim_ok=True)
    assert r.state == SUCCESS
    assert r.ok
    assert all(c["passed"] for c in r.checks)


def test_verify_layer_loaded_failed():
    v = VerificationEngine()
    r = v.verify_layer_loaded("lid1", valid=False, crs_ok=True,
                              extent_ok=True, feature_or_dim_ok=True)
    assert r.state == FAILED
    assert not r.ok


def test_verify_algorithm_partial():
    v = VerificationEngine()
    r = v.verify_algorithm_executed("native:buffer", output_exists=True,
                                    output_valid=False)
    assert r.state == PARTIAL_SUCCESS


def test_verify_georeferencing_success():
    v = VerificationEngine()
    r = v.verify_georeferencing(output_raster=True, crs_match=True,
                                extent_ok=True, rmse=2.0,
                                rmse_threshold=5.0, visual_ok=True)
    assert r.state == SUCCESS


def test_verify_georeferencing_needs_review():
    v = VerificationEngine()
    r = v.verify_georeferencing(output_raster=True, crs_match=True,
                                extent_ok=True, rmse=9.0,
                                rmse_threshold=5.0, visual_ok=True)
    assert r.state == NEEDS_REVIEW


def test_verify_georeferencing_failed_no_output():
    v = VerificationEngine()
    r = v.verify_georeferencing(output_raster=False, crs_match=True,
                                extent_ok=True, rmse=None)
    assert r.state == FAILED


def test_history_and_last_result():
    v = VerificationEngine()
    v.verify_layer_loaded("a", True, True, True, True)
    assert v.last_result() is not None
    assert len(v.history()) == 1
