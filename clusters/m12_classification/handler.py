"""M12 — Image Classification: training, classification algorithms, accuracy assessment, post-processing."""

from clusters.base import ClusterBase, ClusterResult


_ALGO_MAP = {
    "train_samples": ["native:samplepoints", "otb:trainsvm", "otb:trainrf"],
    "supervised_classify": ["otb:trainimagesclassifier", "otb:imageclassifier", "saga:supervisedclassification"],
    "unsupervised_classify": ["otb:kmeansclassification", "saga:unsupervisedclassification", "otb:svmclassification"],
    "random_forest": ["otb:trainrf", "otb:rfclassification"],
    "support_vector_machine": ["otb:trainsvm", "otb:svmclassification"],
    "maximum_likelihood": ["otb:trainmaxlikelihood", "saga:maximumlikelihood"],
    "knn_classification": ["otb:knnclassification"],
    "decision_tree": ["otb:traindtrees", "otb:dtreesclassification"],
    "neural_network": ["otb:trainann", "otb:annclassification"],
    "accuracy_assessment": ["native:zonalstatistics", "otb:confusionmatrix", "saga:confusionmatrix"],
    "confusion_matrix": ["otb:confusionmatrix", "saga:confusionmatrix"],
    "kappa_coefficient": ["otb:kappacoefficient", "native:fieldcalculator"],
    "post_classification_filter": ["saga:majorityfilter", "otb:majorityvote"],
    "class_probability": ["otb:classificationprobability", "native:rastercalculator"],
    "reclassify": ["native:reclassifybytable", "gdal:reclassify", "saga:reclassifygridvalues"],
}


class M12Classification(ClusterBase):
    CLUSTER_ID = "M12"
    CLUSTER_NAME = "Image Classification"
    OPERATIONS = {k: f"Classification {k}" for k in _ALGO_MAP}

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
    return M12Classification(executor)