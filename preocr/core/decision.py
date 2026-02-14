"""Decision engine to determine if OCR is needed."""

from typing import Any, Dict, Optional, Tuple

from .. import constants, reason_codes

CATEGORY_STRUCTURED = constants.CATEGORY_STRUCTURED
CATEGORY_UNSTRUCTURED = constants.CATEGORY_UNSTRUCTURED
Config = constants.Config
ReasonCode = constants.ReasonCode
get_reason_description = reason_codes.get_reason_description

# Default config instance for backward compatibility
_DEFAULT_CONFIG = Config()


def calculate_ocr_score(
    text_length: int,
    image_coverage: float,
    text_coverage: float,
    config: Optional[Config] = None,
) -> float:
    """
    Calculate OCR_SCORE using pixel-aware scoring model.

    OCR_SCORE = 0.35 * image_ratio + 0.25 * (1 - alphabet_ratio) +
                0.2 * low_text_density + 0.2 * font_suspicion

    Args:
        text_length: Length of extracted text
        image_coverage: Image coverage percentage (0-100)
        text_coverage: Text coverage percentage (0-100)
        config: Optional Config object

    Returns:
        OCR_SCORE (0.0-1.0) where higher score indicates more likely to need OCR
    """
    if config is None:
        config = _DEFAULT_CONFIG

    # Calculate image_ratio from image_coverage (convert percentage to ratio)
    image_ratio = image_coverage / 100.0 if image_coverage > 0 else 0.0
    image_weight = (
        config.ocr_score_image_weight if config.ocr_score_image_weight is not None else 0.35
    )

    # Approximate alphabet_ratio (normalized text length factor)
    max_expected_text = 10000  # Reasonable max for a page
    alphabet_ratio = min(text_length / max_expected_text, 1.0) if text_length > 0 else 0.0

    # Calculate low_text_density (inverse of text_coverage, normalized)
    text_density_val = text_coverage / 100.0 if text_coverage > 0 else 0.0
    low_text_density = 1.0 - min(text_density_val, 1.0)

    # Font suspicion: higher when text_length is very low
    font_suspicion = 1.0 - min(text_length / 50.0, 1.0) if text_length < 50 else 0.0

    # Calculate OCR score (image_weight configurable for generic/financial PDFs)
    ocr_score = (
        image_weight * image_ratio
        + 0.25 * (1.0 - alphabet_ratio)
        + 0.20 * low_text_density
        + 0.20 * font_suspicion
    )

    return round(ocr_score, 3)


def calculate_confidence_from_signals(
    signals: Dict[str, Any],
    needs_ocr: bool,
    ocr_score: Optional[float] = None,
    config: Optional[Config] = None,
) -> float:
    """
    Calculate confidence score from signals using unified approach.

    Priority:
    1. Use OCR_SCORE if available (most accurate)
    2. Use layout-based calculation
    3. Fallback to text-length based

    Args:
        signals: Dictionary of signals from signals.collect_signals()
        needs_ocr: Boolean indicating if OCR is needed
        ocr_score: Optional OCR_SCORE (0.0-1.0) if already calculated
        config: Optional Config object

    Returns:
        Confidence score (0.0-1.0)
    """
    if config is None:
        config = _DEFAULT_CONFIG

    # Priority 1: Use OCR_SCORE if available (most accurate)
    if ocr_score is not None and config.use_ocr_score_confidence:
        # Calibrate OCR_SCORE to confidence range (0.50-0.95)
        if needs_ocr:
            # Higher OCR_SCORE = higher confidence for "needs OCR"
            confidence = 0.50 + (ocr_score * 0.45)  # Range: 0.50-0.95
        else:
            # Lower OCR_SCORE = higher confidence for "no OCR"
            confidence = 0.50 + ((1.0 - ocr_score) * 0.45)  # Range: 0.50-0.95
        return round(confidence, 2)

    # Priority 2: Layout-based (if layout data available)
    layout_type = signals.get("layout_type")
    if layout_type and layout_type != "unknown":
        text_coverage = float(signals.get("text_coverage", 0.0))
        image_coverage = float(signals.get("image_coverage", 0.0))

        if needs_ocr:
            # More images = higher confidence
            image_factor = min(image_coverage / 100.0, 1.0)
            confidence = 0.60 + (image_factor * 0.30)  # Range: 0.60-0.90
        else:
            # More text = higher confidence
            text_factor = min(text_coverage / 100.0, 1.0)
            confidence = 0.70 + (text_factor * 0.25)  # Range: 0.70-0.95
        return round(confidence, 2)

    # Priority 3: Text-length based fallback
    text_length = signals.get("text_length", 0)
    if needs_ocr:
        # Less text = higher confidence (scanned)
        if text_length == 0:
            confidence = 0.65  # High confidence for no text
        else:
            proximity = min(text_length / config.min_text_length, 1.0)
            confidence = 0.55 + ((1.0 - proximity) * 0.20)  # Range: 0.55-0.75
    else:
        # More text = higher confidence (digital)
        text_factor = min(text_length / 1000.0, 1.0)
        confidence = 0.75 + (text_factor * 0.20)  # Range: 0.75-0.95

    return round(confidence, 2)


