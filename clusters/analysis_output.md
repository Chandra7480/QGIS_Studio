# Clusters Folder Analysis — Universal AI GIS Studio

**Task:** task-2  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent  
**Context:** core/ analysis output (task-1) read prior

---

## 1. Folder Structure

```
clusters/
├── base.py                      # ClusterBase, ClusterResult (foundation classes)
├── registry.py                  # Cluster registry + factory (get_cluster_handler)
├── m01_data_acquisition/        # ✓ handler.py (2 ops) + __init__.py
├── m02_data_management/         # ✓ handler.py (2 ops) + __init__.py
├── m03_vector/                  # ✓ handler.py (8 ops, _ALGO_MAP) + __init__.py
├── m04_raster/                  # ✓ handler.py (7 ops, _ALGO_MAP) + __init__.py
├── m05_georeferencing/          # ✓ handler.py (4 ops, GeoreferencingEngine) + __init__.py
├── m06_crs/                     # ✓ handler.py (5 ops, _ALGO_MAP) + __init__.py
├── m07_spatial/                 # ✓ handler.py (6 ops, _ALGO_MAP) + __init__.py
├── m08_terrain/                 # ✓ handler.py (23 ops, _ALGO_MAP) + __init__.py
├── m09_hydrology/               # ✓ handler.py (22 ops, _ALGO_MAP) + __init__.py
├── m10_network/                 # ✓ handler.py (22 ops, _ALGO_MAP) + __init__.py
├── m11_remote_sensing/          # ✓ handler.py (22 ops, _ALGO_MAP) + __init__.py
├── m12_classification/          # ✓ handler.py (22 ops, _ALGO_MAP) + __init__.py
├── m13_change_detection/        # ✓ handler.py (22 ops, _ALGO_MAP) + __init__.py
├── m14_3d/                      # ✓ handler.py (22 ops, _ALGO_MAP) + __init__.py
├── m15_lidar/                   # ✓ handler.py (25 ops, _ALGO_MAP) + __init__.py
├── m16_survey/                  # ✓ handler.py (22 ops, _ALGO_MAP) + __init__.py
├── m17_cadastral/               # ✓ handler.py (24 ops, _ALGO_MAP) + __init__.py
├── m18_cartography/             # ✓ handler.py (26 ops, _ALGO_MAP) + __init__.py
├── m19_temporal/                # ✓ handler.py (22 ops, _ALGO_MAP) + __init__.py
├── m20_database/                # ✓ handler.py (24 ops, _ALGO_MAP) + __init__.py
├── m21_web_gis/                 # ✓ handler.py (26 ops, _ALGO_MAP) + __init__.py
├── m22_field_data/              # ✓ handler.py (24 ops, _ALGO_MAP) + __init__.py
├── m23_automation/              # ✓ handler.py (23 ops, _ALGO_MAP) + __init__.py
├── m24_ai_ml/                   # ✓ handler.py (17 ops, _ALGO_MAP + external AI) + __init__.py
├── m25_quality/                 # ✓ handler.py (23 ops, _ALGO_MAP) + __init__.py
└── __pycache__/                 # Compiled bytecode (should be gitignored)
```

**Total:** 25 clusters (M01–M25), 2 foundation files, ~1,000 lines of handler code

---

## 2. Architecture & Patterns

### Core Pattern (used by 23/25 clusters)
```python
# Each handler defines:
_ALGO_MAP = { "operation_name": ["algo_id_1", "algo_id_2", ...] }
CLUSTER_ID = "MXX"
CLUSTER_NAME = "Human Name"
OPERATIONS = {k: f"Category {k}" for k in _ALGO_MAP}

def execute(self, operation, params):
    patterns = _ALGO_MAP.get(operation)
    if not patterns: return ClusterResult(..., error="Unknown operation")
    algo = self.discover_algorithm(patterns)  # From ClusterBase
    if not algo: return ClusterResult(..., error="No algorithm found")
    result = self.run_algorithm(algo, params.get("parameters", {}))
    return ClusterResult(..., "SUCCESS", {"algorithm": algo, "outputs": result.get("outputs")})
```

