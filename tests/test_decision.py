"""Tests for decision engine."""

from preocr.core import decision


def test_plain_text_no_ocr():
    """Test that plain text files don't need OCR."""
    signals = {
        "mime": "text/plain",
        "extension": "txt",
        "text_length": 100,
        "is_binary": False,
    }

    needs, reason, confidence, category, reason_code = decision.decide(signals)
    assert needs is False
    assert category == "structured"
    assert confidence >= 0.9
    assert reason_code is not None


def test_image_needs_ocr():
    """Test that images always need OCR."""
    signals = {
        "mime": "image/png",
        "extension": "png",
        "text_length": 0,
        "is_binary": True,
    }

    needs, reason, confidence, category, reason_code = decision.decide(signals)
    assert needs is True
    assert category == "unstructured"
    assert "image" in reason.lower()
    assert reason_code is not None


def test_pdf_with_text_no_ocr():
    """Test that PDFs with text don't need OCR."""
    signals = {
        "mime": "application/pdf",
        "extension": "pdf",
        "text_length": 500,
        "is_binary": True,
    }

    needs, reason, confidence, category, reason_code = decision.decide(signals)
    assert needs is False
    assert category == "structured"
    assert reason_code is not None


def test_pdf_without_text_needs_ocr():
    """Test that PDFs without text need OCR."""
    signals = {
        "mime": "application/pdf",
        "extension": "pdf",
        "text_length": 10,
        "is_binary": True,
    }

    needs, reason, confidence, category, reason_code = decision.decide(signals)
    assert needs is True
    assert category == "unstructured"
    assert reason_code is not None


def test_office_doc_with_text_no_ocr():
    """Test that office docs with text don't need OCR."""
    signals = {
        "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "extension": "docx",
        "text_length": 200,
        "is_binary": True,
    }

    needs, reason, confidence, category, reason_code = decision.decide(signals)
    assert needs is False
    assert category == "structured"
    assert reason_code is not None


def test_unknown_binary_needs_ocr():
    """Test that unknown binaries default to needing OCR."""
    signals = {
        "mime": "application/octet-stream",
        "extension": "bin",
        "text_length": 0,
        "is_binary": True,
    }

    needs, reason, confidence, category, reason_code = decision.decide(signals)
    assert needs is True
    assert category == "unstructured"
    assert reason_code is not None


def test_digital_bias_high_text_moderate_image():
    """Test hard digital / digital bias: text_length >= 20 → no OCR (or digital bias when layout fits)."""
    from preocr import Config

    signals = {
        "mime": "application/pdf",
        "extension": "pdf",
        "text_length": 500,
        "text_coverage": 68.0,
        "image_coverage": 25.0,
        "layout_type": "mixed",
        "is_binary": True,
    }
    config = Config()
    needs, reason, confidence, category, reason_code = decision.decide(signals, config=config)
    assert needs is False
    assert category == "structured"
    assert reason_code == "PDF_DIGITAL"
    assert "hard digital" in reason.lower() or "digital bias" in reason.lower() or "extractable" in reason.lower()


def test_hybrid_rule_high_image_low_text():
    """Test hard scan: image_coverage >= 80% AND text_length < 20 → OCR."""
    signals = {
        "mime": "application/pdf",
        "extension": "pdf",
        "text_length": 10,  # Low text (< 20 for hard scan)
        "image_coverage": 80.0,  # High image coverage (>= 80%)
        "layout_type": "mixed",
        "is_binary": True,
    }

    needs, reason, confidence, category, reason_code = decision.decide(signals)
    assert needs is True
    assert category == "unstructured"
    assert reason_code == "PDF_SCANNED"
    assert "hard scan" in reason.lower() or "hybrid rule" in reason.lower()
    assert confidence >= 0.9


def test_scoring_model_ocr_detection():
    """Test scoring model for OCR detection."""
    signals = {
        "mime": "application/pdf",
        "extension": "pdf",
        "text_length": 10,  # Very low text
        "image_coverage": 60.0,  # High image coverage
        "text_coverage": 5.0,  # Low text coverage
        "layout_type": "mixed",
        "is_binary": True,
    }

    needs, reason, confidence, category, reason_code = decision.decide(signals)
    # Should detect as needing OCR due to scoring model or hybrid rule
    assert needs is True
    assert category == "unstructured"


def test_calculate_ocr_score():
    """Test OCR_SCORE calculation helper function."""
    # Test with high image, low text (should have high OCR_SCORE)
    ocr_score = decision.calculate_ocr_score(
        text_length=10,
        image_coverage=80.0,
        text_coverage=5.0,
    )
    assert 0.0 <= ocr_score <= 1.0
    assert ocr_score > 0.6  # Should be high for this scenario

    # Test with low image, high text (should have low OCR_SCORE)
    ocr_score2 = decision.calculate_ocr_score(
        text_length=5000,
        image_coverage=10.0,
        text_coverage=70.0,
    )
    assert 0.0 <= ocr_score2 <= 1.0
    assert ocr_score2 < 0.4  # Should be low for this scenario


