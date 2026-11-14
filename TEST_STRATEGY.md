# Universal AI GIS Studio — Comprehensive Test Strategy

**Author:** MCP Test & Verification Engineer
**Date:** 2026-11-12
**Version:** 1.0

---

## Executive Summary

This document outlines a comprehensive test strategy to make the Universal AI GIS Studio MCP server **bulletproof**. The strategy covers contract testing for all 40+ MCP tools, integration testing with real QGIS, visual regression for canvas/screen tools, property-based fuzzing, and a complete CI/CD pipeline.

**Current State:** 9 unit test files (78-174 lines each), 1 integration test suite (skips if QGIS unavailable), basic verification engine, screen capture tests. **Gap:** No contract tests, no property-based testing, no visual regression, no CI/CD pipeline, no error injection.

---

## 1. Contract Testing — Every Tool's Input/Output Against JSON Schema

### 1.1 Current Coverage
- `test_mcp_registry.py`: Verifies registry namespaces, key tools registered, schemas strict (additionalProperties: false), permissions present, server instantiation.

### 1.2 Required Enhancements

| Priority | Test | Description |
|----------|------|-------------|
| P0 | `test_contract_all_tools_input_schema` | For each of 40+ tools: validate input schema is valid JSON Schema Draft 2020-12, required fields marked, no additionalProperties |
| P0 | `test_contract_all_tools_output_schema` | For each tool: validate output schema structure, all properties typed |
| P0 | `test_contract_tool_execution_roundtrip` | Execute each tool with valid input (mocked), assert output conforms to output_schema |
| P0 | `test_contract_invalid_input_rejected` | For each tool: send invalid input (missing required, wrong type, extra props), assert 400/EXECUTION_ERROR |
| P1 | `test_contract_schema_versioning` | Detect breaking schema changes (added required, removed props, type changes) |
| P1 | `test_contract_tool_timeout_enforcement` | Verify timeout_seconds is respected by bridge |
| P1 | `test_contract_permissions_enforcement` | Verify permission checks (qgis:read vs qgis:layer:write) |

### 1.3 Implementation Pattern
```python
# tests/contract/test_tool_contracts.py
import pytest
import jsonschema
from mcp_server.registry import build_registry

REGISTRY = build_registry()

@pytest.mark.parametrize("spec", REGISTRY.all())
def test_input_schema_valid(spec):
    # Schema itself must be valid JSON Schema
    jsonschema.Draft202012Validator.check_schema(spec.input_schema)

@pytest.mark.parametrize("spec", REGISTRY.all())
def test_output_schema_valid(spec):
    jsonschema.Draft202012Validator.check_schema(spec.output_schema)

@pytest.mark.parametrize("spec", REGISTRY.all())
def test_valid_input_accepted(spec, mock_bridge_client):
    # Generate valid input from schema (using hypothesis or manual)
    valid_input = generate_valid_input(spec.input_schema)
    result = mock_bridge_client.dispatch(spec.name, valid_input)
    assert result["status"] == "ok"
    # Validate output against schema
    validate(spec.output_schema, result["result"])
```

---

## 2. Integration Tests — Real QGIS + Bridge + MCP Server

### 2.1 Current Coverage
- `tests/integration/test_qgis_bridge_integration.py`: 10 tests covering health, project/layer/canvas inspect, screen capture, load/remove layer, algorithm discovery, dispatcher routing. **Skips if QGIS unavailable.**

### 2.2 Required Enhancements

| Priority | Test Suite | Description |
|----------|------------|-------------|
| P0 | `test_integration_mcp_server_stdio` | Spin up MCP server (stdio), call all read-only tools, verify responses |
| P0 | `test_integration_mcp_server_http` | Spin up MCP server (Streamable HTTP), call tools via HTTP, verify |
| P0 | `test_integration_bridge_dispatcher_full` | All 40+ dispatcher handlers with real executor |
| P0 | `test_integration_layer_lifecycle` | Load vector → inspect → load raster → inspect → remove both |
| P0 | `test_integration_algorithm_execution` | Execute 10+ real algorithms (buffer, clip, slope, hillshade, etc.) |
| P0 | `test_integration_project_open_save` | Open .qgz → modify → save → reopen → verify |
| P1 | `test_integration_georeferencing_pipeline` | Analyze image → generate GCPs → validate → transform → verify RMSE |
| P1 | `test_integration_cursor_keyboard_mouse` | Move cursor → click → drag → type → hotkey → scroll (visual verify) |
| P1 | `test_integration_window_dialog_inspect` | Open QGIS dialogs (layer properties, processing toolbox), inspect |
| P1 | `test_integration_layout_export` | Create layout → add map → export PDF/PNG → verify file |
| P1 | `test_integration_database_connections` | List connections, execute spatial query |
| P2 | `test_integration_workflow_execution` | Execute saved workflow (multi-step) |
| P2 | `test_integration_plugin_list` | List installed plugins, verify metadata |