def decide(
    signals: Dict[str, Any], config: Optional[Config] = None
) -> Tuple[bool, str, float, str, str]:
    """
    Decide if a file needs OCR based on collected signals.

    Args:
        signals: Dictionary of signals from signals.collect_signals()
        config: Optional Config object with threshold settings. If None, uses default thresholds.

    Returns:
        Tuple of:
            - needs_ocr: Boolean indicating if OCR is needed
            - reason: Human-readable reason for the decision
            - confidence: Confidence score (0.0-1.0)
            - category: "structured" or "unstructured"
            - reason_code: Structured reason code (e.g., "PDF_DIGITAL", "IMAGE_FILE")
    """
    if config is None:
        config = _DEFAULT_CONFIG

    mime = signals.get("mime", "")
    text_length = signals.get("text_length", 0)
    extension = signals.get("extension", "")
    is_binary = signals.get("is_binary", True)

    # Rule 1: Plain text formats - NO OCR
    if mime.startswith("text/"):
        return (
            False,
            get_reason_description(ReasonCode.TEXT_FILE),
            config.high_confidence,
            CATEGORY_STRUCTURED,
            ReasonCode.TEXT_FILE,
        )

    # Rule 2: Office documents with text - NO OCR
    if "officedocument" in mime or extension in ["docx", "pptx", "xlsx"]:
        if text_length >= config.min_office_text_length:
            return (
                False,
                f"{get_reason_description(ReasonCode.OFFICE_WITH_TEXT)} ({text_length} chars)",
                config.high_confidence,
                CATEGORY_STRUCTURED,
                ReasonCode.OFFICE_WITH_TEXT,
            )
        else:
            return (
                True,
                f"{get_reason_description(ReasonCode.OFFICE_NO_TEXT)} ({text_length} chars)",
                config.medium_confidence,
                CATEGORY_UNSTRUCTURED,
                ReasonCode.OFFICE_NO_TEXT,
            )

    # Rule 3: Images - YES OCR (always)
    if mime.startswith("image/"):
        return (
            True,
            get_reason_description(ReasonCode.IMAGE_FILE),
            config.high_confidence,
            CATEGORY_UNSTRUCTURED,
            ReasonCode.IMAGE_FILE,
        )

    # Rule 4: PDFs (with optional layout-aware analysis)
    if mime == "application/pdf" or extension == "pdf":
        # Check if layout analysis is available
        layout_type = signals.get("layout_type")
        is_mixed_content = signals.get("is_mixed_content", False)
        text_coverage = signals.get("text_coverage", 0.0)
        image_coverage = signals.get("image_coverage", 0.0)

        # Calculate image_ratio from image_coverage (convert percentage to ratio)
        # Also check OpenCV results if available (more accurate for scanned PDFs)
        opencv_layout = signals.get("opencv_layout", {})
        image_coverage_opencv = opencv_layout.get("image_coverage", 0.0) if opencv_layout else 0.0
        text_coverage_opencv = opencv_layout.get("text_coverage", 0.0) if opencv_layout else 0.0

        # Use OpenCV coverage if available (more accurate), otherwise use layout analyzer
        effective_image_coverage = (
            image_coverage_opencv if image_coverage_opencv > 0 else image_coverage
        )
        effective_text_coverage = (
            text_coverage_opencv if text_coverage_opencv > 0 else text_coverage
        )
        image_ratio = effective_image_coverage / 100.0 if effective_image_coverage > 0 else 0.0

        # Calculate OCR_SCORE for unified confidence calculation
        ocr_score = None
        if layout_type and layout_type != "unknown":
            ocr_score = calculate_ocr_score(
                text_length, effective_image_coverage, text_coverage, config
            )

        # Digital bias: high text + moderate image = digital (protects product/manual PDFs)
        tc_min = config.digital_bias_text_coverage_min
        ic_max = config.digital_bias_image_coverage_max
        if (
            tc_min is not None
            and ic_max is not None
            and effective_text_coverage >= tc_min
            and effective_image_coverage <= ic_max
            and text_length >= config.min_text_length
        ):
            confidence = calculate_confidence_from_signals(
                signals, needs_ocr=False, ocr_score=ocr_score, config=config
            )
            confidence = max(confidence, 0.85)
            return (
                False,
                f"{get_reason_description(ReasonCode.PDF_DIGITAL)} (high text coverage {effective_text_coverage:.1f}%, digital bias)",
                confidence,
                CATEGORY_STRUCTURED,
                ReasonCode.PDF_DIGITAL,
            )

        # 🔥 Hybrid Rule: Sweet spot for OCR detection
        # If image_ratio > 0.75 AND extracted_text_length < 30 → OCR
        # This catches scanned PDFs that are image-heavy with minimal extractable text
        if image_ratio > 0.75 and text_length < 30:
            # Use unified confidence calculation
            confidence = calculate_confidence_from_signals(
                signals, needs_ocr=True, ocr_score=ocr_score, config=config
            )
            # Ensure high confidence for hybrid rule (override if needed)
            confidence = max(confidence, 0.90)
            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_SCANNED)} (hybrid rule: {effective_image_coverage:.1f}% images, {text_length} chars)",
                confidence,
                CATEGORY_UNSTRUCTURED,
                ReasonCode.PDF_SCANNED,
            )

        # Alternative: If text_length is very low (< 30) and we have layout data suggesting images
        # This handles cases where scanned PDFs aren't detected as images but have no text
        if text_length < 30 and layout_type and layout_type != "unknown":
            # Check if layout suggests image-heavy content
            if image_coverage > 50.0 or (is_mixed_content and image_coverage > text_coverage):
                confidence = calculate_confidence_from_signals(
                    signals, needs_ocr=True, ocr_score=ocr_score, config=config
                )
                return (
                    True,
                    f"{get_reason_description(ReasonCode.PDF_SCANNED)} (low text + high image content: {text_length} chars, {image_coverage:.1f}% images)",
                    confidence,
                    CATEGORY_UNSTRUCTURED,
                    ReasonCode.PDF_SCANNED,
                )

        # Layout-aware decision (if layout analysis was performed)
        if layout_type and layout_type != "unknown":
            # Mixed content: has both text and images
            if is_mixed_content:
                # Table bias: mixed layout with high text density = tables/digital, not scanned
                td_min = config.table_bias_text_density_min
                tc_min_table = config.table_bias_text_coverage_min
                text_density = signals.get("text_density", 0.0)
                if (
                    td_min is not None
                    and tc_min_table is not None
                    and text_density >= td_min
                    and effective_text_coverage >= tc_min_table
                    and text_length >= config.min_text_length
                ):
                    confidence = calculate_confidence_from_signals(
                        signals, needs_ocr=False, ocr_score=ocr_score, config=config
                    )
                    confidence = max(confidence, 0.80)
                    return (
                        False,
                        f"{get_reason_description(ReasonCode.PDF_DIGITAL)} (mixed layout, high text density {text_density:.1f}, table bias)",
                        confidence,
                        CATEGORY_STRUCTURED,
                        ReasonCode.PDF_DIGITAL,
                    )

                # Special case: Very high image coverage (>70%) may contain text in images
                # Even if extractable text exists, background images might need OCR
                # This handles cases like PrinceCatalogue.pdf with decorative/background images
                if image_coverage > 70.0 and text_length >= config.min_text_length:
                    # High image coverage with extractable text = likely background images with text
                    # Flag as needing OCR for image portions
                    confidence = calculate_confidence_from_signals(
                        signals, needs_ocr=True, ocr_score=ocr_score, config=config
                    )
                    # Ensure reasonable confidence for this case
                    confidence = max(confidence, 0.75)
                    return (
                        True,
                        f"{get_reason_description(ReasonCode.PDF_MIXED)} (high image coverage {image_coverage:.1f}% may contain text in images, {text_length} chars extractable)",
                        confidence,
                        CATEGORY_UNSTRUCTURED,
                        ReasonCode.PDF_MIXED,
                    )

                # If text coverage is significant, might not need full OCR
                if text_length >= config.min_text_length and text_coverage > 10:
                    confidence = calculate_confidence_from_signals(
                        signals, needs_ocr=False, ocr_score=ocr_score, config=config
                    )
                    return (
                        False,
                        f"{get_reason_description(ReasonCode.PDF_DIGITAL)} (mixed content, {text_length} chars, {text_coverage:.1f}% text coverage)",
                        confidence,
                        CATEGORY_STRUCTURED,
                        ReasonCode.PDF_DIGITAL,
                    )
                else:
                    # Mixed but text is sparse - needs OCR for images
                    confidence = calculate_confidence_from_signals(
                        signals, needs_ocr=True, ocr_score=ocr_score, config=config
                    )
                    return (
                        True,
                        f"{get_reason_description(ReasonCode.PDF_MIXED)} ({text_length} chars, {image_coverage:.1f}% images)",
                        confidence,
                        CATEGORY_UNSTRUCTURED,
                        ReasonCode.PDF_MIXED,
                    )

            # Image-only layout
            elif layout_type == "image_only":
                confidence = calculate_confidence_from_signals(
                    signals, needs_ocr=True, ocr_score=ocr_score, config=config
                )
                # Ensure high confidence for image-only
                confidence = max(confidence, 0.85)
                return (
                    True,
                    f"{get_reason_description(ReasonCode.PDF_SCANNED)} (image-only layout, {image_coverage:.1f}% images)",
                    confidence,
                    CATEGORY_UNSTRUCTURED,
                    ReasonCode.PDF_SCANNED,
                )

            # Text-only layout
            elif layout_type == "text_only":
                if text_length >= config.min_text_length:
                    confidence = calculate_confidence_from_signals(
                        signals, needs_ocr=False, ocr_score=ocr_score, config=config
                    )
                    # Ensure high confidence for text-only with sufficient text
                    confidence = max(confidence, 0.85)
                    return (
                        False,
                        f"{get_reason_description(ReasonCode.PDF_DIGITAL)} (text-only layout, {text_length} chars)",
                        confidence,
                        CATEGORY_STRUCTURED,
                        ReasonCode.PDF_DIGITAL,
                    )
                else:
                    # Text-only but sparse - might be scanned text
                    confidence = calculate_confidence_from_signals(
                        signals, needs_ocr=True, ocr_score=ocr_score, config=config
                    )
                    return (
                        True,
                        f"{get_reason_description(ReasonCode.PDF_SCANNED)} (text-only layout but sparse, {text_length} chars)",
                        confidence,
                        CATEGORY_UNSTRUCTURED,
                        ReasonCode.PDF_SCANNED,
                    )

        # OCR_SCORE > 0.6 → OCR (but only if layout analysis available, otherwise use text_length)
        # Use scoring model as additional signal when layout data is available
        if ocr_score is not None and ocr_score > 0.6:
            # Use unified confidence calculation based on OCR_SCORE
            confidence = calculate_confidence_from_signals(
                signals, needs_ocr=True, ocr_score=ocr_score, config=config
            )
            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_SCANNED)} (scoring model: OCR score {ocr_score:.2f}, {image_coverage:.1f}% images, {text_length} chars)",
                confidence,
                CATEGORY_UNSTRUCTURED,
                ReasonCode.PDF_SCANNED,
            )

        # Fallback to text-length based decision (when layout analysis not available)
        if text_length >= config.min_text_length:
            # Use unified confidence calculation (fallback mode)
            confidence = calculate_confidence_from_signals(
                signals, needs_ocr=False, ocr_score=None, config=config
            )
            return (
                False,
                f"{get_reason_description(ReasonCode.PDF_DIGITAL)} ({text_length} chars)",
                confidence,
                CATEGORY_STRUCTURED,
                ReasonCode.PDF_DIGITAL,
            )
        else:
            # Use unified confidence calculation (fallback mode)
            confidence = calculate_confidence_from_signals(
                signals, needs_ocr=True, ocr_score=None, config=config
            )
            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_SCANNED)} ({text_length} chars)",
                confidence,
                CATEGORY_UNSTRUCTURED,
                ReasonCode.PDF_SCANNED,
            )

    # Rule 5: JSON/XML - NO OCR
    if mime in ["application/json", "application/xml"] or extension in ["json", "xml"]:
        return (
            False,
            get_reason_description(ReasonCode.STRUCTURED_DATA),
            config.high_confidence,
            CATEGORY_STRUCTURED,
            ReasonCode.STRUCTURED_DATA,
        )

    # Rule 6: HTML - NO OCR (text can be extracted)
    if mime in ["text/html", "application/xhtml+xml"] or extension in ["html", "htm"]:
        if text_length >= config.min_text_length:
            return (
                False,
                f"{get_reason_description(ReasonCode.HTML_WITH_TEXT)} ({text_length} chars)",
                config.high_confidence,
                CATEGORY_STRUCTURED,
                ReasonCode.HTML_WITH_TEXT,
            )
        else:
            return (
                True,
                get_reason_description(ReasonCode.HTML_MINIMAL),
                config.low_confidence,
                CATEGORY_UNSTRUCTURED,
                ReasonCode.HTML_MINIMAL,
            )

    # Rule 7: Unknown binaries - YES OCR (conservative default)
    if is_binary:
        return (
            True,
            get_reason_description(ReasonCode.UNKNOWN_BINARY),
            config.low_confidence,
            CATEGORY_UNSTRUCTURED,
            ReasonCode.UNKNOWN_BINARY,
        )

    # Fallback: default to needing OCR
    return (
        True,
        get_reason_description(ReasonCode.UNRECOGNIZED_TYPE),
        config.low_confidence,
        CATEGORY_UNSTRUCTURED,
        ReasonCode.UNRECOGNIZED_TYPE,
    )


