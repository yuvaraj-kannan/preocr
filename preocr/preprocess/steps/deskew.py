"""Deskew step - rotate image to correct skew angle."""

from typing import Any, Optional, Tuple

import numpy as np

# OpenCV is optional (layout-refinement extra)
cv2: Optional[Any] = None
try:
    import cv2 as _cv2
    cv2 = _cv2
except ImportError:
    pass


def _deskew(img: np.ndarray, **kwargs: Any) -> Tuple[np.ndarray, bool]:
    """
    Deskew image by detecting skew angle and rotating.

    Skips if detected angle < min_angle (idempotent for straight images).
    severe_only=True (fast mode): only apply if angle > 2°.

    Args:
        img: Grayscale (H, W) numpy array, uint8
        **kwargs: min_angle (skip if angle less than this, default 0.5),
                  severe_only (only deskew if angle > 2°, default False)

    Returns:
        (deskewed_img, did_apply)
    """
    if cv2 is None:
        raise ImportError(
            "opencv-python-headless is required for preprocessing. "
            "Install with: pip install preocr[layout-refinement]"
        )

    min_angle = kwargs.get("min_angle", 0.5)
    severe_only = kwargs.get("severe_only", False)
    if severe_only:
        min_angle = 2.0

    # Ensure grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.shape[2] == 3 else cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
    else:
        gray = img.copy()

    # Threshold for line detection
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Find coordinates of non-zero pixels
    coords = np.column_stack(np.where(binary > 0))
    if len(coords) < 100:
        return img, False

    # Get min area rect - returns (center, (width, height), angle)
    rect = cv2.minAreaRect(coords)
    angle = rect[2]

    # minAreaRect returns angle in [-90, 0); normalize
    if angle < -45:
        angle = 90 + angle
    elif angle > 45:
        angle = angle - 90

    if abs(angle) < min_angle:
        return img, False

    # Rotate
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        img,
        M,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated, True
