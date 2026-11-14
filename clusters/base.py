"""Universal AI GIS Studio — GIS Cluster base class.

Each functional cluster (M01-M25) subclasses ClusterBase and implements
real operations backed by native PyQGIS / GDAL / Processing algorithms
discovered dynamically at runtime (never hardcoded algorithm assumptions).
"""

import logging
from typing import Optional

logger = logging.getLogger("uagis.clusters")


class ClusterResult:
    def __init__(self, operation: str, ok: bool, verification_state: str,
                 result: dict, error: str | None = None):
        self.operation = operation
        self.ok = ok
        self.verification_state = verification_state  # SUCCESS/PARTIAL/FAILED/NEEDS_REVIEW/CANCELLED
        self.result = result
        self.error = error

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "ok": self.ok,
            "verification_state": self.verification_state,
            "result": self.result,
            "error": self.error,
        }


class ClusterBase:
    CLUSTER_ID = ""
    CLUSTER_NAME = ""
    OPERATIONS = {}  # operation_name -> description

    def __init__(self, executor):
        self.executor = executor

    def execute(self, operation: str, params: dict) -> ClusterResult:
        raise NotImplementedError

    def discover_algorithm(self, name_patterns: list[str]) -> Optional[str]:
        """Find a processing algorithm id matching any pattern (case-insensitive substring)."""
        try:
            discovery = self.executor.execute_algorithm("qgis:algorithmsdiscover", {}) if False else None
        except Exception:
            pass
        # Prefer the processing registry directly
        try:
            import processing
            from qgis.core import QgsApplication
            registry = QgsApplication.processingRegistry()
            all_ids = [a.id() for a in registry.algorithms()]
            low = [p.lower() for p in name_patterns]
            for aid in all_ids:
                al = aid.lower()
                if any(p in al for p in low):
                    return aid
        except Exception as exc:
            logger.debug("Algorithm discovery failed: %s", exc)
        return None

    def run_algorithm(self, algorithm_id: str, parameters: dict) -> dict:
        return self.executor.execute_algorithm(algorithm_id, parameters)
