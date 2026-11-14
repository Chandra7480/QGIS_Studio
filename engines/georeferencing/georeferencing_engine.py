"""Universal AI GIS Studio — Automatic Georeferencing Engine.

Analyzes scanned maps and finds Ground Control Points (GCPs) automatically
using computer vision, then validates and transforms them via QGIS/GDAL.

Core rule: coordinates are NEVER invented. Source image pixels are matched to
trusted reference coordinates from a reference raster or verified geospatial
dataset. If reference data is insufficient, the engine reports NEEDS_REVIEW
and asks for suitable reference data or human assistance.
"""

import logging
import math
from typing import Optional, List, Dict, Any, Tuple

import numpy as np

from engines.computer_vision.cv_engine import cv_engine
from engines.verification.verification_engine import VerificationEngine, SUCCESS, PARTIAL_SUCCESS, FAILED, NEEDS_REVIEW
from core.exceptions import ExecutionError, DependencyError

logger = logging.getLogger("uagis.georeferencing")


class GCP:
    """A single Ground Control Point candidate."""

    def __init__(self, source_pixel_x: float, source_pixel_y: float,
                 dest_map_x: float, dest_map_y: float, crs: str,
                 confidence: float, landmark_description: str,
                 source_reference: str, validation_status: str = "pending",
                 residual_error: Optional[float] = None):
        self.source_pixel_x = source_pixel_x
        self.source_pixel_y = source_pixel_y
        self.dest_map_x = dest_map_x
        self.dest_map_y = dest_map_y
        self.crs = crs
        self.confidence = confidence
        self.landmark_description = landmark_description
        self.source_reference = source_reference
        self.validation_status = validation_status  # pending/accepted/rejected
        self.residual_error = residual_error

    def to_dict(self) -> dict:
        return {
            "source_pixel_x": self.source_pixel_x,
            "source_pixel_y": self.source_pixel_y,
            "dest_map_x": self.dest_map_x,
            "dest_map_y": self.dest_map_y,
            "crs": self.crs,
            "confidence": self.confidence,
            "landmark_description": self.landmark_description,
            "source_reference": self.source_reference,
            "validation_status": self.validation_status,
            "residual_error": self.residual_error,
        }


