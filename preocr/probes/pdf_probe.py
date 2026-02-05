"""PDF text extraction probe."""

from pathlib import Path
from typing import Any, Dict

from .. import constants, exceptions
from ..utils.logger import get_logger

MIN_TEXT_LENGTH = constants.MIN_TEXT_LENGTH
PDFProcessingError = exceptions.PDFProcessingError
TextExtractionError = exceptions.TextExtractionError

logger = get_logger(__name__)

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore[assignment]

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


def extract_pdf_text(file_path: str, page_level: bool = False) -> Dict[str, Any]:
    """
    Extract text from PDF file.

    Tries pdfplumber first (better text extraction), falls back to PyMuPDF.

    Args:
        file_path: Path to the PDF file
        page_level: If True, return per-page analysis

    Returns:
        Dictionary with keys:
            - text_length: Number of characters in extracted text
            - text: Extracted text (may be truncated for large files)
            - page_count: Number of pages in PDF
            - method: Extraction method used ("pdfplumber" or "pymupdf")
            - pages: (if page_level=True) List of page-level results
    """
    path = Path(file_path)

    # Try pdfplumber first
    if pdfplumber:
        try:
            return _extract_with_pdfplumber(path, page_level)
        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Failed to read PDF file with pdfplumber: {e}")
        except Exception as e:
            logger.warning(f"PDF text extraction failed with pdfplumber: {e}")

    # Fallback to PyMuPDF
    if fitz:
        try:
            return _extract_with_pymupdf(path, page_level)
        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Failed to read PDF file with PyMuPDF: {e}")
        except Exception as e:
            logger.warning(f"PDF text extraction failed with PyMuPDF: {e}")

    # No extractors available or both failed
    result = {
        "text_length": 0,
        "text": "",
        "page_count": 0,
        "method": None,
    }
    if page_level:
        result["pages"] = []
    return result


def _extract_with_pdfplumber(path: Path, page_level: bool = False) -> Dict[str, Any]:
    """Extract text using pdfplumber."""
    text_parts = []
    page_count = 0
    pages_data = []

    try:
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                text_parts.append(page_text)

                if page_level:
                    page_text_len = len(page_text)
                    pages_data.append(
                        {
                            "page_number": page_num,
                            "text_length": page_text_len,
                            "needs_ocr": page_text_len < MIN_TEXT_LENGTH,
                            "has_text": page_text_len > 0,
                        }
                    )
    except (IOError, OSError, PermissionError) as e:
        raise TextExtractionError(f"Failed to read PDF file: {e}") from e
    except Exception as e:
        raise TextExtractionError(f"PDF text extraction failed: {e}") from e

    full_text = "\n".join(text_parts)

    result = {
        "text_length": len(full_text),
        "text": full_text[:1000] if len(full_text) > 1000 else full_text,
        "page_count": page_count,
        "method": "pdfplumber",
    }

    if page_level:
        result["pages"] = pages_data

    return result


def _extract_with_pymupdf(path: Path, page_level: bool = False) -> Dict[str, Any]:
    """Extract text using PyMuPDF."""
    try:
        doc = fitz.open(path)
    except (IOError, OSError, PermissionError) as e:
        raise TextExtractionError(f"Failed to open PDF file: {e}") from e
    except Exception as e:
        raise TextExtractionError(f"PDF processing error: {e}") from e

    text_parts = []
    page_count = len(doc)
    pages_data = []

    try:
        for page_num in range(page_count):
            page = doc[page_num]
            page_text = page.get_text() or ""
            text_parts.append(page_text)

            if page_level:
                page_text_len = len(page_text)
                pages_data.append(
                    {
                        "page_number": page_num + 1,
                        "text_length": page_text_len,
                        "needs_ocr": page_text_len < MIN_TEXT_LENGTH,
                        "has_text": page_text_len > 0,
                    }
                )
    finally:
        doc.close()

    full_text = "\n".join(text_parts)

    result = {
        "text_length": len(full_text),
        "text": full_text[:1000] if len(full_text) > 1000 else full_text,
        "page_count": page_count,
        "method": "pymupdf",
    }

    if page_level:
        result["pages"] = pages_data

    return result
