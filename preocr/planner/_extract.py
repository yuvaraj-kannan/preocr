"""Helper to extract per-page text from PDFs when not provided by caller."""

from pathlib import Path
from typing import List

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import fitz
except ImportError:
    fitz = None


def extract_per_page_texts(file_path: str) -> List[str]:
    """
    Extract text for each page of a PDF.

    Used when caller does not provide per_page_texts. Tries pdfplumber first,
    falls back to PyMuPDF.
    """
    path = Path(file_path)
    if not path.exists():
        return []

    if pdfplumber:
        try:
            return _extract_pdfplumber(path)
        except Exception:
            pass

    if fitz:
        try:
            return _extract_pymupdf(path)
        except Exception:
            pass

    return []


def _extract_pdfplumber(path: Path) -> List[str]:
    """Extract per-page text using pdfplumber."""
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