### Foundation Classes (`base.py`)
- **`ClusterResult`** — Standardized result with `operation`, `ok`, `verification_state`, `result`, `error`, `to_dict()`
- **`ClusterBase`** — Base class with:
  - `discover_algorithm(patterns)` — Dynamic QGIS Processing registry lookup (case-insensitive substring)
  - `run_algorithm(algo_id, params)` — Delegates to `executor.execute_algorithm()`
  - `executor` — Injected dependency (provides `load_layer`, `inspect_layers`, `execute_algorithm`, etc.)

### Registry (`registry.py`)
- **`CLUSTER_MODULES`** — Dict mapping `"M01"`..`"M25"` → `"clusters.mXX_name"`
- **`get_cluster_handler(cluster_id, executor)`** — Dynamic import, calls `mod.create_handler(executor)`

### Cluster Categories
| Range | Category | Clusters |
|-------|----------|----------|
| M01–M02 | **Foundation** | Data Acquisition, Data Management |
| M03–M07 | **Core Processing** | Vector, Raster, Georeferencing, CRS, Spatial |
| M08–M10 | **Analysis** | Terrain, Hydrology, Network |
| M11–M13 | **Remote Sensing** | RS, Classification, Change Detection |
| M14–M15 | **3D & LiDAR** | 3D GIS, LiDAR |
| M16–M18 | **Specialized** | Survey/GPS, Cadastral, Cartography |
| M19 | **Temporal** | Temporal GIS |
| M20–M22 | **Data & Field** | Database, Web GIS, Field Data |
| M23 | **Automation** | Models, Batch, Scripts |
| M24 | **AI/ML** | External AI + OTB/ML algorithms |
| M25 | **Quality** | Validation, Topology, Reports |

---

## 3. Completeness Assessment

### ✅ Fully Implemented (23 clusters)
All clusters M01–M23 + M25 follow the standard pattern with:
- `_ALGO_MAP` with 5–26 operations each
- Proper `discover_algorithm` fallback chains (native → gdal → saga → grass7 → otb → pdal)
- `create_handler(executor)` factory function
- Error handling returning `ClusterResult` with `FAILED` state

### ⚠️ Special Cases
| Cluster | Difference |
|---------|------------|
| **M01** | Custom ops (`import_file`, `validate_source`) using `executor.load_layer` + `os.path.exists` |
| **M02** | Custom ops (`inspect_layers`, `remove_layer`) using `executor` methods |
| **M05** | Uses `GeoreferencingEngine` (not Processing algorithms); 4 custom ops |
| **M24** | Hybrid: `external_analysis` returns `PARTIAL_SUCCESS` with note about external AI; other ops use `_ALGO_MAP` (OTB deep learning) |

### 📊 Operation Counts
```
M01:  2   M02:  2   M03:  8   M04:  7   M05:  4
M06:  5   M07:  6   M08: 23   M09: 22   M10: 22
M11: 22   M12: 22   M13: 22   M14: 22   M15: 25
M16: 22   M17: 24   M18: 26   M19: 22   M20: 24
M21: 26   M22: 24   M23: 23   M24: 17   M25: 23
```
**Total: ~430 unique operations** across 25 clusters

---

## 4. Dependencies

### Internal
- `clusters.base` → `ClusterBase`, `ClusterResult`
- `core.exceptions` → `ExecutionError`, `NotFoundError` (in registry)
- `engines.georeferencing.georeferencing_engine` → M05 only

### External (Algorithm Providers)
| Provider | Prefix | Clusters Using |
|----------|--------|----------------|
| QGIS Native | `native:` | All (primary) |
| GDAL | `gdal:` | M04, M05, M06, M08, M09, M10, M11, M14, M15, M16, M17, M18, M19, M20, M21, M22 |
| SAGA | `saga:` | M08, M09, M10, M11, M12, M13, M14, M15, M16, M17, M19, M20, M22, M25 |
| GRASS 7 | `grass7:` | M08, M09, M10, M12, M13, M14, M16, M17, M19, M20, M22, M25 |
| Orfeo ToolBox | `otb:` | M11, M12, M13, M14, M15, M21, M24 |
| PDAL | `pdal:` | M14, M15 |
| Model/Script | `model:`, `native:script` | M23 |

