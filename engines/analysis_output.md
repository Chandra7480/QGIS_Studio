# Engines Folder Analysis — Universal AI GIS Studio

**Task:** task-3  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent  
**Context:** core/ (task-1) and clusters/ (task-2) analyses read prior

---

## 1. Folder Structure

```
engines/
├── screen_capture/              # Screen capture engine
│   ├── __init__.py
│   ├── screen_capture.py       # ScreenCaptureEngine (221 lines)
│   └── __pycache__/
├── visual_automation/           # Visual desktop automation
│   ├── __init__.py
│   ├── window_detector.py      # WindowDetector (91 lines)
│   ├── macro_recorder.py       # MacroRecorder, MacroPlayer, MacroManager (605 lines)
│   └── __pycache__/
├── mouse_keyboard/              # Low-level mouse/keyboard input
│   ├── __init__.py
│   ├── mouse_keyboard.py       # MouseKeyboardController (176 lines)
│   └── __pycache__/
├── cursor_controller/           # AI cursor overlay (PyQt6)
│   ├── __init__.py
│   ├── cursor_controller.py    # AICursorOverlay, AICursorController (417 lines)
│   └── __pycache__/
├── verification/                # Verification engines
│   ├── __init__.py
│   ├── verification_engine.py  # VerificationEngine (381 lines)
│   ├── visual_regression.py    # VisualRegressionEngine (300 lines)
│   ├── visual_verification.py  # VisualVerificationEngine, AIDiffAnalyzer (563 lines)
│   └── __pycache__/
├── computer_vision/             # OpenCV-based CV engine
│   ├── __init__.py
│   ├── cv_engine.py            # CVEngine (163 lines)
│   └── __pycache__/
├── georeferencing/              # Automatic georeferencing
│   ├── __init__.py
│   ├── georeferencing_engine.py # GeoreferencingEngine, GCP (270 lines)
│   └── __pycache__/
└── __pycache__/
```

**Total:** 7 engines, ~2,300 lines of engine code

---

## 2. Engine Purposes & Architecture

| Engine | Purpose | Key Dependencies | Integration Points |
|--------|---------|------------------|-------------------|
| **screen_capture** | Capture screenshots (full/region), periodic capture, WebSocket frame callbacks | `PIL.ImageGrab`, `base64`, `threading` | Bridge `qgis.screen.*` tools; `VerificationEngine.verify_screen_capture` |
| **visual_automation** | QGIS window detection, macro recording/playback with loops/conditionals | `win32gui`, `win32process`, `win32api`, `core.logging` | `MacroPlayer` uses `executor` (cursor/keyboard); clusters M23 automation |
| **mouse_keyboard** | Low-level Win32 SendInput for mouse/keyboard (screen coordinates) | `ctypes`, `win32api`, `win32con` | `cursor_controller` (human cursor); `MacroPlayer` executor |
| **cursor_controller** | AI-controlled visible cursor overlay (PyQt6) with trail/ripple/highlight | `qgis.PyQt.Qt*` (PyQt6), `core.emergency_stop` | Emergency stop priority 80; visual feedback for AI actions |
| **verification** | Truthful verification states (SUCCESS/PARTIAL/FAILED/NEEDS_REVIEW) | `core.exceptions`, `PIL`, `numpy` (visual) | All clusters/engines; `JobManager` verification_state; M24 AI validation |
| **visual_regression** | pHash + pixel-diff comparison for screenshot testing | `imagehash`, `PIL`, `platform` | CI/CD visual testing; baseline management per-platform |
| **visual_verification** | SSIM-based comparison, diff regions, AI-assisted analysis | `numpy`, `scipy.ndimage`, `PIL`, `base64` | Advanced visual diff; `AIDiffAnalyzer` for intelligent interpretation |
| **computer_vision** | ORB/SIFT feature detection, matching, homography, template match | `cv2` (OpenCV), `numpy` | `georeferencing_engine` (landmark detection); M05 cluster |
| **georeferencing** | Automatic GCP generation, validation, transformation via QGIS/GDAL | `cv_engine`, `VerificationEngine`, `core.exceptions` | M05 Georeferencing cluster; Bridge georeferencing tools |

---

## 3. Detailed Engine Analysis

