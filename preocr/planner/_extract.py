"""Helper to extract per-page text from PDFs when not provided by caller."""

from pathlib import Path
from typing import Any, List, Optional

pdfplumber: Optional[Any] = None
fitz: Optional[Any] = None

try:
    import pdfplumber as _pdfplumber  # noqa: F401

    pdfplumber = _pdfplumber
except ImportError:
    pass

try:
    import fitz as _fitz  # noqa: F401

    fitz = _fitz
except ImportError:
    pass


def extract_per_page_texts(file_path: str) -> List[str]:
    """
    Extract text for each page of a PDF.

    Used when caller does not provide per_page_texts. Tries PyMuPDF first,
    falls back to pdfplumber.
    """
    path = Path(file_path)
    if not path.exists():
        return []

    if fitz:
        try:
            return _extract_pymupdf(path)
        except Exception:
            pass

    if pdfplumber:
        try:
            return _extract_pdfplumber(path)
        except Exception:
            pass

    return []


def _extract_pdfplumber(path: Path) -> List[str]:
    """Extract per-page text using pdfplumber."""
    assert pdfplumber is not None
    texts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            texts.append(t)
    return texts


def _extract_pymupdf(path: Path) -> List[str]:
    """Extract per-page text using PyMuPDF."""
    assert fitz is not None
    texts = []
    doc = fitz.open(path)
    try:
        for i in range(len(doc)):
            page = doc[i]
            try:
                t = page.get_text() or ""
            except Exception:
                t = ""
            texts.append(t)
    finally:
        doc.close()
    return texts