---

## 5. Issues Found

### 🔴 REMOVE (Dead Code / Security Risks / Duplicates)
| Item | Location | Issue |
|------|----------|-------|
| `__pycache__/` | `clusters/__pycache__/`, all `mXX/__pycache__/` | Compiled bytecode committed — should be gitignored |
| Empty `__init__.py` | All 25 cluster folders | Just `"""MXX Name."""` — could export handler class or be removed |
| Duplicate `execute()` logic | 23 clusters | **Identical 15-line `execute()` method** copy-pasted across all algorithm-map clusters |
| Duplicate `ClusterResult` imports | All handlers | `from clusters.base import ClusterBase, ClusterResult` repeated 25× |

### 🟡 ADD (Missing Features / Tests / Docs)
| Gap | Scope | Recommendation |
|-----|-------|----------------|
| **Parameter schemas** | All clusters | No input validation / JSON schema for `params` — operations accept any dict |
| **Operation metadata** | All clusters | `OPERATIONS` only has description; missing: required params, param types, examples, output schema |
| **Unit tests** | 22/25 clusters | Tests only cover M01, M03, M04, M24 (4/25 clusters) |
| **Integration tests** | All | No tests with real QGIS Processing algorithms |
| **Capability registration** | All | Clusters don't register their operations with `core.capability_registry.CapabilityRegistry` |
| **Progress reporting** | All | Long-running algorithms have no progress callbacks |
| **Cancellation support** | All | No way to cancel a running `run_algorithm()` call |
| **Documentation** | All | No per-cluster README or operation catalog |

### 🔵 IMPROVE (Refactoring / Performance / Patterns)
| Opportunity | Details |
|-------------|---------|
| **Extract base `execute()`** | Move the 15-line algorithm-map `execute()` to `ClusterBase` as `execute_mapped(operation, params, algo_map)` — eliminates 300+ lines of duplicate code |
| **Typed parameter validation** | Add Pydantic models or JSON schemas per operation; validate in base `execute()` |
| **Algorithm discovery caching** | `discover_algorithm()` queries QGIS registry on every call — cache results per cluster instance |
| **Executor interface** | Define `Protocol` or ABC for `executor` (required methods: `execute_algorithm`, `load_layer`, `inspect_layers`, `remove_layer`, `discover_algorithm`) |
| **Result enrichment** | `ClusterResult` could include: `algorithm_used`, `execution_time_ms`, `warnings`, `metadata` |
| **Cluster discovery** | Registry could auto-discover clusters via filesystem scan instead of hardcoded `CLUSTER_MODULES` dict |
| **Lazy loading** | Import handler modules only when `get_cluster_handler()` is called (already done) |
| **M05 GeoreferencingEngine coupling** | Tight coupling to specific engine; consider abstracting via protocol |
| **M24 external AI** | `external_analysis` is a special case; consider a separate `ExternalAIClusterBase` pattern |

---

## 6. Cross-Module Integration (with core/ context)

### Current Integration Points
| Cluster | Uses from core/ |
|---------|----------------|
| All | `ClusterBase` → `core.exceptions` (indirect), `core.logging` (via base logger) |
| M05 | `engines.georeferencing.GeoreferencingEngine` |
| Registry | `core.exceptions.NotFoundError` |

### Missing Integration Points (from core/ analysis)
1. **`core.event_bus.EventBus`** — Clusters don't publish events for operation start/complete/fail
2. **`core.job_manager.JobManager`** — Long-running operations (M08–M25) should create jobs for tracking
3. **`core.resource_quota.ResourceQuotaManager`** — No quota tracking for algorithm execution
4. **`core.emergency_stop.EmergencyStop`** — Algorithms don't check `is_emergency_stop_active()`
5. **`core.capability_registry.CapabilityRegistry`** — Clusters don't register available operations
5. **`core.circuit_breaker.CircuitBreaker`** — No circuit breaker around external algorithm calls

