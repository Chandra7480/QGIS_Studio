"""Universal AI GIS Studio — Visual Verification Engine.

Provides SSIM-based image comparison, AI-assisted diff analysis,
and difference highlighting for visual regression testing.
"""

import io
import logging
import base64
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageStat

from core.logging import get_logger

logger = get_logger("uagis.visual_verification")


class ComparisonResult(Enum):
    """Result of visual comparison."""
    IDENTICAL = "identical"
    SIMILAR = "similar"
    DIFFERENT = "different"
    ERROR = "error"


@dataclass
class DiffRegion:
    """A region where differences were detected."""
    x: int
    y: int
    width: int
    height: int
    score: float  # 0.0 = identical, 1.0 = completely different
    pixel_diff_count: int
    max_pixel_diff: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VisualComparisonResult:
    """Complete result of a visual comparison."""
    result: ComparisonResult
    ssim_score: float  # 0.0 to 1.0 (1.0 = identical)
    mse: float  # Mean Squared Error
    diff_regions: List[DiffRegion] = field(default_factory=list)
    diff_image_base64: Optional[str] = None
    highlighted_base64: Optional[str] = None
    reference_width: int = 0
    reference_height: int = 0
    test_width: int = 0
    test_height: int = 0
    comparison_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result": self.result.value,
            "ssim_score": self.ssim_score,
            "mse": self.mse,
            "diff_regions": [r.to_dict() for r in self.diff_regions],
            "diff_image_base64": self.diff_image_base64,
            "highlighted_base64": self.highlighted_base64,
            "reference_width": self.reference_width,
            "reference_height": self.reference_height,
            "test_width": self.test_width,
            "test_height": self.test_height,
            "comparison_time_ms": self.comparison_time_ms,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VisualComparisonResult":
        return cls(
            result=ComparisonResult(d["result"]),
            ssim_score=d["ssim_score"],
            mse=d["mse"],
            diff_regions=[DiffRegion(**r) for r in d.get("diff_regions", [])],
            diff_image_base64=d.get("diff_image_base64"),
            highlighted_base64=d.get("highlighted_base64"),
            reference_width=d.get("reference_width", 0),
            reference_height=d.get("reference_height", 0),
            test_width=d.get("test_width", 0),
            test_height=d.get("test_height", 0),
            comparison_time_ms=d.get("comparison_time_ms", 0.0),
            metadata=d.get("metadata", {}),
        )


