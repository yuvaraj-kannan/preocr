"""Main API for OCR detection."""

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from .. import constants
from ..analysis import layout_analyzer, opencv_layout, page_detection
from ..probes import image_probe, office_probe, pdf_probe, text_probe
from ..utils import cache, filetype, logger as logger_module
from . import decision, signals

Config = constants.Config
LAYOUT_REFINEMENT_THRESHOLD = constants.LAYOUT_REFINEMENT_THRESHOLD
get_logger = logger_module.get_logger
get_cached_result = cache.get_cached_result
cache_result = cache.cache_result

logger = get_logger(__name__)

# Import modules for easier access
filetype_module = filetype
pdf_probe_module = pdf_probe
office_probe_module = office_probe
text_probe_module = text_probe
image_probe_module = image_probe
layout_analyzer_module = layout_analyzer
page_detection_module = page_detection
opencv_layout_module = opencv_layout


def needs_ocr(
    file_path: Union[str, Path],
    page_level: bool = False,
    layout_aware: bool = False,
    use_cache: bool = False,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    config: Optional[Config] = None,
) -> Dict[str, Any]:
    """
    Determine if a file needs OCR processing.

    This is the main API function. It analyzes the file type, extracts text
    where possible, and makes an intelligent decision about whether OCR is needed.

    Args:
        file_path: Path to the file to analyze (string or Path object)
        page_level: If True, return page-level analysis for PDFs (default: False)
        layout_aware: If True, perform layout analysis for PDFs to detect mixed
                     content and improve accuracy (default: False)
        use_cache: If True, cache results for faster repeated calls (default: False)
        progress_callback: Optional callback function(current_stage, progress) called
                          during processing. progress is 0.0-1.0.
        config: Optional Config object with threshold settings. If None, uses default thresholds.

    Returns:
        Dictionary with keys:
            - needs_ocr: Boolean indicating if OCR is needed
            - file_type: Detected file type category (e.g., "image", "pdf", "office")
            - category: "structured" (no OCR) or "unstructured" (needs OCR)
            - confidence: Confidence score (0.0-1.0)
            - reason: Human-readable reason for the decision
            - reason_code: Structured reason code (e.g., "PDF_DIGITAL", "IMAGE_FILE")
            - signals: Dictionary of all collected signals (for debugging)
            - pages: (if page_level=True for PDFs) Page-level analysis results
            - layout: (if layout_aware=True for PDFs) Layout analysis results

    Example:
        >>> result = needs_ocr("document.pdf")
        >>> if result["needs_ocr"]:
        ...     run_ocr("document.pdf")

        >>> # Page-level analysis
        >>> result = needs_ocr("document.pdf", page_level=True)
        >>> for page in result.get("pages", []):
        ...     if page["needs_ocr"]:
        ...         print(f"Page {page['page_number']} needs OCR")
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if progress_callback:
        progress_callback("initializing", 0.0)

    # Check cache if enabled
    if use_cache:
        cached = get_cached_result(str(path))
        if cached is not None:
            # Filter cached result based on requested options
            # Only return cached if it matches requested page_level and layout_aware
            if (
                cached.get("_cache_page_level") == page_level
                and cached.get("_cache_layout_aware") == layout_aware
            ):
                # Remove cache metadata before returning
                result = {k: v for k, v in cached.items() if not k.startswith("_cache_")}
                logger.debug(f"Using cached result for {file_path}")
                if progress_callback:
                    progress_callback("complete", 1.0)
                return result

    # Step 1: Detect file type
    if progress_callback:
        progress_callback("detecting_file_type", 0.1)
    file_info = filetype_module.detect_file_type(str(path))
    mime: str = file_info["mime"]
    extension: str = file_info["extension"]

    # Step 2: Extract text based on file type
    text_result = None
    image_result = None
    page_analysis = None
    layout_result = None

    if mime == "application/pdf":
        # PDF text extraction (with optional page-level analysis)
        if progress_callback:
            progress_callback("extracting_pdf_text", 0.3)
        text_result = pdf_probe_module.extract_pdf_text(str(path), page_level=page_level)

        # Perform layout analysis if requested
        if layout_aware:
            if progress_callback:
                progress_callback("analyzing_layout", 0.5)
            layout_result = layout_analyzer_module.analyze_pdf_layout(
                str(path), page_level=page_level
            )

        # Perform page-level analysis if requested
        if page_level and "pages" in text_result:
            if progress_callback:
                progress_callback("analyzing_pages", 0.6)
            page_analysis = page_detection_module.analyze_pdf_pages(
                str(path), file_info, text_result
            )
    elif "officedocument" in mime or extension in ["docx", "pptx", "xlsx"]:
        # Office document text extraction
        text_result = office_probe_module.extract_office_text(str(path), mime)
    elif mime.startswith("text/") or mime in ["text/html", "application/xhtml+xml"]:
        # Plain text or HTML extraction
        text_result = text_probe_module.extract_text_from_file(str(path), mime)
    elif mime.startswith("image/"):
        # Image analysis (no text extraction)
        image_result = image_probe_module.analyze_image(str(path))

    # Step 3: Collect all signals
    collected_signals = signals.collect_signals(
        str(path), file_info, text_result, image_result, layout_result
    )

    # Step 4: Make initial decision (heuristics)
    # Use config's layout_refinement_threshold if provided, otherwise use default
    refinement_threshold = (
        config.layout_refinement_threshold if config else LAYOUT_REFINEMENT_THRESHOLD
    )
    needs_ocr_flag, reason, confidence, category, reason_code = decision.decide(
        collected_signals, config=config
    )

    # Step 5: Confidence check → OpenCV layout refinement (if needed)
    # If confidence is low OR layout_aware is True, use OpenCV to refine the decision
    if mime == "application/pdf" and (layout_aware or confidence < refinement_threshold):
        if progress_callback:
            progress_callback("opencv_analysis", 0.7)
        opencv_result = opencv_layout_module.analyze_with_opencv(str(path), page_level=page_level)
        if opencv_result:
            # Refine decision based on OpenCV analysis
            needs_ocr_flag, reason, confidence, category, reason_code = decision.refine_with_opencv(
                collected_signals,
                opencv_result,
                needs_ocr_flag,
                reason,
                confidence,
                category,
                reason_code,
                config=config,
            )
            # Add OpenCV results to signals for debugging
            collected_signals["opencv_layout"] = opencv_result

    # Step 6: Determine file type category for user
    file_type_category = _get_file_type_category(mime, extension)

    # Build result dictionary
    result = {
        "needs_ocr": needs_ocr_flag,
        "file_type": file_type_category,
        "category": category,
        "confidence": confidence,
        "reason": reason,
        "reason_code": reason_code,
        "signals": collected_signals,
    }

    # Add page-level results if available
    if page_analysis and "pages" in page_analysis:
        result["pages"] = page_analysis.get("pages", [])
        result["page_count"] = page_analysis.get("page_count", 0)
        result["pages_needing_ocr"] = page_analysis.get("pages_needing_ocr", 0)
        result["pages_with_text"] = page_analysis.get("pages_with_text", 0)
        # Override overall decision with page-level analysis if available
        if page_analysis.get("overall_needs_ocr") is not None:
            result["needs_ocr"] = page_analysis["overall_needs_ocr"]
            result["confidence"] = page_analysis["overall_confidence"]
            result["reason_code"] = page_analysis["overall_reason_code"]
            result["reason"] = page_analysis["overall_reason"]

    # Add layout analysis results if available (from pdfplumber-based analyzer)
    if layout_result:
        result["layout"] = {
            "text_coverage": layout_result.get("text_coverage", 0.0),
            "image_coverage": layout_result.get("image_coverage", 0.0),
            "has_images": layout_result.get("has_images", False),
            "text_density": layout_result.get("text_density", 0.0),
            "layout_type": layout_result.get("layout_type", "unknown"),
            "is_mixed_content": layout_result.get("is_mixed_content", False),
        }
        if page_level and "pages" in layout_result:
            result["layout"]["pages"] = layout_result["pages"]

    # Add OpenCV layout results if available (from OpenCV-based analyzer)
    if collected_signals.get("opencv_layout"):
        opencv_layout_data = collected_signals["opencv_layout"]
        if "layout" not in result:
            result["layout"] = {}
        result["layout"]["opencv"] = {
            "text_coverage": opencv_layout_data.get("text_coverage", 0.0),
            "image_coverage": opencv_layout_data.get("image_coverage", 0.0),
            "text_regions": opencv_layout_data.get("text_regions", 0),
            "image_regions": opencv_layout_data.get("image_regions", 0),
            "has_text_regions": opencv_layout_data.get("has_text_regions", False),
            "has_image_regions": opencv_layout_data.get("has_image_regions", False),
            "layout_type": opencv_layout_data.get("layout_type", "unknown"),
            "layout_complexity": opencv_layout_data.get("layout_complexity", "unknown"),
            "total_pages": opencv_layout_data.get("total_pages", 0),
            "pages_analyzed": opencv_layout_data.get("pages_analyzed", 0),
        }
        if page_level and "pages" in opencv_layout_data:
            result["layout"]["opencv"]["pages"] = opencv_layout_data["pages"]

    # Cache result if enabled
    if use_cache:
        if progress_callback:
            progress_callback("caching", 0.9)
        # Add cache metadata
        result["_cache_page_level"] = page_level
        result["_cache_layout_aware"] = layout_aware
        cache_result(str(path), result)

    if progress_callback:
        progress_callback("complete", 1.0)

    return result


def _get_file_type_category(mime: str, extension: str) -> str:
    """Get a user-friendly file type category."""
    if mime.startswith("image/"):
        return "image"
    elif mime == "application/pdf" or extension == "pdf":
        return "pdf"
    elif "officedocument" in mime or extension in ["docx", "pptx", "xlsx", "doc", "ppt", "xls"]:
        return "office"
    elif mime.startswith("text/") or extension in ["txt", "csv", "html", "htm"]:
        return "text"
    elif mime in ["application/json", "application/xml"] or extension in ["json", "xml"]:
        return "structured"
    else:
        return "unknown"
