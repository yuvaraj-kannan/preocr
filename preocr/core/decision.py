"""Decision engine to determine if OCR is needed."""

from typing import Any, Dict, Optional, Tuple

from .. import constants, reason_codes

CATEGORY_STRUCTURED = constants.CATEGORY_STRUCTURED
CATEGORY_UNSTRUCTURED = constants.CATEGORY_UNSTRUCTURED
Config = constants.Config
ReasonCode = constants.ReasonCode
get_reason_description = reason_codes.get_reason_description

_DEFAULT_CONFIG = Config()


# ─────────────────────────────────────────────
# CHANGE 1: Direct ocr_score formula
# Before:  digital_score = ... ; ocr_score = 1 - digital_score
# After:   ocr_score computed directly — easier to reason about
# ─────────────────────────────────────────────
def _calculate_ocr_score_from_signals(
    signals: Dict[str, Any],
    text_coverage: float,
    image_coverage: float,
    config: Optional[Config] = None,
) -> float:
    """
    Calculate OCR_SCORE using direct weighted scoring model.

    Returns score 0–1 where:
        0 = confidently digital
        1 = confidently scanned

    Components (all normalized to [0, 1]):
        image_norm   ↑  → scanned (image-heavy)
        noise_norm   ↑  → scanned (bad text layer)
        text_norm    ↓  → scanned (little extractable text)
        font_norm    ↓  → scanned (no embedded fonts)
    """
    if config is None:
        config = _DEFAULT_CONFIG

    # Raw signals
    text_length = int(signals.get("text_length", 0) or 0)
    non_printable = float(signals.get("non_printable_ratio", 0.0) or 0.0)
    unicode_noise = float(signals.get("unicode_noise_ratio", 0.0) or 0.0)
    font_count = signals.get("font_count")
    font_count_int = int(font_count) if isinstance(font_count, int) and font_count >= 0 else 0

    # Normalize to [0, 1]
    text_norm = min(text_length / 200.0, 1.0) if text_length > 0 else 0.0
    image_norm = max(0.0, min(image_coverage / 100.0, 1.0)) if image_coverage > 0 else 0.0
    noise_raw = (
        (non_printable + unicode_noise) / 2.0 if (non_printable > 0 or unicode_noise > 0) else 0.0
    )
    noise_norm = max(0.0, min(noise_raw, 1.0))
    font_norm = max(0.0, min(font_count_int / 5.0, 1.0)) if font_count_int > 0 else 0.0

    # Weights
    text_w = config.ocr_score_text_weight if config.ocr_score_text_weight is not None else 0.35
    image_w = config.ocr_score_image_weight if config.ocr_score_image_weight is not None else 0.35
    noise_w = config.ocr_score_noise_weight if config.ocr_score_noise_weight is not None else 0.20
    font_w = config.ocr_score_font_weight if config.ocr_score_font_weight is not None else 0.10

    # CHANGE 1: Direct formula — high image/noise and low text/fonts → high ocr_score
    ocr_score = (
        image_w * image_norm
        + noise_w * noise_norm
        + text_w * (1.0 - text_norm)
        + font_w * (1.0 - font_norm)
    )
    ocr_score = round(max(0.0, min(ocr_score, 1.0)), 3)

    # Debug breakdown
    if signals.get("_debug_scoring"):
        signals["_debug_scoring"]["components"] = {
            "text_norm": text_norm,
            "image_norm": image_norm,
            "noise_norm": noise_norm,
            "font_norm": font_norm,
            "weights": {"text": text_w, "image": image_w, "noise": noise_w, "font": font_w},
            "ocr_score": ocr_score,
        }

    return ocr_score


def calculate_ocr_score(
    text_length: int,
    image_coverage: float,
    text_coverage: float,
    config: Optional[Config] = None,
) -> float:
    """Backward-compatible public wrapper."""
    signals: Dict[str, Any] = {
        "text_length": text_length,
        "image_coverage": image_coverage,
        "text_coverage": text_coverage,
    }
    return _calculate_ocr_score_from_signals(signals, text_coverage, image_coverage, config)


