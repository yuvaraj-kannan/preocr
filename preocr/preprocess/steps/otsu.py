"""Otsu binarization step."""

from typing import Any, Optional, Tuple

import numpy as np

# OpenCV is optional (layout-refinement extra)
cv2: Optional[Any] = None
try:
    import cv2 as _cv2

    cv2 = _cv2
except ImportError:
    pass


def _otsu_binarize(img: np.ndarray, **kwargs: Any) -> Tuple[np.ndarray, bool]:
    """
    Apply Otsu binarization. Skips if image is already binary (strict check).

    Args:
        img: Grayscale (H, W) numpy array, uint8
        **kwargs: Future rich hints (e.g. invert)

    Returns:
        (binary_img, did_apply). did_apply is False when already binary.
    """
    if cv2 is None:
        raise ImportError(
            "opencv-python-headless is required for preprocessing. "
            "Install with: pip install preocr[layout-refinement]"
        )

    # Strict binary detection: only skip if values are exactly 0 and 255
    unique_vals = np.unique(img)
    if len(unique_vals) <= 2 and set(unique_vals).issubset({0, 255}):
        return img, False

    # Ensure grayscale
    if len(img.shape) == 3:
        gray = (
            cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            if img.shape[2] == 3
            else cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
        )
    else:
        gray = img.copy()

    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Tesseract prefers dark text on light background - ensure that
    # If majority of pixels are dark, invert
    if np.mean(binary) < 127:
        binary = cv2.bitwise_not(binary)

    # Match output shape to input
    if len(img.shape) == 3:
        binary = np.expand_dims(binary, axis=-1)
        binary = np.repeat(binary, img.shape[2], axis=-1)

    return binary, True
