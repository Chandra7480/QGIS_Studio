"""Image Classification Agent — Supervised/unsupervised classification."""

from agents.base_agent import SpecializedAgent


class ImageClassificationAgent(SpecializedAgent):
    """Agent for image classification: supervised, unsupervised, random forest, SVM."""

    def __init__(self, db=None):
        super().__init__(
            agent_id="agent_classification",
            name="Image Classification Agent",
            description="Supervised/unsupervised classification.",
            instructions=(
                "You classify imagery: supervised classification (Random Forest, SVM, KNN), "
                "unsupervised clustering (K-means, ISODATA), object-based classification, "
                "accuracy assessment, and confusion matrices. Use SAGA, OTB, and native algorithms."
            ),
            permission_level="standard",
            max_steps=15,
            db=db,
            domain="classification",
            tool_namespace="qgis.algorithms",
        )
        
        self.class_algorithms = {
            "random_forest": "saga:randomforestclassification",
            "svm": "saga:svmclassification",
            "knn": "saga:knnclassification",
            "kmeans": "saga:kmeansclustering",
            "isodata": "saga:isodataclustering",
            "maximum_likelihood": "saga:maximumlikelihoodclassification",
            "decision_tree": "saga:decisiontreeclassification",
            "gradient_boost": "saga:gradientboostingclassification",
            "accuracy_assessment": "saga:crossvalidation",
            "confusion_matrix": "saga:confusionmatrix",
            "object_based": "otb:otbclassification",
            "segmentation": "otb:otbsegmentation",
        }

    async def execute(self, task: dict) -> dict:
        action = task.get("action", "classify")
        params = task.get("params", {})

        self.add_to_history("user", f"Classification: {action}", {"action": action})

        if action == "classify":
            result = await self._classify(params)
        elif action == "supervised":
            result = await self._supervised(params)
        elif action == "unsupervised":
            result = await self._unsupervised(params)
        elif action == "accuracy":
            result = await self._accuracy(params)
        elif action == "segmentation":
            result = await self._segmentation(params)
        elif action == "list_operations":
            result = {"operations": list(self.class_algorithms.keys())}
        else:
            result = {"error": f"Unknown action: {action}"}

        self.add_to_history("assistant", str(result), {"action": action})
        return {"agent_id": self.agent_id, "status": "completed", "result": result}

    async def _classify(self, params: dict) -> dict:
        method = params.get("method", "random_forest")
        if method in self.class_algorithms:
            return await self._run_algorithm(self.class_algorithms[method], params)
        return {"error": f"Unknown method: {method}", "available": list(self.class_algorithms.keys())}

    async def _supervised(self, params: dict) -> dict:
        """Supervised classification."""
        required = ["input", "training", "method"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        
        method_map = {
            "random_forest": "saga:randomforestclassification",
            "svm": "saga:svmclassification",
            "knn": "saga:knnclassification",
            "maximum_likelihood": "saga:maximumlikelihoodclassification",
            "decision_tree": "saga:decisiontreeclassification",
            "gradient_boost": "saga:gradientboostingclassification",
        }
        algo = method_map.get(params["method"], "saga:randomforestclassification")
        return await self._run_algorithm(algo, params)

    async def _unsupervised(self, params: dict) -> dict:
        """Unsupervised clustering."""
        required = ["input", "n_clusters"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        
        method = params.get("method", "kmeans")
        algo_map = {
            "kmeans": "saga:kmeansclustering",
            "isodata": "saga:isodataclustering",
        }
        algo = algo_map.get(method, "saga:kmeansclustering")
        return await self._run_algorithm(algo, params)

    async def _accuracy(self, params: dict) -> dict:
        """Accuracy assessment."""
        required = ["classified", "reference"]
        for r in required:
            if r not in params:
                return {"error": f"Missing required parameter: {r}"}
        return await self._run_algorithm("saga:confusionmatrix", params)

    async def _segmentation(self, params: dict) -> dict:
        """Image segmentation for object-based classification."""
        if "input" not in params:
            return {"error": "Missing required parameter: input"}
        return await self._run_algorithm("otb:otbsegmentation", params)

    async def _run_algorithm(self, algorithm: str, params: dict) -> dict:
        alg_params = {k: v for k, v in params.items() if k not in ["method", "n_clusters"]}
        return await self.call_tool(
            "qgis.algorithms.execute",
            {"algorithm": algorithm, "parameters": alg_params}
        )