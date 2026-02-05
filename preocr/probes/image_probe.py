"""Image analysis and entropy calculation."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from .. import exceptions
from ..utils.logger import get_logger

ImageProcessingError = exceptions.ImageProcessingError

logger = get_logger(__name__)

if TYPE_CHECKING:
    pass

# Declare these as Optional[Any] so mypy knows they can be None
Image: Optional[Any]
np: Optional[Any]

try:
    from PIL import Image as _Image
    import numpy as _np

    Image = _Image
    np = _np
except ImportError:
    Image = None
    np = None


def is_image_file(mime_type: str) -> bool:
    """
    Check if MIME type represents an image.

    Args:
        mime_type: MIME type string

    Returns:
        True if MIME type is an image, False otherwise
    """
    return mime_type.startswith("image/")


def analyze_image(file_path: str) -> Dict[str, Any]:
    """
    Analyze image file and calculate entropy.

    Args:
        file_path: Path to the image file

    Returns:
        Dictionary with keys:
            - entropy: Image entropy value (0-8, higher = more complex)
            - width: Image width in pixels
            - height: Image height in pixels
            - mode: Image mode (RGB, L, etc.)
            - is_image: Always True for images
    """
    if not Image:
        return {
            "entropy": None,
            "width": None,
            "height": None,
            "mode": None,
            "is_image": True,
        }

    path = Path(file_path)

    try:
        with Image.open(path) as img:
            # Convert to grayscale for entropy calculation
            gray_img = img.convert("L")

            # Calculate entropy
            entropy = _calculate_entropy(gray_img)

            return {
                "entropy": entropy,
                "width": img.width,
                "height": img.height,
                "mode": img.mode,
                "is_image": True,
            }
    except (IOError, OSError, PermissionError) as e:
        logger.warning(f"Failed to read image file: {e}")
        return {
            "entropy": None,
            "width": None,
            "height": None,
            "mode": None,
            "is_image": True,
        }
    except Exception as e:
        logger.warning(f"Image processing failed: {e}")
        return {
            "entropy": None,
            "width": None,
            "height": None,
            "mode": None,
            "is_image": True,
        }


def _calculate_entropy(image: Any) -> float:
    """
    Calculate entropy of an image.

    Entropy measures the randomness/complexity of pixel values.
    Low entropy (0-4): Simple images, likely scanned text
    High entropy (4-8): Complex images, photos

    Args:
        image: PIL Image object (should be grayscale)

    Returns:
        Entropy value between 0 and 8
    """
    if not np:
        # Fallback: simple histogram-based entropy
        histogram = image.histogram()
        histogram = [h for h in histogram if h > 0]  # Remove zeros
        total_pixels = sum(histogram)

        if total_pixels == 0:
            return 0.0

        entropy = 0.0
        for count in histogram:
            probability = count / total_pixels
            if probability > 0:
                entropy -= probability * (probability.bit_length() - 1)  # Approximate log2
        return entropy

    # NumPy-based calculation (more accurate)
    try:
        img_array = np.array(image)
        histogram, _ = np.histogram(img_array.flatten(), bins=256, range=(0, 256))
        histogram = histogram[histogram > 0]  # Remove zeros
        total_pixels = histogram.sum()

        if total_pixels == 0:
            return 0.0

        probabilities = histogram / total_pixels
        entropy = -np.sum(probabilities * np.log2(probabilities))
        return float(entropy)
    except Exception:
        # Fallback to simple calculation
        histogram = image.histogram()
        histogram = [h for h in histogram if h > 0]
        total_pixels = sum(histogram)

        if total_pixels == 0:
            return 0.0

        entropy = 0.0
        for count in histogram:
            probability = count / total_pixels
            if probability > 0:
                entropy -= probability * (probability.bit_length() - 1)
        return entropy
