"""Rescale step - adjust image to target DPI."""

from typing import Any, Optional, Tuple

import numpy as np

# OpenCV is optional (layout-refinement extra)
cv2: Optional[Any] = None
try:
    import cv2 as _cv2

    cv2 = _cv2
except ImportError:
    pass


def _rescale_to_dpi(
    img: np.ndarray,
    current_dpi: float = 72.0,
    target_dpi: int = 300,
    tolerance: float = 5.0,
    min_dimension_large: int = 1500,
    **kwargs: Any,
) -> Tuple[np.ndarray, bool]:
    """
    Rescale image to target DPI. Skips if already at target or large enough.

    Rescale guard: skip if abs(current_dpi - target_dpi) < tolerance.
    If DPI unknown, skip if min dimension already > min_dimension_large.

    Args:
        img: Image (H, W) or (H, W, C) numpy array
        current_dpi: Assumed current DPI (default 72)
        target_dpi: Target DPI (default 300)
        tolerance: Skip if within this many DPI of target
        min_dimension_large: Skip if min(H,W) >= this when DPI unknown
        **kwargs: Override any of above from hints

    Returns:
        (rescaled_img, did_apply)
    """
    if cv2 is None:
        raise ImportError(
            "opencv-python-headless is required for preprocessing. "
            "Install with: pip install preocr[layout-refinement]"
        )

    current_dpi = kwargs.get("current_dpi", current_dpi)
    target_dpi = kwargs.get("target_dpi", target_dpi)
    tolerance = kwargs.get("tolerance", tolerance)
    min_dimension_large = kwargs.get("min_dimension_large", min_dimension_large)

    h, w = img.shape[:2]

    # Rescale guard: already at target DPI
    if abs(current_dpi - target_dpi) < tolerance:
        return img, False

    # If DPI unknown or very low, skip if image already large enough
    if current_dpi <= 72 and min(h, w) >= min_dimension_large:
        return img, False

    scale = target_dpi / current_dpi
    new_w = int(w * scale)
    new_h = int(h * scale)

    if new_w == w and new_h == h:
        return img, False

    result = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    return result, True
