"""Unit tests for Georeferencing Engine (Stage 6). Uses synthetic data."""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.georeferencing.georeferencing_engine import (
    GeoreferencingEngine, GCP,
)
from engines.verification.verification_engine import (
    VerificationEngine, SUCCESS, FAILED, NEEDS_REVIEW,
)


def test_gcp_to_dict():
    g = GCP(10.0, 20.0, 100.0, 200.0, "EPSG:4326", 0.8, "road junction",
            "ref_raster", "pending")
    d = g.to_dict()
    assert d["source_pixel_x"] == 10.0
    assert d["dest_map_x"] == 100.0
    assert d["crs"] == "EPSG:4326"
    assert d["validation_status"] == "pending"


def test_apply_geotransform():
    eng = GeoreferencingEngine()
    # GDAL geotransform: originX=0, pxW=1, no rot, originY=10, no rot, pxH=-1
    gt = [0.0, 1.0, 0.0, 10.0, 0.0, -1.0]
    mx, my = eng._apply_geotransform(gt, 3.0, 4.0)
    assert mx == 3.0
    assert my == 6.0  # 10 + 4*(-1)


def test_match_pixels_to_reference():
    eng = GeoreferencingEngine()
    gt = [0.0, 1.0, 0.0, 10.0, 0.0, -1.0]
    res = eng.match_pixels_to_reference([(3.0, 4.0), (0.0, 0.0)], gt)
    assert len(res) == 2
    assert res[0]["dest_map_x"] == 3.0
    assert res[1]["dest_map_y"] == 10.0


def test_generate_gcps_never_invents(monkeypatch):
    eng = GeoreferencingEngine()
    # Detection returns no landmarks -> no GCPs (nothing invented)
    monkeypatch.setattr(eng, "detect_landmarks",
                        lambda *a, **k: {"landmarks": []})
    gt = [0.0, 1.0, 0.0, 10.0, 0.0, -1.0]
    gcps = eng.generate_gcps("fake.png", gt, "EPSG:4326")
    assert gcps == []


def test_validate_gcps_duplicates_and_min():
    eng = GeoreferencingEngine()
    gcps = [
        GCP(10.0, 10.0, 100.0, 100.0, "EPSG:4326", 0.9, "a", "ref", "pending"),
        GCP(10.0, 10.0, 200.0, 200.0, "EPSG:4326", 0.9, "b", "ref", "pending"),  # duplicate pixel
        GCP(100.0, 100.0, 300.0, 300.0, "EPSG:4326", 0.9, "c", "ref", "pending"),
    ]
    rep = eng.validate_gcps(gcps, min_points=3)
    assert rep["total"] == 3
    assert rep["accepted"] == 2  # one duplicate rejected
    assert rep["min_points_met"] is False  # only 2 accepted < 3


def test_validate_gcps_low_confidence():
    eng = GeoreferencingEngine()
    gcps = [
        GCP(10.0, 10.0, 100.0, 100.0, "EPSG:4326", 0.1, "low", "ref", "pending"),
        GCP(100.0, 100.0, 300.0, 300.0, "EPSG:4326", 0.9, "c", "ref", "pending"),
    ]
    rep = eng.validate_gcps(gcps, min_points=1)
    assert rep["accepted"] == 1
    assert rep["rejected"] == 1


def test_transform_needs_min_gcps():
    eng = GeoreferencingEngine()
    gcps = [GCP(10.0, 10.0, 100.0, 100.0, "EPSG:4326", 0.9, "a", "ref", "accepted")]
    try:
        eng.transform_with_qgis("in.png", "out.tif", gcps)
        assert False, "should have raised"
    except Exception as e:
        assert "at least 2 accepted GCPs" in str(e)


def test_verify_georeferencing_states():
    eng = GeoreferencingEngine()
    r = eng.verify_georeferencing(True, True, True, 2.0, 5.0, True)
    assert r.state == SUCCESS
    r = eng.verify_georeferencing(True, True, True, 9.0, 5.0, True)
    assert r.state == NEEDS_REVIEW
    r = eng.verify_georeferencing(False, True, True, None)
    assert r.state == FAILED
