"""OpenCV-based layout analysis for PDFs (used when confidence is low)."""

from typing import Any, Dict, Optional, cast

from .. import exceptions
from ..utils.logger import get_logger

LayoutAnalysisError = exceptions.LayoutAnalysisError

logger = get_logger(__name__)

# Declare these as Optional[Any] so mypy knows they can be None
cv2: Optional[Any]
np: Optional[Any]

try:
    import cv2 as _cv2
    import numpy as _np

    cv2 = _cv2
    np = _np
except ImportError:
    cv2 = None
    np = None

try:
    import fitz  # PyMuPDF for PDF to image conversion
except ImportError:
    fitz = None


def analyze_with_opencv(
    file_path: str,
    page_level: bool = False,
    max_pages_to_analyze: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Analyze PDF layout using OpenCV for text/image region detection.

    This is used when initial heuristics have low confidence or layout_aware=True,
    to refine the decision.

    Args:
        file_path: Path to the PDF file
        page_level: If True, analyze all pages and return per-page results
        max_pages_to_analyze: Cap on pages to analyze (e.g. 2 for light refinement).
            None = use default sampling (5 for small docs, 5 sampled for large).

    Returns:
        Dictionary with layout analysis results:
            - text_regions: Number of detected text regions (overall)
            - image_regions: Number of detected image regions (overall)
            - text_coverage: Estimated text coverage percentage (overall)
            - image_coverage: Estimated image coverage percentage (overall)
            - layout_complexity: "simple", "moderate", or "complex"
            - has_text_regions: Boolean indicating text regions found
            - has_image_regions: Boolean indicating image regions found
            - layout_type: "text_only", "image_only", "mixed", or "unknown"
            - total_pages: Number of pages analyzed
            - pages: (if page_level=True) List of per-page layout data
        Returns None if OpenCV/PyMuPDF not available or analysis fails
    """
    if not cv2 or not np or not fitz:
        return None

    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)

        if total_pages == 0:
            doc.close()
            return None

        # Analyze multiple pages for better accuracy
        # For small PDFs, analyze all pages; for large ones, sample pages
        if total_pages <= 5:
            pages_to_analyze = list(range(total_pages))
        else:
            # Sample: first, middle, last, and a few random pages
            pages_to_analyze = [0, total_pages // 2, total_pages - 1]
            if total_pages > 3:
                import random

                additional = min(2, total_pages - 3)
                other_pages = [i for i in range(1, total_pages - 1) if i != total_pages // 2]
                pages_to_analyze.extend(random.sample(other_pages, additional))
        if max_pages_to_analyze is not None and max_pages_to_analyze > 0:
            pages_to_analyze = pages_to_analyze[: max_pages_to_analyze]

        overall_text_area = 0.0
        overall_image_area = 0.0
        overall_page_area = 0.0
        overall_has_text = False
        overall_has_images = False
        total_text_regions = 0
        total_image_regions = 0
        page_layout_data = []

        for page_idx in pages_to_analyze:
            if page_idx >= total_pages:
                continue

            page = doc[page_idx]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better quality
            img_array = _np.frombuffer(pix.samples, dtype=_np.uint8)

            if pix.n == 1:  # Grayscale
                img = img_array.reshape(pix.height, pix.width)
            else:
                img = img_array.reshape(pix.height, pix.width, pix.n)

            # Convert to grayscale if needed
            if len(img.shape) == 3:
                if img.shape[2] == 4:  # RGBA
                    img = _cv2.cvtColor(img, _cv2.COLOR_RGBA2GRAY)
                elif img.shape[2] == 3:  # RGB
                    img = _cv2.cvtColor(img, _cv2.COLOR_RGB2GRAY)

            # Analyze layout for this page
            # Pass cv2 and np to avoid Optional[Any] issues in _analyze_layout
            page_result = _analyze_layout(img, cv2_module=cv2, np_module=np)

            page_area = pix.height * pix.width
            page_text_area = (page_result["text_coverage"] / 100.0) * page_area
            page_image_area = (page_result["image_coverage"] / 100.0) * page_area

            overall_text_area += page_text_area
            overall_image_area += page_image_area
            overall_page_area += page_area
            total_text_regions += page_result["text_regions"]
            total_image_regions += page_result["image_regions"]

            if page_result["has_text_regions"]:
                overall_has_text = True
            if page_result["has_image_regions"]:
                overall_has_images = True

            if page_level:
                page_layout_data.append(
                    {
                        "page_number": page_idx + 1,
                        "text_coverage": page_result["text_coverage"],
                        "image_coverage": page_result["image_coverage"],
                        "text_regions": page_result["text_regions"],
                        "image_regions": page_result["image_regions"],
                        "has_text_regions": page_result["has_text_regions"],
                        "has_image_regions": page_result["has_image_regions"],
                        "layout_complexity": page_result["layout_complexity"],
                    }
                )

        doc.close()

        # Calculate overall metrics
        overall_text_coverage = (
            (overall_text_area / overall_page_area * 100) if overall_page_area > 0 else 0.0
        )
        overall_image_coverage = (
            (overall_image_area / overall_page_area * 100) if overall_page_area > 0 else 0.0
        )

        # Determine overall layout type
        if overall_has_text and not overall_has_images:
            layout_type = "text_only"
        elif not overall_has_text and overall_has_images:
            layout_type = "image_only"
        elif overall_has_text and overall_has_images:
            layout_type = "mixed"
        else:
            layout_type = "unknown"

        # Determine complexity based on total regions
        total_regions = total_text_regions + total_image_regions
        if total_regions < 10:
            complexity = "simple"
        elif total_regions < 30:
            complexity = "moderate"
        else:
            complexity = "complex"

        result = {
            "text_regions": total_text_regions,
            "image_regions": total_image_regions,
            "text_coverage": round(overall_text_coverage, 2),
            "image_coverage": round(overall_image_coverage, 2),
            "layout_complexity": complexity,
            "has_text_regions": overall_has_text,
            "has_image_regions": overall_has_images,
            "layout_type": layout_type,
            "total_pages": total_pages,
            "pages_analyzed": len(pages_to_analyze),
        }

        if page_level:
            result["pages"] = page_layout_data

        return result

    except (IOError, OSError, PermissionError) as e:
        logger.warning(f"Failed to read PDF file for OpenCV analysis: {e}")
        return None
    except Exception as e:
        logger.warning(f"OpenCV layout analysis failed: {e}")
        return None


def _analyze_layout(img: Any, cv2_module: Any = None, np_module: Any = None) -> Dict[str, Any]:
    """
    Analyze image layout using OpenCV with improved accuracy.

    Uses multiple techniques:
    1. Text detection: Morphological operations + aspect ratio filtering
    2. Image detection: Edge density + variance analysis
    3. Better filtering to reduce false positives

    Args:
        img: Grayscale image as numpy array
        cv2_module: OpenCV module (for type narrowing)
        np_module: NumPy module (for type narrowing)

    Returns:
        Dictionary with layout analysis results
    """
    # Use provided modules or fall back to global ones
    # Cast to Any to tell mypy these are not None (guaranteed by caller)
    _cv2: Any = cast(Any, cv2_module if cv2_module is not None else cv2)
    _np: Any = cast(Any, np_module if np_module is not None else np)

    height, width = img.shape
    total_area = height * width

    # 1. Detect text regions using improved morphological operations
    # Use adaptive thresholding for better text detection
    binary = _cv2.adaptiveThreshold(
        img, 255, _cv2.ADAPTIVE_THRESH_GAUSSIAN_C, _cv2.THRESH_BINARY_INV, 11, 2
    )

    # Morphological operations to connect text components
    # Use horizontal kernel to connect characters into words/lines
    kernel_h = _cv2.getStructuringElement(_cv2.MORPH_RECT, (9, 1))
    kernel_v = _cv2.getStructuringElement(_cv2.MORPH_RECT, (1, 3))

    # Dilate horizontally to connect characters, then vertically to connect lines
    dilated = _cv2.dilate(binary, kernel_h, iterations=1)
    dilated = _cv2.dilate(dilated, kernel_v, iterations=1)

    # Find text contours
    text_contours, _ = _cv2.findContours(dilated, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)

    # Filter text regions with better criteria
    text_regions = []
    text_area = 0.0
    min_text_area = max(20, total_area * 0.0001)  # Adaptive minimum area
    max_text_area = total_area * 0.5  # Don't consider huge regions as text

    for contour in text_contours:
        area = _cv2.contourArea(contour)
        if area < min_text_area or area > max_text_area:
            continue

        # Get bounding box to check aspect ratio
        x, y, w, h = _cv2.boundingRect(contour)
        aspect_ratio = w / h if h > 0 else 0

        # Text typically has reasonable aspect ratios (not too wide or too tall)
        # Allow wider ratios for tables/lists
        if 0.1 < aspect_ratio < 50 and h > 5 and w > 5:
            # Check if region has text-like characteristics (high contrast)
            roi = img[y : y + h, x : x + w] if y + h <= height and x + w <= width else None
            if roi is not None and roi.size > 0:
                std_dev = _np.std(roi)
                # Text regions typically have moderate to high contrast
                if std_dev > 10:  # Threshold for text-like contrast
                    text_regions.append(contour)
                    text_area += area

    # 2. Detect image regions using improved edge detection + variance
    # Images typically have high variance and many edges
    edges = _cv2.Canny(img, 30, 100)  # Lower thresholds to catch more edges

    # Use variance to identify image regions (images have high variance)
    kernel_size = 15
    kernel = _np.ones((kernel_size, kernel_size), _np.float32) / (kernel_size * kernel_size)
    mean = _cv2.filter2D(img.astype(_np.float32), -1, kernel)
    variance = _cv2.filter2D((img.astype(_np.float32) - mean) ** 2, -1, kernel)

    # Combine edge density and variance
    edge_density = _cv2.filter2D(edges.astype(_np.float32), -1, kernel) / 255.0
    variance_normalized = variance / 255.0

    # Regions with high edge density AND high variance are likely images
    image_mask = ((edge_density > 0.1) & (variance_normalized > 50)).astype(_np.uint8) * 255

    # Find image contours
    image_contours, _ = _cv2.findContours(image_mask, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)

    # Filter image regions
    image_regions = []
    image_area = 0.0
    min_image_area = max(500, total_area * 0.001)  # Adaptive minimum area

    for contour in image_contours:
        area = _cv2.contourArea(contour)
        if area < min_image_area:
            continue

        # Check if this region overlaps significantly with text regions
        # If so, it's likely not a pure image region
        overlap = False
        for text_contour in text_regions:
            if _contours_overlap(contour, text_contour, overlap_threshold=0.2):
                overlap = True
                break

        if not overlap:
            image_regions.append(contour)
            image_area += area

    # Calculate coverage percentages
    text_coverage = (text_area / total_area * 100) if total_area > 0 else 0.0
    image_coverage = (image_area / total_area * 100) if total_area > 0 else 0.0

    # Determine layout complexity
    num_regions = len(text_regions) + len(image_regions)
    if num_regions < 5:
        complexity = "simple"
    elif num_regions < 20:
        complexity = "moderate"
    else:
        complexity = "complex"

    return {
        "text_regions": len(text_regions),
        "image_regions": len(image_regions),
        "text_coverage": round(text_coverage, 2),
        "image_coverage": round(image_coverage, 2),
        "layout_complexity": complexity,
        "has_text_regions": len(text_regions) > 0,
        "has_image_regions": len(image_regions) > 0,
    }


def _contours_overlap(contour1, contour2, overlap_threshold: float = 0.3) -> bool:
    """
    Check if two contours overlap significantly.

    Args:
        contour1: First contour
        contour2: Second contour
        overlap_threshold: Minimum overlap ratio to consider as overlapping

    Returns:
        True if contours overlap significantly
    """
    if not cv2:
        return False

    try:
        # Get bounding boxes
        x1, y1, w1, h1 = cv2.boundingRect(contour1)
        x2, y2, w2, h2 = cv2.boundingRect(contour2)

        # Calculate intersection
        x_overlap = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
        y_overlap = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
        overlap_area = x_overlap * y_overlap

        # Calculate union
        area1 = w1 * h1
        area2 = w2 * h2
        union_area = area1 + area2 - overlap_area

        # Check overlap ratio
        if union_area == 0:
            return False

        overlap_ratio = overlap_area / union_area
        return bool(overlap_ratio >= overlap_threshold)
    except Exception as e:
        logger.debug(f"Contour overlap check failed: {e}")
        return False
