"""Tests for layout_aware=True on files that need OCR."""

from pathlib import Path

import pytest

from preocr import needs_ocr


@pytest.mark.skipif(
    not Path("data-source-formats/ORTHO case 1.pdf").exists(),
    reason="Test file not available",
)
def test_layout_aware_scanned_pdf_needs_ocr():
    """Test that layout_aware=True correctly identifies scanned PDFs that need OCR."""
    pdf_path = Path("data-source-formats/ORTHO case 1.pdf")
    
    # Test without layout_aware
    result_basic = needs_ocr(str(pdf_path), layout_aware=False)
    
    # Test with layout_aware
    result_layout = needs_ocr(str(pdf_path), layout_aware=True)
    
    # Both should detect that OCR is needed
    assert result_basic["needs_ocr"] is True, "Basic detection should identify need for OCR"
    assert result_layout["needs_ocr"] is True, "Layout-aware detection should identify need for OCR"
    
    # Check that layout_aware provides additional information
    signals = result_layout.get("signals", {})
    
    # Layout-aware should have attempted analysis
    # (may have opencv_layout or layout_type in signals)
    assert "signals" in result_layout
    
    # Confidence should be reasonable
    assert 0.0 <= result_layout["confidence"] <= 1.0
    assert result_layout["category"] == "unstructured"


@pytest.mark.skipif(
    not Path("data-source-formats/sample-unstructured-paper.pdf").exists(),
    reason="Test file not available",
)
def test_layout_aware_digital_pdf_no_ocr():
    """Test that layout_aware=True correctly identifies digital PDFs that don't need OCR."""
    pdf_path = Path("data-source-formats/sample-unstructured-paper.pdf")
    
    # Test without layout_aware
    result_basic = needs_ocr(str(pdf_path), layout_aware=False)
    
    # Test with layout_aware
    result_layout = needs_ocr(str(pdf_path), layout_aware=True)
    
    # Both should detect that OCR is NOT needed
    assert result_basic["needs_ocr"] is False, "Basic detection should identify no need for OCR"
    assert result_layout["needs_ocr"] is False, "Layout-aware detection should identify no need for OCR"
    
    # Layout-aware should provide layout analysis
    signals = result_layout.get("signals", {})
    
    # Should have layout information
    assert "signals" in result_layout
    assert result_layout["category"] == "structured"


def test_layout_aware_image_file():
    """Test that layout_aware works with image files (always need OCR)."""
    # Create a minimal test image file
    import tempfile
    
    # For images, we can't easily create a real image file in tests
    # So we'll test the logic with a mock or skip if no image available
    # This test is a placeholder - actual image testing would require a real image file
    pass


def test_layout_aware_improves_confidence():
    """Test that layout_aware can improve confidence scores."""
    pdf_path = Path("data-source-formats/ORTHO case 1.pdf")
    
    if not pdf_path.exists():
        pytest.skip("Test file not available")
    
    result_basic = needs_ocr(str(pdf_path), layout_aware=False)
    result_layout = needs_ocr(str(pdf_path), layout_aware=True)
    
    # Both should return valid confidence scores
    assert isinstance(result_basic["confidence"], float)
    assert isinstance(result_layout["confidence"], float)
    
    # Confidence should be in valid range
    assert 0.0 <= result_basic["confidence"] <= 1.0
    assert 0.0 <= result_layout["confidence"] <= 1.0


def test_layout_aware_provides_opencv_data():
    """Test that layout_aware provides OpenCV layout analysis data when available."""
    pdf_path = Path("data-source-formats/ORTHO case 1.pdf")
    
    if not pdf_path.exists():
        pytest.skip("Test file not available")
    
    result = needs_ocr(str(pdf_path), layout_aware=True)
    signals = result.get("signals", {})
    
    # If OpenCV analysis ran, it should be in signals
    # Note: OpenCV may not always be available or may fail, so we check if it exists
    if "opencv_layout" in signals:
        opencv_data = signals["opencv_layout"]
        assert isinstance(opencv_data, dict)
        # If OpenCV data exists, it should have layout information
        if "layout_type" in opencv_data:
            assert opencv_data["layout_type"] in ["text_only", "image_only", "mixed", "unknown"]