# ─────────────────────────────────────────────
# CHANGE 3: Shared bias helpers
# Extracted from decide() and refine_with_opencv() to eliminate duplication.
# ─────────────────────────────────────────────
def _check_digital_bias(
    text_coverage: float,
    image_coverage: float,
    text_length: int,
    ocr_score: float,
    signals: Dict[str, Any],
    config: Config,
) -> Optional[Tuple[bool, str, float, str, str]]:
    """
    Digital bias: high text + moderate images → digital.
    Returns a decision tuple if bias fires, else None.
    """
    tc_min = config.digital_bias_text_coverage_min
    ic_max = config.digital_bias_image_coverage_max
    if (
        tc_min is not None
        and ic_max is not None
        and text_coverage >= tc_min
        and image_coverage <= ic_max
        and text_length >= config.min_text_length
    ):
        confidence = calculate_confidence_from_signals(
            signals, needs_ocr=False, ocr_score=ocr_score, config=config
        )
        confidence = max(confidence, 0.85)
        return (
            False,
            f"{get_reason_description(ReasonCode.PDF_DIGITAL)} "
            f"(high text coverage {text_coverage:.1f}%, digital bias)",
            confidence,
            CATEGORY_STRUCTURED,
            ReasonCode.PDF_DIGITAL,
        )
    return None


def _check_hybrid_scan(
    image_coverage: float,
    text_length: int,
    ocr_score: float,
    signals: Dict[str, Any],
    config: Config,
) -> Optional[Tuple[bool, str, float, str, str]]:
    """
    Hybrid rule: image_ratio > 0.75 AND text_length < 30 → scanned.
    Returns a decision tuple if rule fires, else None.
    """
    image_ratio = image_coverage / 100.0 if image_coverage > 0 else 0.0
    if image_ratio > 0.75 and text_length < 30:
        confidence = calculate_confidence_from_signals(
            signals, needs_ocr=True, ocr_score=ocr_score, config=config
        )
        confidence = max(confidence, 0.90)
        return (
            True,
            f"{get_reason_description(ReasonCode.PDF_SCANNED)} "
            f"(hybrid rule: {image_coverage:.1f}% images, {text_length} chars)",
            confidence,
            CATEGORY_UNSTRUCTURED,
            ReasonCode.PDF_SCANNED,
        )
    return None


def _check_table_bias(
    text_coverage: float,
    text_length: int,
    ocr_score: float,
    signals: Dict[str, Any],
    config: Config,
) -> Optional[Tuple[bool, str, float, str, str]]:
    """
    Table bias: mixed layout with high text density → digital (tables, not scans).
    Returns a decision tuple if bias fires, else None.
    """
    td_min = config.table_bias_text_density_min
    tc_min = config.table_bias_text_coverage_min
    text_density = signals.get("text_density", 0.0)
    if (
        td_min is not None
        and tc_min is not None
        and text_density >= td_min
        and text_coverage >= tc_min
        and text_length >= config.min_text_length
    ):
        confidence = calculate_confidence_from_signals(
            signals, needs_ocr=False, ocr_score=ocr_score, config=config
        )
        confidence = max(confidence, 0.80)
        return (
            False,
            f"{get_reason_description(ReasonCode.PDF_DIGITAL)} "
            f"(mixed layout, high text density {text_density:.1f}, table bias)",
            confidence,
            CATEGORY_STRUCTURED,
            ReasonCode.PDF_DIGITAL,
        )
    return None


