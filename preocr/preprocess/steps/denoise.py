"""Denoise step using Non-Local Means."""

from typing import Any, Optional, Tuple

import numpy as np

# OpenCV is optional (layout-refinement extra)
cv2: Optional[Any] = None
try:
    import cv2 as _cv2

    cv2 = _cv2
except ImportError:
    pass


def _denoise(img: np.ndarray, **kwargs: Any) -> Tuple[np.ndarray, bool]:
    """
    Apply Non-Local Means denoising to grayscale or color image.

    Args:
        img: Grayscale (H, W) or color (H, W, 3) numpy array, uint8
        **kwargs: Optional h, templateWindowSize, searchWindowSize

    Returns:
        (denoised_img, did_apply). did_apply is True when denoising was applied.
    """
    if cv2 is None:
        raise ImportError(
            "opencv-python-headless is required for preprocessing. "
            "Install with: pip install preocr[layout-refinement]"
        )

    h = kwargs.get("h", 10)
    template_window = kwargs.get("templateWindowSize", 7)
    search_window = kwargs.get("searchWindowSize", 21)

    if len(img.shape) == 3:
        if img.shape[2] == 3:
            result = cv2.fastNlMeansDenoisingColored(
                img,
                h=h,
                hForColorComponents=h,
                templateWindowSize=template_window,
                searchWindowSize=search_window,
            )
        else:
            # RGBA or other - convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
            result = cv2.fastNlMeansDenoising(
                gray, h=h, templateWindowSize=template_window, searchWindowSize=search_window
            )
    else:
        result = cv2.fastNlMeansDenoising(
            img, h=h, templateWindowSize=template_window, searchWindowSize=search_window
        )

    return result, True