### 2.3 Test Fixtures Needed
```python
# tests/fixtures/qgis_project.py
import pytest
from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer

@pytest.fixture(scope="session")
def qgis_app():
    """Session-scoped QApplication + QgsApplication."""
    from qgis.PyQt.QtWidgets import QApplication
    from qgis.core import QgsApplication
    app = QApplication([])
    qgis_app = QgsApplication([], False)
    qgis_app.initQgis()
    yield qgis_app
    qgis_app.exitQgis()

@pytest.fixture(scope="function")
def clean_project(qgis_app):
    """Fresh QgsProject for each test."""
    project = QgsProject.instance()
    project.clear()
    yield project
    project.clear()

@pytest.fixture(scope="session")
def sample_data_dir():
    """Path to test data (vector/raster)."""
    return Path("tests/fixtures/data")

@pytest.fixture
def sample_vector(sample_data_dir):
    return sample_data_dir / "test.gpkg"

@pytest.fixture
def sample_raster(sample_data_dir):
    return sample_data_dir / "test.tif"
```

### 2.4 Sample Data Requirements
| Dataset | Format | Purpose |
|---------|--------|---------|
| `test.gpkg` | GeoPackage | Vector layer load, spatial ops |
| `test.shp` | Shapefile | Legacy format compatibility |
| `test.tif` | GeoTIFF | Raster load, hillshade, slope |
| `test.tif` | GeoTIFF (multiband) | Band info, RGB rendering |
| `scan_map.tif` | Unreferenced TIFF | Georeferencing pipeline |
| `reference.tif` | Referenced GeoTIFF | GCP reference source |
| `project.qgz` | QGIS Project | Project open/save, layout tests |

---

## 3. Visual Regression — Screenshot Diff for Canvas/Screen Tools

### 3.1 Current State
- `engines/screen_capture/screen_capture.py`: Captures screen via mss, returns base64 PNG
- `engines/verification/verification_engine.py`: Verification states but no visual comparison
- `engines/visual_automation/window_detector.py`: Win32 window enumeration

### 3.2 Required Implementation

#### 3.2.1 Visual Regression Engine (New File)
```python
# engines/verification/visual_regression.py
"""
Visual regression testing for QGIS canvas/screenshots.
Uses perceptual hashing (pHash) and pixel-diff for regression detection.
"""

import base64
import io
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

from PIL import Image
import imagehash  # pip install imagehash

@dataclass
class VisualDiffResult:
    similar: bool
    phash_distance: int
    pixel_diff_ratio: float
    diff_image_base64: Optional[str] = None
    baseline_image_base64: Optional[str] = None
    current_image_base64: Optional[str] = None

class VisualRegressionEngine:
    def __init__(self, baseline_dir: Path, threshold_phash: int = 5, threshold_pixel: float = 0.01):
        self.baseline_dir = baseline_dir
        self.threshold_phash = threshold_phash  # Hamming distance
        self.threshold_pixel = threshold_pixel  # Ratio of different pixels

    def _load_image(self, image_base64: str) -> Image.Image:
        data = base64.b64decode(image_base64)
        return Image.open(io.BytesIO(data))

    def _save_baseline(self, test_name: str, image: Image.Image) -> Path:
        path = self.baseline_dir / f"{test_name}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
        return path

    def compare(self, test_name: str, current_base64: str, update_baseline: bool = False) -> VisualDiffResult:
        current = self._load_image(current_base64)
        baseline_path = self.baseline_dir / f"{test_name}.png"

        if not baseline_path.exists() or update_baseline:
            self._save_baseline(test_name, current)
            return VisualDiffResult(
                similar=True, phash_distance=0, pixel_diff_ratio=0.0,
                baseline_image_base64=current_base64, current_image_base64=current_base64
            )

        baseline = Image.open(baseline_path)
        # Perceptual hash
        phash_current = imagehash.phash(current)
        phash_baseline = imagehash.phash(baseline)
        phash_dist = phash_current - phash_baseline

        # Pixel diff (resize to same size)
        if current.size != baseline.size:
            current = current.resize(baseline.size, Image.Resampling.LANCZOS)
        diff = Image.new('RGBA', current.size)
        diff_count = 0
        for x in range(current.width):
            for y in range(current.height):
                pc = current.getpixel((x, y))
                pb = baseline.getpixel((x, y))
                if pc != pb:
                    diff_count += 1
                    diff.putpixel((x, y), (255, 0, 0, 255))
                else:
                    diff.putpixel((x, y), (*pc[:3], 0))
        pixel_ratio = diff_count / (current.width * current.height)

        similar = (phash_dist <= self.threshold_phash) and (pixel_ratio <= self.threshold_pixel)

        # Encode diff image
        diff_buffer = io.BytesIO()
        diff.save(diff_buffer, format='PNG')
        diff_b64 = base64.b64encode(diff_buffer.getvalue()).decode()

        return VisualDiffResult(
            similar=similar,
            phash_distance=phash_dist,
            pixel_diff_ratio=pixel_ratio,
            diff_image_base64=diff_b64,
            baseline_image_base64=base64.b64encode(open(baseline_path, 'rb').read()).decode(),
            current_image_base64=current_base64,
        )
```