def refine_with_opencv(
    signals: Dict[str, Any],
    opencv_result: Dict[str, Any],
    initial_needs_ocr: bool,
    initial_reason: str,
    initial_confidence: float,
    initial_category: str,
    initial_reason_code: str,
    config: Optional[Config] = None,
) -> Tuple[bool, str, float, str, str]:
    """
    Refine decision using OpenCV layout analysis results.

    This is called when initial heuristics have low confidence (< layout_refinement_threshold).
    Uses OpenCV layout analysis to improve accuracy.

    Args:
        signals: Original signals from heuristics
        opencv_result: OpenCV layout analysis results
        initial_needs_ocr: Initial decision from heuristics
        initial_reason: Initial reason
        initial_confidence: Initial confidence score
        initial_category: Initial category
        initial_reason_code: Initial reason code
        config: Optional Config object with threshold settings. If None, uses default thresholds.

    Returns:
        Refined decision tuple: (needs_ocr, reason, confidence, category, reason_code)
    """
    if config is None:
        config = _DEFAULT_CONFIG

    text_length = signals.get("text_length", 0)
    text_coverage_opencv = opencv_result.get("text_coverage", 0.0)
    image_coverage_opencv = opencv_result.get("image_coverage", 0.0)
    has_text_regions = opencv_result.get("has_text_regions", False)
    layout_type = opencv_result.get("layout_type", "unknown")

    # Calculate OCR_SCORE from OpenCV results for unified confidence
    ocr_score_opencv = calculate_ocr_score(
        text_length, image_coverage_opencv, text_coverage_opencv, config
    )

    # Update signals with OpenCV layout data for confidence calculation
    signals_with_opencv = signals.copy()
    signals_with_opencv["layout_type"] = layout_type
    signals_with_opencv["text_coverage"] = text_coverage_opencv
    signals_with_opencv["image_coverage"] = image_coverage_opencv

    # Calculate image_ratio from image_coverage (convert percentage to ratio)
    image_ratio = image_coverage_opencv / 100.0 if image_coverage_opencv > 0 else 0.0

    # 🔥 Hybrid Rule: Sweet spot for OCR detection (applied in OpenCV refinement too)
    # If image_ratio > 0.75 AND extracted_text_length < 30 → OCR
    if image_ratio > 0.75 and text_length < 30:
        # Use unified confidence calculation
        confidence = calculate_confidence_from_signals(
            signals_with_opencv, needs_ocr=True, ocr_score=ocr_score_opencv, config=config
        )
        # Ensure high confidence for hybrid rule
        confidence = max(confidence, 0.90)
        return (
            True,
            f"{get_reason_description(ReasonCode.PDF_SCANNED)} (hybrid rule: {image_coverage_opencv:.1f}% images, {text_length} chars)",
            confidence,
            CATEGORY_UNSTRUCTURED,
            ReasonCode.PDF_SCANNED,
        )

    # Digital bias: high text + moderate image = digital (applied in refinement too)
    tc_min = config.digital_bias_text_coverage_min
    ic_max = config.digital_bias_image_coverage_max
    if (
        tc_min is not None
        and ic_max is not None
        and text_coverage_opencv >= tc_min
        and image_coverage_opencv <= ic_max
        and text_length >= config.min_text_length
    ):
        confidence = calculate_confidence_from_signals(
            signals_with_opencv, needs_ocr=False, ocr_score=ocr_score_opencv, config=config
        )
        confidence = max(confidence, 0.85)
        return (
            False,
            f"{get_reason_description(ReasonCode.PDF_DIGITAL)} (OpenCV digital bias: {text_coverage_opencv:.1f}% text, {image_coverage_opencv:.1f}% images)",
            confidence,
            CATEGORY_STRUCTURED,
            ReasonCode.PDF_DIGITAL,
        )

    # Refinement logic based on OpenCV analysis
    # Use layout_type for more accurate decisions

    # Case 1: Text-only layout
    # BUT: Check if layout analyzer detected high image coverage (OpenCV might miss background images)
    layout_analyzer_image_coverage = signals.get("image_coverage", 0.0)
    if layout_type == "text_only":
        # If layout analyzer shows high image coverage (>70%) but OpenCV says text-only,
        # OpenCV likely missed background images - trust layout analyzer instead
        if layout_analyzer_image_coverage > 70.0 and text_length >= config.min_text_length:
            # High image coverage from layout analyzer - images may need OCR
            confidence = calculate_confidence_from_signals(
                signals_with_opencv, needs_ocr=True, ocr_score=ocr_score_opencv, config=config
            )
            confidence = max(confidence, 0.75)
            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_MIXED)} (OpenCV text-only but layout analyzer detected {layout_analyzer_image_coverage:.1f}% images, may contain text in images)",
                confidence,
                CATEGORY_UNSTRUCTURED,
                ReasonCode.PDF_MIXED,
            )

        if text_length >= config.min_text_length and text_coverage_opencv > 15:
            # Digital text document - use unified confidence calculation
            confidence = calculate_confidence_from_signals(
                signals_with_opencv, needs_ocr=False, ocr_score=ocr_score_opencv, config=config
            )
            # Ensure high confidence for text-only with sufficient text
            confidence = max(confidence, 0.85)
            return (
                False,
                f"{get_reason_description(ReasonCode.PDF_DIGITAL)} (OpenCV detected text-only layout, {text_length} chars, {text_coverage_opencv:.1f}% coverage)",
                confidence,
                CATEGORY_STRUCTURED,
                ReasonCode.PDF_DIGITAL,
            )
        elif text_length < config.min_text_length and text_coverage_opencv > 10:
            # Text regions detected but no extractable text = likely scanned text
            # Use unified confidence calculation
            confidence = calculate_confidence_from_signals(
                signals_with_opencv, needs_ocr=True, ocr_score=ocr_score_opencv, config=config
            )
            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_SCANNED)} (OpenCV detected text-only layout but no extractable text, {text_coverage_opencv:.1f}% coverage)",
                confidence,
                CATEGORY_UNSTRUCTURED,
                ReasonCode.PDF_SCANNED,
            )

    # Case 2: Image-only layout
    elif layout_type == "image_only":
        # Use unified confidence calculation
        confidence = calculate_confidence_from_signals(
            signals_with_opencv, needs_ocr=True, ocr_score=ocr_score_opencv, config=config
        )
        # Ensure high confidence for image-only (override if needed)
        confidence = max(confidence, 0.85)
        # Weight with initial confidence: 30% initial, 70% OCR_SCORE-based
        confidence = (initial_confidence * 0.3) + (confidence * 0.7)
        confidence = min(confidence, config.high_confidence)
        return (
            True,
            f"{get_reason_description(ReasonCode.PDF_SCANNED)} (OpenCV detected image-only layout, {image_coverage_opencv:.1f}% images)",
            round(confidence, 2),
            CATEGORY_UNSTRUCTURED,
            ReasonCode.PDF_SCANNED,
        )

    # Case 3: Mixed content layout
    elif layout_type == "mixed":
        # Table bias: high text density = tables/digital
        td_min = config.table_bias_text_density_min
        tc_min_table = config.table_bias_text_coverage_min
        text_density = signals.get("text_density", 0.0)
        if (
            td_min is not None
            and tc_min_table is not None
            and text_density >= td_min
            and text_coverage_opencv >= tc_min_table
            and text_length >= config.min_text_length
        ):
            confidence = calculate_confidence_from_signals(
                signals_with_opencv, needs_ocr=False, ocr_score=ocr_score_opencv, config=config
            )
            confidence = max(confidence, 0.80)
            return (
                False,
                f"{get_reason_description(ReasonCode.PDF_DIGITAL)} (OpenCV mixed, table bias: text_density {text_density:.1f})",
                confidence,
                CATEGORY_STRUCTURED,
                ReasonCode.PDF_DIGITAL,
            )
        if text_coverage_opencv > 15 and text_length >= config.min_text_length:
            # Text is significant, might not need full OCR
            # Use unified confidence calculation
            confidence = calculate_confidence_from_signals(
                signals_with_opencv, needs_ocr=False, ocr_score=ocr_score_opencv, config=config
            )
            return (
                False,
                f"{get_reason_description(ReasonCode.PDF_DIGITAL)} (OpenCV detected mixed content, text sufficient, {text_length} chars, {text_coverage_opencv:.1f}% text, {image_coverage_opencv:.1f}% images)",
                confidence,
                CATEGORY_STRUCTURED,
                ReasonCode.PDF_DIGITAL,
            )
        else:
            # Mixed but text is sparse, needs OCR
            # Use unified confidence calculation
            confidence = calculate_confidence_from_signals(
                signals_with_opencv, needs_ocr=True, ocr_score=ocr_score_opencv, config=config
            )
            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_MIXED)} (OpenCV detected mixed content, {text_coverage_opencv:.1f}% text, {image_coverage_opencv:.1f}% images)",
                confidence,
                CATEGORY_UNSTRUCTURED,
                ReasonCode.PDF_MIXED,
            )

    # If OpenCV confirms initial decision, use weighted confidence
    if (initial_needs_ocr and not has_text_regions) or (not initial_needs_ocr and has_text_regions):
        # Calculate OCR_SCORE-based confidence
        ocr_confidence = calculate_confidence_from_signals(
            signals_with_opencv,
            needs_ocr=initial_needs_ocr,
            ocr_score=ocr_score_opencv,
            config=config,
        )
        # Weighted combination: 30% initial, 70% OCR_SCORE-based (OpenCV is more accurate)
        confidence = (initial_confidence * 0.3) + (ocr_confidence * 0.7)
        confidence = min(confidence, config.high_confidence)
        return (
            initial_needs_ocr,
            f"{initial_reason} (OpenCV confirmed)",
            round(confidence, 2),
            initial_category,
            initial_reason_code,
        )

    # Default: return refined but keep initial decision
    # Use weighted confidence: 50% initial, 50% OCR_SCORE-based
    ocr_confidence = calculate_confidence_from_signals(
        signals_with_opencv, needs_ocr=initial_needs_ocr, ocr_score=ocr_score_opencv, config=config
    )
    confidence = (initial_confidence * 0.5) + (ocr_confidence * 0.5)
    confidence = min(confidence, config.high_confidence)
    return (
        initial_needs_ocr,
        f"{initial_reason} (OpenCV refined)",
        round(confidence, 2),
        initial_category,
        initial_reason_code,
    )
