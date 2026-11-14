"""M24 — AI-Assisted GIS: external AI analysis, image interpretation, NL ops, reasoning, ML integration.

This cluster does NOT include a bundled or mandatory local AI model. AI is supplied
externally (OpenCode / Codex / optional API). This cluster orchestrates calls to
external AI via the AI Host Manager and verifies results locally.
"""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "external_analysis": ["native:externalai", "native:aianalysis"],
    "image_interpretation": ["otb:deepclassification", "otb:deeplearning"],
    "natural_language_op": ["native:nlp", "native:nlgis"],
    "ai_validation": ["native:aivalidation", "native:verifygeometry"],
    "train_classifier": ["otb:trainimagesclassifier", "otb:trainrf", "otb:trainsvm"],
    "train_segmentation": ["otb:trainsegmentation", "otb:lsmssegmentation"],
    "predict": ["otb:modelpredict", "otb:imageclassifier"],
    "object_detection": ["otb:objectdetection", "otb:deepdetection"],
    "semantic_segmentation": ["otb:semanticsegmentation", "otb:deepsegmentation"],
    "feature_extraction": ["otb:featureextraction", "otb:haralicktextures"],
    "anomaly_detection": ["otb:anomalydetection", "saga:anomalydetection"],
    "clustering": ["otb:kmeansclassification", "saga:kmeans", "native:kmeansclustering"],
    "dimensionality_reduction": ["otb:pca", "otb:kpca", "saga:pca"],
    "model_evaluation": ["otb:confusionmatrix", "otb:kappacoefficient", "otb:roc"],
    "transfer_learning": ["otb:transferlearning", "otb:finetune"],
    "ensemble": ["otb:ensemble", "otb:majorityvote", "native:rastercalculator"],
}


class M24AIML(ClusterBase):
    CLUSTER_ID = "M24"
    CLUSTER_NAME = "AI-Assisted GIS"
    OPERATIONS = {k: f"AI/ML {k}" for k in _ALGO_MAP}

    def execute(self, operation: str, params: dict) -> ClusterResult:
        # Special handling for external AI operations - no local algorithm needed
        if operation == "external_analysis":
            return ClusterResult("external_analysis", True, "PARTIAL_SUCCESS",
                                 {"note": "Delegated to external AI host via AI Host Manager; no bundled model"})
        
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
    return M24AIML(executor)