def calculate_confidence_from_signals(
    signals: Dict[str, Any],
    needs_ocr: bool,
    ocr_score: Optional[float] = None,
    config: Optional[Config] = None,
) -> float:
    """Calculate confidence score from signals. Unchanged from original."""
    if config is None:
        config = _DEFAULT_CONFIG

    if ocr_score is not None and config.use_ocr_score_confidence:
        if needs_ocr:
            confidence = 0.50 + (ocr_score * 0.45)
        else:
            confidence = 0.50 + ((1.0 - ocr_score) * 0.45)
        return round(confidence, 2)

    layout_type = signals.get("layout_type")
    if layout_type and layout_type != "unknown":
        text_coverage = float(signals.get("text_coverage", 0.0))
        image_coverage = float(signals.get("image_coverage", 0.0))
        if needs_ocr:
            image_factor = min(image_coverage / 100.0, 1.0)
            confidence = 0.60 + (image_factor * 0.30)
        else:
            text_factor = min(text_coverage / 100.0, 1.0)
            confidence = 0.70 + (text_factor * 0.25)
        return round(confidence, 2)

    text_length = signals.get("text_length", 0)
    if needs_ocr:
        if text_length == 0:
            confidence = 0.65
        else:
            proximity = min(text_length / config.min_text_length, 1.0)
            confidence = 0.55 + ((1.0 - proximity) * 0.20)
    else:
        text_factor = min(text_length / 1000.0, 1.0)
        confidence = 0.75 + (text_factor * 0.20)

    return round(confidence, 2)


