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

        # Layout-aware decision (if layout analysis was performed)
        if layout_type and layout_type != "unknown":
            # Mixed content: has both text and images
            if is_mixed_content:
                # If text coverage is significant, might not need full OCR
                if text_length >= config.min_text_length and text_coverage > 10:
                    return (
                        False,
                        f"{get_reason_description(ReasonCode.PDF_DIGITAL)} (mixed content, {text_length} chars, {text_coverage:.1f}% text coverage)",
                        config.medium_confidence,
                        CATEGORY_STRUCTURED,
                        ReasonCode.PDF_DIGITAL,
                    )
                else:
                    # Mixed but text is sparse - needs OCR for images
                    return (
                        True,
                        f"{get_reason_description(ReasonCode.PDF_MIXED)} ({text_length} chars, {image_coverage:.1f}% images)",
                        config.medium_confidence,
                        CATEGORY_UNSTRUCTURED,
                        ReasonCode.PDF_MIXED,
                    )

            # Image-only layout
            elif layout_type == "image_only":
                return (
                    True,
                    f"{get_reason_description(ReasonCode.PDF_SCANNED)} (image-only layout, {image_coverage:.1f}% images)",
                    config.high_confidence,
                    CATEGORY_UNSTRUCTURED,
                    ReasonCode.PDF_SCANNED,
                )

            # Text-only layout
            elif layout_type == "text_only":
                if text_length >= config.min_text_length:
                    return (
                        False,
                        f"{get_reason_description(ReasonCode.PDF_DIGITAL)} (text-only layout, {text_length} chars)",
                        config.high_confidence,
                        CATEGORY_STRUCTURED,
                        ReasonCode.PDF_DIGITAL,
                    )
                else:
                    # Text-only but sparse - might be scanned text
                    return (
                        True,
                        f"{get_reason_description(ReasonCode.PDF_SCANNED)} (text-only layout but sparse, {text_length} chars)",
                        config.medium_confidence,
                        CATEGORY_UNSTRUCTURED,
                        ReasonCode.PDF_SCANNED,
                    )

        # Fallback to text-length based decision (when layout analysis not available)
        if text_length >= config.min_text_length:
            # Calculate confidence based on text length (more text = higher confidence)
            # Scale from 0.85 to 0.95 based on text length
            file_size = signals.get("file_size", 1)
            text_ratio = min(text_length / max(file_size / 10, config.min_text_length), 1.0)
            confidence = 0.85 + (text_ratio * 0.1)  # Range: 0.85 to 0.95
            confidence = min(confidence, config.high_confidence)

            return (
                False,
                f"{get_reason_description(ReasonCode.PDF_DIGITAL)} ({text_length} chars)",
                round(confidence, 2),
                CATEGORY_STRUCTURED,
                ReasonCode.PDF_DIGITAL,
            )
        else:
            # Calculate confidence based on how close text_length is to threshold
            # Formula: confidence = 0.60 + (proximity_to_threshold * 0.15)
            # - 0 chars: 0.60 (lowest - might be image-only)
            # - Close to threshold: 0.75 (highest - definitely scanned text)
            # Linear interpolation between 0 and min_text_length
            if config.min_text_length > 0:
                proximity_factor = min(text_length / config.min_text_length, 1.0)
                confidence = 0.60 + (proximity_factor * 0.15)  # Range: 0.60 to 0.75
            else:
                confidence = 0.65  # Fallback

            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_SCANNED)} ({text_length} chars)",
                round(confidence, 2),
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

    # Refinement logic based on OpenCV analysis
    # Use layout_type for more accurate decisions

    # Case 1: Text-only layout
    if layout_type == "text_only":
        if text_length >= config.min_text_length and text_coverage_opencv > 15:
            # Digital text document - calculate confidence based on text length and coverage
            text_factor = min(text_length / (config.min_text_length * 10), 1.0)  # Normalize
            coverage_factor = min(text_coverage_opencv / 50.0, 1.0)  # Normalize
            confidence = 0.88 + ((text_factor + coverage_factor) / 2 * 0.07)  # Range: 0.88 to 0.95
            confidence = min(confidence, config.high_confidence)

            return (
                False,
                f"{get_reason_description(ReasonCode.PDF_DIGITAL)} (OpenCV detected text-only layout, {text_length} chars, {text_coverage_opencv:.1f}% coverage)",
                round(confidence, 2),
                CATEGORY_STRUCTURED,
                ReasonCode.PDF_DIGITAL,
            )
        elif text_length < config.min_text_length and text_coverage_opencv > 10:
            # Text regions detected but no extractable text = likely scanned text
            # Calculate confidence based on text coverage (more coverage = higher confidence)
            coverage_factor = min(text_coverage_opencv / 30.0, 1.0)  # Normalize to 0-1
            confidence = 0.75 + (coverage_factor * 0.15)  # Range: 0.75 to 0.90
            confidence = min(confidence, config.high_confidence)

            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_SCANNED)} (OpenCV detected text-only layout but no extractable text, {text_coverage_opencv:.1f}% coverage)",
                round(confidence, 2),
                CATEGORY_UNSTRUCTURED,
                ReasonCode.PDF_SCANNED,
            )

    # Case 2: Image-only layout
    elif layout_type == "image_only":
        return (
            True,
            f"{get_reason_description(ReasonCode.PDF_SCANNED)} (OpenCV detected image-only layout, {image_coverage_opencv:.1f}% images)",
            min(initial_confidence + 0.2, config.high_confidence),
            CATEGORY_UNSTRUCTURED,
            ReasonCode.PDF_SCANNED,
        )

    # Case 3: Mixed content layout
    elif layout_type == "mixed":
        if text_coverage_opencv > 15 and text_length >= config.min_text_length:
            # Text is significant, might not need full OCR
            # Calculate confidence based on text vs image ratio
            total_coverage = text_coverage_opencv + image_coverage_opencv
            if total_coverage > 0:
                text_ratio = text_coverage_opencv / total_coverage
                confidence = 0.80 + (text_ratio * 0.10)  # Range: 0.80 to 0.90
            else:
                confidence = 0.80
            confidence = min(confidence, config.high_confidence)

            return (
                False,
                f"{get_reason_description(ReasonCode.PDF_DIGITAL)} (OpenCV detected mixed content, text sufficient, {text_length} chars, {text_coverage_opencv:.1f}% text, {image_coverage_opencv:.1f}% images)",
                round(confidence, 2),
                CATEGORY_STRUCTURED,
                ReasonCode.PDF_DIGITAL,
            )
        else:
            # Mixed but text is sparse, needs OCR
            # Calculate confidence based on image coverage (more images = higher confidence needs OCR)
            image_factor = min(image_coverage_opencv / 50.0, 1.0)
            confidence = 0.75 + (image_factor * 0.10)  # Range: 0.75 to 0.85
            confidence = min(confidence, config.high_confidence)

            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_MIXED)} (OpenCV detected mixed content, {text_coverage_opencv:.1f}% text, {image_coverage_opencv:.1f}% images)",
                round(confidence, 2),
                CATEGORY_UNSTRUCTURED,
                ReasonCode.PDF_MIXED,
            )

    # If OpenCV confirms initial decision, increase confidence
    if (initial_needs_ocr and not has_text_regions) or (not initial_needs_ocr and has_text_regions):
        return (
            initial_needs_ocr,
            f"{initial_reason} (OpenCV confirmed)",
            min(initial_confidence + 0.1, config.high_confidence),
            initial_category,
            initial_reason_code,
        )

    # Default: return refined but keep initial decision
    return (
        initial_needs_ocr,
        f"{initial_reason} (OpenCV refined)",
        min(initial_confidence + 0.05, config.high_confidence),
        initial_category,
        initial_reason_code,
    )
