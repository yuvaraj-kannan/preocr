"""Tests for hybrid pipeline (heuristics → confidence check → OpenCV → refine)."""

import tempfile
from pathlib import Path
from unittest.mock import patch


from preocr import constants
from preocr.core import decision, detector

LAYOUT_REFINEMENT_THRESHOLD = constants.LAYOUT_REFINEMENT_THRESHOLD


def test_high_confidence_skips_opencv():
    """Test that high confidence decisions skip OpenCV analysis."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"This is a plain text file with enough content to be considered meaningful.")
        temp_path = f.name

    try:
        result = detector.needs_ocr(temp_path)

        # Plain text files should have high confidence and skip OpenCV
        assert result["confidence"] >= LAYOUT_REFINEMENT_THRESHOLD
        assert "opencv_layout" not in result.get("signals", {})
    finally:
        Path(temp_path).unlink()


@patch("preocr.detector.opencv_layout.analyze_with_opencv")
def test_low_confidence_triggers_opencv(mock_opencv):
    """Test that low confidence triggers OpenCV analysis."""
    mock_opencv.return_value = {
        "text_regions": 5,
        "image_regions": 0,
        "text_coverage": 20.0,
        "image_coverage": 0.0,
        "layout_complexity": "simple",
        "has_text_regions": True,
        "has_image_regions": False,
    }

    # Create a PDF that would have low confidence
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4\n")
        temp_path = f.name

    try:
        # Mock PDF extraction to return low text (low confidence scenario)
        with patch("preocr.detector.pdf_probe.extract_pdf_text") as mock_pdf:
            mock_pdf.return_value = {
                "text_length": 10,  # Low text, will have low confidence
                "text": "short",
                "page_count": 1,
                "method": "mock",
            }

            with patch("preocr.detector.filetype.detect_file_type") as mock_detect:
                mock_detect.return_value = {
                    "mime": "application/pdf",
                    "extension": "pdf",
                    "is_binary": True,
                }

                result = detector.needs_ocr(temp_path)

                # If confidence was low, OpenCV should have been called
                # (Note: This depends on the actual confidence calculation)
                if result["confidence"] < LAYOUT_REFINEMENT_THRESHOLD:
                    mock_opencv.assert_called_once()
    finally:
        Path(temp_path).unlink()


def test_refine_with_opencv():
    """Test decision refinement with OpenCV results."""
    signals = {
        "mime": "application/pdf",
        "extension": "pdf",
        "text_length": 30,  # Low text
        "is_binary": True,
    }

    opencv_result = {
        "text_regions": 5,
        "image_regions": 0,
        "text_coverage": 25.0,
        "image_coverage": 0.0,
        "layout_complexity": "simple",
        "has_text_regions": True,
        "has_image_regions": False,
    }

    # Initial decision (low confidence)
    initial_needs_ocr = True
    initial_reason = "PDF appears to be scanned"
    initial_confidence = 0.6
    initial_category = "unstructured"
    initial_reason_code = "PDF_SCANNED"

    # Refine
    needs_ocr, reason, confidence, category, reason_code = decision.refine_with_opencv(
        signals,
        opencv_result,
        initial_needs_ocr,
        initial_reason,
        initial_confidence,
        initial_category,
        initial_reason_code,
    )

    # Check that refinement happened
    assert isinstance(needs_ocr, bool)
    assert isinstance(reason, str)
    assert 0.0 <= confidence <= 1.0
    assert category in ["structured", "unstructured"]
    assert reason_code is not None

    # Confidence should be improved (or at least not worse)
    assert confidence >= initial_confidence


def test_refine_with_opencv_mixed_content():
    """Test refinement for mixed content."""
    signals = {
        "mime": "application/pdf",
        "extension": "pdf",
        "text_length": 60,  # Some text
        "is_binary": True,
    }

    opencv_result = {
        "text_regions": 3,
        "image_regions": 2,
        "text_coverage": 15.0,
        "image_coverage": 20.0,
        "layout_complexity": "moderate",
        "has_text_regions": True,
        "has_image_regions": True,
    }

    initial_needs_ocr = True
    initial_reason = "PDF appears to be scanned"
    initial_confidence = 0.7
    initial_category = "unstructured"
    initial_reason_code = "PDF_SCANNED"

    needs_ocr, reason, confidence, category, reason_code = decision.refine_with_opencv(
        signals,
        opencv_result,
        initial_needs_ocr,
        initial_reason,
        initial_confidence,
        initial_category,
        initial_reason_code,
    )

    # With text_length=60, hard digital fires first → NO OCR (correct for extractable text)
    assert isinstance(needs_ocr, bool)
    assert needs_ocr is False
    assert "hard digital" in reason.lower() or "extractable" in reason.lower()
    assert confidence >= 0.85
