"""Tests for the intent-aware OCR planner."""

from pathlib import Path

import pytest

from preocr import plan_ocr_for_document
from preocr.planner import PageContextSignals, PageIntent, PageOCRDecision
from preocr.planner.config import PlannerConfig
from preocr.planner.intent import classify_medical_intent, OCR_CRITICAL_INTENTS


def test_classify_medical_intent():
    """Test intent classification."""
    intent = classify_medical_intent("PRESCRIPTION: Amoxicillin 500mg TID")
    assert "prescription" in intent.scores
    assert intent.get_critical_score(OCR_CRITICAL_INTENTS) >= 0.5

    intent2 = classify_medical_intent("")
    assert intent2.scores == {} or len(intent2.scores) == 0


def test_planner_config():
    """Test planner config and threshold."""
    cfg = PlannerConfig(decision_mode="safety")
    assert cfg.get_decision_threshold() == cfg.decision_threshold_safety

    cfg2 = PlannerConfig(decision_mode="cost")
    assert cfg2.get_decision_threshold() == cfg2.decision_threshold_cost

    # Generic mode: higher balanced threshold, zero intent weight
    generic_balanced = PlannerConfig(domain_mode="generic", decision_mode="balanced")
    assert generic_balanced.get_decision_threshold() == generic_balanced.decision_threshold_balanced_generic
    assert generic_balanced.get_intent_weight() == 0.0

    # Medical mode: standard balanced threshold, intent weight applied
    medical_balanced = PlannerConfig(domain_mode="medical", decision_mode="balanced")
    assert medical_balanced.get_decision_threshold() == medical_balanced.decision_threshold_balanced
    assert medical_balanced.get_intent_weight() == medical_balanced.intent_weight


def test_domain_mode_gating():
    """Test domain_mode and override policy gating."""
    medical_cfg = PlannerConfig(domain_mode="medical")
    assert medical_cfg.intent_override_active() is True
    assert medical_cfg.failsafe_override_active() is True

    generic_cfg = PlannerConfig(domain_mode="generic")
    assert generic_cfg.intent_override_active() is False
    assert generic_cfg.failsafe_override_active() is True

    none_cfg = PlannerConfig(override_policy="none")
    assert none_cfg.intent_override_active() is False
    assert none_cfg.failsafe_override_active() is False


def test_page_context_signals_from_preocr():
    """Test building PageContextSignals from preocr page data."""
    page_data = {
        "page_number": 1,
        "text_length": 100,
        "needs_ocr": False,
        "confidence": 0.9,
        "reason_code": "PDF_PAGE_DIGITAL",
    }
    layout = {"text_coverage": 40.0, "image_coverage": 10.0}
    signals = PageContextSignals.from_preocr_page(
        page_data, layout_page=layout, page_index=0, layout_expected=True
    )
    assert signals.text_length == 100
    assert signals.text_coverage == 40.0
    assert signals.image_coverage == 10.0
    assert signals.content_based_recommendation is False
    assert signals.layout_missing is False


@pytest.mark.skipif(
    not Path("data-source-formats/sample-unstructured-paper.pdf").exists(),
    reason="Test file not available",
)
def test_plan_ocr_for_document_digital_pdf():
    """Test planner on a digital PDF."""
    pdf_path = "data-source-formats/sample-unstructured-paper.pdf"
    result = plan_ocr_for_document(pdf_path)
    assert "decision_version" in result
    assert "needs_ocr_any" in result
    assert "pages" in result
    assert "pages_needing_ocr" in result
    assert "overall_confidence" in result
    assert "summary_reason" in result
    assert "metrics" in result
    assert result["metrics"]["terminal_override"] >= 0
    assert result["metrics"]["scored"] >= 0
    for page in result["pages"]:
        assert "needs_ocr" in page
        assert "decision_type" in page
        assert "debug" in page
        assert "score" in page["debug"]
        assert "components" in page["debug"]
