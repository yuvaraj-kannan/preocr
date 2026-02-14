"""Data models for the intent-aware OCR planner.

These models define the structure for page-level signals, intent classification,
and OCR decisions. Confidence represents the estimated correctness of the
decision (need vs no-need for OCR), NOT OCR accuracy or text recognition quality.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PageIntent:
    """Medical/business intent classification for a single page."""

    labels: List[str]
    scores: Dict[str, float]

    def get_critical_score(self, critical_intents: set) -> float:
        """Return the maximum score among OCR-critical intents, or 0.0 if none match."""
        return max(
            (self.scores.get(label, 0.0) for label in critical_intents),
            default=0.0,
        )


@dataclass
class PageContextSignals:
    """Page-level content and extraction signals from preocr + layout analysis."""

    text_length: int
    text_coverage: float
    image_coverage: float
    content_based_recommendation: bool
    confidence_base: float
    reason_code_base: str
    extraction_failed: bool
    layout_missing: bool
    page_number: int = 0

    @classmethod
    def from_preocr_page(
        cls,
        page_data: Dict[str, Any],
        layout_page: Optional[Dict[str, Any]] = None,
        page_index: int = 0,
        layout_expected: bool = False,
    ) -> "PageContextSignals":
        """Build PageContextSignals from preocr page-level result."""
        text_length = page_data.get("text_length", 0)
        content_based = page_data.get("needs_ocr", text_length < 50)
        confidence_base = page_data.get("confidence", 0.5)
        reason_code = page_data.get("reason_code", "")

        text_coverage = 0.0
        image_coverage = 0.0
        if layout_page:
            text_coverage = float(layout_page.get("text_coverage", 0.0))
            image_coverage = float(layout_page.get("image_coverage", 0.0))

        extraction_failed = page_data.get("extraction_failed", False) or (
            text_length == 0 and page_data.get("has_text", True) is False
        )
        layout_missing = layout_expected and (layout_page is None or layout_page == {})

        return cls(
            text_length=text_length,
            text_coverage=text_coverage,
            image_coverage=image_coverage,
            content_based_recommendation=content_based,
            confidence_base=confidence_base,
            reason_code_base=reason_code,
            extraction_failed=extraction_failed,
            layout_missing=layout_missing,
            page_number=page_data.get("page_number", page_index + 1),
        )


@dataclass
class PageOCRDecision:
    """Final OCR decision for a single page with explainability."""

    needs_ocr: bool
    decision_type: str
    reason: str
    confidence: float
    decision_version: str
    debug: Dict[str, Any] = field(default_factory=dict)
    page_number: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "page_number": self.page_number,
            "needs_ocr": self.needs_ocr,
            "decision_type": self.decision_type,
            "reason": self.reason,
            "confidence": round(self.confidence, 2),
            "decision_version": self.decision_version,
            "debug": self.debug,
        }