### 3.1 Screen Capture Engine (`screen_capture.py`)

**Capabilities:**
- Full screen / region capture → base64 PNG
- Periodic capture (1-60s interval) with background thread
- Frame callbacks for WebSocket streaming
- Multi-monitor awareness (best-effort via `ImageGrab.grab(all_screens=True)`)

**Strengths:**
- Clean async callback pattern with thread-safe registration
- Graceful fallback for older Pillow versions
- Periodic capture integrates with emergency stop (configurable via config)

**Issues:**
- Windows-only (`ImageGrab`); no Linux/macOS backend
- No cursor capture on all Pillow versions (fallback to basic grab)
- `all_monitors()` returns single virtual screen, not per-monitor details
- No integration with `core.resource_quota` for memory tracking

### 3.2 Visual Automation (`window_detector.py`, `macro_recorder.py`)

**WindowDetector:**
- Win32 API enumeration → finds QGIS window by title substring
- Security: `bring_to_foreground()` only allows authorized QGIS window
- Returns window geometry (rect, pid, title)

**MacroRecorder/MacroPlayer/MacroManager:**
- Full macro lifecycle: record → save → parameterize → play
- Event types: mouse_move, click, drag, scroll, key_type, hotkey, wait, loop, condition
- Template variables with `{{name}}` placeholder substitution
- Loop support (count-based), basic conditionals (stub)
- Variable playback speed (0.1x–10x), pause/resume/stop
- JSON file storage with `MacroManager`

**Issues:**
- Windows-only (Win32 API)
- `win32con` imported at bottom of file (style issue)
- Condition evaluation is stub (`_handle_condition` only logs)
- No integration with `core.job_manager` for long macro playback
- No `EmergencyStop` check during playback (only cursor has it)

### 3.3 Mouse/Keyboard Controller (`mouse_keyboard.py`)

**Capabilities:**
- Absolute mouse move via `SendInput` (screen coords → 0..65535)
- Click (left/right/middle), double-click, drag, scroll
- Keyboard: `type_text` (char by char), `hotkey` (multi-key), `press`
- `get_position()` for current cursor

**Issues:**
- Windows-only (Win32 `SendInput`, `VkKeyScanW`)
- No input verification (fire-and-forget)
- No integration with `cursor_controller` (separate systems)
- `type_text` uses `VkKeyScanW` per char — slow for long strings
- No high-DPI awareness beyond `GetSystemMetrics`

### 3.4 Cursor Controller (`cursor_controller.py`)

**Capabilities:**
- PyQt6 transparent overlay on QGIS window
- Smooth animated movement (`QPropertyAnimation`)
- Visual effects: cyan ring cursor, target highlight (crosshair), click ripple, fading trail
- Pause/resume, emergency stop integration (priority 80)
- Configurable: highlight radius, trail length, ripple, trail fade time

**Strengths:**
- Excellent visual feedback for AI actions
- Proper `EmergencyStop` registration
- Thread-safe via Qt main loop

**Issues:**
- Requires PyQt6/QGIS environment (not available in headless/CI)
- `QApplication.instance() or QApplication([])` — creates new app if none (risky)
- No coordinate conversion (screen ↔ map) — relies on caller
- Trail/ripple animation runs at 60 FPS continuously (CPU cost)

### 3.5 Verification Engine (`verification_engine.py`)

**Verification States:** `SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`, `NEEDS_REVIEW`, `CANCELLED`

**Methods (25+):**
- Generic: `verify()`, `verify_layer_loaded()`, `verify_algorithm_executed()`
- Georeferencing: `verify_georeferencing()` (RMSE thresholds)
- Layout: `verify_layout_export()`
- Cursor: `verify_cursor_move/click/drag()` (position tolerance)
- Keyboard: `verify_keyboard_type/hotkey()`
- Project: `verify_project_open/save()`
- Workflow: `verify_workflow_execution()`
- Screen: `verify_screen_capture()` (base64 decode + size check)
- Layer removal: `verify_layer_removed()`

**Strengths:**
- Structured checks with `{"name", "passed", "detail"}`
- History tracking (`last_result()`, `history()`)
- Nuanced states (`PARTIAL_SUCCESS`, `NEEDS_REVIEW`)

