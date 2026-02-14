"""Medical intent classifier interface and default rule-based implementation.

OCR-critical intents (medical domain-specific) trigger terminal override when
intent_high_threshold is met. Do not add non-critical intents (e.g. "cover_page")
to OCR_CRITICAL_INTENTS. Thresholds are configurable and should be calibrated
using false-positive cost (OCR cost) vs false-negative cost (missed extraction).
"""

import re
from typing import Any, Callable, Dict, List, Optional

from .models import PageIntent

# Domain-specific OCR-critical intents (medical).
# Override fires only when intent_high_threshold is met.
OCR_CRITICAL_INTENTS = frozenset(
    {
        "prescription",
        "diagnosis",
        "chief_complaint",
        "discharge_summary",
        "lab_report",
    }
)

# Conditional intents: OCR-eligible but not forced; defer to content rules.
OCR_CONDITIONAL_INTENTS = frozenset(
    {
        "external_document_reference",
        "attachment_index",
    }
)

# Optional intents: low-risk pages (cover, TOC, etc.).
OCR_OPTIONAL_INTENTS = frozenset(
    {
        "cover_page",
        "table_of_contents",
    }
)

# Keyword patterns for rule-based classification (label -> list of patterns).
INTENT_PATTERNS: Dict[str, List[tuple]] = {
    "prescription": [
        (r"\bprescription\b", re.I),
        (r"\brx\b", re.I),
        (r"\bmedication\b", re.I),
        (r"\bdispense\b", re.I),
        (r"\bdose\b", re.I),
        (r"\bpharmacy\b", re.I),
        (r"PRESCRIPTION",),
        (r"MEDICATIONS?", re.I),
    ],
    "diagnosis": [
        (r"\bdiagnosis\b", re.I),
        (r"\bdiagnoses\b", re.I),
        (r"\bicd[- ]?\d", re.I),
    ],
    "chief_complaint": [
        (r"\bchief complaint\b", re.I),
        (r"\bcc\s*:", re.I),
    ],
    "discharge_summary": [
        (r"\bdischarge summary\b", re.I),
        (r"\bdischarge diagnosis\b", re.I),
        (r"DISCHARGE",),
    ],
    "lab_report": [
        (r"\blab\b", re.I),
        (r"\blaboratory\b", re.I),
        (r"\bresults?\b", re.I),
        (r"\bhemoglobin\b", re.I),
        (r"\bwbc\b", re.I),
    ],
}


def classify_medical_intent(
    page_text: str,
    layout_hints: Optional[Dict[str, Any]] = None,
    *,
    patterns: Optional[Dict[str, List[tuple]]] = None,
) -> PageIntent:
    """
    Classify medical/business intent for a page.

    Does NOT use page index as a primary feature. Layout hints (headers, form
    regions, etc.) are optional and can improve accuracy.

    Args:
        page_text: Extracted text for the page.
        layout_hints: Optional structured hints (e.g. headers, section titles).
        patterns: Optional override of keyword patterns for testing.

    Returns:
        PageIntent with labels and scores (0-1 per label).
    """
    pats = patterns or INTENT_PATTERNS
    text = page_text or ""
    scores: Dict[str, float] = {}

    for label, pattern_list in pats.items():
        max_score = 0.0
        for item in pattern_list:
            if isinstance(item, tuple):
                if len(item) == 1:
                    pat = re.compile(item[0])
                else:
                    pat = re.compile(item[0], item[1])
            else:
                pat = re.compile(str(item))
            matches = pat.findall(text)
            if matches:
                count = len(matches)
                score = min(0.5 + 0.1 * count, 1.0)
                max_score = max(max_score, score)
        if max_score > 0:
            scores[label] = round(max_score, 2)

    if not scores:
        return PageIntent(labels=[], scores={})

    labels = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    return PageIntent(labels=labels, scores=scores)


def get_intent_classifier() -> Callable[..., PageIntent]:
    """Return the default intent classifier function."""
    return classify_medical_intent
