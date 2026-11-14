# Utils Folder Analysis — Universal AI GIS Studio

**Task:** task-14  
**Date:** 2026-11-14  
**Analyzer:** folder-inspector agent  
**Context:** security/ (task-13) analysis read prior

---

## 1. Folder Structure

```
utils/
```

**Status:** Empty directory — no files present.

---

## 2. Analysis

The `utils/` folder exists but contains no utility modules, helper functions, or common code. This is unusual for a project of this size and complexity.

### Expected Utility Categories (Missing)
| Category | Examples | Status |
|----------|----------|--------|
| **String/Path utilities** | slugify, path normalization, safe filename | ❌ Missing |
| **Date/Time helpers** | ISO formatting, timezone conversion, duration parsing | ❌ Missing |
| **Data validation** | JSON schema validation, coordinate validation, CRS parsing | ❌ Missing |
| **Serialization** | JSON/MessagePack helpers, base64 utilities | ❌ Missing |
| **Async utilities** | retry with backoff, timeout, circuit breaker helpers | ❌ Missing |
| **Logging/debug** | structured log formatting, context managers | ❌ Missing |
| **Geometry/Geospatial** | WKT/WKB parsing, bounding box, CRS transform helpers | ❌ Missing |
| **File I/O** | atomic write, temp file context, safe read | ❌ Missing |
| **Testing utilities** | fixtures, mock factories, assertion helpers | ❌ Missing |

---

## 3. Impact Assessment

### Code Duplication Risk
Without centralized utilities, the following patterns are likely duplicated across modules:
- **ISO timestamp formatting** — seen in `core.logging`, `database.db`, `agents.base_agent`, `monitoring.audit`
- **JSON serialization with datetime handling** — seen in `core.exceptions`, `database.repositories`, `agents.base_agent`
- **Path normalization** — seen in `engines.screen_capture`, `engines.visual_automation`, `clusters` handlers
- **Base64 encoding/decoding** — seen in `engines.screen_capture`, `engines.verification`, `mcp_server.verification`
- **Coordinate/CRS string parsing** — seen in `engines.georeferencing`, `clusters.m06_crs`, `clusters.m05_georeferencing`

### Maintenance Burden
- Bug fixes must be applied in multiple locations
- Inconsistent behavior across modules (e.g., different timestamp formats)
- Harder to enforce standards (e.g., all timestamps should be UTC ISO 8601)

---

## 4. Recommendations

### Priority 1 (Immediate)
1. **Create `utils/` module structure** with `__init__.py` exporting key utilities
2. **Move common patterns** from existing modules into `utils/`:
   - `utils.datetime` — ISO formatting, parsing, UTC enforcement
   - `utils.json` — custom encoder/decoder for datetime, UUID, Path, numpy
   - `utils.path` — safe path joining, normalization, temp file helpers
   - `utils.base64` — encode/decode with validation
   - `utils.validation` — coordinate/CRS/bbox validators

### Priority 2 (Short-term)
3. **Add async utilities**:
   - `utils.async_utils` — `retry_async()`, `timeout_async()`, `gather_with_concurrency()`
   - `utils.retry` — exponential backoff with jitter (replace duplicated retry logic)
4. **Add geospatial utilities**:
   - `utils.geospatial` — WKT/WKB parsing, bbox operations, CRS helpers
5. **Add testing utilities**:
   - `utils.testing` — fixtures, mock builders, assertion helpers

### Priority 3 (Medium-term)
6. **Refactor existing modules** to import from `utils.*` instead of duplicating code
6. **Add type stubs** (`.pyi`) for better IDE support
7. **Document utility APIs** with docstrings and examples

---

## 5. Suggested Module Structure

```
utils/
├── __init__.py              # Re-exports: datetime, json, path, base64, validation
├── datetime.py              # ISO format, parse, UTC helpers
├── json.py                  # Custom encoder/decoder, safe loads/dumps
├── path.py                  # Safe join, normalize, temp file context
├── base64.py                # Encode/decode with validation
├── validation.py            # Coordinate, CRS, bbox, geometry validators
├── async_utils.py           # retry, timeout, gather_with_concurrency
├── geospatial.py            # WKT/WKB, bbox, CRS transform helpers
├── testing.py               # Fixtures, mock factories, assertions
├── serialization.py         # MessagePack, CBOR, pickle safety
└── __pycache__/
```

---

## 6. Output for Next Task (tests/)

**Context to pass forward:**
- Utils folder is empty — no utility modules exist
- Common patterns duplicated across 15+ modules (datetime, JSON, path, base64, validation)
- Tests folder contains unit tests for some modules but no utility tests
- Next task should analyze `tests/` folder for coverage gaps

---

*End of utils/ folder analysis*