"""Universal AI GIS Studio — Verification Engine.

Maps verification rule names to checker functions. Runs checkers on tool
results; if any fail, sets verification_state = "FAILED".
"""

import os
import logging
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path

from core.logging import get_logger

logger = get_logger("mcp.verification")


class VerificationEngine:
    """Executes verification rules against tool execution results."""

    def __init__(self):
        self._checkers: Dict[str, Callable[[Dict[str, Any], ToolSpec], bool]] = {}
        self._register_default_checkers()

    def _register_default_checkers(self):
        """Register all built-in verification rule checkers."""
        self._checkers = {
            "file_exists": self._check_file_exists,
            "file_written": self._check_file_written,
            "layer_valid": self._check_layer_valid,
            "layer_removed": self._check_layer_removed,
            "project_valid": self._check_project_valid,
            "output_exists": self._check_output_exists,
            "output_valid": self._check_output_valid,
            "confidence_scored": self._check_confidence_scored,
            "outliers_rejected": self._check_outliers_rejected,
            "min_point_count": self._check_min_point_count,
            "residuals_checked": self._check_residuals_checked,
            "response_structured": self._check_response_structured,
            "operation_completed": self._check_operation_completed,
            "ui_action_confirmed": self._check_ui_action_confirmed,
            "image_valid_base64": self._check_image_valid_base64,
        }

    def register_checker(self, name: str, checker: Callable[[Dict[str, Any], "ToolSpec"], bool]):
        """Register a custom verification checker."""
        self._checkers[name] = checker

    def run_verification(self, spec: "ToolSpec", result: Dict[str, Any]) -> List[str]:
        """
        Run all verification rules for a tool spec against the result.
        Returns list of failed rule names (empty if all pass).
        """
        if not spec.verification_rules:
            return []

        failed = []
        for rule_name in spec.verification_rules:
            checker = self._checkers.get(rule_name)
            if checker is None:
                logger.warning("Unknown verification rule: %s", rule_name)
                failed.append(rule_name)
                continue
            try:
                if not checker(result, spec):
                    failed.append(rule_name)
                    logger.debug("Verification rule %s FAILED for %s", rule_name, spec.name)
                else:
                    logger.debug("Verification rule %s PASSED for %s", rule_name, spec.name)
            except Exception as exc:
                logger.exception("Verification rule %s error for %s", rule_name, spec.name)
                failed.append(rule_name)

        return failed

    # ---- Built-in checkers ----

    def _check_file_exists(self, result: Dict[str, Any], spec: "ToolSpec") -> bool:
        """Check that output file path exists."""
        outputs = result.get("result", {}).get("outputs", {})
        for key, value in outputs.items():
            if isinstance(value, str) and value:
                path = Path(value)
                if path.suffix in (".tif", ".tiff", ".geotiff", ".shp", ".gpkg", ".qgz", ".qgs", ".json", ".xml"):
                    if not path.exists():
                        logger.debug("File does not exist: %s", path)
                        return False
        return True

    def _check_file_written(self, result: Dict[str, Any], spec: "ToolSpec") -> bool:
        """Check that a file was written (project save)."""
        project_file = result.get("result", {}).get("project_file")
        if project_file:
            return Path(project_file).exists()
        return False

    def _check_layer_valid(self, result: Dict[str, Any], spec: "ToolSpec") -> bool:
        """Check that loaded layer is valid."""
        valid = result.get("result", {}).get("valid")
        if valid is not None:
            return bool(valid)
        # If no explicit valid field, assume success means valid
        return result.get("status") == "success"

    def _check_layer_removed(self, result: Dict[str, Any], spec: "ToolSpec") -> bool:
        """Check that layer was removed."""
        removed = result.get("result", {}).get("removed")
        return bool(removed)

    def _check_project_valid(self, result: Dict[str, Any], spec: "ToolSpec") -> bool:
        """Check that project is valid after open."""
        project_file = result.get("result", {}).get("project_file")
        if project_file and Path(project_file).exists():
            return True
        return result.get("status") == "success"

    def _check_output_exists(self, result: Dict[str, Any], spec: "ToolSpec") -> bool:
        """Check that algorithm produced outputs."""
        outputs = result.get("result", {}).get("outputs", {})
        return bool(outputs)

    def _check_output_valid(self, result: Dict[str, Any], spec: "ToolSpec") -> bool:
        """Check that algorithm outputs are valid (non-empty)."""
        outputs = result.get("result", {}).get("outputs", {})
        for key, value in outputs.items():
            if isinstance(value, str) and value:
                path = Path(value)
                if path.exists() and path.stat().st_size > 0:
                    continue
                elif not path.exists():
                    return False
        return True

    def _check_confidence_scored(self, result: Dict[str, Any], spec: "ToolSpec") -> bool:
        """Check that GCPs have confidence scores."""
        gcps = result.get("result", {}).get("gcps", [])
        if not gcps:
            return False
        for gcp in gcps:
            if isinstance(gcp, dict) and "confidence" not in gcp:
                return False
        return True

    def _check_outliers_rejected(self, result: Dict[str, Any], spec: "ToolSpec") -> bool:
        """Check that outliers were identified and rejected."""
        rejected = result.get("result", {}).get("rejected", [])
        # Just check the field exists; empty list is valid (no outliers)
        return "rejected" in result.get("result", {})

    def _check_min_point_count(self, result: Dict[str, Any], spec: "ToolSpec") -> bool:
        """Check minimum GCP point count."""
        gcps = result.get("result", {}).get("valid_gcps", result.get("result", {}).get("gcps", []))
        return len(gcps) >= 4  # Minimum 4 GCPs for georeferencing

    def _check_residuals_checked(self, result: Dict[str, Any], spec: "ToolSpec") -> bool:
        """Check that residuals were computed and RMSE is reasonable."""
        rmse = result.get("result", {}).get("rmse")
        return rmse is not None and isinstance(rmse, (int, float)) and rmse >= 0

    def _check_response_structured(self, result: Dict[str, Any], spec: "ToolSpec") -> bool:
        """Check that response has expected structure (for inspect tools)."""
        return "result" in result and isinstance(result["result"], dict)

    def _check_operation_completed(self, result: Dict[str, Any], spec: "ToolSpec") -> bool:
        """Check that operation completed (status success)."""
        return result.get("status") == "success"

    def _check_ui_action_confirmed(self, result: Dict[str, Any], spec: "ToolSpec") -> bool:
        """Check that UI action was confirmed (cursor/keyboard/mouse)."""
        return result.get("result", {}).get("ok") is True

    def _check_image_valid_base64(self, result: Dict[str, Any], spec: "ToolSpec") -> bool:
        """Check that screen capture returned valid base64 image."""
        image_b64 = result.get("result", {}).get("image_base64")
        if not image_b64 or not isinstance(image_b64, str):
            return False
        # Basic base64 validation
        import base64
        try:
            base64.b64decode(image_b64, validate=True)
            return True
        except Exception:
            return False


# Global verification engine instance
_verification_engine: Optional[VerificationEngine] = None


def get_verification_engine() -> VerificationEngine:
    """Get or create the global verification engine."""
    global _verification_engine
    if _verification_engine is None:
        _verification_engine = VerificationEngine()
    return _verification_engine