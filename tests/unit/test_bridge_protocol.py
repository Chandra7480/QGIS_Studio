"""Unit tests for Bridge protocol + dispatcher (mock executor, no QGIS)."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bridge.protocol import (
    Request, Response, success_response, error_response,
    VERIFICATION_SUCCESS, VERIFICATION_FAILED,
)
from bridge.dispatcher import BridgeDispatcher


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def inspect_project(self):
        return {"layer_count": 2}

    def inspect_layers(self):
        return {"layers": [], "count": 0}

    def inspect_canvas(self):
        return {"scale": 1000}

    def capture_canvas(self):
        return {"image_base64": "abc", "width": 100, "height": 100, "format": "png"}

    def load_layer(self, path, layer_name=None, provider=None):
        self.calls.append(("load_layer", path, layer_name, provider))
        return {"id": "lid", "name": "layer", "type": "vector", "valid": True}

    def remove_layer(self, layer_id):
        return {"removed": True, "id": layer_id}

    def health(self):
        return {"qgis_connected": True}

    def execute_algorithm(self, algorithm_id, parameters):
        return {"outputs": {}, "algorithm": algorithm_id}

    def algorithms_discover(self):
        return {"algorithms": [{"id": "native:buffer"}], "count": 1}

    def _is_main_thread(self):
        return True


def test_success_response_shape():
    resp = success_response("req1", {"ok": True}, VERIFICATION_SUCCESS, "job1")
    d = resp.to_dict()
    assert d["request_id"] == "req1"
    assert d["status"] == "ok"
    assert d["verification_state"] == "SUCCESS"
    assert d["job_id"] == "job1"


def test_error_response_shape():
    resp = error_response("req2", "NOT_FOUND", "nope", {"k": "v"})
    d = resp.to_dict()
    assert d["status"] == "error"
    assert d["error"]["code"] == "NOT_FOUND"
    assert d["verification_state"] == "FAILED"


def test_dispatcher_routes_to_executor():
    exec_ = FakeExecutor()
    disp = BridgeDispatcher(exec_)
    resp = disp.dispatch(Request("r1", "qgis.system.health", {}))
    assert resp.status == "ok"
    assert resp.result["qgis_connected"] is True


def test_dispatcher_project_inspect():
    exec_ = FakeExecutor()
    disp = BridgeDispatcher(exec_)
    resp = disp.dispatch(Request("r2", "qgis.project.inspect", {}))
    assert resp.result["layer_count"] == 2


def test_dispatcher_layer_load():
    exec_ = FakeExecutor()
    disp = BridgeDispatcher(exec_)
    resp = disp.dispatch(Request("r3", "qgis.layers.load", {"path": "/data.gpkg"}))
    assert resp.status == "ok"
    assert exec_.calls[0][0] == "load_layer"
    assert exec_.calls[0][1] == "/data.gpkg"


def test_dispatcher_missing_param():
    exec_ = FakeExecutor()
    disp = BridgeDispatcher(exec_)
    resp = disp.dispatch(Request("r4", "qgis.layers.load", {}))
    assert resp.status == "error"
    assert resp.error["code"] == "EXECUTION_ERROR"


def test_dispatcher_unknown_tool():
    exec_ = FakeExecutor()
    disp = BridgeDispatcher(exec_)
    resp = disp.dispatch(Request("r5", "qgis.fake.tool", {}))
    assert resp.status == "error"
    assert resp.error["code"] == "TOOL_NOT_FOUND"
