"""M23 — GIS Automation: processing models, batch, Python automation, repeatable workflows, model builder."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "run_model": ["model:", "native:modelrunner"],
    "create_model": ["native:createmodel", "native:modelbuilder"],
    "edit_model": ["native:editmodel", "native:modelbuilder"],
    "export_model": ["native:exportmodel", "native:modeltofile"],
    "import_model": ["native:importmodel", "native:modelfromfile"],
    "batch_process": ["native:batchprocess", "native:processingrun"],
    "batch_vector": ["native:batchprocess", "native:mergevectorlayers"],
    "batch_raster": ["native:batchprocess", "native:mosaicrasterlayers"],
    "workflow_create": ["native:createworkflow", "native:workflowbuilder"],
    "workflow_run": ["native:runworkflow", "native:workflowrunner"],
    "workflow_export": ["native:exportworkflow", "native:workflowtofile"],
    "script_run": ["native:runscript", "native:pythonscript"],
    "script_create": ["native:createscript", "native:pythonscript"],
    "process_history": ["native:processhistory", "native:algorithmhistory"],
    "algorithm_help": ["native:algorithmlist", "native:algorithmhelp"],
    "model_validate": ["native:validatemodel", "native:modelcheck"],
}


class M23Automation(ClusterBase):
    CLUSTER_ID = "M23"
    CLUSTER_NAME = "GIS Automation"
    OPERATIONS = {k: f"Automation {k}" for k in _ALGO_MAP}

    def execute(self, operation: str, params: dict) -> ClusterResult:
        patterns = _ALGO_MAP.get(operation)
        if not patterns:
            return ClusterResult(operation, False, "FAILED", {},
                                 error=f"Unknown operation: {operation}")
        algo = self.discover_algorithm(patterns)
        if not algo:
            return ClusterResult(operation, False, "FAILED", {},
                                 error=f"No processing algorithm found for {operation}")
        try:
            result = self.run_algorithm(algo, params.get("parameters", {}))
            return ClusterResult(operation, True, "SUCCESS",
                                 {"algorithm": algo, "outputs": result.get("outputs", {})})
        except Exception as exc:
            return ClusterResult(operation, False, "FAILED", {},
                                 error=str(exc))


def create_handler(executor):
    return M23Automation(executor)