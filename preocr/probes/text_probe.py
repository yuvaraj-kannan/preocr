"""Text extraction for plain text files and HTML."""

from pathlib import Path
from typing import Any, Dict, Optional

from .. import exceptions
from ..utils.logger import get_logger

TextExtractionError = exceptions.TextExtractionError

logger = get_logger(__name__)

# Declare BeautifulSoup as Optional[Any] so mypy knows it can be None
BeautifulSoup: Optional[Any]
try:
    from bs4 import BeautifulSoup as _BeautifulSoup

    BeautifulSoup = _BeautifulSoup
except ImportError:
    BeautifulSoup = None


def extract_text_from_file(file_path: str, mime_type: str) -> Dict[str, Any]:
    """
    Extract text from plain text files and HTML.

    Args:
        file_path: Path to the file
        mime_type: MIME type of the file

    Returns:
        Dictionary with keys:
            - text_length: Number of characters in extracted text
            - text: Extracted text (may be truncated for large files)
            - encoding: Detected encoding (for text files)
    """
    path = Path(file_path)

    if mime_type.startswith("text/html") or mime_type == "application/xhtml+xml":
        return _extract_html_text(path)
    elif mime_type.startswith("text/"):
        return _extract_plain_text(path)
    else:
        return {"text_length": 0, "text": "", "encoding": None}


def _extract_plain_text(path: Path) -> Dict[str, Any]:
    """Extract text from plain text files."""
    encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
    text = ""
    encoding = None

    for enc in encodings:
        try:
            with open(path, "r", encoding=enc) as f:
                text = f.read()
                encoding = enc
                break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if not text:
        # Last resort: try binary read and decode
        try:
            with open(path, "rb") as f:
                raw = f.read()
                text = raw.decode("utf-8", errors="ignore")
                encoding = "utf-8"
        except (IOError, OSError, PermissionError) as e:
            logger.warning(f"Failed to read text file: {e}")
        except Exception as e:
            logger.warning(f"Text extraction failed: {e}")

    # Always return, even if text extraction failed (text will be empty string)
    return {
        "text_length": len(text),
        "text": text[:1000] if len(text) > 1000 else text,  # Truncate for large files
        "encoding": encoding,
    }


def _extract_html_text(path: Path) -> Dict[str, Any]:
    """Extract text from HTML files."""
    if BeautifulSoup is None:
        # Fallback: basic HTML tag removal
        return _extract_plain_text(path)

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        soup = BeautifulSoup(content, "html.parser")
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        text = soup.get_text(separator=" ", strip=True)

        return {
            "text_length": len(text),
            "text": text[:1000] if len(text) > 1000 else text,
            "encoding": "utf-8",
        }
    except (IOError, OSError, PermissionError) as e:
        logger.warning(f"Failed to read HTML file: {e}")
        # Fallback to plain text extraction
        return _extract_plain_text(path)
    except Exception as e:
        logger.warning(f"HTML text extraction failed: {e}")
        # Fallback to plain text extraction
        return _extract_plain_text(path)


def has_meaningful_text(text: str, min_chars: int = 50) -> bool:
    """
    Check if text has meaningful content.

    Args:
        text: Text to check
        min_chars: Minimum number of characters to consider meaningful

    Returns:
        True if text has meaningful content, False otherwise
    """
    if not text:
        return False
    return len(text.strip()) >= min_chars