### Recommended Integration Pattern
```python
# In ClusterBase.execute() or a new base method:
def execute_with_core_integration(self, operation, params, job_id=None):
    # 1. Check emergency stop
    if is_emergency_stop_active(): return ClusterResult(..., "CANCELLED", error="Emergency stop active")
    
    # 2. Create job if long-running
    if job_id is None and self._is_long_running(operation):
        job_id = job_manager.create_job(f"cluster.{self.CLUSTER_ID}.{operation}", ...)
        job_manager.start_job(job_id)
    
    # 3. Publish event
    event_bus.publish("cluster.operation.started", {"cluster": self.CLUSTER_ID, "operation": operation})
    
    # 4. Execute with quota tracking
    with resource_quota.track(job_id):
        result = self._execute_core(operation, params)
    
    # 5. Complete job, publish event
    if job_id: job_manager.complete_job(job_id, ...)
    event_bus.publish("cluster.operation.completed", {"cluster": self.CLUSTER_ID, "operation": operation, "ok": result.ok})
    
    return result
```

---

## 7. Test Coverage Analysis (`tests/unit/test_clusters.py`)

| Test | Coverage |
|------|----------|
| `test_all_cluster_ids_registered` | Registry completeness (25 IDs) |
| `test_create_handler_for_each_cluster` | Factory works for all 25 |
| `test_m01_import_and_validate` | M01 custom ops |
| `test_m03_vector_buffer` | Algorithm-map pattern (graceful FAILED) |
| `test_m03_unknown_op` | Unknown operation handling |
| `test_m04_raster_mosaic` | Raster cluster pattern |
| `test_m24_no_bundled_model` | M24 external AI special case |

**Gaps:** No tests for M02, M05–M23, M25 (21 clusters untested); no parameter validation tests; no error path tests beyond "unknown op".

---

## 8. Recommendations Summary

### Priority 1 (Immediate)
1. **Add `clusters/__pycache__/` and all `mXX/__pycache__/` to `.gitignore`**
2. **Extract duplicate `execute()` logic** into `ClusterBase.execute_mapped(operation, params, algo_map)`
3. **Add unit tests** for all 21 untested clusters (target: at least 1 test per cluster)

### Priority 2 (Short-term)
4. **Define `ExecutorProtocol`** (ABC/Protocol) for type safety and mocking
5. **Add parameter schemas** (JSON Schema or Pydantic) per operation
6. **Register operations** with `core.capability_registry.CapabilityRegistry` on handler creation
7. **Wire `EventBus`** for operation lifecycle events
8. **Add algorithm discovery caching** in `ClusterBase`

### Priority 3 (Medium-term)
9. **Integrate with `JobManager`** for long-running operations (M08–M25)
10. **Add `ResourceQuotaManager`** tracking for algorithm execution
11. **Implement cancellation** via `EmergencyStop` checks in `run_algorithm()`
12. **Add circuit breaker** around `executor.execute_algorithm()` calls
13. **Create per-cluster documentation** (operation catalog with params/examples)
14. **Auto-discover clusters** from filesystem instead of hardcoded `CLUSTER_MODULES`

---

## 9. Output for Next Task (engines/)

**Context to pass forward:**
- Clusters depend on: `core.exceptions`, `core.logging`, `engines.georeferencing` (M05 only)
- Clusters provide: 430+ operations across 25 domains, all using dynamic algorithm discovery
- Key integration gaps: No EventBus, JobManager, ResourceQuota, EmergencyStop, CapabilityRegistry, CircuitBreaker usage
- Engines folder contains: `screen_capture`, `visual_automation`, `mouse_keyboard`, `cursor_controller`, `verification`, `computer_vision`, `georeferencing`
- M05 Georeferencing cluster uses `engines.georeferencing.GeoreferencingEngine` — this is the primary integration point
- Other engines likely used by: agents (visual_automation, mouse_keyboard), verification cluster (verification engine), screen capture for documentation
- Watch for: Circular imports between clusters and engines; ensure engines don't import clusters

---

*End of clusters/ folder analysis*