"""Layout analysis for PDFs to detect text regions, images, and mixed content."""

from pathlib import Path
from typing import Any, Dict, Optional

from .. import exceptions
from ..utils.logger import get_logger, suppress_pdf_warnings

LayoutAnalysisError = exceptions.LayoutAnalysisError

logger = get_logger(__name__)

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore[assignment]

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


def analyze_pdf_layout(file_path: str, page_level: bool = False) -> Dict[str, Any]:
    """
    Analyze PDF layout to detect text regions, images, and mixed content.

    Args:
        file_path: Path to the PDF file
        page_level: If True, return per-page layout analysis

    Returns:
        Dictionary with keys:
            - text_coverage: Percentage of page covered by text (0-100)
            - image_coverage: Percentage of page covered by images (0-100)
            - has_images: Boolean indicating if PDF contains images
            - text_density: Average text density (chars per page area)
            - layout_type: "text_only", "image_only", "mixed", or "unknown"
            - is_mixed_content: Boolean indicating mixed text and images
            - pages: (if page_level=True) List of page-level layout data
    """
    path = Path(file_path)

    # Try PyMuPDF first (best for image coverage: fast ⚡⚡⚡ and accurate 💯)
    # Based on library comparison: PyMuPDF > pdfplumber for image detection/coverage
    if fitz:
        try:
            return _analyze_with_pymupdf(path, page_level)
        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Failed to read PDF file for layout analysis with PyMuPDF: {e}")
        except Exception as e:
            logger.warning(f"Layout analysis failed with PyMuPDF: {e}")

    # Fallback to pdfplumber (good for text layout detection)
    if pdfplumber:
        try:
            return _analyze_with_pdfplumber(path, page_level)
        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Failed to read PDF file for layout analysis with pdfplumber: {e}")
        except Exception as e:
            logger.warning(f"Layout analysis failed with pdfplumber: {e}")

    # No analyzers available
    if fitz:
        try:
            return _analyze_with_pymupdf(path, page_level)
        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Failed to read PDF file for layout analysis with PyMuPDF: {e}")
        except Exception as e:
            logger.warning(f"Layout analysis failed with PyMuPDF: {e}")

    # No analyzers available or both failed
    result = {
        "text_coverage": 0.0,
        "image_coverage": 0.0,
        "has_images": False,
        "text_density": 0.0,
        "layout_type": "unknown",
        "is_mixed_content": False,
    }
    if page_level:
        result["pages"] = []
    return result


def get_quick_image_coverage(file_path: str) -> Optional[float]:
    """
    Fast image coverage check using PyMuPDF (no full layout analysis).

    Used for Hard Scan Shortcut: when image_coverage > 85 and text_length < 10,
    we can exit early without running layout or OpenCV.

    Returns:
        Image coverage percentage (0-100) or None if unavailable/failed.
    """
    if fitz is None:
        return None

    path = Path(file_path)
    try:
        with suppress_pdf_warnings():
            doc = fitz.open(path)
            total_image_area = 0.0
            total_page_area = 0.0
            try:
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    page_rect = page.rect
                    page_area = page_rect.width * page_rect.height
                    total_page_area += page_area
                    for img in page.get_images():
                        try:
                            xref = img[0]
                            for rect in page.get_image_rects(xref):
                                total_image_area += rect.width * rect.height
                        except Exception:
                            pass
            finally:
                doc.close()
        if total_page_area > 0:
            return round((total_image_area / total_page_area) * 100, 2)
        return 0.0
    except Exception as e:
        logger.debug(f"Quick image coverage failed for {file_path}: {e}")
        return None


