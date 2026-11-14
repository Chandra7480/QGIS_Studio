"""Visual Regression Engine for Universal AI GIS Studio.

Provides perceptual hash (pHash) and pixel-diff comparison for screenshot testing.
Supports baseline management with UPDATE_BASELINES environment variable.

Usage:
    engine = VisualRegressionEngine(baseline_dir)
    result = engine.compare("tool_name", current_base64)
    assert result.similar, f"Visual regression: {result}"
"""

import base64
import io
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageChops, ImageStat

try:
    import imagehash
    IMAGEHASH_AVAILABLE = True
except ImportError:
    IMAGEHASH_AVAILABLE = False


@dataclass
class VisualDiffResult:
    """Result of visual comparison."""
    similar: bool
    phash_distance: int
    pixel_diff_ratio: float
    diff_image_base64: Optional[str] = None
    baseline_image_base64: Optional[str] = None
    current_image_base64: Optional[str] = None
    baseline_path: Optional[Path] = None
    test_name: str = ""

    def __str__(self) -> str:
        return (f"VisualDiffResult(similar={self.similar}, "
                f"phash_dist={self.phash_distance}, "
                f"pixel_diff={self.pixel_diff_ratio:.4f}, "
                f"test={self.test_name})")


class VisualRegressionEngine:
    """Visual regression testing using perceptual hashing and pixel diff."""

    def __init__(
        self,
        baseline_dir: Path,
        phash_threshold: int = 5,
        pixel_threshold: float = 0.01,
        hash_size: int = 8,
        update_baselines: bool = False,
    ):
        """
        Args:
            baseline_dir: Directory to store/load baseline images
            phash_threshold: Maximum Hamming distance for pHash (0-64, default 5)
            pixel_threshold: Maximum pixel difference ratio (0.0-1.0, default 0.01 = 1%)
            hash_size: pHash hash size (8 = 64 bits, 16 = 256 bits)
            update_baselines: If True, always update baselines (env var UPDATE_BASELINES=1)
        """
        if not IMAGEHASH_AVAILABLE:
            raise ImportError(
                "imagehash library required for visual regression. "
                "Install with: pip install imagehash"
            )

        self.baseline_dir = Path(baseline_dir)
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.phash_threshold = phash_threshold
        self.pixel_threshold = pixel_threshold
        self.hash_size = hash_size
        self.update_baselines = update_baselines or os.environ.get("UPDATE_BASELINES", "0") == "1"

        # Platform-specific subdirectory for cross-platform baseline management
        self.platform = platform.system().lower()
        self.platform_dir = self.baseline_dir / self.platform
        self.platform_dir.mkdir(parents=True, exist_ok=True)

    def _load_image(self, image_base64: str) -> Image.Image:
        """Load PIL Image from base64 string."""
        data = base64.b64decode(image_base64)
        return Image.open(io.BytesIO(data))

    def _image_to_base64(self, image: Image.Image, format: str = "PNG") -> str:
        """Convert PIL Image to base64 string."""
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return base64.b64encode(buffer.getvalue()).decode()

    def _save_baseline(self, test_name: str, image: Image.Image) -> Path:
        """Save baseline image."""
        path = self.platform_dir / f"{test_name}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, "PNG")
        return path

    def _load_baseline(self, test_name: str) -> Optional[Image.Image]:
        """Load baseline image if exists."""
        path = self.platform_dir / f"{test_name}.png"
        if path.exists():
            return Image.open(path)
        return None

    def _compute_phash(self, image: Image.Image) -> imagehash.ImageHash:
        """Compute perceptual hash of image."""
        # Convert to RGB if needed (pHash works on RGB)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        return imagehash.phash(image, hash_size=self.hash_size)

    def _compute_pixel_diff(self, img1: Image.Image, img2: Image.Image) -> Tuple[float, Image.Image]:
        """Compute pixel difference ratio and diff image."""
        # Ensure same size and mode
        if img1.size != img2.size:
            img2 = img2.resize(img1.size, Image.Resampling.LANCZOS)
        if img1.mode != img2.mode:
            img2 = img2.convert(img1.mode)

        # Compute difference
        diff = ImageChops.difference(img1, img2)

        # Count different pixels
        stat = ImageStat.Stat(diff)
        # For RGB, sum of mean across channels
        if isinstance(stat.mean, (list, tuple)):
            total_diff = sum(stat.mean)
            max_possible = 255 * len(stat.mean)
        else:
            total_diff = stat.mean
            max_possible = 255

        diff_ratio = total_diff / max_possible if max_possible > 0 else 0.0

        # Create visual diff image (red for differences)
        diff_rgb = diff.convert("RGB")
        # Enhance differences for visibility
        enhancer = Image.eval(diff_rgb, lambda x: min(x * 10, 255))
        return diff_ratio, enhancer

    def compare(
        self,
        test_name: str,
        current_base64: str,
        update_baseline: Optional[bool] = None,
    ) -> VisualDiffResult:
        """
        Compare current screenshot with baseline.

        Args:
            test_name: Unique test identifier (used as baseline filename)
            current_base64: Current screenshot as base64 PNG
            update_baseline: Override update_baselines setting for this comparison

        Returns:
            VisualDiffResult with comparison details
        """
        current = self._load_image(current_base64)
        current_b64 = self._image_to_base64(current)

        should_update = update_baseline if update_baseline is not None else self.update_baselines

        baseline = self._load_baseline(test_name)

        if baseline is None or should_update:
            # No baseline or forced update - save current as baseline
            self._save_baseline(test_name, current)
            return VisualDiffResult(
                similar=True,
                phash_distance=0,
                pixel_diff_ratio=0.0,
                baseline_image_base64=current_b64,
                current_image_base64=current_b64,
                baseline_path=self.platform_dir / f"{test_name}.png",
                test_name=test_name,
            )

        # Compute perceptual hash distance
        phash_current = self._compute_phash(current)
        phash_baseline = self._compute_phash(baseline)
        phash_distance = phash_current - phash_baseline

        # Compute pixel diff
        pixel_diff_ratio, diff_image = self._compute_pixel_diff(current, baseline)
        diff_b64 = self._image_to_base64(diff_image)

        # Determine similarity
        phash_ok = phash_distance <= self.phash_threshold
        pixel_ok = pixel_diff_ratio <= self.pixel_threshold
        similar = phash_ok and pixel_ok

        baseline_b64 = self._image_to_base64(baseline)

        return VisualDiffResult(
            similar=similar,
            phash_distance=phash_distance,
            pixel_diff_ratio=pixel_diff_ratio,
            diff_image_base64=diff_b64,
            baseline_image_base64=baseline_b64,
            current_image_base64=current_b64,
            baseline_path=self.platform_dir / f"{test_name}.png",
            test_name=test_name,
        )

    def compare_file(
        self,
        test_name: str,
        current_path: Path,
        update_baseline: Optional[bool] = None,
    ) -> VisualDiffResult:
        """Compare image file with baseline."""
        with open(current_path, "rb") as f:
            current_b64 = base64.b64encode(f.read()).decode()
        return self.compare(test_name, current_b64, update_baseline)

    def assert_similar(
        self,
        test_name: str,
        current_base64: str,
        update_baseline: Optional[bool] = None,
        msg: Optional[str] = None,
    ) -> VisualDiffResult:
        """Assert that current image matches baseline (raises AssertionError if not)."""
        result = self.compare(test_name, current_base64, update_baseline)
        if not result.similar:
            details = (
                f"Visual regression detected for '{test_name}': "
                f"pHash distance={result.phash_distance} (threshold={self.phash_threshold}), "
                f"pixel diff={result.pixel_diff_ratio:.4f} (threshold={self.pixel_threshold})"
            )
            if msg:
                details = f"{msg}: {details}"
            raise AssertionError(details)
        return result