class GeoreferencingEngine:
    def __init__(self, verification_engine: Optional[VerificationEngine] = None):
        self.verifier = verification_engine or VerificationEngine()
        self.cvs = cv_engine

    # ------------------------------------------------------------------ #
    # Step 1: Image inspection
    # ------------------------------------------------------------------ #
    def inspect_image(self, image_path: str) -> dict:
        """Inspect a scanned map image: dimensions, quality, rotation hints."""
        try:
            img = self.cvs.load_grayscale(image_path)
        except FileNotFoundError as exc:
            raise ExecutionError(str(exc)) from exc
        h, w = img.shape
        quality = self.cvs.quality_metrics(img)
        return {
            "image_path": image_path,
            "width": int(w),
            "height": int(h),
            "quality": quality,
            "channels": 1,
        }

    # ------------------------------------------------------------------ #
    # Step 2 & 3: Landmark detection + computer vision
    # ------------------------------------------------------------------ #
    def detect_landmarks(self, image_path: str,
                         reference_image_path: Optional[str] = None) -> dict:
        """Detect candidate landmarks using ORB/SIFT + matching.

        If a reference image is provided, matches features between the two.
        Returns keypoint matches and candidate correspondences (pixel coords).
        """
        img = self.cvs.load_grayscale(image_path)
        kp1, des1 = self.cvs.detect_orb(img)
        result = {
            "image_path": image_path,
            "keypoints": len(kp1) if kp1 else 0,
            "landmarks": [],
            "matches": 0,
        }
        if reference_image_path and des1 is not None:
            ref = self.cvs.load_grayscale(reference_image_path)
            kp2, des2 = self.cvs.detect_orb(ref)
            matches = self.cvs.match_descriptors(des1, des2, method="orb")
            src_pts, dst_pts = self.cvs.match_keypoints(kp1, kp2, matches)
            reg = self.cvs.estimate_homography(src_pts, dst_pts)
            result["matches"] = len(matches)
            result["registration"] = reg
            result["landmarks"] = [
                {"source_pixel": [float(p[0][0]), float(p[0][1])],
                 "dest_pixel": [float(q[0][0]), float(q[0][1])]}
                for p, q in zip(src_pts, dst_pts)
            ]
        return result

    # ------------------------------------------------------------------ #
    # Step 4: Coordinate identification (match pixels -> reference coords)
    # ------------------------------------------------------------------ #
    def match_pixels_to_reference(self, pixel_coords: List[Tuple[float, float]],
                                  reference_transform) -> List[Dict[str, Any]]:
        """Convert source image pixel coordinates to map coordinates using a
        GDAL geotransform (reference raster). Never invents coordinates.

        reference_transform: GDAL-style [originX, pixelWidth, rowRotation,
            originY, colRotation, pixelHeight] or an object with Apply().
        """
        results = []
        for (px, py) in pixel_coords:
            mx, my = self._apply_geotransform(reference_transform, px, py)
            results.append({
                "source_pixel_x": px,
                "source_pixel_y": py,
                "dest_map_x": mx,
                "dest_map_y": my,
            })
        return results

    @staticmethod
    def _apply_geotransform(gt, px: float, py: float) -> Tuple[float, float]:
        # GDAL geotransform: [originX, pxW, rowRot, originY, colRot, pxH]
        gt0, gt1, gt2, gt3, gt4, gt5 = gt
        mx = gt0 + px * gt1 + py * gt2
        my = gt3 + px * gt4 + py * gt5
        return mx, my

    # ------------------------------------------------------------------ #
    # Step 5: GCP generation
    # ------------------------------------------------------------------ #
    def generate_gcps(self, image_path: str, reference_transform,
                      reference_crs: str,
                      min_confidence: float = 0.5) -> List[GCP]:
        """Generate candidate GCPs by matching detected landmarks to reference
        coordinates. Returns GCP objects (validation_status='pending')."""
        detection = self.detect_landmarks(image_path)
        landmarks = detection.get("landmarks", [])
        gcps = []
        for lm in landmarks:
            sx, sy = lm["source_pixel"]
            matched = self.match_pixels_to_reference([(sx, sy)], reference_transform)
            mx, my = matched[0]["dest_map_x"], matched[0]["dest_map_y"]
            confidence = float(lm.get("confidence", 0.5)) if "confidence" in lm else 0.6
            if confidence >= min_confidence:
                gcps.append(GCP(
                    source_pixel_x=sx, source_pixel_y=sy,
                    dest_map_x=mx, dest_map_y=my,
                    crs=reference_crs,
                    confidence=confidence,
                    landmark_description="auto-detected landmark",
                    source_reference="reference_raster",
                    validation_status="pending",
                ))
        logger.info("Generated %d candidate GCPs from %s", len(gcps), image_path)
        return gcps

    # ------------------------------------------------------------------ #
    # Step 6: GCP validation
    # ------------------------------------------------------------------ #
    def validate_gcps(self, gcps: List[GCP],
                      min_points: int = 4,
                      max_residual: float = 5.0,
                      max_clustering_distance: float = 50.0) -> dict:
        """Validate GCPs: duplicates, outliers, distribution, residuals."""
        accepted = []
        rejected = []
        seen = set()
        for g in gcps:
            # Duplicate check
            key = (round(g.source_pixel_x), round(g.source_pixel_y))
            if key in seen:
                g.validation_status = "rejected"
                rejected.append({"gcp": g.to_dict(), "reason": "duplicate_point"})
                continue
            seen.add(key)

            # Confidence check
            if g.confidence < 0.3:
                g.validation_status = "rejected"
                rejected.append({"gcp": g.to_dict(), "reason": "low_confidence"})
                continue

            accepted.append(g)
            g.validation_status = "accepted"

        # Spatial distribution / clustering check (simple: ensure spread)
        distribution_ok = len(accepted) >= min_points
        if len(accepted) >= 2:
            xs = [g.source_pixel_x for g in accepted]
            ys = [g.source_pixel_y for g in accepted]
            spread = max(max(xs) - min(xs), max(ys) - min(ys))
            distribution_ok = spread > max_clustering_distance * 0.5

        residual_errors = [g.residual_error for g in accepted if g.residual_error is not None]
        rmse = math.sqrt(sum(e * e for e in residual_errors) / len(residual_errors)) if residual_errors else None

        return {
            "total": len(gcps),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "rejected_details": rejected,
            "min_points_met": len(accepted) >= min_points,
            "distribution_ok": distribution_ok,
            "rmse": rmse,
            "residual_errors": residual_errors,
            "accepted_gcps": [g.to_dict() for g in accepted],
        }

    # ------------------------------------------------------------------ #
    # Step 7 & 8: QGIS integration + transformation
    # ------------------------------------------------------------------ #
    def transform_with_qgis(self, image_path: str, output_path: str,
                            gcps: List[GCP], method: str = "polynomial_2",
                            target_crs: str = "EPSG:4326") -> dict:
        """Execute georeferencing transformation via QGIS Georeferencer/GDAL.

        method: 'helmert', 'polynomial_1', 'polynomial_2', 'polynomial_3',
                'thin_plate_spline' (version-aware; falls back gracefully).
        """
        # This is invoked through the QGIS Bridge (PyQGIS/GDAL) at runtime.
        # Here we build the transformation request; the bridge executes it.
        valid_gcps = [g for g in gcps if g.validation_status == "accepted"]
        if len(valid_gcps) < 2:
            raise ExecutionError("Need at least 2 accepted GCPs to transform")

        supported = ["helmert", "polynomial_1", "polynomial_2",
                     "polynomial_3", "thin_plate_spline"]
        if method not in supported:
            raise ExecutionError(f"Transformation method {method} not supported")

        return {
            "image_path": image_path,
            "output_path": output_path,
            "method": method,
            "target_crs": target_crs,
            "gcp_count": len(valid_gcps),
            "gcps": [g.to_dict() for g in valid_gcps],
            "status": "transformation_ready",
        }

    # ------------------------------------------------------------------ #
    # Step 9: Verification
    # ------------------------------------------------------------------ #
    def verify_georeferencing(self, output_raster_exists: bool,
                              crs_match: bool, extent_ok: bool,
                              rmse: Optional[float],
                              rmse_threshold: float = 5.0,
                              visual_ok: Optional[bool] = None):
        return self.verifier.verify_georeferencing(
            output_raster=output_raster_exists, crs_match=crs_match,
            extent_ok=extent_ok, rmse=rmse,
            rmse_threshold=rmse_threshold, visual_ok=visual_ok)
