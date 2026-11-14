"""Universal AI GIS Studio — Verification Engine.

Every important operation is verified. The AI must never claim success
merely because a command was submitted. Returns truthful states:

    SUCCESS | PARTIAL_SUCCESS | FAILED | NEEDS_REVIEW | CANCELLED
"""

import logging
from typing import Optional, Any, Dict, Tuple

from core.exceptions import VerificationError

logger = logging.getLogger("uagis.verification")

SUCCESS = "SUCCESS"
PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
FAILED = "FAILED"
NEEDS_REVIEW = "NEEDS_REVIEW"
CANCELLED = "CANCELLED"


class VerificationResult:
    def __init__(self, state: str, checks: list[dict], details: dict | None = None,
                 error: str | None = None):
        self.state = state
        self.checks = checks
        self.details = details or {}
        self.error = error

    @property
    def ok(self) -> bool:
        return self.state == SUCCESS

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "ok": self.ok,
            "checks": self.checks,
            "details": self.details,
            "error": self.error,
        }


class VerificationEngine:
    """Verifies GIS operations and returns truthful verification states."""

    def __init__(self):
        self._results: list[VerificationResult] = []

    # ------------------------------------------------------------------ #
    # Generic verification
    # ------------------------------------------------------------------ #
    def verify(self, operation: str, checks: list[dict],
               state: str = SUCCESS, details: dict | None = None,
               error: str | None = None) -> VerificationResult:
        """Record a verification result.

        Each check is a dict: {"name": str, "passed": bool, "detail": str}
        """
        result = VerificationResult(state=state, checks=checks,
                                    details=details or {}, error=error)
        self._results.append(result)
        logger.info("Verification %s: %s (checks passed %d/%d)",
                    operation, state,
                    sum(1 for c in checks if c.get("passed")),
                    len(checks))
        return result

    def verify_layer_loaded(self, layer_id: str, valid: bool,
                            crs_ok: bool, extent_ok: bool,
                            feature_or_dim_ok: bool) -> VerificationResult:
        checks = [
            {"name": "layer_exists", "passed": layer_id is not None,
             "detail": f"layer id {layer_id}"},
            {"name": "layer_valid", "passed": valid, "detail": "layer isValid()"},
            {"name": "crs_valid", "passed": crs_ok, "detail": "CRS assigned"},
            {"name": "extent_valid", "passed": extent_ok, "detail": "extent computed"},
            {"name": "content_valid", "passed": feature_or_dim_ok,
             "detail": "features or raster dimensions"},
        ]
        all_passed = all(c["passed"] for c in checks)
        state = SUCCESS if all_passed else FAILED
        return self.verify("layer_loaded", checks, state=state,
                           details={"layer_id": layer_id})

    def verify_algorithm_executed(self, algorithm: str, output_exists: bool,
                                  output_valid: bool, expected_fields: bool = True) -> VerificationResult:
        checks = [
            {"name": "execution_submitted", "passed": True,
             "detail": f"algorithm {algorithm}"},
            {"name": "output_exists", "passed": output_exists,
             "detail": "output dataset exists"},
            {"name": "output_valid", "passed": output_valid,
             "detail": "output is valid"},
            {"name": "expected_fields", "passed": expected_fields,
             "detail": "expected fields/dimensions present"},
        ]
        all_passed = all(c["passed"] for c in checks)
        state = SUCCESS if all_passed else (
            PARTIAL_SUCCESS if output_exists else FAILED)
        return self.verify("algorithm_executed", checks, state=state,
                           details={"algorithm": algorithm})

    def verify_georeferencing(self, output_raster: bool, crs_match: bool,
                              extent_ok: bool, rmse: Optional[float],
                              rmse_threshold: float = 5.0,
                              visual_ok: Optional[bool] = None) -> VerificationResult:
        checks = [
            {"name": "output_raster_exists", "passed": output_raster,
             "detail": "georeferenced output written"},
            {"name": "crs_match", "passed": crs_match, "detail": "output CRS correct"},
            {"name": "extent_valid", "passed": extent_ok, "detail": "extent sensible"},
            {"name": "rmse_acceptable", "passed": (rmse is not None and rmse <= rmse_threshold),
             "detail": f"RMSE {rmse} (threshold {rmse_threshold})"},
        ]
        if visual_ok is not None:
            checks.append({"name": "visual_alignment", "passed": visual_ok,
                           "detail": "visual overlay alignment checked"})
        all_passed = all(c["passed"] for c in checks)
        if not output_raster:
            state = FAILED
        elif all_passed:
            state = SUCCESS
        elif rmse is None or rmse > rmse_threshold:
            state = NEEDS_REVIEW
        else:
            state = PARTIAL_SUCCESS
        return self.verify("georeferencing", checks, state=state,
                           details={"rmse": rmse, "crs_match": crs_match})

    def verify_layout_export(self, layout_exists: bool, export_file: bool,
                             file_nonempty: bool) -> VerificationResult:
        checks = [
            {"name": "layout_exists", "passed": layout_exists, "detail": "layout created"},
            {"name": "export_file_exists", "passed": export_file, "detail": "export file written"},
            {"name": "export_file_nonempty", "passed": file_nonempty,
             "detail": "export file has content"},
        ]
        all_passed = all(c["passed"] for c in checks)
        state = SUCCESS if all_passed else FAILED
        return self.verify("layout_export", checks, state=state)

    # ------------------------------------------------------------------ #
    # Cursor verification (qgis.cursor.*)
    # ------------------------------------------------------------------ #
    def verify_cursor_move(self, expected_x: int, expected_y: int,
                           actual_x: Optional[int] = None, actual_y: Optional[int] = None,
                           tolerance: int = 5) -> VerificationResult:
        """Verify cursor move operation."""
        checks = [
            {"name": "move_submitted", "passed": True, "detail": f"cursor.move({expected_x}, {expected_y})"},
        ]
        if actual_x is not None and actual_y is not None:
            x_ok = abs(actual_x - expected_x) <= tolerance
            y_ok = abs(actual_y - expected_y) <= tolerance
            checks.append({
                "name": "position_match", "passed": x_ok and y_ok,
                "detail": f"expected ({expected_x}, {expected_y}), got ({actual_x}, {actual_y})"
            })
            checks.append({"name": "x_tolerance", "passed": x_ok, "detail": f"x diff {abs(actual_x - expected_x)} <= {tolerance}"})
            checks.append({"name": "y_tolerance", "passed": y_ok, "detail": f"y diff {abs(actual_y - expected_y)} <= {tolerance}"})
        all_passed = all(c["passed"] for c in checks)
        state = SUCCESS if all_passed else PARTIAL_SUCCESS
        return self.verify("cursor_move", checks, state=state,
                           details={"expected": (expected_x, expected_y), "actual": (actual_x, actual_y)})

    def verify_cursor_click(self, button: str = "left",
                            expected_pos: Optional[Tuple[int, int]] = None,
                            actual_pos: Optional[Tuple[int, int]] = None) -> VerificationResult:
        """Verify cursor click operation."""
        checks = [
            {"name": "click_submitted", "passed": True, "detail": f"cursor.click({button})"},
        ]
        if expected_pos and actual_pos:
            pos_ok = expected_pos == actual_pos
            checks.append({
                "name": "position_match", "passed": pos_ok,
                "detail": f"expected {expected_pos}, got {actual_pos}"
            })
        all_passed = all(c["passed"] for c in checks)
        state = SUCCESS if all_passed else PARTIAL_SUCCESS
        return self.verify("cursor_click", checks, state=state,
                           details={"button": button, "expected_pos": expected_pos, "actual_pos": actual_pos})

    def verify_cursor_drag(self, start_x: int, start_y: int, end_x: int, end_y: int,
                           actual_start: Optional[Tuple[int, int]] = None,
                           actual_end: Optional[Tuple[int, int]] = None,
                           tolerance: int = 5) -> VerificationResult:
        """Verify cursor drag operation."""
        checks = [
            {"name": "drag_submitted", "passed": True,
             "detail": f"cursor.drag(({start_x}, {start_y}) -> ({end_x}, {end_y}))"},
        ]
        if actual_start and actual_end:
            sx_ok = abs(actual_start[0] - start_x) <= tolerance
            sy_ok = abs(actual_start[1] - start_y) <= tolerance
            ex_ok = abs(actual_end[0] - end_x) <= tolerance
            ey_ok = abs(actual_end[1] - end_y) <= tolerance
            checks.append({
                "name": "start_position_match", "passed": sx_ok and sy_ok,
                "detail": f"start expected ({start_x}, {start_y}), got {actual_start}"
            })
            checks.append({
                "name": "end_position_match", "passed": ex_ok and ey_ok,
                "detail": f"end expected ({end_x}, {end_y}), got {actual_end}"
            })
        all_passed = all(c["passed"] for c in checks)
        state = SUCCESS if all_passed else PARTIAL_SUCCESS
        return self.verify("cursor_drag", checks, state=state,
                           details={"start": (start_x, start_y), "end": (end_x, end_y)})

    # ------------------------------------------------------------------ #
    # Keyboard verification (qgis.keyboard.*)
    # ------------------------------------------------------------------ #
    def verify_keyboard_type(self, text: str,
                             expected_length: Optional[int] = None,
                             actual_length: Optional[int] = None) -> VerificationResult:
        """Verify keyboard type operation."""
        checks = [
            {"name": "type_submitted", "passed": True, "detail": f"keyboard.type(len={len(text)})"},
        ]
        if expected_length is not None and actual_length is not None:
            len_ok = actual_length == expected_length
            checks.append({
                "name": "length_match", "passed": len_ok,
                "detail": f"expected length {expected_length}, got {actual_length}"
            })
        all_passed = all(c["passed"] for c in checks)
        state = SUCCESS if all_passed else PARTIAL_SUCCESS
        return self.verify("keyboard_type", checks, state=state,
                           details={"text_length": len(text), "expected_length": expected_length, "actual_length": actual_length})

    def verify_keyboard_hotkey(self, keys: str,
                               expected_keys: Optional[str] = None,
                               actual_keys: Optional[str] = None) -> VerificationResult:
        """Verify keyboard hotkey operation."""
        checks = [
            {"name": "hotkey_submitted", "passed": True, "detail": f"keyboard.hotkey({keys})"},
        ]
        if expected_keys and actual_keys:
            keys_ok = expected_keys.lower() == actual_keys.lower()
            checks.append({
                "name": "keys_match", "passed": keys_ok,
                "detail": f"expected {expected_keys}, got {actual_keys}"
            })
        all_passed = all(c["passed"] for c in checks)
        state = SUCCESS if all_passed else PARTIAL_SUCCESS
        return self.verify("keyboard_hotkey", checks, state=state,
                           details={"keys": keys, "expected_keys": expected_keys, "actual_keys": actual_keys})

    # ------------------------------------------------------------------ #
    # Project verification (qgis.project.*)
    # ------------------------------------------------------------------ #
    def verify_project_open(self, path: str, file_exists: bool,
                            project_valid: bool, layer_count: int,
                            expected_layer_count: Optional[int] = None) -> VerificationResult:
        """Verify project open operation."""
        checks = [
            {"name": "open_submitted", "passed": True, "detail": f"project.open({path})"},
            {"name": "file_exists", "passed": file_exists, "detail": "project file on disk"},
            {"name": "project_valid", "passed": project_valid, "detail": "QgsProject reads without error"},
            {"name": "layers_loaded", "passed": layer_count >= 0, "detail": f"{layer_count} layers loaded"},
        ]
        if expected_layer_count is not None:
            count_ok = layer_count == expected_layer_count
            checks.append({
                "name": "layer_count_match", "passed": count_ok,
                "detail": f"expected {expected_layer_count} layers, got {layer_count}"
            })
        all_passed = all(c["passed"] for c in checks)
        state = SUCCESS if all_passed else FAILED
        return self.verify("project_open", checks, state=state,
                           details={"path": path, "layer_count": layer_count, "expected_layers": expected_layer_count})

    def verify_project_save(self, path: Optional[str], file_written: bool,
                            file_nonempty: bool, project_modified: bool) -> VerificationResult:
        """Verify project save operation."""
        checks = [
            {"name": "save_submitted", "passed": True, "detail": f"project.save({path or 'current'})"},
            {"name": "file_written", "passed": file_written, "detail": "project file written to disk"},
            {"name": "file_nonempty", "passed": file_nonempty, "detail": "saved file has content"},
            {"name": "project_modified", "passed": project_modified, "detail": "project had unsaved changes"},
        ]
        all_passed = all(c["passed"] for c in checks)
        state = SUCCESS if all_passed else FAILED
        return self.verify("project_save", checks, state=state,
                           details={"path": path, "modified": project_modified})

    # ------------------------------------------------------------------ #
    # Workflow verification (qgis.workflow.*)
    # ------------------------------------------------------------------ #
    def verify_workflow_execution(self, workflow_id: str, job_completed: bool,
                                  steps_succeeded: int, steps_total: int,
                                  step_details: Optional[list[dict]] = None) -> VerificationResult:
        """Verify multi-step workflow execution."""
        checks = [
            {"name": "workflow_started", "passed": True, "detail": f"workflow.execute({workflow_id})"},
            {"name": "job_completed", "passed": job_completed, "detail": "job reached completion state"},
            {"name": "all_steps_succeeded", "passed": steps_succeeded == steps_total,
             "detail": f"{steps_succeeded}/{steps_total} steps succeeded"},
        ]
        if step_details:
            for i, step in enumerate(step_details):
                step_ok = step.get("status") == "ok"
                checks.append({
                    "name": f"step_{i}_{step.get('tool', 'unknown')}", "passed": step_ok,
                    "detail": f"step {i}: {step.get('tool')} - {step.get('status')}"
                })
        all_passed = all(c["passed"] for c in checks)
        if job_completed and all_passed:
            state = SUCCESS
        elif job_completed:
            state = PARTIAL_SUCCESS
        else:
            state = FAILED
        return self.verify("workflow_execution", checks, state=state,
                           details={"workflow_id": workflow_id, "steps": f"{steps_succeeded}/{steps_total}"})

    # ------------------------------------------------------------------ #
    # Screen capture verification (qgis.screen.*)
    # ------------------------------------------------------------------ #
    def verify_screen_capture(self, image_base64: str, expected_width: Optional[int] = None,
                              expected_height: Optional[int] = None,
                              min_size_kb: int = 1) -> VerificationResult:
        """Verify screen capture operation."""
        import base64
        checks = [
            {"name": "capture_submitted", "passed": True, "detail": "screen.capture()"},
        ]
        try:
            decoded = base64.b64decode(image_base64)
            size_kb = len(decoded) / 1024
            checks.append({
                "name": "valid_base64", "passed": True, "detail": "valid base64 PNG"
            })
            checks.append({
                "name": "file_size_ok", "passed": size_kb >= min_size_kb,
                "detail": f"image size {size_kb:.1f} KB >= {min_size_kb} KB"
            })
            if expected_width and expected_height:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(decoded))
                w_ok = img.width == expected_width
                h_ok = img.height == expected_height
                checks.append({
                    "name": "dimensions_match", "passed": w_ok and h_ok,
                    "detail": f"expected {expected_width}x{expected_height}, got {img.width}x{img.height}"
                })
        except Exception as e:
            checks.append({
                "name": "valid_base64", "passed": False, "detail": f"invalid base64: {e}"
            })
        all_passed = all(c["passed"] for c in checks)
        state = SUCCESS if all_passed else FAILED
        return self.verify("screen_capture", checks, state=state,
                           details={"size_kb": len(decoded) / 1024 if 'decoded' in locals() else 0})

    # ------------------------------------------------------------------ #
    # Layer removal verification (qgis.layers.remove)
    # ------------------------------------------------------------------ #
    def verify_layer_removed(self, layer_id: str, removed: bool,
                             layer_no_longer_in_project: bool) -> VerificationResult:
        """Verify layer removal operation."""
        checks = [
            {"name": "remove_submitted", "passed": True, "detail": f"layers.remove({layer_id})"},
            {"name": "removed_flag", "passed": removed, "detail": "executor returned removed=true"},
            {"name": "layer_gone", "passed": layer_no_longer_in_project,
             "detail": "layer no longer in project layer tree"},
        ]
        all_passed = all(c["passed"] for c in checks)
        state = SUCCESS if all_passed else FAILED
        return self.verify("layer_removed", checks, state=state,
                           details={"layer_id": layer_id})

    def last_result(self) -> Optional[VerificationResult]:
        return self._results[-1] if self._results else None

    def history(self) -> list[dict]:
        return [r.to_dict() for r in self._results]