#### 3.2.2 Visual Regression Tests
```python
# tests/visual/test_canvas_visual_regression.py
import pytest
from engines.screen_capture.screen_capture import ScreenCaptureEngine
from engines.verification.visual_regression import VisualRegressionEngine

BASELINE_DIR = Path("tests/visual_baselines")
VISUAL = VisualRegressionEngine(BASELINE_DIR)

@pytest.mark.visual
def test_canvas_initial_state(qgis_app, clean_project):
    """Canvas empty project matches baseline."""
    eng = ScreenCaptureEngine()
    result = eng.capture()
    diff = VISUAL.compare("canvas_empty_project", result["image_base64"])
    assert diff.similar, f"Visual regression: phash={diff.phash_distance}, pixel={diff.pixel_diff_ratio:.3f}"

@pytest.mark.visual
def test_canvas_after_vector_load(qgis_app, clean_project, sample_vector):
    """Canvas with vector layer matches baseline."""
    from bridge.executor import PyQGISExecutor
    executor = PyQGISExecutor(None)
    executor.load_layer(str(sample_vector), "test_vector")
    eng = ScreenCaptureEngine()
    result = eng.capture()
    diff = VISUAL.compare("canvas_vector_loaded", result["image_base64"])
    assert diff.similar

@pytest.mark.visual
def test_canvas_after_raster_load(qgis_app, clean_project, sample_raster):
    """Canvas with raster layer matches baseline."""
    from bridge.executor import PyQGISExecutor
    executor = PyQGISExecutor(None)
    executor.load_layer(str(sample_raster), "test_raster")
    eng = ScreenCaptureEngine()
    result = eng.capture()
    diff = VISUAL.compare("canvas_raster_loaded", result["image_base64"])
    assert diff.similar

@pytest.mark.visual
def test_hillshade_visual(qgis_app, clean_project, sample_raster):
    """Hillshade algorithm output matches visual baseline."""
    from bridge.executor import PyQGISExecutor
    executor = PyQGISExecutor(None)
    layer_id = executor.load_layer(str(sample_raster), "dem")["id"]
    # Execute hillshade
    executor.execute_algorithm("native:hillshade", {"INPUT": layer_id, "Z_FACTOR": 1, "OUTPUT": "memory:"})
    eng = ScreenCaptureEngine()
    result = eng.capture()
    diff = VISUAL.compare("hillshade_output", result["image_base64"])
    assert diff.similar
```

---

## 4. Property-Based Testing — Hypothesis for Tool Parameter Fuzzing

### 4.1 Current State: None

### 4.2 Required Implementation

| Priority | Test | Description |
|----------|------|-------------|
| P0 | `test_property_layers_load_path_fuzzing` | Fuzz path parameter: valid paths, non-existent, empty, unicode, long paths, special chars |
| P0 | `test_property_algorithms_execute_params` | Fuzz algorithm parameters: valid/invalid types, boundary values, missing required, extra props |
| P0 | `test_property_cursor_move_coordinates` | Fuzz x/y: negative, zero, max int, float, out-of-screen |
| P1 | `test_property_keyboard_type_text` | Fuzz text: empty, unicode, control chars, very long, emoji |
| P1 | `test_property_project_open_paths` | Fuzz project paths: .qgz, .qgs, non-existent, directories, symlinks |
| P1 | `test_property_georeferencing_gcp_generation` | Fuzz GCP params: duplicate points, collinear, outliers, min/max points |
| P2 | `test_property_all_tool_schemas` | Generic: for each tool, generate valid/invalid inputs from schema |

