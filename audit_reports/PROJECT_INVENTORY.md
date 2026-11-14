# PROJECT INVENTORY — Universal AI GIS Studio Audit

**Audit Date:** 2026-11-11  
**Auditor:** Independent Principal Software Auditor  
**Rule:** Evidence-based only. No trust in README/comments/developer claims without verification.

## 1. File Count Summary

| Category | Count | Evidence |
|----------|-------|----------|
| Python files (.py) | 69 | project_inventory.txt |
| Markdown docs (.md) | 7 | README, CHANGELOG, LICENSE, 5 docs files |
| SQL files | 2 | schema.sql, migration |
| YAML files | 1 | manifest.yaml |
| TOML files | 1 | pyproject.toml |
| TXT requirements | 5 | base, dev, keyring, mcp, opencv |
| ZIP release artifacts | 2 | plugin zip, full platform zip |
| Test files | 8 | tests/unit/ |
| **Total source files** | **~94** | |

## 2. Module Inventory by Directory

### core/ (7 files)
- `__init__.py` — package init with exception exports
- `exceptions.py` — 15 exception classes (UAGISError hierarchy)
- `config.py` — Config class with defaults, typed accessors
- `logging.py` — setup_logging, LogContext, SensitiveFilter
- `event_bus.py` — EventBus pub/sub
- `job_manager.py` — JobManager (create/start/complete/fail/cancel/list)
- `capability_registry.py` — CapabilityRegistry (discover_qgis, discover_processing_algorithms)

### bridge/ (6 files)
- `__init__.py`
- `protocol.py` — Request/Response dataclasses, verification states
- `executor.py` — PyQGISExecutor (main-thread-safe, project/layer/canvas ops)
- `dispatcher.py` — BridgeDispatcher (routes requests to handlers)
- `request_handler.py` — BridgeRequestHandler (HTTP POST /dispatch)
- `bridge_server.py` — BridgeServer (ThreadingHTTPServer on localhost)

### mcp_server/ (5 files)
- `__init__.py`
- `server.py` — UniversalMCPServer (low-level MCP Server, stdio + Streamable HTTP)
- `qgis_client.py` — QgisBridgeClient (HTTP client to bridge)
- `registry.py` — ToolRegistry + build_registry() (25+ qgis.* tools)
- `main.py` — CLI entry point

### clusters/ (27 files: base + registry + 25 handler pairs)
- `base.py` — ClusterBase + ClusterResult
- `registry.py` — CLUSTER_MODULES mapping M01-M25
- `m01_data_acquisition/handler.py` — import_file, validate_source
- `m02_data_management/handler.py` — inspect_layers, remove_layer
- `m03_vector/handler.py` — buffer, clip, dissolve, intersection, union, difference, merge, repair
- `m04_raster/handler.py` — raster_calculation, reclassify, mosaic, clip_raster, resample, convert, band_operations
- `m05_georeferencing/handler.py` — inspect_image, detect_landmarks, generate_gcps, validate_gcps
- `m06_crs/handler.py` — detect_crs, assign_crs, reproject, transform, validate_crs
- `m07_spatial/handler.py` — spatial_join, proximity, overlay, density, interpolation, suitability
- `m08_terrain/handler.py` — slope, aspect, hillshade, contours, terrain_derivatives, dem_processing
- `m09_hydrology/handler.py` — flow_direction, flow_accumulation, watershed, stream_extraction, drainage_network
- `m10_network/handler.py` — shortest_path, service_areas, routing, connectivity
- `m11_remote_sensing/handler.py` — satellite_processing, band_combinations, spectral_indices, image_preparation
- `m12_classification/handler.py` — classify, train, accuracy, output
- `m13_change_detection/handler.py` — temporal_comparison, raster_difference, landcover_change, change_report
- `m14_3d/handler.py` — inspect_3d, create_terrain_model, export_3d
- `m15_lidar/handler.py` — point_cloud_inspection, filtering, classification, terrain_extraction
- `m16_survey/handler.py` — import_gps, validate_coords, process_tracks
- `m17_cadastral/handler.py` — manage_parcel, calculate_area, validate_topology
- `m18_cartography/handler.py` — create_layout, export_layout, apply_symbology
- `m19_temporal/handler.py` — enable_time, temporal_filter, temporal_analysis
- `m20_database/handler.py` — connect_geopackage, connect_postgis, spatial_sql, validate
- `m21_web_gis/handler.py` — add_wms, add_wfs, add_wmts, add_xyz
- `m22_field_data/handler.py` — import_field, sync_survey, collect_attributes, validate
- `m23_automation/handler.py` — run_model, batch, workflow
- `m24_ai_ml/handler.py` — external_analysis, image_interpretation, natural_language_op, ai_validation
- `m25_quality/handler.py` — geometry_validation, topology_validation, crs_validation, attribute_validation, completeness