class VisualVerificationEngine:
    """Engine for visual comparison and verification."""

    def __init__(self):
        self._default_threshold = 0.95  # SSIM threshold for "similar"
        self._diff_threshold = 30  # Pixel difference threshold (0-255)
        self._min_region_size = 10  # Minimum diff region size in pixels

    def compare_images(self, reference: Image.Image, test: Image.Image,
                       threshold: float = None,
                       generate_diff: bool = True,
                       generate_highlighted: bool = True,
                       ignore_regions: List[Tuple[int, int, int, int]] = None) -> VisualComparisonResult:
        """
        Compare two images using SSIM and pixel difference.

        Args:
            reference: Reference (expected) image
            test: Test (actual) image
            threshold: SSIM threshold (0-1), defaults to 0.95
            generate_diff: Whether to generate diff image
            generate_highlighted: Whether to generate highlighted reference
            ignore_regions: List of (x, y, w, h) regions to ignore

        Returns:
            VisualComparisonResult with detailed analysis
        """
        start_time = time.time()
        threshold = threshold or self._default_threshold

        # Ensure same size
        if reference.size != test.size:
            # Resize test to match reference
            test = test.resize(reference.size, Image.Resampling.LANCZOS)
            logger.warning("Test image resized to match reference: %s -> %s",
                          test.size, reference.size)

        ref_width, ref_height = reference.size

        # Convert to numpy arrays
        ref_arr = np.array(reference.convert("RGB"), dtype=np.float32)
        test_arr = np.array(test.convert("RGB"), dtype=np.float32)

        # Apply ignore regions
        if ignore_regions:
            for x, y, w, h in ignore_regions:
                x = max(0, min(x, ref_width - 1))
                y = max(0, min(y, ref_height - 1))
                w = max(1, min(w, ref_width - x))
                h = max(1, min(h, ref_height - y))
                ref_arr[y:y+h, x:x+w] = test_arr[y:y+h, x:x+w]

        # Calculate MSE
        mse = np.mean((ref_arr - test_arr) ** 2)

        # Calculate SSIM
        ssim_score = self._calculate_ssim(ref_arr, test_arr)

        # Determine result
        if ssim_score >= 0.9999:
            result = ComparisonResult.IDENTICAL
        elif ssim_score >= threshold:
            result = ComparisonResult.SIMILAR
        else:
            result = ComparisonResult.DIFFERENT

        # Find diff regions
        diff_regions = self._find_diff_regions(ref_arr, test_arr)

        # Generate diff image
        diff_image_b64 = None
        if generate_diff:
            diff_image = self._create_diff_image(ref_arr, test_arr)
            diff_image_b64 = self._image_to_base64(diff_image)

        # Generate highlighted reference
        highlighted_b64 = None
        if generate_highlighted and diff_regions:
            highlighted = self._create_highlighted_image(reference, diff_regions)
            highlighted_b64 = self._image_to_base64(highlighted)

        comparison_time = (time.time() - start_time) * 1000

        return VisualComparisonResult(
            result=result,
            ssim_score=ssim_score,
            mse=mse,
            diff_regions=diff_regions,
            diff_image_base64=diff_image_b64,
            highlighted_base64=highlighted_b64,
            reference_width=ref_width,
            reference_height=ref_height,
            test_width=test.size[0],
            test_height=test.size[1],
            comparison_time_ms=comparison_time,
            metadata={
                "threshold_used": threshold,
                "ignore_regions_count": len(ignore_regions) if ignore_regions else 0,
            }
        )

    def _calculate_ssim(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """Calculate Structural Similarity Index (SSIM)."""
        # Simplified SSIM implementation
        # Based on: https://en.wikipedia.org/wiki/Structural_similarity

        C1 = (0.01 * 255) ** 2
        C2 = (0.03 * 255) ** 2

        # Calculate means
        mu1 = np.mean(img1, axis=(0, 1))
        mu2 = np.mean(img2, axis=(0, 1))

        # Calculate variances and covariance
        sigma1_sq = np.var(img1, axis=(0, 1))
        sigma2_sq = np.var(img2, axis=(0, 1))
        sigma12 = np.mean((img1 - mu1) * (img2 - mu2), axis=(0, 1))

        # SSIM per channel
        ssim_num = (2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)
        ssim_den = (mu1**2 + mu2**2 + C1) * (sigma1_sq + sigma2_sq + C2)
        ssim_per_channel = ssim_num / ssim_den

        # Average across channels
        return float(np.mean(ssim_per_channel))

    def _find_diff_regions(self, ref_arr: np.ndarray, test_arr: np.ndarray) -> List[DiffRegion]:
        """Find connected regions of difference."""
        # Calculate absolute difference
        diff = np.abs(ref_arr.astype(np.int16) - test_arr.astype(np.int16))
        diff_max = np.max(diff, axis=2)  # Max across channels

        # Threshold
        threshold = self._diff_threshold
        diff_mask = diff_max > threshold

        if not np.any(diff_mask):
            return []

        # Find connected components
        regions = self._connected_components(diff_mask, diff_max)
        return regions

    def _connected_components(self, mask: np.ndarray, diff_values: np.ndarray) -> List[DiffRegion]:
        """Find connected components in binary mask."""
        from scipy import ndimage

        # Label connected components
        labeled, num_features = ndimage.label(mask)

        regions = []
        for i in range(1, num_features + 1):
            component_mask = labeled == i
            coords = np.where(component_mask)

            if len(coords[0]) == 0:
                continue

            y_min, y_max = coords[0].min(), coords[0].max()
            x_min, x_max = coords[1].min(), coords[1].max()

            width = x_max - x_min + 1
            height = y_max - y_min + 1

            # Filter small regions
            if width < self._min_region_size or height < self._min_region_size:
                continue

            pixel_count = np.sum(component_mask)
            max_diff = np.max(diff_values[component_mask])
            avg_diff = np.mean(diff_values[component_mask])
            score = min(1.0, avg_diff / 255.0)

            regions.append(DiffRegion(
                x=int(x_min),
                y=int(y_min),
                width=int(width),
                height=int(height),
                score=float(score),
                pixel_diff_count=int(pixel_count),
                max_pixel_diff=int(max_diff),
            ))

        # Sort by score descending (most different first)
        regions.sort(key=lambda r: -r.score)
        return regions

    def _create_diff_image(self, ref_arr: np.ndarray, test_arr: np.ndarray) -> Image.Image:
        """Create a visual diff image (red = different)."""
        diff = np.abs(ref_arr.astype(np.int16) - test_arr.astype(np.int16))
        diff_max = np.max(diff, axis=2)

        # Create RGB diff image
        diff_img = np.zeros((*ref_arr.shape[:2], 3), dtype=np.uint8)

        # Red channel for differences
        diff_img[:, :, 0] = np.clip(diff_max * 2, 0, 255).astype(np.uint8)

        # Green channel for reference (dimmed)
        diff_img[:, :, 1] = (ref_arr[:, :, 1] * 0.3).astype(np.uint8)

        # Blue channel for test (dimmed)
        diff_img[:, :, 2] = (test_arr[:, :, 2] * 0.3).astype(np.uint8)

        return Image.fromarray(diff_img, "RGB")

    def _create_highlighted_image(self, reference: Image.Image,
                                   regions: List[DiffRegion]) -> Image.Image:
        """Create reference image with diff regions highlighted."""
        highlighted = reference.copy().convert("RGBA")
        draw = ImageDraw.Draw(highlighted)

        for region in regions:
            # Draw rectangle around diff region
            x, y, w, h = region.x, region.y, region.width, region.height

            # Color based on severity (red = high diff)
            intensity = int(region.score * 255)
            color = (255, 255 - intensity, 0, 180)  # Yellow to red

            draw.rectangle([x, y, x + w, y + h], outline=color, width=3)

            # Add score label
            label = f"{region.score:.2f}"
            try:
                draw.text((x, y - 20), label, fill=(255, 255, 255, 255))
            except Exception:
                pass

        return highlighted.convert("RGB")

    def _image_to_base64(self, image: Image.Image, format: str = "PNG") -> str:
        """Convert PIL image to base64 string."""
        buf = io.BytesIO()
        image.save(buf, format=format)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def compare_from_base64(self, reference_b64: str, test_b64: str,
                            **kwargs) -> VisualComparisonResult:
        """Compare images from base64 strings."""
        ref_img = self._base64_to_image(reference_b64)
        test_img = self._base64_to_image(test_b64)
        return self.compare_images(ref_img, test_img, **kwargs)

    def _base64_to_image(self, b64: str) -> Image.Image:
        """Convert base64 string to PIL Image."""
        img_data = base64.b64decode(b64)
        return Image.open(io.BytesIO(img_data))

    def compare_files(self, reference_path: str, test_path: str,
                      **kwargs) -> VisualComparisonResult:
        """Compare images from file paths."""
        ref_img = Image.open(reference_path)
        test_img = Image.open(test_path)
        return self.compare_images(ref_img, test_img, **kwargs)

    def batch_compare(self, reference_dir: str, test_dir: str,
                      pattern: str = "*.png",
                      threshold: float = None) -> List[Dict[str, Any]]:
        """Batch compare images in two directories."""
        ref_dir = Path(reference_dir)
        test_dir = Path(test_dir)

        results = []
        for ref_file in ref_dir.glob(pattern):
            test_file = test_dir / ref_file.name
            if test_file.exists():
                try:
                    result = self.compare_files(str(ref_file), str(test_file),
                                                threshold=threshold)
                    results.append({
                        "file": ref_file.name,
                        "result": result.to_dict(),
                    })
                except Exception as exc:
                    logger.error("Failed to compare %s: %s", ref_file.name, exc)
                    results.append({
                        "file": ref_file.name,
                        "error": str(exc),
                    })
            else:
                results.append({
                    "file": ref_file.name,
                    "error": "Test file not found",
                })

        return results


class AIDiffAnalyzer:
    """AI-assisted diff analysis for intelligent difference interpretation."""

    def __init__(self, api_provider=None):
        self.api_provider = api_provider  # Optional AI provider for analysis

    def analyze_diff(self, comparison: VisualComparisonResult,
                     context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze diff regions and provide intelligent interpretation.

        Returns:
            Dict with analysis, suggested actions, and severity assessment
        """
        analysis = {
            "summary": self._generate_summary(comparison),
            "severity": self._assess_severity(comparison),
            "categories": self._categorize_diffs(comparison),
            "suggestions": self._generate_suggestions(comparison),
            "false_positive_likelihood": self._estimate_false_positive(comparison),
        }

        # If AI provider available, enhance with AI analysis
        if self.api_provider and comparison.diff_regions:
            ai_analysis = self._ai_analyze(comparison, context)
            analysis["ai_analysis"] = ai_analysis

        return analysis

    def _generate_summary(self, comparison: VisualComparisonResult) -> str:
        """Generate human-readable summary."""
        if comparison.result == ComparisonResult.IDENTICAL:
            return "Images are identical (SSIM: {:.4f})".format(comparison.ssim_score)
        elif comparison.result == ComparisonResult.SIMILAR:
            return "Images are similar (SSIM: {:.4f}, {} diff regions)".format(
                comparison.ssim_score, len(comparison.diff_regions))
        else:
            return "Images are significantly different (SSIM: {:.4f}, {} diff regions)".format(
                comparison.ssim_score, len(comparison.diff_regions))

    def _assess_severity(self, comparison: VisualComparisonResult) -> str:
        """Assess overall severity of differences."""
        if comparison.result == ComparisonResult.IDENTICAL:
            return "none"

        # Count high-severity regions
        high_severity = sum(1 for r in comparison.diff_regions if r.score > 0.5)
        total_pixels = comparison.reference_width * comparison.reference_height
        diff_pixels = sum(r.pixel_diff_count for r in comparison.diff_regions)
        diff_ratio = diff_pixels / total_pixels if total_pixels > 0 else 0

        if high_severity > 5 or diff_ratio > 0.1:
            return "critical"
        elif high_severity > 2 or diff_ratio > 0.05:
            return "high"
        elif high_severity > 0 or diff_ratio > 0.01:
            return "medium"
        else:
            return "low"

    def _categorize_diffs(self, comparison: VisualComparisonResult) -> Dict[str, int]:
        """Categorize diff regions by type (heuristic)."""
        categories = {
            "color_shift": 0,
            "content_change": 0,
            "position_shift": 0,
            "noise": 0,
            "ui_change": 0,
            "unknown": 0,
        }

        for region in comparison.diff_regions:
            # Simple heuristics based on region properties
            if region.max_pixel_diff < 50:
                categories["noise"] += 1
            elif region.width > comparison.reference_width * 0.5:
                categories["ui_change"] += 1
            elif region.score > 0.7:
                categories["content_change"] += 1
            elif region.score > 0.3:
                categories["color_shift"] += 1
            else:
                categories["unknown"] += 1

        return categories

    def _generate_suggestions(self, comparison: VisualComparisonResult) -> List[str]:
        """Generate actionable suggestions."""
        suggestions = []

        if comparison.result == ComparisonResult.IDENTICAL:
            suggestions.append("No action needed - images match perfectly")
            return suggestions

        if len(comparison.diff_regions) == 0:
            suggestions.append("Overall difference detected but no distinct regions - may be global color/brightness change")
        else:
            for region in comparison.diff_regions[:3]:  # Top 3 regions
                if region.score > 0.7:
                    suggestions.append(f"Major content change at ({region.x},{region.y}) size {region.width}x{region.height} - verify intentional")
                elif region.score > 0.3:
                    suggestions.append(f"Moderate change at ({region.x},{region.y}) - check for UI updates")

        if comparison.mse > 1000:
            suggestions.append("High MSE indicates significant pixel-level differences")

        return suggestions

    def _estimate_false_positive(self, comparison: VisualComparisonResult) -> float:
        """Estimate likelihood of false positive (0-1)."""
        # Heuristic: small, low-score regions are more likely to be false positives
        if not comparison.diff_regions:
            return 0.0

        small_regions = sum(1 for r in comparison.diff_regions
                           if r.width * r.height < 100 and r.score < 0.3)
        total_regions = len(comparison.diff_regions)

        return min(0.9, small_regions / max(1, total_regions))

    def _ai_analyze(self, comparison: VisualComparisonResult,
                    context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Use AI provider for advanced analysis (placeholder)."""
        # This would call an AI service with the diff image and context
        # For now, return placeholder
        return {
            "analysis": "AI analysis not configured - set api_provider to enable",
            "confidence": 0.0,
        }


# Convenience functions
def create_verification_engine() -> VisualVerificationEngine:
    return VisualVerificationEngine()


def create_ai_analyzer(api_provider=None) -> AIDiffAnalyzer:
    return AIDiffAnalyzer(api_provider)


def compare_images(reference: Image.Image, test: Image.Image,
                   threshold: float = 0.95) -> VisualComparisonResult:
    """Quick compare function."""
    engine = create_verification_engine()
    return engine.compare_images(reference, test, threshold=threshold)


if __name__ == "__main__":  # pragma: no cover
    # Demo
    engine = create_verification_engine()

    # Create test images
    ref = Image.new("RGB", (400, 300), color="white")
    draw = ImageDraw.Draw(ref)
    draw.rectangle([50, 50, 150, 150], fill="blue")
    draw.rectangle([200, 100, 300, 200], fill="red")

    test = ref.copy()
    draw = ImageDraw.Draw(test)
    draw.rectangle([50, 50, 150, 150], fill="green")  # Changed color
    draw.ellipse([300, 50, 350, 100], fill="yellow")  # Added element

    # Compare
    result = engine.compare_images(ref, test)
    print(f"Result: {result.result.value}")
    print(f"SSIM: {result.ssim_score:.4f}")
    print(f"MSE: {result.mse:.2f}")
    print(f"Diff regions: {len(result.diff_regions)}")
    for r in result.diff_regions:
        print(f"  Region: ({r.x},{r.y}) {r.width}x{r.height} score={r.score:.3f}")

    # Analyze
    analyzer = create_ai_analyzer()
    analysis = analyzer.analyze_diff(result)
    print(f"\nSeverity: {analysis['severity']}")
    print(f"Categories: {analysis['categories']}")
    print(f"Suggestions: {analysis['suggestions']}")