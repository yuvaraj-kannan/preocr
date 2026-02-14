"""Hybrid decision logic: explicit overrides + weighted scoring.

Decision invariant: Once a terminal override fires, no subsequent logic may
reverse the decision. Overrides are terminal.
"""

from typing import Any, Dict, Tuple

from .config import PlannerConfig
from .intent import OCR_CRITICAL_INTENTS
from .models import PageContextSignals, PageIntent, PageOCRDecision


def _normalize(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Normalize value to 0-1 range."""
    if high <= low:
        return 0.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


def _compute_ocr_score(
    signals: PageContextSignals,
    intent: PageIntent,
    config: PlannerConfig,
) -> Tuple[float, Dict[str, float]]:
    """
    Compute OCR_score = f(intent, image_coverage, text_weakness, extraction_risk).

    Returns (score, components_dict).
    """
    intent_contrib = intent.get_critical_score(OCR_CRITICAL_INTENTS) * config.get_intent_weight()
    image_dominance = _normalize(signals.image_coverage, 0, 100) * config.image_weight
    text_weakness = (1.0 - _normalize(signals.text_coverage, 0, 100)) * config.text_weakness_weight

    failsafe_boost = 0.0
    if signals.text_length < config.very_low_text_threshold and signals.text_coverage < 10:
        failsafe_boost = 0.3

    components = {
        "intent": round(intent_contrib, 3),
        "image_dominance": round(image_dominance, 3),
        "text_weakness": round(text_weakness, 3),
        "failsafe_boost": round(failsafe_boost, 3),
    }

    score = intent_contrib + image_dominance + text_weakness + failsafe_boost
    score = min(1.0, score)

    return round(score, 3), components


def _compute_scored_confidence(score: float, threshold: float) -> float:
    """Confidence for scored decisions: margin = abs(score - threshold); confidence = clamp(0.5 + margin, 0, 1)."""
    margin = abs(score - threshold)
    return max(0.0, min(1.0, 0.5 + margin))


def decide_page(
    signals: PageContextSignals,
    intent: PageIntent,
    config: PlannerConfig,
) -> PageOCRDecision:
    """
    Apply hybrid decision logic for a single page.

    Step 1: Hard failsafe override (extraction_failed or layout_missing)
    Step 2: OCR-critical intent override (score >= intent_high_threshold)
    Step 3: Weighted scoring (OCR_score >= decision_threshold)
    """
    threshold = config.get_decision_threshold()
    score, components = _compute_ocr_score(signals, intent, config)

    debug_base: Dict[str, Any] = {
        "score": score,
        "components": components,
        "terminal_override": False,
    }

    # Step 1: Hard failsafe override (terminal) – if policy allows
    if config.failsafe_override_active() and (
        signals.extraction_failed or signals.layout_missing
    ):
        return PageOCRDecision(
            needs_ocr=True,
            decision_type="terminal_override",
            reason="Extraction/layout failure – OCR applied as safety fallback.",
            confidence=0.65,
            decision_version=config.decision_version,
            debug={**debug_base, "terminal_override": True, "override_reason": "failsafe"},
            page_number=signals.page_number,
        )

    # Step 2: OCR-critical intent override (terminal) – medical_strict only
    if config.intent_override_active():
        critical_score = intent.get_critical_score(OCR_CRITICAL_INTENTS)
        if critical_score >= config.intent_high_threshold:
            return PageOCRDecision(
                needs_ocr=True,
                decision_type="terminal_override",
                reason="OCR-critical intent (e.g. prescription) with high confidence.",
                confidence=critical_score,
                decision_version=config.decision_version,
                debug={**debug_base, "terminal_override": True, "override_reason": "intent_critical"},
                page_number=signals.page_number,
            )

    # Step 3: Weighted scoring (non-overridden pages)
    needs_ocr = score >= threshold
    confidence = _compute_scored_confidence(score, threshold)
    reason = (
        f"Score {score:.2f} {'>=' if needs_ocr else '<'} threshold {threshold:.2f}; "
        f"components: intent={components['intent']}, image={components['image_dominance']}, "
        f"text_weakness={components['text_weakness']}."
    )

    return PageOCRDecision(
        needs_ocr=needs_ocr,
        decision_type="scored",
        reason=reason,
        confidence=confidence,
        decision_version=config.decision_version,
        debug=debug_base,
        page_number=signals.page_number,
    )