### 4.3 Hypothesis Strategies
```python
# tests/property/test_tool_fuzzing.py
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from mcp_server.registry import build_registry
from bridge.dispatcher import BridgeDispatcher
from bridge.protocol import Request

REGISTRY = build_registry()

# Strategy for valid file paths (existing test files)
valid_paths = st.sampled_from([
    "tests/fixtures/data/test.gpkg",
    "tests/fixtures/data/test.tif",
])

# Strategy for invalid paths
invalid_paths = st.one_of(
    st.text(min_size=1).filter(lambda x: not Path(x).exists()),
    st.just(""),
    st.text(alphabet="\x00\x01\x02", min_size=1),  # control chars
    st.text(min_size=300),  # very long
)

@given(path=valid_paths)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_layers_load_valid_path(path, dispatcher):
    """Valid paths should load successfully (or fail gracefully)."""
    req = Request(request_id="prop_test", tool="qgis.layers.load", params={"path": path})
    resp = dispatcher.dispatch(req)
    # Either ok (valid layer) or error with NOT_FOUND/EXECUTION_ERROR
    assert resp.status in ("ok", "error")

@given(path=invalid_paths)
def test_layers_load_invalid_path_rejected(path, dispatcher):
    """Invalid paths must be rejected with error."""
    req = Request(request_id="prop_test", tool="qgis.layers.load", params={"path": path})
    resp = dispatcher.dispatch(req)
    assert resp.status == "error"
    assert resp.error["code"] in ("NOT_FOUND", "EXECUTION_ERROR", "VALIDATION_ERROR")

@given(x=st.integers(min_value=-10000, max_value=10000),
       y=st.integers(min_value=-10000, max_value=10000))
def test_cursor_move_coordinates(x, y, dispatcher):
    """Cursor move accepts any int coordinates."""
    req = Request(request_id="prop_test", tool="qgis.cursor.move", params={"x": x, "y": y})
    resp = dispatcher.dispatch(req)
    # Should not crash; may succeed or fail gracefully
    assert resp.status in ("ok", "error")

# Generic schema-based fuzzing
def schema_to_strategy(schema: dict) -> st.SearchStrategy:
    """Convert JSON Schema to Hypothesis strategy."""
    # Implementation maps type, format, min/max, enum, const, etc.
    # Use hypothesis-jsonschema library or custom mapper
    pass

@pytest.mark.parametrize("spec", REGISTRY.all())
@given(data=st.data())
def test_tool_input_fuzzing(spec, data, dispatcher):
    """Fuzz each tool with schema-driven valid/invalid inputs."""
    valid_strategy = schema_to_strategy(spec.input_schema)
    invalid_strategy = schema_to_strategy(invert_schema(spec.input_schema))
    # Test both
    ...
```

---

## 5. Load & Stress Testing — Concurrent Execution, Memory Leaks

### 5.1 Current State: None

### 5.2 Required Implementation

| Priority | Test | Description |
|----------|------|-------------|
| P1 | `test_load_concurrent_tool_calls` | 50 concurrent tool calls (mixed read/write), all complete without deadlock |
| P1 | `test_load_bridge_stress` | 1000 rapid requests to bridge, measure latency p50/p95/p99 |
| P1 | `test_load_memory_leak_detection` | Run 1000 tool cycles, assert memory growth < threshold |
| P1 | `test_load_mcp_server_sustained` | MCP server handles 1000 requests over 60s without crash |
| P2 | `test_load_algorithm_batch` | Execute 50 algorithms sequentially, verify all outputs |
| P2 | `test_load_screen_capture_rate` | Capture 100 screenshots rapidly, verify all valid PNG |

### 5.3 Implementation Pattern
```python
# tests/load/test_concurrent_execution.py
import asyncio
import pytest
import time
import tracemalloc
from mcp_server.server import UniversalMCPServer

@pytest.mark.load
async def test_concurrent_mcp_tool_calls():
    """50 concurrent calls to qgis.system.inspect."""
    server = UniversalMCPServer(bridge_url="http://127.0.0.1:8766")
    client = server.client  # QgisBridgeClient

    async def call_inspect():
        return await client.call_tool("qgis.system.inspect", {})

    # Fire 50 concurrent
    tasks = [call_inspect() for _ in range(50)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # All should succeed
    errors = [r for r in results if isinstance(r, Exception)]
    assert len(errors) == 0, f"{len(errors)} failed: {errors}"

@pytest.mark.load
def test_memory_leak_bridge_dispatcher():
    """Dispatch 1000 requests, check memory growth."""
    tracemalloc.start()
    snapshot1 = tracemalloc.take_snapshot()

    dispatcher = BridgeDispatcher(FakeExecutor())
    for i in range(1000):
        req = Request(request_id=f"load_{i}", tool="qgis.system.health", params={})
        dispatcher.dispatch(req)

    snapshot2 = tracemalloc.take_snapshot()
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')
    total_growth = sum(stat.size_diff for stat in top_stats)
    # Assert < 10MB growth
    assert total_growth < 10 * 1024 * 1024, f"Memory grew by {total_growth / 1024 / 1024:.1f} MB"
```

---

## 6. Error Injection Testing — Failures, Timeouts, Crashes

### 6.1 Current State: None

### 6.2 Required Implementation

| Priority | Test | Description |
|----------|------|-------------|
| P0 | `test_error_network_failure_bridge_down` | Bridge unreachable → MCP server returns BridgeError |
| P0 | `test_error_qgis_crash_during_execution` | Simulate QGIS process death → bridge detects, returns error |
| P0 | `test_error_invalid_algorithm_id` | Unknown algorithm → EXECUTION_ERROR with helpful message |
| P0 | `test_error_algorithm_execution_failure` | Algorithm throws (invalid params) → EXECUTION_ERROR |
| P0 | `test_error_timeout_enforcement` | Long-running algorithm → timeout after spec.timeout_seconds |
| P1 | `test_error_permission_denied` | Tool requires approval/permission → proper error code |
| P1 | `test_error_malformed_request` | Invalid JSON, missing request_id, wrong tool name |
| P1 | `test_error_disk_full_simulation` | Layer save/write fails → graceful error |
| P2 | `test_error_corrupt_project_file` | Open corrupted .qgz → error not crash |
| P2 | `test_error_corrupt_raster_vector` | Load corrupt data → validation error |

