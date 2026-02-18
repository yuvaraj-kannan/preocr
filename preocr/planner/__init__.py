"""Intent-aware OCR planner for cost-optimized document extraction."""

from .models import (
    PageContextSignals,
    PageIntent,
    PageOCRDecision,
)
from .planner import plan_ocr_for_document

# Alias: intent_refinement refines needs_ocr with domain-specific scoring
intent_refinement = plan_ocr_for_document

__all__ = [
    "plan_ocr_for_document",
    "intent_refinement",
    "PageContextSignals",
    "PageIntent",
    "PageOCRDecision",
]