def create_visual_regression_engine(
    baseline_dir: Optional[Path] = None,
    **kwargs
) -> VisualRegressionEngine:
    """Factory function to create VisualRegressionEngine with default settings."""
    if baseline_dir is None:
        baseline_dir = Path(__file__).parent.parent.parent / "tests" / "visual_baselines"
    return VisualRegressionEngine(baseline_dir, **kwargs)


# Pytest integration
def pytest_visual_regression(
    test_name: str,
    current_base64: str,
    baseline_dir: Optional[Path] = None,
    phash_threshold: int = 5,
    pixel_threshold: float = 0.01,
) -> VisualDiffResult:
    """Convenience function for use in pytest tests."""
    engine = VisualRegressionEngine(
        baseline_dir or Path("tests/visual_baselines"),
        phash_threshold=phash_threshold,
        pixel_threshold=pixel_threshold,
    )
    return engine.compare(test_name, current_base64)


if __name__ == "__main__":
    # Demo usage
    import argparse

    parser = argparse.ArgumentParser(description="Visual Regression Engine CLI")
    parser.add_argument("--baseline-dir", type=Path, default=Path("tests/visual_baselines"))
    parser.add_argument("--test-name", required=True)
    parser.add_argument("--current", type=Path, required=True, help="Current screenshot PNG")
    parser.add_argument("--update", action="store_true", help="Update baseline")
    parser.add_argument("--phash-threshold", type=int, default=5)
    parser.add_argument("--pixel-threshold", type=float, default=0.01)
    args = parser.parse_args()

    engine = VisualRegressionEngine(
        args.baseline_dir,
        phash_threshold=args.phash_threshold,
        pixel_threshold=args.pixel_threshold,
        update_baselines=args.update,
    )

    with open(args.current, "rb") as f:
        current_b64 = base64.b64encode(f.read()).decode()

    result = engine.compare(args.test_name, current_b64, update_baseline=args.update)
    print(result)
    if not result.similar:
        print("VISUAL REGRESSION DETECTED!")
        sys.exit(1)
    else:
        print("OK - Images match")
        sys.exit(0)