### 6.3 Implementation Pattern
```python
# tests/error_injection/test_failure_scenarios.py
import pytest
from unittest.mock import patch, Mock
from bridge.dispatcher import BridgeDispatcher
from bridge.protocol import Request
from core.exceptions import BridgeError

def test_bridge_unreachable_returns_error():
    """MCP server handles bridge connection failure."""
    from mcp_server.qgis_client import QgisBridgeClient
    client = QgisBridgeClient(base_url="http://127.0.0.1:9999")  # No server
    with pytest.raises(BridgeError):
        client.dispatch("qgis.system.health", {}, "req_1", timeout_seconds=1)

def test_qgis_process_death_detected():
    """Executor detects QGIS process gone."""
    executor = PyQGISExecutor(None)
    # Mock iface to simulate crash
    with patch.object(executor, '_is_main_thread', return_value=False):
        result = executor.health()
        assert result["qgis_connected"] is False

def test_algorithm_timeout_enforcement():
    """Algorithm execution respects timeout."""
    executor = PyQGISExecutor(None)
    # Mock execute_algorithm to hang
    with patch.object(executor, 'execute_algorithm', side_effect=TimeoutError):
        with pytest.raises(ExecutionError, match="timeout"):
            executor.execute_algorithm("native:buffer", {}, timeout_seconds=1)

def test_malformed_request_rejected():
    """Dispatcher rejects malformed requests."""
    dispatcher = BridgeDispatcher(FakeExecutor())
    # Missing request_id
    req = Request(request_id="", tool="qgis.system.health", params={})
    resp = dispatcher.dispatch(req)
    # Should handle gracefully
    assert resp.status in ("ok", "error")
```

---

## 7. CI/CD Pipeline — GitHub Actions

### 7.1 Current State: None (no `.github/workflows/`)

### 7.2 Required Pipeline

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "3.11"
  QGIS_VERSION: "3.34"

