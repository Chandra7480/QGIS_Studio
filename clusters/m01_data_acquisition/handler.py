"""M01 — Data Acquisition: dataset discovery, file import, remote access, validation."""

from clusters.base import ClusterBase, ClusterResult
from core.exceptions import ExecutionError


class M01DataAcquisition(ClusterBase):
    CLUSTER_ID = "M01"
    CLUSTER_NAME = "Data Acquisition"
    OPERATIONS = {
        "import_file": "Import a vector or raster file into the project",
        "validate_source": "Validate that a data source exists and is readable",
    }

    def execute(self, operation: str, params: dict) -> ClusterResult:
        if operation == "import_file":
            return self._import_file(params)
        if operation == "validate_source":
            return self._validate_source(params)
        return ClusterResult(operation, False, "FAILED", {},
                             error=f"Unknown operation: {operation}")

    def _import_file(self, params: dict) -> ClusterResult:
        path = params.get("path")
        if not path:
            return ClusterResult("import_file", False, "FAILED", {},
                                 error="Missing required parameter: path")
        provider = params.get("provider")
        try:
            result = self.executor.load_layer(path=path,
                                              layer_name=params.get("layer_name"),
                                              provider=provider)
            return ClusterResult("import_file", True, "SUCCESS", result)
        except Exception as exc:
            return ClusterResult("import_file", False, "FAILED", {},
                                 error=str(exc))

    def _validate_source(self, params: dict) -> ClusterResult:
        import os
        path = params.get("path")
        if not path:
            return ClusterResult("validate_source", False, "FAILED", {},
                                 error="Missing required parameter: path")
        exists = os.path.exists(path)
        return ClusterResult("validate_source", exists, "SUCCESS" if exists else "FAILED",
                             {"path": path, "exists": exists})


def create_handler(executor):
    return M01DataAcquisition(executor)