def get_pdf_font_count(file_path: str, max_pages: int = 5) -> Optional[int]:
    """
    Fast font count extraction from PDF. font_count == 0 is a strong scan indicator
    (scanned PDFs often have no embedded fonts; digital PDFs have fonts).

    Returns:
        Number of unique fonts, or None if unavailable.
    """
    path = Path(file_path)
    fonts: set = set()

    if pdfplumber:
        try:
            with suppress_pdf_warnings():
                with pdfplumber.open(path) as pdf:
                    for i, page in enumerate(pdf.pages):
                        if i >= max_pages:
                            break
                        chars = page.chars if hasattr(page, "chars") else []
                        for c in chars:
                            fn = c.get("fontname")
                            if fn:
                                fonts.add(str(fn))
        except Exception as e:
            logger.debug(f"Font count extraction failed (pdfplumber) for {file_path}: {e}")
            return None

    if fitz and not fonts:
        try:
            with suppress_pdf_warnings():
                doc = fitz.open(path)
                try:
                    for i in range(min(len(doc), max_pages)):
                        page = doc[i]
                        for block in page.get_text("dict", flags=0).get("blocks", []):
                            for line in block.get("lines", []):
                                for span in line.get("spans", []):
                                    fn = span.get("font")
                                    if fn:
                                        fonts.add(str(fn))
                finally:
                    doc.close()
        except Exception as e:
            logger.debug(f"Font count extraction failed (PyMuPDF) for {file_path}: {e}")
            return None

    return len(fonts)


def _analyze_with_pdfplumber(path: Path, page_level: bool = False) -> Dict[str, Any]:
    """Analyze layout using pdfplumber (better layout detection)."""
    pages_data = []
    total_text_area = 0.0
    total_image_area = 0.0
    total_page_area = 0.0
    total_text_chars = 0
    has_images = False
    page_count = 0

    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)

        for page_num, page in enumerate(pdf.pages, start=1):
            page_width = page.width
            page_height = page.height
            page_area = page_width * page_height

            # Extract text and calculate text area
            chars = page.chars if hasattr(page, "chars") else []

            # Calculate text bounding boxes
            text_area = 0.0
            text_chars = len(chars)

            if chars:
                # Calculate bounding box of all text
                min_x = min(char["x0"] for char in chars)
                max_x = max(char["x1"] for char in chars)
                min_y = min(char["top"] for char in chars)
                max_y = max(char["bottom"] for char in chars)

                text_width = max_x - min_x
                text_height = max_y - min_y
                text_area = text_width * text_height

                # Clamp to page area
                text_area = min(text_area, page_area)

            # Check for images
            images = page.images if hasattr(page, "images") else []
            image_area = 0.0

            if images:
                has_images = True
                for img in images:
                    img_width = img.get("width", 0)
                    img_height = img.get("height", 0)
                    image_area += img_width * img_height

                # Clamp to page area
                image_area = min(image_area, page_area)

            # Calculate coverage percentages
            text_coverage = (text_area / page_area * 100) if page_area > 0 else 0.0
            image_coverage = (image_area / page_area * 100) if page_area > 0 else 0.0

            # Determine layout type for this page
            layout_type = _determine_layout_type(text_coverage, image_coverage, text_chars)
            is_mixed = text_coverage > 5 and image_coverage > 5

            # Calculate text density (chars per unit area)
            text_density = (text_chars / page_area * 1000) if page_area > 0 else 0.0

            total_text_area += text_area
            total_image_area += image_area
            total_page_area += page_area
            total_text_chars += text_chars

            if page_level:
                pages_data.append(
                    {
                        "page_number": page_num,
                        "text_coverage": round(text_coverage, 2),
                        "image_coverage": round(image_coverage, 2),
                        "text_chars": text_chars,
                        "text_density": round(text_density, 2),
                        "layout_type": layout_type,
                        "is_mixed_content": is_mixed,
                        "has_images": len(images) > 0,
                    }
                )

    # Calculate overall metrics
    overall_text_coverage = (
        (total_text_area / total_page_area * 100) if total_page_area > 0 else 0.0
    )
    overall_image_coverage = (
        (total_image_area / total_page_area * 100) if total_page_area > 0 else 0.0
    )
    overall_text_density = (
        (total_text_chars / total_page_area * 1000) if total_page_area > 0 else 0.0
    )
    overall_layout_type = _determine_layout_type(
        overall_text_coverage, overall_image_coverage, total_text_chars
    )
    is_mixed_content = overall_text_coverage > 5 and overall_image_coverage > 5

    result = {
        "text_coverage": round(overall_text_coverage, 2),
        "image_coverage": round(overall_image_coverage, 2),
        "has_images": has_images,
        "text_density": round(overall_text_density, 2),
        "layout_type": overall_layout_type,
        "is_mixed_content": is_mixed_content,
        "page_count": page_count,
    }

    if page_level:
        result["pages"] = pages_data

    return result