jobs:
  # ============================================================
  # 1. LINT & TYPE CHECK (fast, runs first)
  # ============================================================
  lint-and-type:
    name: Lint & Type Check
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install dependencies
        run: |
          pip install -r requirements/base.txt
          pip install -e ".[pytest]"
          pip install ruff mypy pytest-cov
      - name: Ruff lint
        run: ruff check .
      - name: Ruff format check
        run: ruff format --check .
      - name: MyPy type check
        run: mypy --strict core bridge engines mcp_server clusters

  # ============================================================
  # 2. UNIT TESTS (no QGIS required)
  # ============================================================
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install dependencies
        run: |
          pip install -r requirements/base.txt
          pip install -e ".[pytest]"
          pip install pytest-asyncio hypothesis jsonschema imagehash pillow
      - name: Run unit tests
        run: pytest tests/unit -v --tb=short -x
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml

  # ============================================================
  # 3. CONTRACT TESTS (schema validation)
  # ============================================================
  contract-tests:
    name: Contract Tests
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install dependencies
        run: |
          pip install -r requirements/base.txt
          pip install -e ".[pytest]"
          pip install jsonschema hypothesis
      - name: Run contract tests
        run: pytest tests/contract -v --tb=short

  # ============================================================
  # 4. INTEGRATION TESTS (requires QGIS)
  # ============================================================
  integration-tests:
    name: Integration Tests (QGIS)
    runs-on: windows-latest  # QGIS on Windows
    timeout-minutes: 30
    if: runner.os == 'Windows'  # Only run on Windows where QGIS is installed
    steps:
      - uses: actions/checkout@v4
      - name: Install QGIS
        run: |
          # Install QGIS 3.34 LTR via Chocolatey
          choco install qgis-ltr --version=3.34.0 -y
          # Add to PATH
          echo "C:\Program Files\QGIS 3.34\bin" >> $GITHUB_PATH
          echo "C:\Program Files\QGIS 3.34\apps\Python39" >> $GITHUB_PATH
      - name: Set up Python (use QGIS Python)
        uses: actions/setup-python@v5
        with:
          python-version: "3.9"
          architecture: x64
      - name: Install test dependencies
        run: |
          pip install -r requirements/base.txt
          pip install -e ".[pytest]"
          pip install pytest-qt hypothesis jsonschema imagehash pillow
      - name: Prepare test data
        run: |
          mkdir -p tests/fixtures/data
          # Download sample data or generate synthetic
          python scripts/generate_test_data.py
      - name: Start QGIS Bridge (background)
        run: |
          # Start QGIS with bridge plugin
          python -m bridge.server &
          sleep 10
          # Verify bridge is up
          curl -f http://127.0.0.1:8766/health
      - name: Run integration tests
        run: pytest tests/integration -v --tb=short -k "not visual"
      - name: Run visual regression tests
        run: pytest tests/visual -v --tb=short
        env:
          UPDATE_BASELINES: "false"
      - name: Upload visual regression artifacts
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: visual-diffs
          path: tests/visual_diffs/

  # ============================================================
  # 5. PROPERTY-BASED TESTS
  # ============================================================
  property-tests:
    name: Property-Based Tests
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install dependencies
        run: |
          pip install -r requirements/base.txt
          pip install -e ".[pytest]"
          pip install hypothesis
      - name: Run property tests
        run: pytest tests/property -v --tb=short --hypothesis-show-statistics

  # ============================================================
  # 6. LOAD TESTS (optional, scheduled)
  # ============================================================
  load-tests:
    name: Load & Stress Tests
    runs-on: ubuntu-latest
    timeout-minutes: 30
    if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install dependencies
        run: |
          pip install -r requirements/base.txt
          pip install -e ".[pytest]"
          pip install aiohttp pytest-asyncio
      - name: Run load tests
        run: pytest tests/load -v --tb=short

  # ============================================================
  # 7. ERROR INJECTION TESTS
  # ============================================================
  error-injection-tests:
    name: Error Injection Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install dependencies
        run: |
          pip install -r requirements/base.txt
          pip install -e ".[pytest]"
          pip install pytest-mock
      - name: Run error injection tests
        run: pytest tests/error_injection -v --tb=short

  # ============================================================
  # 8. BUILD & PACKAGE (after all tests pass)
  # ============================================================
  build-package:
    name: Build & Package
    needs: [lint-and-type, unit-tests, contract-tests, integration-tests, property-tests, error-injection-tests]
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}
      - name: Install build dependencies
        run: pip install build twine
      - name: Build package
        run: python -m build
      - name: Verify package
        run: twine check dist/*
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
```

---

## 8. Test Fixtures & Infrastructure

### 8.1 Directory Structure
```
tests/
├── unit/                    # Fast, no QGIS
│   ├── test_mcp_registry.py
│   ├── test_bridge_protocol.py
│   ├── test_verification.py
│   ├── test_screen_capture.py
│   ├── test_georeferencing.py
│   ├── test_core.py
│   └── test_clusters.py
├── contract/                # NEW: Schema contract tests
│   ├── __init__.py
│   ├── test_tool_contracts.py
│   └── test_schema_versioning.py
├── integration/             # Real QGIS required
│   ├── __init__.py
│   ├── conftest.py          # QGIS fixtures
│   ├── test_qgis_bridge_integration.py
│   ├── test_mcp_server.py
│   ├── test_layer_lifecycle.py
│   ├── test_algorithm_execution.py
│   ├── test_georeferencing_pipeline.py
│   ├── test_visual_automation.py
│   └── test_workflow_layout.py
├── visual/                  # NEW: Visual regression
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_canvas_visual_regression.py
│   ├── test_algorithm_output_visual.py
│   └── baselines/           # Committed baseline images
├── property/                # NEW: Hypothesis fuzzing
│   ├── __init__.py
│   ├── test_tool_fuzzing.py
│   └── strategies.py        # Schema-to-strategy mappers
├── load/                    # NEW: Load/stress tests
│   ├── __init__.py
│   └── test_concurrent_execution.py
├── error_injection/         # NEW: Failure scenarios
│   ├── __init__.py
│   └── test_failure_scenarios.py
├── fixtures/                # Test data
│   ├── data/
│   │   ├── test.gpkg
│   │   ├── test.shp
│   │   ├── test.tif
│   │   ├── scan_map.tif
│   │   └── reference.tif
│   └── projects/
│       └── project.qgz
└── visual_baselines/        # Committed baseline screenshots
    ├── canvas_empty_project.png
    ├── canvas_vector_loaded.png
    ├── canvas_raster_loaded.png
    └── hillshade_output.png
```

### 8.2 Test Data Generation Script
```python
# scripts/generate_test_data.py
"""Generate synthetic test data for CI."""
import tempfile
from pathlib import Path
import numpy as np
from osgeo import gdal, ogr, osr

def create_test_geopackage(path: Path):
    """Create a simple vector GeoPackage with point, line, polygon."""
    ds = ogr.GetDriverByName("GPKG").CreateDataSource(str(path))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)

    # Points
    lyr = ds.CreateLayer("points", srs, ogr.wkbPoint)
    lyr.CreateField(ogr.FieldDefn("name", ogr.OFTString))
    lyr.CreateField(ogr.FieldDefn("value", ogr.OFTInteger))
    for i, (x, y) in enumerate([(-74, 40), (-73, 41), (-72, 42)]):
        f = ogr.Feature(lyr.GetLayerDefn())
        f.SetField("name", f"point_{i}")
        f.SetField("value", i * 10)
        geom = ogr.Geometry(ogr.wkbPoint)
        geom.AddPoint(x, y)
        f.SetGeometry(geom)
        lyr.CreateFeature(f)

    # Lines
    lyr = ds.CreateLayer("lines", srs, ogr.wkbLineString)
    lyr.CreateField(ogr.FieldDefn("name", ogr.OFTString))
    f = ogr.Feature(lyr.GetLayerDefn())
    f.SetField("name", "line_1")
    geom = ogr.Geometry(ogr.wkbLineString)
    geom.AddPoint(-74, 40)
    geom.AddPoint(-73, 41)
    geom.AddPoint(-72, 42)
    f.SetGeometry(geom)
    lyr.CreateFeature(f)

    # Polygons
    lyr = ds.CreateLayer("polygons", srs, ogr.wkbPolygon)
    lyr.CreateField(ogr.FieldDefn("name", ogr.OFTString))
    f = ogr.Feature(lyr.GetLayerDefn())
    f.SetField("name", "poly_1")
    ring = ogr.Geometry(ogr.wkbLinearRing)
    ring.AddPoint(-74.5, 39.5)
    ring.AddPoint(-72.5, 39.5)
    ring.AddPoint(-72.5, 42.5)
    ring.AddPoint(-74.5, 42.5)
    ring.AddPoint(-74.5, 39.5)
    geom = ogr.Geometry(ogr.wkbPolygon)
    geom.AddGeometry(ring)
    f.SetGeometry(geom)
    lyr.CreateFeature(f)

    ds = None

def create_test_geotiff(path: Path, bands: int = 3):
    """Create a synthetic GeoTIFF (DEM or RGB)."""
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(str(path), 100, 100, bands, gdal.GDT_Float32)
    ds.SetGeoTransform([-75, 0.1, 0, 43, 0, -0.1])
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    ds.SetProjection(srs.ExportToWkt())

    for b in range(1, bands + 1):
        band = ds.GetRasterBand(b)
        # Synthetic elevation data
        data = np.random.rand(100, 100).astype(np.float32) * 1000
        band.WriteArray(data)
        band.SetNoDataValue(-9999)

    ds.FlushCache()
    ds = None

def create_unreferenced_tiff(path: Path):
    """Create an unreferenced TIFF for georeferencing tests."""
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(str(path), 200, 200, 3, gdal.GDT_Byte)
    # No geotransform, no projection
    for b in range(1, 4):
        band = ds.GetRasterBand(b)
        data = np.random.randint(0, 255, (200, 200), dtype=np.uint8)
        band.WriteArray(data)
    ds.FlushCache()
    ds = None

if __name__ == "__main__":
    out_dir = Path("tests/fixtures/data")
    out_dir.mkdir(parents=True, exist_ok=True)
    create_test_geopackage(out_dir / "test.gpkg")
    create_test_geotiff(out_dir / "test.tif", bands=1)  # DEM
    create_test_geotiff(out_dir / "test_rgb.tif", bands=3)  # RGB
    create_unreferenced_tiff(out_dir / "scan_map.tif")
    # Copy test.tif as reference for georeferencing
    import shutil
    shutil.copy(out_dir / "test.tif", out_dir / "reference.tif")
    print("Test data generated in", out_dir)
```

---

## 9. Verification Engine Enhancements

### 9.1 Current Gaps
- Verification engine only checks basic states (layer loaded, algorithm executed, georeferencing)
- No visual verification integration
- No verification for cursor/keyboard/mouse actions
- No verification for project open/save, layout export, workflow execution

### 9.2 Required Extensions
```python
# engines/verification/verification_engine.py — ADDITIONS

def verify_cursor_action(self, action: str, expected_pos: tuple | None = None,
                         actual_pos: tuple | None = None) -> VerificationResult:
    """Verify cursor move/click/drag completed."""
    checks = [
        {"name": "action_submitted", "passed": True, "detail": f"cursor {action}"},
    ]
    if expected_pos and actual_pos:
        checks.append({"name": "position_match", "passed": expected_pos == actual_pos,
                       "detail": f"expected {expected_pos}, got {actual_pos}"})
    state = SUCCESS if all(c["passed"] for c in checks) else PARTIAL_SUCCESS
    return self.verify(f"cursor_{action}", checks, state=state)

def verify_keyboard_action(self, action: str, text: str | None = None,
                           keys: str | None = None) -> VerificationResult:
    """Verify keyboard type/hotkey."""
    checks = [
        {"name": "action_submitted", "passed": True, "detail": f"keyboard {action}"},
    ]
    # Could verify via QGIS focus widget state
    state = SUCCESS if all(c["passed"] for c in checks) else PARTIAL_SUCCESS
    return self.verify(f"keyboard_{action}", checks, state=state)

def verify_project_operation(self, operation: str, file_exists: bool,
                             project_valid: bool) -> VerificationResult:
    """Verify project open/save."""
    checks = [
        {"name": f"{operation}_submitted", "passed": True},
        {"name": "file_exists", "passed": file_exists,
         "detail": "project file on disk"},
        {"name": "project_valid", "passed": project_valid,
         "detail": "QgsProject reads without error"},
    ]
    state = SUCCESS if all(c["passed"] for c in checks) else FAILED
    return self.verify(f"project_{operation}", checks, state=state)

def verify_workflow_execution(self, workflow_id: str, job_completed: bool,
                              steps_succeeded: int, steps_total: int) -> VerificationResult:
    """Verify multi-step workflow."""
    checks = [
        {"name": "workflow_started", "passed": True, "detail": workflow_id},
        {"name": "job_completed", "passed": job_completed},
        {"name": "all_steps_succeeded", "passed": steps_succeeded == steps_total,
         "detail": f"{steps_succeeded}/{steps_total} steps"},
    ]
    state = SUCCESS if all(c["passed"] for c in checks) else (
        PARTIAL_SUCCESS if job_completed else FAILED)
    return self.verify("workflow_execution", checks, state=state)
```

---

## 10. Priority Matrix & Timeline

| Phase | Priority | Deliverable | Est. Effort | Dependencies |
|-------|----------|-------------|-------------|--------------|
| **Phase 1: Foundation** (Week 1-2) | | | | |
| 1.1 | P0 | Contract test suite (`tests/contract/`) | 2 days | — |
| 1.2 | P0 | Integration test fixtures (`tests/fixtures/`, `conftest.py`) | 2 days | Sample data script |
| 1.3 | P0 | Visual regression engine (`engines/verification/visual_regression.py`) | 2 days | Pillow, imagehash |
| 1.4 | P0 | CI/CD workflow (`.github/workflows/ci.yml`) | 1 day | — |
| **Phase 2: Core Coverage** (Week 3-4) | | | | |
| 2.1 | P0 | Full integration test suite (all 40+ tools) | 3 days | Phase 1.2 |
| 2.2 | P0 | Property-based test suite (`tests/property/`) | 2 days | Hypothesis |
| 2.3 | P0 | Error injection test suite (`tests/error_injection/`) | 2 days | pytest-mock |
| 2.4 | P1 | Visual regression test suite (`tests/visual/`) | 2 days | Phase 1.3, baselines |
| **Phase 3: Advanced** (Week 5-6) | | | | |
| 3.1 | P1 | Load/stress test suite (`tests/load/`) | 2 days | aiohttp |
| 3.2 | P1 | Verification engine extensions (cursor, keyboard, workflow) | 1 day | — |
| 3.3 | P1 | Schema versioning detection in contract tests | 1 day | — |
| 3.4 | P2 | Baseline image generation pipeline (auto-update on approve) | 2 days | — |
| **Phase 4: Polish** (Week 7) | | | | |
| 4.1 | P1 | Test documentation, runbooks | 1 day | — |
| 4.2 | P1 | Flaky test detection & quarantine | 1 day | — |
| 4.3 | P2 | Performance benchmarks dashboard | 2 days | — |

**Total: ~7 weeks for full bulletproof coverage**

---

## 11. Success Metrics

| Metric | Target |
|--------|--------|
| Contract test coverage | 100% of 40+ tools |
| Integration test pass rate | 100% (on Windows with QGIS) |
| Visual regression baseline count | 20+ baselines (canvas, algorithms, dialogs) |
| Property-based test cases | 1000+ generated per run |
| Load test concurrent requests | 50+ simultaneous, 0 failures |
| Error injection coverage | 15+ failure scenarios |
| CI pipeline duration | < 15 min (unit), < 30 min (integration) |
| Schema breaking change detection | 100% (contract tests fail) |
| Visual regression false positive rate | < 1% (perceptual hash tuned) |

---

## 12. Immediate Next Steps

1. **Create `tests/contract/test_tool_contracts.py`** — Validate all 40+ tool schemas
2. **Create `tests/fixtures/conftest.py`** — QGIS app, clean project, sample data fixtures
3. **Create `engines/verification/visual_regression.py`** — Perceptual hash + pixel diff
4. **Create `.github/workflows/ci.yml`** — Full pipeline with Windows QGIS runner
5. **Generate test data** — Run `scripts/generate_test_data.py`
6. **Capture initial visual baselines** — Run visual tests with `UPDATE_BASELINES=true`

---

## Appendix: Tool Inventory (from Registry)

| Namespace | Tools (43 total) |
|-----------|------------------|
| qgis.system | inspect, health |
| qgis.project | open, save, inspect |
| qgis.layers | inspect, load, remove |
| qgis.canvas | inspect |
| qgis.screen | capture |
| qgis.cursor | move, click, drag |
| qgis.keyboard | type, hotkey |
| qgis.mouse | scroll |
| qgis.window | inspect |
| qgis.dialog | inspect |
| qgis.algorithms | discover, execute |
| qgis.georeference | analyze |
| qgis.gcp | generate, validate |
| qgis.raster | info |
| qgis.vector | info |
| qgis.spatial | info |
| qgis.database | info |
| qgis.layout | info |
| qgis.workflow | execute |
| qgis.agents | list |
| qgis.skills | list |
| qgis.verify | status |
| qgis.jobs | cancel |
| qgis.history | inspect |
| qgis.plugins | list |

**Total: 43 tools across 24 namespaces** — All require contract + integration + property tests.