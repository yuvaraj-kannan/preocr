"""Tests for PDF text extraction."""

import tempfile
from pathlib import Path


from preocr.probes import pdf_probe


def test_extract_pdf_no_libraries():
    """Test PDF extraction when libraries are not available."""
    # Create a dummy file (not a real PDF, but tests the fallback)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"Not a real PDF")
        temp_path = f.name

    try:
        result = pdf_probe.extract_pdf_text(temp_path)
        # Should return a result dict even if extraction fails
        assert "text_length" in result
        assert "text" in result
        assert "page_count" in result
        assert "method" in result
    finally:
        Path(temp_path).unlink()


def test_extract_pdf_structure():
    """Test that PDF extraction returns correct structure."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4\n")
        temp_path = f.name

    try:
        result = pdf_probe.extract_pdf_text(temp_path)
        assert isinstance(result, dict)
        assert "text_length" in result
        assert "text" in result
        assert "page_count" in result
        assert "method" in result
    finally:
        Path(temp_path).unlink()


def test_extract_pdf_page_level():
    """Test PDF extraction with page_level=True."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4\n")
        temp_path = f.name

    try:
        result = pdf_probe.extract_pdf_text(temp_path, page_level=True)
        assert "pages" in result
        assert isinstance(result["pages"], list)
    finally:
        Path(temp_path).unlink()


def test_extract_pdf_scanned_no_text():
    """Test PDF extraction for scanned PDFs (no extractable text)."""
    # Create a minimal PDF structure (simulating scanned PDF)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4\n")
        temp_path = f.name

    try:
        result = pdf_probe.extract_pdf_text(temp_path, page_level=True)
        # Even if text extraction fails, should return page_count if possible
        assert "page_count" in result
        assert "pages" in result
        # For scanned PDFs, text_length should be 0
        assert result["text_length"] == 0
    finally:
        Path(temp_path).unlink()


def test_get_page_count_only():
    """Test getting page count without text extraction."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4\n")
        temp_path = f.name

    try:
        page_count = pdf_probe._get_page_count_only(Path(temp_path))
        # Should return 0 for invalid PDF, or actual count for valid PDF
        assert isinstance(page_count, int)
        assert page_count >= 0
    finally:
        Path(temp_path).unlink()
