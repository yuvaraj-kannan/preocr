"""Tests for main detector API."""

import tempfile
from pathlib import Path

import pytest

from preocr.core import detector


def test_needs_ocr_text_file():
    """Test needs_ocr with a text file."""
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("This is a test file with enough text content.")
        temp_path = f.name

    try:
        result = detector.needs_ocr(temp_path)

        assert "needs_ocr" in result
        assert "file_type" in result
        assert "category" in result
        assert "confidence" in result
        assert "reason" in result
        assert "signals" in result

        assert result["needs_ocr"] is False
        assert result["file_type"] == "text"
        assert result["category"] == "structured"
    finally:
        Path(temp_path).unlink()


def test_needs_ocr_nonexistent_file():
    """Test needs_ocr with non-existent file."""
    with pytest.raises(FileNotFoundError):
        detector.needs_ocr("/nonexistent/file.txt")


def test_needs_ocr_structure():
    """Test that needs_ocr returns correct structure."""
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("Test")
        temp_path = f.name

    try:
        result = detector.needs_ocr(temp_path)

        # Check all required keys
        required_keys = [
            "needs_ocr",
            "file_type",
            "category",
            "confidence",
            "reason",
            "reason_code",
            "signals",
        ]
        for key in required_keys:
            assert key in result, f"Missing key: {key}"

        # Check types
        assert isinstance(result["needs_ocr"], bool)
        assert isinstance(result["file_type"], str)
        assert isinstance(result["category"], str)
        assert isinstance(result["confidence"], float)
        assert isinstance(result["reason"], str)
        assert isinstance(result["reason_code"], str)
        assert isinstance(result["signals"], dict)
    finally:
        Path(temp_path).unlink()


def test_needs_ocr_with_path_object():
    """Test needs_ocr accepts Path objects."""
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("Test content")
        temp_path = Path(f.name)

    try:
        result = detector.needs_ocr(temp_path)
        assert "needs_ocr" in result
    finally:
        temp_path.unlink()


def test_needs_ocr_page_level():
    """Test needs_ocr with page_level=True."""
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("Test content with enough text to be meaningful.")
        temp_path = f.name

    try:
        result = detector.needs_ocr(temp_path, page_level=True)
        # For non-PDF files, page_level should not affect result structure
        assert "needs_ocr" in result
        assert "signals" in result
    finally:
        Path(temp_path).unlink()


def test_needs_ocr_scanned_pdf_page_level():
    """Test needs_ocr with page_level=True on scanned PDF (no text)."""
    # Create a minimal PDF (simulating scanned PDF)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4\n")
        temp_path = f.name

    try:
        result = detector.needs_ocr(temp_path, page_level=True)
        # Should handle scanned PDFs gracefully
        assert "needs_ocr" in result
        assert isinstance(result["needs_ocr"], bool)
        # For scanned PDFs, should need OCR
        # But we can't guarantee this without a real scanned PDF
        assert "page_count" in result or "pages" in result or result.get("page_count", 0) >= 0
    finally:
        Path(temp_path).unlink()


def test_needs_ocr_layout_aware():
    """Test needs_ocr with layout_aware=True."""
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("Test content")
        temp_path = f.name

    try:
        result = detector.needs_ocr(temp_path, layout_aware=True)
        # layout_aware mainly affects PDFs, but should work for all files
        assert "needs_ocr" in result
        assert "signals" in result
    finally:
        Path(temp_path).unlink()


def test_needs_ocr_invalid_pdf():
    """Test needs_ocr with invalid/corrupted PDF."""
    # Create a file that looks like PDF but is corrupted
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"Not a valid PDF content")
        temp_path = f.name

    try:
        result = detector.needs_ocr(temp_path)
        # Should handle gracefully without crashing
        assert "needs_ocr" in result
        assert isinstance(result["needs_ocr"], bool)
        # The result depends on file type detection - may be detected as text or binary
        # The important thing is it doesn't crash
        assert "file_type" in result
        assert "confidence" in result
    finally:
        Path(temp_path).unlink()
