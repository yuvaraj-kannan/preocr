"""Tests for OpenCV skip heuristics (skip_opencv_* config)."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from preocr import Config, needs_ocr


@patch("preocr.detector.opencv_layout.analyze_with_opencv")
def test_skip_opencv_when_file_size_exceeds_threshold(mock_opencv):
    """With skip_opencv_if_file_size_mb=0.001, OpenCV is skipped for PDFs >= 1KB."""
    # Create a PDF file >= 1KB so file_size_mb >= 0.001
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4\n" + b"x" * 1100)  # ~1.1 KB
        temp_path = f.name

    try:
        with patch("preocr.detector.pdf_probe_module.extract_pdf_text") as mock_pdf:
            mock_pdf.return_value = {
                "text_length": 500,
                "text": "x" * 500,
                "page_count": 1,
                "method": "mock",
            }
            with patch("preocr.detector.filetype_module.detect_file_type") as mock_detect:
                mock_detect.return_value = {
                    "mime": "application/pdf",
                    "extension": "pdf",
                    "is_binary": True,
                }
                with patch(
                    "preocr.detector.layout_analyzer_module.analyze_pdf_layout"
                ) as mock_layout:
                    mock_layout.return_value = {
                        "text_coverage": 80.0,
                        "image_coverage": 5.0,
                        "layout_type": "text_only",
                    }

                    config = Config(skip_opencv_if_file_size_mb=0.001)
                    result = needs_ocr(temp_path, layout_aware=True, config=config)

                # OpenCV should have been skipped
                mock_opencv.assert_not_called()
                assert "opencv_layout" not in result.get("signals", {})

                # Result should still be correct: digital PDF with text -> no OCR needed
                assert result["needs_ocr"] is False
                assert result["category"] == "structured"
    finally:
        Path(temp_path).unlink()


@pytest.mark.skipif(
    not Path("datasets/sample-unstructured-paper.pdf").exists(),
    reason="Test file not available",
)
def test_skip_opencv_with_real_digital_pdf():
    """Skip heuristic with real digital PDF: OpenCV skipped, result correct."""
    from preocr.analysis import opencv_layout

    pdf_path = Path("datasets/sample-unstructured-paper.pdf")
    config = Config(skip_opencv_if_file_size_mb=0.001)

    with patch.object(opencv_layout, "analyze_with_opencv") as mock_opencv:
        result = needs_ocr(str(pdf_path), layout_aware=True, config=config)

        # OpenCV should have been skipped (file is well over 1KB)
        mock_opencv.assert_not_called()
        assert "opencv_layout" not in result.get("signals", {})

        # Digital PDF with text -> no OCR needed
        assert result["needs_ocr"] is False
        assert result["category"] == "structured"