**Issues:**
- No integration with `core.event_bus` for verification events
- No automatic verification chaining (caller must invoke)
- `verify_screen_capture` imports `PIL` inside method (runtime cost)

### 3.6 Visual Regression (`visual_regression.py`)

**Capabilities:**
- Perceptual hash (pHash) via `imagehash` library
- Pixel-diff ratio with configurable thresholds
- Per-platform baselines (`baseline_dir/platform/`)
- `UPDATE_BASELINES=1` env var for CI baseline updates
- CLI and pytest integration

**Thresholds:** pHash Hamming distance ≤ 5, pixel diff ratio ≤ 1%

**Issues:**
- Requires `imagehash` (extra dependency)
- No SSIM (uses simpler pHash + pixel diff)
- Baseline management manual (no auto-cleanup of old baselines)

### 3.7 Visual Verification (`visual_verification.py`)

**Capabilities:**
- Full SSIM implementation (NumPy-based)
- Connected-component diff region detection (`scipy.ndimage`)
- Diff image generation (red = differences)
- Highlighted reference image with labeled regions
- Ignore regions (for dynamic UI elements)
- Batch directory comparison
- `AIDiffAnalyzer`: categorizes diffs, assesses severity, generates suggestions, estimates false positive likelihood

**Strengths:**
- Production-grade visual diff with region analysis
- AI-assisted interpretation framework (pluggable `api_provider`)
- Comprehensive metadata in results

**Issues:**
- Heavy dependencies: `numpy`, `scipy`, `PIL`
- SSIM implementation simplified (no sliding window)
- `scipy.ndimage` import inside method (runtime cost)
- `AIDiffAnalyzer` AI integration is placeholder

### 3.8 Computer Vision (`cv_engine.py`)

**Capabilities:**
- ORB (binary) and SIFT (float) feature detection
- BFMatcher with Lowe's ratio test (0.75)
- Homography estimation with RANSAC (configurable threshold)
- Template matching (normalized cross-correlation)
- Histogram correlation similarity
- Image quality metrics: sharpness (Laplacian variance), contrast, brightness

**Issues:**
- Graceful fallback if OpenCV missing (logs warning)
- SIFT may not be available in all OpenCV builds (patent history)
- No GPU acceleration (CUDA) support
- Single global `cv_engine` instance (not configurable)

### 3.9 Georeferencing (`georeferencing_engine.py`)

**Pipeline (9 steps):**
1. `inspect_image()` — dimensions, quality metrics
2. `detect_landmarks()` — ORB matching with reference image
3. `match_pixels_to_reference()` — pixel → map coords via GDAL geotransform
4. `generate_gcps()` — combines detection + coordinate mapping
5. `validate_gcps()` — duplicates, confidence, spatial distribution, RMSE
6. `transform_with_qgis()` — builds request for QGIS/GDAL (method: helmert/polynomial/TPS)
7. `verify_georeferencing()` — uses `VerificationEngine`

**Core Rule:** "Coordinates are NEVER invented" — only matches pixels to trusted reference coords

**Strengths:**
- Clear step-by-step pipeline with validation at each stage
- Duplicate GCP rejection, confidence filtering, spatial distribution check
- RMSE calculation from residuals
- Integration with `VerificationEngine` for final verification

**Issues:**
- `transform_with_qgis()` only builds request dict — actual execution via Bridge
- No automatic outlier detection beyond confidence/spread
- Requires reference raster with known geotransform
- `min_confidence` hardcoded default 0.5

---

## 4. Dependencies

### Internal
```
engines.screen_capture          → core.logging, core.emergency_stop (config)
engines.visual_automation       → core.logging, engines.mouse_keyboard (via executor)
engines.mouse_keyboard          → (stdlib + win32)
engines.cursor_controller       → core.logging, core.emergency_stop, qgis.PyQt
engines.verification            → core.exceptions, PIL, numpy, scipy
engines.visual_regression       → imagehash, PIL, platform
engines.visual_verification     → numpy, scipy, PIL, core.logging
engines.computer_vision         → cv2 (OpenCV), numpy
engines.georeferencing          → engines.computer_vision, engines.verification, core.exceptions
clusters.m05_georeferencing     → engines.georeferencing.GeoreferencingEngine
```