def test_calculate_confidence_from_signals_with_ocr_score():
    """Test unified confidence calculation with OCR_SCORE."""
    signals = {
        "text_length": 10,
        "image_coverage": 80.0,
        "text_coverage": 5.0,
        "layout_type": "mixed",
    }

    # Calculate OCR_SCORE
    ocr_score = decision.calculate_ocr_score(10, 80.0, 5.0)

    # Test for "needs OCR" case
    confidence = decision.calculate_confidence_from_signals(
        signals, needs_ocr=True, ocr_score=ocr_score
    )
    assert 0.50 <= confidence <= 0.95
    # Higher OCR_SCORE should give higher confidence for "needs OCR"
    assert confidence > 0.70  # Should be reasonably high

    # Test for "no OCR" case
    ocr_score_low = decision.calculate_ocr_score(5000, 10.0, 70.0)
    confidence2 = decision.calculate_confidence_from_signals(
        signals, needs_ocr=False, ocr_score=ocr_score_low
    )
    assert 0.50 <= confidence2 <= 0.95
    # Lower OCR_SCORE should give higher confidence for "no OCR"
    assert confidence2 > 0.70  # Should be reasonably high


def test_calculate_confidence_fallback():
    """Test confidence calculation fallback when OCR_SCORE unavailable."""
    signals = {
        "text_length": 500,
        "image_coverage": 0.0,
        "text_coverage": 0.0,
        # No layout_type = fallback mode
    }

    # Test fallback for "no OCR" (digital PDF)
    confidence = decision.calculate_confidence_from_signals(
        signals, needs_ocr=False, ocr_score=None
    )
    assert 0.75 <= confidence <= 0.95  # Should be in fallback range

    # Test fallback for "needs OCR" (scanned PDF)
    signals2 = {"text_length": 10}
    confidence2 = decision.calculate_confidence_from_signals(
        signals2, needs_ocr=True, ocr_score=None
    )
    assert 0.55 <= confidence2 <= 0.75  # Should be in fallback range


def test_hard_digital_design_heavy_page():
    """Digital heavy design page: text_length=100, image_coverage=85% → NO OCR."""
    signals = {
        "mime": "application/pdf",
        "extension": "pdf",
        "text_length": 100,
        "image_coverage": 85.0,
        "layout_type": "mixed",
        "is_binary": True,
    }

    needs, reason, confidence, category, reason_code = decision.decide(signals)
    assert needs is False
    assert category == "structured"
    assert reason_code == "PDF_DIGITAL"
    assert "hard digital" in reason.lower()


def test_hard_scan_real_scanned_page():
    """Real scanned page: text_length=10, image_coverage=85% → OCR."""
    signals = {
        "mime": "application/pdf",
        "extension": "pdf",
        "text_length": 10,
        "image_coverage": 85.0,
        "layout_type": "mixed",
        "is_binary": True,
    }

    needs, reason, confidence, category, reason_code = decision.decide(signals)
    assert needs is True
    assert category == "unstructured"
    assert reason_code == "PDF_SCANNED"
    assert "hard scan" in reason.lower()


def test_mixed_page_weighted_model():
    """Mixed page: text_length=15, image_coverage=50% → weighted model (not hard scan)."""
    signals = {
        "mime": "application/pdf",
        "extension": "pdf",
        "text_length": 15,
        "image_coverage": 50.0,
        "layout_type": "mixed",
        "is_binary": True,
    }

    needs, reason, confidence, category, reason_code = decision.decide(signals)
    # Not hard digital (15 < 20), not hard scan (50 < 80) → weighted model decides
    assert "hard digital" not in reason.lower()
    assert "hard scan" not in reason.lower()
    assert reason_code in ("PDF_SCANNED", "PDF_DIGITAL", "PDF_MIXED")


def test_confidence_alignment_with_ocr_score():
    """Test that confidence aligns with OCR_SCORE."""
    signals = {
        "text_length": 20,
        "image_coverage": 75.0,
        "text_coverage": 10.0,
        "layout_type": "mixed",
    }

    ocr_score = decision.calculate_ocr_score(20, 75.0, 10.0)

    # Get confidence using OCR_SCORE
    confidence = decision.calculate_confidence_from_signals(
        signals, needs_ocr=True, ocr_score=ocr_score
    )

    # Confidence should be aligned with OCR_SCORE
    # For needs_ocr=True: confidence = 0.50 + (ocr_score * 0.45)
    expected_confidence = 0.50 + (ocr_score * 0.45)
    assert abs(confidence - expected_confidence) < 0.01  # Very close alignment
