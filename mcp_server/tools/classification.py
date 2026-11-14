"""MCP tool implementations for qgis.classification namespace — 11 image classification tools."""

from mcp_server.qgis_client import QgisBridgeClient
from core.logging import get_logger

logger = get_logger("mcp.tools.classification")


def _dispatch(tool: str, params: dict, request_id: str) -> dict:
    client = QgisBridgeClient()
    return client.dispatch(tool, params or {}, request_id=request_id)


def classification_train_samples(params: dict) -> dict:
    """Generate training samples for supervised classification."""
    return _dispatch("qgis.classification.train_samples", params, request_id="cls_train_samples")


def classification_supervised_classify(params: dict) -> dict:
    """Perform supervised classification (RF, SVM, ML, etc.)."""
    return _dispatch("qgis.classification.supervised_classify", params, request_id="cls_supervised_classify")


def classification_unsupervised_classify(params: dict) -> dict:
    """Perform unsupervised classification (K-means, ISODATA)."""
    return _dispatch("qgis.classification.unsupervised_classify", params, request_id="cls_unsupervised_classify")


def classification_random_forest(params: dict) -> dict:
    """Random Forest classification with training and prediction."""
    return _dispatch("qgis.classification.random_forest", params, request_id="cls_random_forest")


def classification_svm(params: dict) -> dict:
    """Support Vector Machine classification."""
    return _dispatch("qgis.classification.svm", params, request_id="cls_svm")


def classification_maximum_likelihood(params: dict) -> dict:
    """Maximum Likelihood classification."""
    return _dispatch("qgis.classification.maximum_likelihood", params, request_id="cls_maximum_likelihood")


def classification_knn(params: dict) -> dict:
    """K-Nearest Neighbors classification."""
    return _dispatch("qgis.classification.knn", params, request_id="cls_knn")


def classification_decision_tree(params: dict) -> dict:
    """Decision Tree classification."""
    return _dispatch("qgis.classification.decision_tree", params, request_id="cls_decision_tree")


def classification_neural_network(params: dict) -> dict:
    """Neural Network / MLP classification."""
    return _dispatch("qgis.classification.neural_network", params, request_id="cls_neural_network")


def classification_accuracy_assessment(params: dict) -> dict:
    """Assess classification accuracy (confusion matrix, kappa, OA, PA, UA)."""
    return _dispatch("qgis.classification.accuracy_assessment", params, request_id="cls_accuracy_assessment")


def classification_confusion_matrix(params: dict) -> dict:
    """Generate confusion matrix from classified and reference data."""
    return _dispatch("qgis.classification.confusion_matrix", params, request_id="cls_confusion_matrix")


def classification_post_filter(params: dict) -> dict:
    """Post-classification filtering (majority filter, sieve)."""
    return _dispatch("qgis.classification.post_filter", params, request_id="cls_post_filter")


def classification_reclassify(params: dict) -> dict:
    """Reclassify thematic raster (merge/split classes)."""
    return _dispatch("qgis.classification.reclassify", params, request_id="cls_reclassify")