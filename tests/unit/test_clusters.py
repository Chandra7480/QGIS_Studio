"""Unit tests for the 25 GIS Functional Clusters (Stage 7)."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clusters.registry import CLUSTER_MODULES, get_cluster_handler


class FakeExecutor:
    def __init__(self):
        self.calls = []
        self.algorithms = {"native:buffer": True, "native:clip": True}

    def load_layer(self, path, layer_name=None, provider=None):
        self.calls.append(("load_layer", path))
        return {"id": "lid", "name": "layer", "type": "vector", "valid": True}

    def inspect_layers(self):
        return {"layers": [], "count": 0}

    def remove_layer(self, layer_id):
        return {"removed": True, "id": layer_id}

    def execute_algorithm(self, algorithm_id, parameters):
        self.calls.append(("execute_algorithm", algorithm_id))
        if algorithm_id not in self.algorithms:
            raise Exception(f"Algorithm not found: {algorithm_id}")
        return {"outputs": {"OUTPUT": "out.gpkg"}}

    def discover_algorithm(self, patterns):
        import re
        for p in patterns:
            for aid in self.algorithms:
                if p.lower() in aid.lower():
                    return aid
        return None


def test_all_cluster_ids_registered():
    expected = {f"M{i:02d}" for i in range(1, 26)}
    assert set(CLUSTER_MODULES.keys()) == expected


def test_create_handler_for_each_cluster():
    exec_ = FakeExecutor()
    for cid in CLUSTER_MODULES:
        handler = get_cluster_handler(cid, exec_)
        assert handler.CLUSTER_ID == cid
        assert handler.OPERATIONS


def test_m01_import_and_validate():
    exec_ = FakeExecutor()
    h = get_cluster_handler("M01", exec_)
    r = h.execute("import_file", {"path": "/data.shp"})
    assert r.ok is True
    assert r.verification_state == "SUCCESS"
    r = h.execute("validate_source", {"path": "/data.shp"})
    assert r.ok is False  # /data.shp does not exist on this machine


def test_m03_vector_buffer():
    exec_ = FakeExecutor()
    h = get_cluster_handler("M03", exec_)
    # Outside QGIS, no processing algorithms are discoverable -> FAILED gracefully
    r = h.execute("buffer", {"parameters": {"INPUT": "x", "DISTANCE": 10}})
    assert r.ok is False
    assert r.verification_state == "FAILED"
    assert "No processing algorithm found" in (r.error or "")


def test_m03_unknown_op():
    exec_ = FakeExecutor()
    h = get_cluster_handler("M03", exec_)
    r = h.execute("not_an_op", {})
    assert r.ok is False
    assert r.verification_state == "FAILED"


def test_m04_raster_mosaic():
    exec_ = FakeExecutor()
    h = get_cluster_handler("M04", exec_)
    # No processing algorithms available outside QGIS -> FAILED gracefully
    r = h.execute("mosaic", {"parameters": {}})
    assert r.ok is False
    assert r.verification_state == "FAILED"
    assert "No processing algorithm found" in (r.error or "")


def test_m24_no_bundled_model():
    exec_ = FakeExecutor()
    h = get_cluster_handler("M24", exec_)
    r = h.execute("external_analysis", {})
    assert r.ok is True
    assert "no bundled model" in r.result["note"]
