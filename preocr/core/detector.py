"""Main API for OCR detection."""

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from .. import constants
from ..analysis import layout_analyzer, opencv_layout, page_detection
from ..probes import image_probe, office_probe, pdf_probe, text_probe
from ..utils import cache, filetype, logger as logger_module, telemetry
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
    telemetry_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
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
        telemetry_callback: Optional callback(event, data) for structured telemetry events.
            Also enable PREOCR_TELEMETRY=1 for default JSON logging.

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

    Note on Confidence Scores:
        Confidence scores may vary between page_level=True and page_level=False modes:

        - **Without page_level**: Confidence is calculated based on document-level heuristics
          and OpenCV analysis (if triggered). Typical range: 0.60-0.95.

        - **With page_level=True**: Confidence is calculated as the average of per-page
          confidence scores, adjusted for consistency. For mixed documents (some pages
          need OCR, some don't), confidence may be lower due to the averaging effect.
          Typical range: 0.60-0.95, but may be lower for mixed documents.

        - **Why the difference**: Page-level analysis provides more granular information
          but averages confidence across pages. Document-level analysis uses overall
          text extraction and layout analysis, which can be more confident for uniform
          documents.

        Both modes are accurate; the difference reflects the analysis granularity.
        Use page_level=True when you need per-page decisions, otherwise use the
        default (page_level=False) for faster, document-level decisions.

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
    skip_page_analysis_for_variance = False
    font_count: Optional[int] = None

    if mime == "application/pdf":
        # PDF text extraction (with optional page-level analysis)
        if progress_callback:
            progress_callback("extracting_pdf_text", 0.3)
        text_result = pdf_probe_module.extract_pdf_text(str(path), page_level=page_level)
        font_count = layout_analyzer_module.get_pdf_font_count(str(path))

        # 1. Hard Digital Check (early exit) - runs before layout / OpenCV / scoring
        # If PDF has extractable text >= threshold → NO OCR. Saves compute for design-heavy PDFs.
        c = config or Config()
        text_length = text_result.get("text_length", 0)
        if text_length >= c.hard_digital_text_threshold:
            telemetry.emit_with_callback(
                telemetry_callback,
                "digital_guard_exit",
                {"text_length": text_length, "needs_ocr": False},
            )
            if progress_callback:
                progress_callback("complete", 1.0)
            minimal_signals = signals.collect_signals(
                str(path), file_info, text_result, image_result, None
            )
            result = _build_result(
                needs_ocr=False,
                file_type_category="pdf",
                category=constants.CATEGORY_STRUCTURED,
                confidence=c.high_confidence,
                reason=f"Digital PDF with extractable text ({text_length} chars, hard digital guard)",
                reason_code=constants.ReasonCode.PDF_DIGITAL,
                signals=minimal_signals,
            )
            if page_level and "pages" in text_result:
                pages = [{**p, "needs_ocr": False} for p in text_result["pages"]]
                result["pages"] = pages
                result["page_count"] = text_result.get("page_count", len(pages))
                result["pages_needing_ocr"] = 0
                result["pages_with_text"] = sum(1 for p in pages if p.get("has_text", False))
            return result

        # 2. Hard Scan Shortcut - obvious scans: image>85%, text<10, font_count==0 → direct OCR
        # font_count==0 guards against digital PDFs with background raster images
        if text_length < getattr(constants, "HARD_SCAN_SHORTCUT_TEXT_MAX", 10):
            quick_img = layout_analyzer_module.get_quick_image_coverage(str(path))
            font_ok = font_count is None or font_count == 0
            if (
                font_ok
                and quick_img is not None
                and quick_img >= getattr(constants, "HARD_SCAN_SHORTCUT_IMAGE_MIN", 85.0)
            ):
                telemetry.emit_with_callback(
                    telemetry_callback,
                    "hard_scan_shortcut",
                    {"image_coverage": quick_img, "text_length": text_length},
                )
                if progress_callback:
                    progress_callback("complete", 1.0)
                minimal_signals = signals.collect_signals(
                    str(path), file_info, text_result, image_result, None
                )
                minimal_signals["image_coverage"] = quick_img
                minimal_signals["font_count"] = font_count
                result = _build_result(
                    needs_ocr=True,
                    file_type_category="pdf",
                    category=constants.CATEGORY_UNSTRUCTURED,
                    confidence=0.95,
                    reason=f"Hard scan shortcut: {quick_img:.1f}% images, {text_length} chars",
                    reason_code=constants.ReasonCode.PDF_SCANNED,
                    signals=minimal_signals,
                )
                if page_level and "pages" in text_result:
                    pages = [{**p, "needs_ocr": True} for p in text_result["pages"]]
                    result["pages"] = pages
                    result["page_count"] = text_result.get("page_count", len(pages))
                    result["pages_needing_ocr"] = len(pages)
                    result["pages_with_text"] = 0
                return result

        # Perform layout analysis if requested
        if layout_aware:
            if progress_callback:
                progress_callback("analyzing_layout", 0.5)
            layout_result = layout_analyzer_module.analyze_pdf_layout(
                str(path), page_level=page_level
            )

        # Perform page-level analysis if requested (with variance-based escalation)
        # Only run full page-level when std(page_scores) > threshold (pages differ)
        if page_level and "pages" in text_result:
            c = config or Config()
            pages_data = text_result.get("pages", [])
            std_threshold = getattr(c, "variance_page_escalation_std", 0.18)
            if std_threshold > 0 and len(pages_data) >= 3:
                scores = [
                    1.0 if p.get("text_length", 0) < constants.MIN_TEXT_LENGTH else 0.0
                    for p in pages_data
                ]
                if len(scores) >= 2:
                    mean_s = sum(scores) / len(scores)
                    var_s = sum((x - mean_s) ** 2 for x in scores) / len(scores)
                    std_s = (var_s**0.5) if var_s > 0 else 0.0
                    if std_s <= std_threshold:
                        skip_page_analysis_for_variance = True
            if not skip_page_analysis_for_variance:
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

    # Step 3: Collect all signals (font_count already set for PDFs in block above)
    if mime != "application/pdf":
        font_count = None  # Only PDFs have font_count
    collected_signals = signals.collect_signals(
        str(path), file_info, text_result, image_result, layout_result, font_count=font_count
    )

    # Step 4: Make initial decision (heuristics)
    # Use config's layout_refinement_threshold if provided, otherwise use default
    refinement_threshold = (
        config.layout_refinement_threshold if config else LAYOUT_REFINEMENT_THRESHOLD
    )
    needs_ocr_flag, reason, confidence, category, reason_code = decision.decide(
        collected_signals, config=config
    )

    # Step 5: Confidence band → OpenCV layout refinement (if needed)
    # >= 0.90: immediate exit | 0.75-0.90: skip unless image-heavy | 0.50-0.75: light (2-3 pg) | < 0.50: full
    c = config or Config()
    conf_exit = getattr(c, "confidence_exit_threshold", 0.90)
    conf_light = getattr(c, "confidence_light_refinement_min", 0.50)
    skip_image_guard = getattr(c, "skip_opencv_image_guard", None) or getattr(
        c, "confidence_image_heavy_threshold", 50.0
    )
    run_opencv = mime == "application/pdf" and (layout_aware or confidence < refinement_threshold)
    if run_opencv and confidence >= conf_exit:
        run_opencv = False  # >= 0.90: immediate exit
        telemetry.emit_with_callback(
            telemetry_callback,
            "opencv_skipped",
            {"reason": "confidence_exit", "confidence": confidence},
        )
    elif run_opencv and 0.75 <= confidence < conf_exit:
        # 0.75-0.90: skip OpenCV unless image-heavy
        ic = collected_signals.get("image_coverage")
        if ic is None or ic <= skip_image_guard:
            run_opencv = False
            telemetry.emit_with_callback(
                telemetry_callback,
                "opencv_skipped",
                {
                    "reason": "confidence_band_075_090",
                    "confidence": confidence,
                    "image_coverage": ic,
                    "skip_opencv_image_guard": skip_image_guard,
                },
            )
    use_light_refinement = run_opencv and conf_light <= confidence < 0.75
    if run_opencv and config:
        # Optional heuristics: skip OpenCV when document clearly looks digital
        c = config
        file_size_mb = collected_signals.get("file_size", 0) / (1024.0 * 1024.0)
        page_count = collected_signals.get("page_count", 0)
        text_coverage = collected_signals.get("text_coverage")
        image_coverage = collected_signals.get("image_coverage")
        has_skip_triggers = (c.skip_opencv_if_file_size_mb is not None) or (
            c.skip_opencv_if_page_count is not None
        )
        if has_skip_triggers:
            # Never skip when image_coverage exceeds threshold (suggests scanned content)
            image_ok = c.skip_opencv_max_image_coverage is None or (
                image_coverage is not None and image_coverage <= c.skip_opencv_max_image_coverage
            )
            file_size_ok = (
                c.skip_opencv_if_file_size_mb is not None
                and file_size_mb >= c.skip_opencv_if_file_size_mb
            )
            text_ok_for_pages = c.skip_opencv_text_coverage_min is None or (
                text_coverage is not None and text_coverage >= c.skip_opencv_text_coverage_min
            )
            page_count_ok = (
                c.skip_opencv_if_page_count is not None
                and page_count >= c.skip_opencv_if_page_count
                and text_ok_for_pages
            )
            confidence_ok = (
                c.skip_opencv_confidence_min is None or confidence >= c.skip_opencv_confidence_min
            )
            strong_digital_signal = (file_size_ok or page_count_ok) and image_ok and confidence_ok
            if strong_digital_signal:
                run_opencv = False
                logger.debug(
                    "Skipping OpenCV refinement (strong digital signals: file_size_mb=%.3f, "
                    "page_count=%d, text_coverage=%s)",
                    file_size_mb,
                    page_count,
                    text_coverage,
                )
    if run_opencv:
        telemetry.emit_with_callback(
            telemetry_callback,
            "opencv_run",
            {"refinement": "light" if use_light_refinement else "full"},
        )
        if progress_callback:
            progress_callback("opencv_analysis", 0.7)
        max_pages = 2 if use_light_refinement else None
        opencv_result = opencv_layout_module.analyze_with_opencv(
            str(path), page_level=page_level, max_pages_to_analyze=max_pages
        )
        if opencv_result:
            # Add OpenCV results to signals BEFORE refining (so hybrid rule can use it)
            collected_signals["opencv_layout"] = opencv_result

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

    # Step 6: Determine file type category for user
    file_type_category = _get_file_type_category(mime, extension)

    # Build hints (suggested_engine, preprocessing) - only when needs_ocr
    hints = _compute_adaptive_ocr_signals(collected_signals, needs_ocr_flag)

    # Build result with signal/decision/hints separation (and backward-compat flat keys)
    result = {
        # Flat keys (backward compatibility)
        "needs_ocr": needs_ocr_flag,
        "file_type": file_type_category,
        "category": category,
        "confidence": confidence,
        "reason": reason,
        "reason_code": reason_code,
        "signals": collected_signals,
        # Structured separation for debugging
        "decision": {
            "needs_ocr": needs_ocr_flag,
            "confidence": confidence,
            "reason_code": reason_code,
            "reason": reason,
        },
        "hints": {
            "suggested_engine": hints["suggested_engine"],
            "suggest_preprocessing": hints["suggest_preprocessing"],
            "ocr_complexity_score": hints["ocr_complexity_score"],
        },
    }

    # Add page-level results if available (or synthetic when variance skipped)
    if skip_page_analysis_for_variance and page_level and text_result and "pages" in text_result:
        pages_data = text_result["pages"]
        page_count = len(pages_data)
        pages_list = [
            {
                "page_number": p.get("page_number", i + 1),
                "needs_ocr": needs_ocr_flag,
                "text_length": p.get("text_length", 0),
                "confidence": confidence,
                "reason_code": reason_code,
                "reason": reason,
            }
            for i, p in enumerate(pages_data)
        ]
        result["pages"] = pages_list
        result["page_count"] = page_count
        result["pages_needing_ocr"] = page_count if needs_ocr_flag else 0
        result["pages_with_text"] = 0 if needs_ocr_flag else page_count
    elif page_analysis and "pages" in page_analysis:
        page_count = page_analysis.get("page_count", 0)
        pages_list = page_analysis.get("pages", [])

        # Only add page-level data if it's valid
        if page_count > 0 and len(pages_list) > 0:
            result["pages"] = pages_list
            result["page_count"] = page_count
            result["pages_needing_ocr"] = page_analysis.get("pages_needing_ocr", 0)
            result["pages_with_text"] = page_analysis.get("pages_with_text", 0)

            # Override overall decision with page-level analysis only if data is valid
            if page_analysis.get("overall_needs_ocr") is not None:
                # Validate that page-level analysis is complete and consistent
                if len(pages_list) == page_count:
                    # Do not override when document-level has strong digital signals
                    # (avoids 1 sparse page flipping whole doc to needs_ocr=True)
                    tc = collected_signals.get("text_coverage") or 0.0
                    ic = collected_signals.get("image_coverage") or 0.0
                    text_len = collected_signals.get("text_length", 0)
                    text_density = collected_signals.get("text_density") or 0.0
                    c = config or constants.Config()
                    digital_guard = (
                        not needs_ocr_flag
                        and c.digital_bias_text_coverage_min is not None
                        and c.digital_bias_image_coverage_max is not None
                        and tc >= c.digital_bias_text_coverage_min
                        and ic <= c.digital_bias_image_coverage_max
                        and text_len >= c.min_text_length
                    )
                    table_guard = (
                        not needs_ocr_flag
                        and c.table_bias_text_density_min is not None
                        and c.table_bias_text_coverage_min is not None
                        and text_density >= c.table_bias_text_density_min
                        and tc >= c.table_bias_text_coverage_min
                        and text_len >= c.min_text_length
                    )
                    if not (digital_guard or table_guard):
                        result["needs_ocr"] = page_analysis["overall_needs_ocr"]
                        result["confidence"] = page_analysis["overall_confidence"]
                        result["reason_code"] = page_analysis["overall_reason_code"]
                        result["reason"] = page_analysis["overall_reason"]
                        result["decision"]["needs_ocr"] = page_analysis["overall_needs_ocr"]
                        result["decision"]["confidence"] = page_analysis["overall_confidence"]
                        result["decision"]["reason_code"] = page_analysis["overall_reason_code"]
                        result["decision"]["reason"] = page_analysis["overall_reason"]
                        result["hints"] = _compute_adaptive_ocr_signals(
                            collected_signals, page_analysis["overall_needs_ocr"]
                        )
                else:
                    logger.warning(
                        f"Page-level analysis incomplete: {len(pages_list)} pages found, "
                        f"but page_count is {page_count}. Using document-level decision."
                    )
        else:
            logger.debug(
                f"Page-level analysis invalid: page_count={page_count}, "
                f"pages_list length={len(pages_list)}. Using document-level decision."
            )

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


def _compute_adaptive_ocr_signals(signals: Dict[str, Any], needs_ocr: bool) -> Dict[str, Any]:
    """
    Feature-driven OCR engine suggestion based on ocr_complexity_score.
    Score components: layout_complexity, image_ratio (blur proxy), text_weakness.
    Engine tiers: < 0.3 Tesseract | 0.3-0.7 PaddleOCR | > 0.7 Vision LLM.
    """
    if not needs_ocr:
        return {
            "suggested_engine": None,
            "suggest_preprocessing": False,
            "ocr_complexity_score": 0.0,
        }
    ocv = signals.get("opencv_layout", {})
    lc_str = ocv.get("layout_complexity", "simple")
    layout_complexity = 0.6 if lc_str == "complex" else (0.4 if lc_str == "moderate" else 0.2)
    ic = signals.get("image_coverage") or 0.0
    image_ratio = ic / 100.0
    text_len = signals.get("text_length", 0)
    text_weakness = 0.3 if text_len < 20 else (0.2 if text_len < 50 else 0.0)
    # Placeholder components for future: skew_score, blur_score, multilingual_hint, low_contrast
    skew_score = 0.1 if image_ratio > 0.6 else 0.0
    ocr_complexity_score = (
        layout_complexity * 0.3 + image_ratio * 0.35 + text_weakness * 0.25 + skew_score * 0.1
    )
    ocr_complexity_score = min(1.0, ocr_complexity_score)
    if ocr_complexity_score < 0.3:
        suggested_engine = "tesseract"
    elif ocr_complexity_score < 0.7:
        suggested_engine = "paddle"
    else:
        suggested_engine = "vision_llm"
    preprocess = []
    if ic > 60 or layout_complexity >= 0.4:
        preprocess.append("deskew")
    if ic > 50 or text_len < 30:
        preprocess.append("otsu")
    if ic > 70:
        preprocess.append("denoise")
    return {
        "suggested_engine": suggested_engine,
        "suggest_preprocessing": list(dict.fromkeys(preprocess)),
        "ocr_complexity_score": round(ocr_complexity_score, 2),
    }


def _build_result(
    needs_ocr: bool,
    file_type_category: str,
    category: str,
    confidence: float,
    reason: str,
    reason_code: str,
    signals: Dict[str, Any],
) -> Dict[str, Any]:
    """Build result with signal/decision/hints separation."""
    hints = _compute_adaptive_ocr_signals(signals, needs_ocr)
    return {
        "needs_ocr": needs_ocr,
        "file_type": file_type_category,
        "category": category,
        "confidence": confidence,
        "reason": reason,
        "reason_code": reason_code,
        "signals": signals,
        "decision": {
            "needs_ocr": needs_ocr,
            "confidence": confidence,
            "reason_code": reason_code,
            "reason": reason,
        },
        "hints": {
            "suggested_engine": hints["suggested_engine"],
            "suggest_preprocessing": hints["suggest_preprocessing"],
            "ocr_complexity_score": hints["ocr_complexity_score"],
        },
    }


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
