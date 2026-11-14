"""M02 — Data Management: layer organization, metadata, conversion, cleaning."""

from clusters.base import ClusterBase, ClusterResult


class M02DataManagement(ClusterBase):
    CLUSTER_ID = "M02"
    CLUSTER_NAME = "Data Management"
    OPERATIONS = {
        "inspect_layers": "Inspect all loaded layers",
        "remove_layer": "Remove a layer from the project",
    }

    def execute(self, operation: str, params: dict) -> ClusterResult:
        if operation == "inspect_layers":
            return self._inspect_layers(params)
        if operation == "remove_layer":
            return self._remove_layer(params)
        return ClusterResult(operation, False, "FAILED", {},
                             error=f"Unknown operation: {operation}")

    def _inspect_layers(self, params: dict) -> ClusterResult:
        result = self.executor.inspect_layers()
        return ClusterResult("inspect_layers", True, "SUCCESS", result)

    def _remove_layer(self, params: dict) -> ClusterResult:
        layer_id = params.get("layer_id")
        if not layer_id:
            return ClusterResult("remove_layer", False, "FAILED", {},
                                 error="Missing required parameter: layer_id")
        try:
            result = self.executor.remove_layer(layer_id)
            return ClusterResult("remove_layer", True, "SUCCESS", result)
        except Exception as exc:
            return ClusterResult("remove_layer", False, "FAILED", {},
                                 error=str(exc))


def create_handler(executor):
    return M02DataManagement(executor)