### External
| Engine | Required | Optional |
|--------|----------|----------|
| screen_capture | Pillow | — |
| visual_automation | pywin32 | — |
| mouse_keyboard | pywin32, ctypes | — |
| cursor_controller | PyQt6 (qgis.PyQt) | — |
| verification | Pillow | numpy, scipy (visual) |
| visual_regression | imagehash, Pillow | — |
| visual_verification | numpy, scipy, Pillow | — |
| computer_vision | opencv-python (cv2), numpy | — |
| georeferencing | opencv-python, numpy | — |

---

## 5. Issues Found

### 🔴 REMOVE (Dead Code / Security Risks / Duplicates)
| Item | Location | Issue |
|------|----------|-------|
| `__pycache__/` | All engine subfolders | Compiled bytecode committed — gitignore |
| `win32con` import at bottom | `window_detector.py:91` | Violates import ordering; lazy import unnecessary |
| `scipy.ndimage` import inside method | `visual_verification.py:243` | Runtime import hides missing dependency |
| `PIL` import inside method | `verification_engine.py:342` | Runtime import, performance cost |
| Global `cv_engine` instance | `cv_engine.py:163` | Singleton prevents config per-use-case |

### 🟡 ADD (Missing Features / Tests / Docs)
| Gap | Engine(s) | Recommendation |
|-----|-----------|----------------|
| **Cross-platform support** | screen_capture, visual_automation, mouse_keyboard | Add Linux (X11/Wayland), macOS (Quartz) backends |
| **Unit tests** | cursor_controller, computer_vision, visual_verification, visual_regression | Only screen_capture, verification, georeferencing have tests |
| **Integration tests** | All | No tests with real QGIS/Windows environment |
| **JobManager integration** | macro_recorder (playback), screen_capture (periodic) | Long operations should create jobs for tracking/cancellation |
| **ResourceQuota tracking** | screen_capture (memory), macro_recorder (duration) | No quota enforcement for engine operations |
| **EventBus publishing** | All engines | No events for capture, macro events, verification results |
| **CapabilityRegistry registration** | All engines | Engines don't register their capabilities |
| **CircuitBreaker** | computer_vision, georeferencing | No failure isolation for OpenCV/GDAL calls |
| **Parameter schemas** | All engine methods | No input validation / JSON schemas |
| **Documentation** | All engines | No per-engine README or API docs |

### 🔵 IMPROVE (Refactoring / Performance / Patterns)
| Opportunity | Engine(s) | Details |
|-------------|-----------|---------|
| **Abstract base for input engines** | mouse_keyboard, cursor_controller | Common protocol: `move(x,y)`, `click()`, `drag()`, `type()` |
| **Coordinate conversion layer** | cursor_controller, mouse_keyboard | Screen ↔ map coordinate conversion (via Bridge) |
| **Lazy imports** | visual_verification, verification_engine | Move `scipy`, `PIL` imports to module level with try/except |
| **Configurable CV engine** | computer_vision | Allow multiple instances with different ORB/SIFT params |
| **Async/await support** | screen_capture, macro_recorder | Convert threading to async for better integration |
| **EmergencyStop checks** | macro_recorder (playback), screen_capture (periodic) | Add `is_emergency_stop_active()` checks in loops |
| **Visual diff optimization** | visual_verification | SSIM sliding window; cache reference image features |
| **Macro condition evaluation** | macro_recorder | Implement real condition parsing (expr/JS) |
| **Baseline management** | visual_regression | Auto-cleanup old baselines; metadata (git commit, date) |
| **Executor protocol** | macro_recorder, cursor_controller | Define `ExecutorProtocol` for type safety |

---

## 6. Cross-Module Integration (with core/ & clusters/ context)

### Current Integration
```
clusters.m05_georeferencing  ──uses──▶ engines.georeferencing
engines.georeferencing       ──uses──▶ engines.computer_vision, engines.verification
engines.visual_automation    ──uses──▶ engines.mouse_keyboard (via executor)
engines.cursor_controller    ──registers──▶ core.emergency_stop (priority 80)
engines.verification         ──returns──▶ ClusterResult.verification_state
engines.screen_capture       ──config──▶ core.config (screenshot_interval_seconds)
```