### engines/ (8 files)
- `screen_capture/screen_capture.py` — ScreenCaptureEngine (PIL ImageGrab)
- `visual_automation/window_detector.py` — WindowDetector (win32gui)
- `mouse_keyboard/mouse_keyboard.py` — MouseKeyboardController (Win32 SendInput)
- `cursor_controller/cursor_controller.py` — AICursorController + AICursorOverlay (PyQt6)
- `computer_vision/cv_engine.py` — CVEngine (OpenCV ORB/SIFT, matching, RANSAC)
- `georeferencing/georeferencing_engine.py` — GeoreferencingEngine + GCP class
- `verification/verification_engine.py` — VerificationEngine (5 states)

### agents/ (7 files)
- `__init__.py`, `base_agent.py`, `orchestrator.py`, `supervisor.py`, `agent_manager.py`, `custom/__init__.py`, `custom/custom_builder.py`
- 29 built-in agent definitions in agent_manager.py
- AgentOrchestrator (delegate, cancel, status)

### skills/ (6 files + 1 built-in skill)
- `skill_manager.py`, `skill_loader.py`, `skill_validator.py`
- `builtin/automatic-georeferencing/manifest.yaml`, `SKILL.md`

### workflows/ (2 files)
- `workflow_engine.py` — 12 node types, CRUD, execution

### integrations/ (4 files)
- `ai_hosts/ai_host_manager.py`, `api_providers/api_manager.py`, `external_mcp/mcp_manager.py`

### security/ (4 files)
- `permission_manager.py`, `approval_manager.py`, `auth.py`

### monitoring/ (3 files)
- `audit.py`, `resource_monitor.py`

### extensions/ (2 files)
- `extension_manager.py`

### database/ (8 files)
- `db.py`, `schema.py`, `schema.sql` (18 tables), migrations, repositories (3)

### plugin/universal_ai_gis/ (4 files)
- `__init__.py` (classFactory), `metadata.txt`, `plugin.py`, `main_window.py`

### tests/unit/ (8 files)
- test_bridge_protocol.py, test_clusters.py, test_core.py, test_database.py, test_georeferencing.py, test_mcp_registry.py, test_screen_capture.py, test_verification.py

## 3. Empty Files Detected
None — all Python files contain code.

## 4. Broken Imports (Source Level)
**CRITICAL:** `plugin/universal_ai_gis/plugin.py` imports `from bridge.executor import ...`, `from core.logging import ...`, `from database.db import ...` WITHOUT adding project root to `sys.path`. Inside QGIS, these imports will fail unless the path is fixed. **This was fixed in the release ZIP but the source file still lacks the sys.path fix.** (Fixed in rebuilt ZIP — see plugin.py diff.)

## 5. Duplicate Modules
None detected.

## 6. Dependencies
- `mcp>=1.2.0` (installed, verified)
- `pydantic>=2.5.0` (installed)
- `pytest>=7.0.0` (installed, pytest-9.2.0)
- `opencv-python-headless>=4.8.0` (cv2 installed, verified)
- `numpy>=1.24.0` (installed)
- `keyring>=24.0.0` (not installed — optional)
- `aiohttp>=3.9.0` (not installed — optional for dev)
- PyQGIS: only available inside QGIS bundled Python (verified importable)
- PyQt6: available inside QGIS Python env