def decide(
    signals: Dict[str, Any], config: Optional[Config] = None
) -> Tuple[bool, str, float, str, str]:
    """
    Decide if a file needs OCR based on collected signals.
    """
    if config is None:
        config = _DEFAULT_CONFIG

    mime = signals.get("mime", "")
    text_length = signals.get("text_length", 0)
    extension = signals.get("extension", "")
    is_binary = signals.get("is_binary", True)

    # Rule 1: Plain text — no OCR
    if mime.startswith("text/"):
        return (
            False,
            get_reason_description(ReasonCode.TEXT_FILE),
            config.high_confidence,
            CATEGORY_STRUCTURED,
            ReasonCode.TEXT_FILE,
        )

    # Rule 2: Office documents
    if "officedocument" in mime or extension in ["docx", "pptx", "xlsx"]:
        if text_length >= config.min_office_text_length:
            return (
                False,
                f"{get_reason_description(ReasonCode.OFFICE_WITH_TEXT)} ({text_length} chars)",
                config.high_confidence,
                CATEGORY_STRUCTURED,
                ReasonCode.OFFICE_WITH_TEXT,
            )
        return (
            True,
            f"{get_reason_description(ReasonCode.OFFICE_NO_TEXT)} ({text_length} chars)",
            config.medium_confidence,
            CATEGORY_UNSTRUCTURED,
            ReasonCode.OFFICE_NO_TEXT,
        )

    # Rule 3: Images — always OCR
    if mime.startswith("image/"):
        return (
            True,
            get_reason_description(ReasonCode.IMAGE_FILE),
            config.high_confidence,
            CATEGORY_UNSTRUCTURED,
            ReasonCode.IMAGE_FILE,
        )

    # Rule 4: PDFs
    if mime == "application/pdf" or extension == "pdf":

        # ── Hard Digital guard ──────────────────────────────────────────────
        if text_length >= config.hard_digital_text_threshold:
            return (
                False,
                f"{get_reason_description(ReasonCode.PDF_DIGITAL)} "
                f"(hard digital: {text_length} chars extractable)",
                config.high_confidence,
                CATEGORY_STRUCTURED,
                ReasonCode.PDF_DIGITAL,
            )

        # ── Resolve effective coverage values ───────────────────────────────
        layout_type = signals.get("layout_type")
        is_mixed_content = signals.get("is_mixed_content", False)
        text_coverage = signals.get("text_coverage", 0.0)
        image_coverage = signals.get("image_coverage", 0.0)
        opencv_layout = signals.get("opencv_layout", {})
        image_coverage_opencv = opencv_layout.get("image_coverage", 0.0) if opencv_layout else 0.0
        text_coverage_opencv = opencv_layout.get("text_coverage", 0.0) if opencv_layout else 0.0
        effective_image_coverage = (
            image_coverage_opencv if image_coverage_opencv > 0 else image_coverage
        )
        effective_text_coverage = (
            text_coverage_opencv if text_coverage_opencv > 0 else text_coverage
        )

        # CHANGE 2: Compute ocr_score EARLY so all guards can use it
        ocr_score = _calculate_ocr_score_from_signals(
            signals, effective_text_coverage, effective_image_coverage, config
        )

        # ── Hard Scan guard ─────────────────────────────────────────────────
        if (
            effective_image_coverage >= config.hard_scan_image_coverage_min
            and text_length < config.hard_scan_text_max
        ):
            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_SCANNED)} "
                f"(hard scan: {effective_image_coverage:.1f}% images, {text_length} chars)",
                config.high_confidence,
                CATEGORY_UNSTRUCTURED,
                ReasonCode.PDF_SCANNED,
            )

        # ── Font-count guard ────────────────────────────────────────────────
        font_count = signals.get("font_count")
        if font_count is not None and font_count == 0 and text_length < config.hard_scan_text_max:
            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_SCANNED)} "
                f"(no embedded fonts, {text_length} chars - strong scan signal)",
                config.high_confidence,
                CATEGORY_UNSTRUCTURED,
                ReasonCode.PDF_SCANNED,
            )

        # CHANGE 4: Noise guard — only fires when score ALSO agrees
        # Replaces the old hard exit; avoids silencing the score for mildly noisy digital PDFs.
        non_printable = signals.get("non_printable_ratio", 0.0)
        unicode_noise = signals.get("unicode_noise_ratio", 0.0)
        if (
            (non_printable > 0.05 or unicode_noise > 0.08)
            and text_length > 0
            and ocr_score > 0.6  # score must also lean scanned
        ):
            confidence = calculate_confidence_from_signals(
                signals, needs_ocr=True, ocr_score=ocr_score, config=config
            )
            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_SCANNED)} "
                f"(low-quality text layer: non_printable={non_printable*100:.1f}%, "
                f"unicode_noise={unicode_noise*100:.1f}%, ocr_score={ocr_score:.2f})",
                max(confidence, 0.75),
                CATEGORY_UNSTRUCTURED,
                ReasonCode.PDF_SCANNED,
            )

        # CHANGE 3: Use shared bias helpers instead of inline duplicates
        result = _check_digital_bias(
            effective_text_coverage,
            effective_image_coverage,
            text_length,
            ocr_score,
            signals,
            config,
        )
        if result:
            return result

        result = _check_hybrid_scan(
            effective_image_coverage, text_length, ocr_score, signals, config
        )
        if result:
            return result

        # Low text + image-heavy (layout-aware fallback)
        if text_length < 30 and layout_type and layout_type != "unknown":
            if image_coverage > 50.0 or (is_mixed_content and image_coverage > text_coverage):
                confidence = calculate_confidence_from_signals(
                    signals, needs_ocr=True, ocr_score=ocr_score, config=config
                )
                return (
                    True,
                    f"{get_reason_description(ReasonCode.PDF_SCANNED)} "
                    f"(low text + high image content: {text_length} chars, "
                    f"{image_coverage:.1f}% images)",
                    confidence,
                    CATEGORY_UNSTRUCTURED,
                    ReasonCode.PDF_SCANNED,
                )

        # ── Layout-aware decisions ──────────────────────────────────────────
        if layout_type and layout_type != "unknown":
            if is_mixed_content:
                # CHANGE 3: shared table bias helper
                result = _check_table_bias(
                    effective_text_coverage, text_length, ocr_score, signals, config
                )
                if result:
                    return result

                if text_length >= config.min_text_length and text_coverage > 10:
                    confidence = calculate_confidence_from_signals(
                        signals, needs_ocr=False, ocr_score=ocr_score, config=config
                    )
                    return (
                        False,
                        f"{get_reason_description(ReasonCode.PDF_DIGITAL)} "
                        f"(mixed content, {text_length} chars, "
                        f"{text_coverage:.1f}% text coverage)",
                        confidence,
                        CATEGORY_STRUCTURED,
                        ReasonCode.PDF_DIGITAL,
                    )
                else:
                    confidence = calculate_confidence_from_signals(
                        signals, needs_ocr=True, ocr_score=ocr_score, config=config
                    )
                    return (
                        True,
                        f"{get_reason_description(ReasonCode.PDF_MIXED)} "
                        f"({text_length} chars, {image_coverage:.1f}% images)",
                        confidence,
                        CATEGORY_UNSTRUCTURED,
                        ReasonCode.PDF_MIXED,
                    )

            elif layout_type == "image_only":
                confidence = calculate_confidence_from_signals(
                    signals, needs_ocr=True, ocr_score=ocr_score, config=config
                )
                confidence = max(confidence, 0.85)
                return (
                    True,
                    f"{get_reason_description(ReasonCode.PDF_SCANNED)} "
                    f"(image-only layout, {image_coverage:.1f}% images)",
                    confidence,
                    CATEGORY_UNSTRUCTURED,
                    ReasonCode.PDF_SCANNED,
                )

            elif layout_type == "text_only":
                if text_length >= config.min_text_length:
                    confidence = calculate_confidence_from_signals(
                        signals, needs_ocr=False, ocr_score=ocr_score, config=config
                    )
                    confidence = max(confidence, 0.85)
                    return (
                        False,
                        f"{get_reason_description(ReasonCode.PDF_DIGITAL)} "
                        f"(text-only layout, {text_length} chars)",
                        confidence,
                        CATEGORY_STRUCTURED,
                        ReasonCode.PDF_DIGITAL,
                    )
                else:
                    confidence = calculate_confidence_from_signals(
                        signals, needs_ocr=True, ocr_score=ocr_score, config=config
                    )
                    return (
                        True,
                        f"{get_reason_description(ReasonCode.PDF_SCANNED)} "
                        f"(text-only layout but sparse, {text_length} chars)",
                        confidence,
                        CATEGORY_UNSTRUCTURED,
                        ReasonCode.PDF_SCANNED,
                    )

        # ── Score bands: primary fallback (now always reached for borderline PDFs) ──
        low_band = config.ocr_score_low_band_max
        high_band = config.ocr_score_high_band_min

        if ocr_score <= low_band:
            confidence = calculate_confidence_from_signals(
                signals, needs_ocr=False, ocr_score=ocr_score, config=config
            )
            return (
                False,
                f"{get_reason_description(ReasonCode.PDF_DIGITAL)} "
                f"(score band: digital, OCR score {ocr_score:.2f})",
                confidence,
                CATEGORY_STRUCTURED,
                ReasonCode.PDF_DIGITAL,
            )

        if ocr_score >= high_band:
            confidence = calculate_confidence_from_signals(
                signals, needs_ocr=True, ocr_score=ocr_score, config=config
            )
            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_SCANNED)} "
                f"(score band: scanned, OCR score {ocr_score:.2f})",
                confidence,
                CATEGORY_UNSTRUCTURED,
                ReasonCode.PDF_SCANNED,
            )

        # Borderline band: text length as tiebreaker
        if text_length >= config.min_text_length:
            confidence = calculate_confidence_from_signals(
                signals, needs_ocr=False, ocr_score=ocr_score, config=config
            )
            return (
                False,
                f"{get_reason_description(ReasonCode.PDF_DIGITAL)} "
                f"(borderline score {ocr_score:.2f}, {text_length} chars)",
                confidence,
                CATEGORY_STRUCTURED,
                ReasonCode.PDF_DIGITAL,
            )

        confidence = calculate_confidence_from_signals(
            signals, needs_ocr=True, ocr_score=ocr_score, config=config
        )
        return (
            True,
            f"{get_reason_description(ReasonCode.PDF_SCANNED)} "
            f"(borderline score {ocr_score:.2f}, {text_length} chars)",
            confidence,
            CATEGORY_UNSTRUCTURED,
            ReasonCode.PDF_SCANNED,
        )

    # Rule 5: JSON/XML
    if mime in ["application/json", "application/xml"] or extension in ["json", "xml"]:
        return (
            False,
            get_reason_description(ReasonCode.STRUCTURED_DATA),
            config.high_confidence,
            CATEGORY_STRUCTURED,
            ReasonCode.STRUCTURED_DATA,
        )

    # Rule 6: HTML
    if mime in ["text/html", "application/xhtml+xml"] or extension in ["html", "htm"]:
        if text_length >= config.min_text_length:
            return (
                False,
                f"{get_reason_description(ReasonCode.HTML_WITH_TEXT)} ({text_length} chars)",
                config.high_confidence,
                CATEGORY_STRUCTURED,
                ReasonCode.HTML_WITH_TEXT,
            )
        return (
            True,
            get_reason_description(ReasonCode.HTML_MINIMAL),
            config.low_confidence,
            CATEGORY_UNSTRUCTURED,
            ReasonCode.HTML_MINIMAL,
        )

    # Rule 7: Unknown binaries
    if is_binary:
        return (
            True,
            get_reason_description(ReasonCode.UNKNOWN_BINARY),
            config.low_confidence,
            CATEGORY_UNSTRUCTURED,
            ReasonCode.UNKNOWN_BINARY,
        )

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
    """Refine decision using OpenCV layout analysis results."""
    if config is None:
        config = _DEFAULT_CONFIG

    text_length = signals.get("text_length", 0)
    text_coverage_opencv = opencv_result.get("text_coverage", 0.0)
    image_coverage_opencv = opencv_result.get("image_coverage", 0.0)
    has_text_regions = opencv_result.get("has_text_regions", False)
    layout_type = opencv_result.get("layout_type", "unknown")

    # Hard Digital guard
    if text_length >= config.hard_digital_text_threshold:
        return (
            False,
            f"{get_reason_description(ReasonCode.PDF_DIGITAL)} "
            f"(hard digital: {text_length} chars extractable)",
            config.high_confidence,
            CATEGORY_STRUCTURED,
            ReasonCode.PDF_DIGITAL,
        )

    # Hard Scan guard
    if (
        image_coverage_opencv >= config.hard_scan_image_coverage_min
        and text_length < config.hard_scan_text_max
    ):
        return (
            True,
            f"{get_reason_description(ReasonCode.PDF_SCANNED)} "
            f"(hard scan: {image_coverage_opencv:.1f}% images, {text_length} chars)",
            config.high_confidence,
            CATEGORY_UNSTRUCTURED,
            ReasonCode.PDF_SCANNED,
        )

    # Merge OpenCV values into signals for scoring
    signals_with_opencv = signals.copy()
    signals_with_opencv["layout_type"] = layout_type
    signals_with_opencv["text_coverage"] = text_coverage_opencv
    signals_with_opencv["image_coverage"] = image_coverage_opencv

    # CHANGE 2: compute score before bias checks
    ocr_score_opencv = _calculate_ocr_score_from_signals(
        signals_with_opencv, text_coverage_opencv, image_coverage_opencv, config
    )

    # CHANGE 3: shared helpers instead of inline duplicates
    result = _check_hybrid_scan(
        image_coverage_opencv, text_length, ocr_score_opencv, signals_with_opencv, config
    )
    if result:
        return result

    result = _check_digital_bias(
        text_coverage_opencv,
        image_coverage_opencv,
        text_length,
        ocr_score_opencv,
        signals_with_opencv,
        config,
    )
    if result:
        return result

    # Layout-type based refinement
    layout_analyzer_image_coverage = signals.get("image_coverage", 0.0)

    if layout_type == "text_only":
        if layout_analyzer_image_coverage > 70.0 and text_length >= config.min_text_length:
            confidence = calculate_confidence_from_signals(
                signals_with_opencv,
                needs_ocr=True,
                ocr_score=ocr_score_opencv,
                config=config,
            )
            confidence = max(confidence, 0.75)
            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_MIXED)} "
                f"(OpenCV text-only but layout analyzer detected "
                f"{layout_analyzer_image_coverage:.1f}% images)",
                confidence,
                CATEGORY_UNSTRUCTURED,
                ReasonCode.PDF_MIXED,
            )

        if text_length >= config.min_text_length and text_coverage_opencv > 15:
            confidence = calculate_confidence_from_signals(
                signals_with_opencv,
                needs_ocr=False,
                ocr_score=ocr_score_opencv,
                config=config,
            )
            confidence = max(confidence, 0.85)
            return (
                False,
                f"{get_reason_description(ReasonCode.PDF_DIGITAL)} "
                f"(OpenCV text-only, {text_length} chars, "
                f"{text_coverage_opencv:.1f}% coverage)",
                confidence,
                CATEGORY_STRUCTURED,
                ReasonCode.PDF_DIGITAL,
            )

        if text_length < config.min_text_length and text_coverage_opencv > 10:
            confidence = calculate_confidence_from_signals(
                signals_with_opencv,
                needs_ocr=True,
                ocr_score=ocr_score_opencv,
                config=config,
            )
            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_SCANNED)} "
                f"(OpenCV text-only but no extractable text, "
                f"{text_coverage_opencv:.1f}% coverage)",
                confidence,
                CATEGORY_UNSTRUCTURED,
                ReasonCode.PDF_SCANNED,
            )

    elif layout_type == "image_only":
        confidence = calculate_confidence_from_signals(
            signals_with_opencv,
            needs_ocr=True,
            ocr_score=ocr_score_opencv,
            config=config,
        )
        confidence = max(confidence, 0.85)
        confidence = (initial_confidence * 0.3) + (confidence * 0.7)
        confidence = min(confidence, config.high_confidence)
        return (
            True,
            f"{get_reason_description(ReasonCode.PDF_SCANNED)} "
            f"(OpenCV image-only, {image_coverage_opencv:.1f}% images)",
            round(confidence, 2),
            CATEGORY_UNSTRUCTURED,
            ReasonCode.PDF_SCANNED,
        )

    elif layout_type == "mixed":
        # CHANGE 3: shared table bias helper
        result = _check_table_bias(
            text_coverage_opencv,
            text_length,
            ocr_score_opencv,
            signals_with_opencv,
            config,
        )
        if result:
            return result

        if text_coverage_opencv > 15 and text_length >= config.min_text_length:
            confidence = calculate_confidence_from_signals(
                signals_with_opencv,
                needs_ocr=False,
                ocr_score=ocr_score_opencv,
                config=config,
            )
            return (
                False,
                f"{get_reason_description(ReasonCode.PDF_DIGITAL)} "
                f"(OpenCV mixed, text sufficient: {text_length} chars, "
                f"{text_coverage_opencv:.1f}% text, {image_coverage_opencv:.1f}% images)",
                confidence,
                CATEGORY_STRUCTURED,
                ReasonCode.PDF_DIGITAL,
            )
        else:
            confidence = calculate_confidence_from_signals(
                signals_with_opencv,
                needs_ocr=True,
                ocr_score=ocr_score_opencv,
                config=config,
            )
            return (
                True,
                f"{get_reason_description(ReasonCode.PDF_MIXED)} "
                f"(OpenCV mixed, {text_coverage_opencv:.1f}% text, "
                f"{image_coverage_opencv:.1f}% images)",
                confidence,
                CATEGORY_UNSTRUCTURED,
                ReasonCode.PDF_MIXED,
            )

    # OpenCV confirms initial decision
    if (initial_needs_ocr and not has_text_regions) or (not initial_needs_ocr and has_text_regions):
        ocr_confidence = calculate_confidence_from_signals(
            signals_with_opencv,
            needs_ocr=initial_needs_ocr,
            ocr_score=ocr_score_opencv,
            config=config,
        )
        confidence = (initial_confidence * 0.3) + (ocr_confidence * 0.7)
        confidence = min(confidence, config.high_confidence)
        return (
            initial_needs_ocr,
            f"{initial_reason} (OpenCV confirmed)",
            round(confidence, 2),
            initial_category,
            initial_reason_code,
        )

    # Default: keep initial decision, blend confidence
    ocr_confidence = calculate_confidence_from_signals(
        signals_with_opencv,
        needs_ocr=initial_needs_ocr,
        ocr_score=ocr_score_opencv,
        config=config,
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