### Missing Integration (from core/ analysis)
| Core Service | Should Integrate With | Current State |
|--------------|----------------------|---------------|
| `EventBus` | screen_capture (frame), macro_recorder (events), verification (results) | **Not used** |
| `JobManager` | screen_capture (periodic), macro_player (playback), georeferencing (transform) | **Not used** |
| `ResourceQuotaManager` | screen_capture (memory), computer_vision (GPU/CPU), macro_player (duration) | **Not used** |
| `EmergencyStop` | macro_player, screen_capture periodic, cursor_controller (✓ done) | **Partial** |
| `CapabilityRegistry` | All engines | **Not used** |
| `CircuitBreaker` | computer_vision, georeferencing (external libs) | **Not used** |

### Recommended Integration Pattern
```python
# In each engine's long-running methods:
from core.emergency_stop import is_emergency_stop_active
from core.job_manager import get_job_manager
from core.resource_quota import get_resource_quota_manager

def periodic_capture_loop(self, job_id=None):
    if job_id:
        quota_mgr = get_resource_quota_manager()
        quota_mgr.start_tracking(job_id)
    
    while not self._stop_event.is_set():
        if is_emergency_stop_active():
            break
        # ... capture ...
        if job_id:
            quota_mgr.update_usage(job_id, memory_mb=current_memory)
            quota_mgr.enforce_quotas(job_id)
        
        event_bus.publish("screen_capture.frame", frame_data)
```

---

## 7. Test Coverage Analysis

| Test File | Engines Covered | Tests |
|-----------|----------------|-------|
| `test_screen_capture.py` | screen_capture | 3 (size, capture, region) |
| `test_verification.py` | verification | 7 (layer, algorithm, georef, layout, history) |
| `test_georeferencing.py` | georeferencing | 8 (GCP, transform, validation, verify) |
| **Missing** | cursor_controller, visual_automation, mouse_keyboard, computer_vision, visual_regression, visual_verification | 0 |

**Total:** 3/9 engines have tests (33%)

---

## 8. Recommendations Summary

### Priority 1 (Immediate)
1. **Add all `engines/*/__pycache__/` to `.gitignore`**
2. **Fix import ordering** in `window_detector.py`, `visual_verification.py`, `verification_engine.py`
3. **Add unit tests** for 6 untested engines (target: 1 test file per engine)
4. **Wire `EmergencyStop`** into `MacroPlayer._playback_loop()` and `ScreenCaptureEngine._periodic_capture_loop()`

### Priority 2 (Short-term)
5. **Define `ExecutorProtocol`** for `MacroPlayer` and `AICursorController`
6. **Add `EventBus` publishing** for key engine events (capture, macro start/stop, verification)
7. **Integrate `JobManager`** for long-running operations (periodic capture, macro playback, georef transform)
8. **Add `ResourceQuotaManager` tracking** for memory/CPU in screen_capture and computer_vision
9. **Move runtime imports** to module level with graceful fallback

### Priority 3 (Medium-term)
10. **Cross-platform backends** for screen_capture (mss), mouse_keyboard (pynput), visual_automation
11. **CircuitBreaker** around OpenCV/GDAL calls in computer_vision and georeferencing
12. **CapabilityRegistry registration** for all engine capabilities
13. **Async/await conversion** for better integration with MCP/Bridge
14. **Parameter validation** (Pydantic/JSON Schema) for all public engine methods
15. **Coordinate conversion service** (screen ↔ map) shared between cursor_controller and mouse_keyboard

---

## 9. Output for Next Task (agents/)

**Context to pass forward:**
- Engines provide: screen capture, visual automation (window detection, macros), mouse/keyboard input, AI cursor overlay, verification (functional + visual), computer vision, georeferencing
- Key integration gaps: No EventBus, JobManager, ResourceQuota, CapabilityRegistry, CircuitBreaker usage in engines
- Agents folder contains: `supervisor.py`, `custom/custom_builder.py`
- Supervisor agent likely orchestrates clusters + engines
- Custom agent builder may use macro_recorder for automation
- Visual automation engines (window_detector, macro_recorder, mouse_keyboard, cursor_controller) are primary dependencies for agent execution
- Verification engine integrates with JobManager verification_state
- Watch for: Circular imports between agents and engines; agents should not import clusters directly

---

*End of engines/ folder analysis*