def _analyze_with_pymupdf(path: Path, page_level: bool = False) -> Dict[str, Any]:
    """Analyze layout using PyMuPDF (fallback, less detailed)."""
    with suppress_pdf_warnings():
        doc = fitz.open(path)
        pages_data = []
        total_text_area = 0.0
        total_image_area = 0.0
        total_page_area = 0.0
        total_text_chars = 0
        has_images = False
        page_count = len(doc)

        for page_num in range(page_count):
            page = doc[page_num]
            page_rect = page.rect
            page_width = page_rect.width
            page_height = page_rect.height
            page_area = page_width * page_height

            # Extract text
            text_dict = page.get_text("dict")
            text_chars = len(page.get_text())

            # Calculate text area from text blocks
            text_area = 0.0
            if "blocks" in text_dict:
                for block in text_dict["blocks"]:
                    if block.get("type") == 0:  # Text block
                        bbox = block.get("bbox", [0, 0, 0, 0])
                        block_width = bbox[2] - bbox[0]
                        block_height = bbox[3] - bbox[1]
                        text_area += block_width * block_height

            # Check for images
            # Use PyMuPDF's get_image_rects() to get rendered image sizes (more accurate)
            image_list = page.get_images()
            image_area = 0.0

            if image_list:
                has_images = True
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        # Get rendered rectangles for this image on the page (actual displayed size)
                        image_rects = page.get_image_rects(xref)
                        for rect in image_rects:
                            # Calculate area from rendered rectangle
                            img_width = rect.width
                            img_height = rect.height
                            image_area += img_width * img_height
                    except Exception:
                        pass

            # Clamp areas to page area
            text_area = min(text_area, page_area)
            image_area = min(image_area, page_area)

            # Calculate coverage
            text_coverage = (text_area / page_area * 100) if page_area > 0 else 0.0
            image_coverage = (image_area / page_area * 100) if page_area > 0 else 0.0

            # Determine layout type
            layout_type = _determine_layout_type(text_coverage, image_coverage, text_chars)
            is_mixed = text_coverage > 5 and image_coverage > 5
            text_density = (text_chars / page_area * 1000) if page_area > 0 else 0.0

            total_text_area += text_area
            total_image_area += image_area
            total_page_area += page_area
            total_text_chars += text_chars

            if page_level:
                pages_data.append(
                    {
                        "page_number": page_num + 1,
                        "text_coverage": round(text_coverage, 2),
                        "image_coverage": round(image_coverage, 2),
                        "text_chars": text_chars,
                        "text_density": round(text_density, 2),
                        "layout_type": layout_type,
                        "is_mixed_content": is_mixed,
                        "has_images": len(image_list) > 0,
                    }
                )

        doc.close()

        # Calculate overall metrics
        overall_text_coverage = (
            (total_text_area / total_page_area * 100) if total_page_area > 0 else 0.0
        )
        overall_image_coverage = (
            (total_image_area / total_page_area * 100) if total_page_area > 0 else 0.0
        )
        overall_text_density = (
            (total_text_chars / total_page_area * 1000) if total_page_area > 0 else 0.0
        )
        overall_layout_type = _determine_layout_type(
            overall_text_coverage, overall_image_coverage, total_text_chars
        )
        is_mixed_content = overall_text_coverage > 5 and overall_image_coverage > 5

        result = {
            "text_coverage": round(overall_text_coverage, 2),
            "image_coverage": round(overall_image_coverage, 2),
            "has_images": has_images,
            "text_density": round(overall_text_density, 2),
            "layout_type": overall_layout_type,
            "is_mixed_content": is_mixed_content,
            "page_count": page_count,
        }

        if page_level:
            result["pages"] = pages_data

        return result


def _determine_layout_type(text_coverage: float, image_coverage: float, text_chars: int) -> str:
    """
    Determine layout type based on coverage and text content.

    Args:
        text_coverage: Percentage of page covered by text
        image_coverage: Percentage of page covered by images
        text_chars: Number of text characters

    Returns:
        Layout type: "text_only", "image_only", "mixed", or "unknown"
    """
    if text_coverage > 10 and image_coverage < 5:
        return "text_only"
    elif image_coverage > 10 and text_coverage < 5 and text_chars < 50:
        return "image_only"
    elif text_coverage > 5 and image_coverage > 5:
        return "mixed"
    elif text_chars >= 50:
        return "text_only"  # Has text even if coverage is low
    else:
        return "unknown"
