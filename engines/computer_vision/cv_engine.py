"""Universal AI GIS Studio — Computer Vision Engine.

Feature detection, matching, and image registration for landmark detection
and automatic georeferencing. Uses OpenCV where available (cv2 + numpy are
present in this environment). Falls back gracefully if OpenCV is missing.

No coordinates are ever invented; all matches are between image pixels and
trusted reference coordinates supplied by the caller.
"""

import logging
from typing import Optional, Tuple, List, Dict, Any

import numpy as np

logger = logging.getLogger("uagis.computer_vision")

try:
    import cv2
    _CV2 = True
except Exception:  # pragma: no cover
    cv2 = None
    _CV2 = False


class CVEngine:
    def __init__(self):
        self.orb = None
        self.sift = None
        if _CV2:
            self.orb = cv2.ORB_create(nfeatures=2000)
            try:
                self.sift = cv2.SIFT_create()
            except Exception:
                self.sift = None
            logger.info("OpenCV %s available (ORB=%s, SIFT=%s)",
                        cv2.__version__, bool(self.orb), bool(self.sift))
        else:
            logger.warning("OpenCV not available; CV features limited")

    # ------------------------------------------------------------------ #
    # Image loading helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def load_grayscale(path: str) -> np.ndarray:
        import cv2 as _cv2
        img = _cv2.imread(path, _cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {path}")
        return img

    @staticmethod
    def load_color(path: str) -> np.ndarray:
        import cv2 as _cv2
        img = _cv2.imread(path, _cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {path}")
        return img

    # ------------------------------------------------------------------ #
    # Feature detection
    # ------------------------------------------------------------------ #
    def detect_orb(self, image: np.ndarray) -> Tuple[List, Optional[np.ndarray]]:
        if not _CV2 or self.orb is None:
            raise RuntimeError("ORB not available")
        kp, des = self.orb.detectAndCompute(image, None)
        return kp, des

    def detect_sift(self, image: np.ndarray) -> Tuple[List, Optional[np.ndarray]]:
        if not _CV2 or self.sift is None:
            raise RuntimeError("SIFT not available in this OpenCV build")
        kp, des = self.sift.detectAndCompute(image, None)
        return kp, des

    # ------------------------------------------------------------------ #
    # Feature matching
    # ------------------------------------------------------------------ #
    def match_descriptors(self, des1: np.ndarray, des2: np.ndarray,
                          method: str = "orb") -> List[Any]:
        if not _CV2:
            raise RuntimeError("OpenCV not available")
        if method == "sift" and des1.dtype == np.float32:
            matcher = cv2.BFMatcher(cv2.NORM_L2)
        else:
            matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        matches = matcher.knnMatch(des1, des2, k=2)
        # Ratio test (Lowe)
        good = []
        for pair in matches:
            if len(pair) == 2:
                m, n = pair
                if m.distance < 0.75 * n.distance:
                    good.append(m)
        return good

    def match_keypoints(self, kp1: List, kp2: List,
                        matches: List[Any]) -> Tuple[np.ndarray, np.ndarray]:
        src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
        return src_pts, dst_pts

    # ------------------------------------------------------------------ #
    # Image registration / homography with RANSAC
    # ------------------------------------------------------------------ #
    def estimate_homography(self, src_pts: np.ndarray, dst_pts: np.ndarray,
                            ransac_threshold: float = 5.0) -> Dict[str, Any]:
        if not _CV2:
            raise RuntimeError("OpenCV not available")
        if len(src_pts) < 4:
            return {"ok": False, "reason": "need at least 4 points",
                    "inliers": 0, "homography": None}
        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, ransac_threshold)
        inliers = int(mask.sum()) if mask is not None else 0
        return {"ok": H is not None, "homography": H,
                "inliers": inliers, "total": len(src_pts),
                "inlier_ratio": inliers / max(1, len(src_pts))}

    # ------------------------------------------------------------------ #
    # Template matching
    # ------------------------------------------------------------------ #
    def template_match(self, image: np.ndarray, template: np.ndarray,
                       method: int = None) -> Dict[str, Any]:
        if not _CV2:
            raise RuntimeError("OpenCV not available")
        if method is None:
            method = cv2.TM_CCOEFF_NORMED
        res = cv2.matchTemplate(image, template, method)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        return {
            "ok": True,
            "confidence": float(max_val),
            "location": [int(max_loc[0]), int(max_loc[1])],
            "match_size": [int(template.shape[1]), int(template.shape[0])],
        }

    # ------------------------------------------------------------------ #
    # Image similarity
    # ------------------------------------------------------------------ #
    def image_similarity(self, img1: np.ndarray, img2: np.ndarray) -> float:
        if not _CV2:
            return 0.0
        # Resize to same size, compare histograms
        h, w = min(img1.shape[0], img2.shape[0]), min(img1.shape[1], img2.shape[1])
        a = cv2.resize(img1, (w, h))
        b = cv2.resize(img2, (w, h))
        ha = cv2.calcHist([a], [0], None, [256], [0, 256])
        hb = cv2.calcHist([b], [0], None, [256], [0, 256])
        return float(cv2.compareHist(ha, hb, cv2.HISTCMP_CORREL))

    # ------------------------------------------------------------------ #
    # Image quality metrics
    # ------------------------------------------------------------------ #
    def quality_metrics(self, image: np.ndarray) -> Dict[str, float]:
        if not _CV2:
            return {"sharpness": 0.0, "contrast": 0.0, "brightness": 0.0}
        laplacian = cv2.Laplacian(image, cv2.CV_64F)
        sharpness = float(laplacian.var())
        contrast = float(image.std())
        brightness = float(image.mean())
        return {"sharpness": sharpness, "contrast": contrast, "brightness": brightness}


cv_engine = CVEngine()
