"""File type detection using MIME types and extensions."""

import mimetypes
from pathlib import Path
from typing import Optional, TypedDict

try:
    import magic
except ImportError:
    magic = None


class FileTypeInfo(TypedDict):
    """File type information dictionary."""

    mime: str
    extension: str
    is_binary: bool


def detect_file_type(file_path: str) -> FileTypeInfo:
    """
    Detect file type using MIME detection and extension fallback.

    Args:
        file_path: Path to the file to analyze

    Returns:
        Dictionary with keys:
            - mime: MIME type string (e.g., "application/pdf")
            - extension: File extension without dot (e.g., "pdf")
            - is_binary: Boolean indicating if file is binary (True for non-text types)
    """
    path = Path(file_path)
    extension = path.suffix.lower().lstrip(".")

    # Try python-magic first (more reliable)
    mime_type = None
    if magic:
        try:
            mime_type = magic.from_file(str(path), mime=True)
        except (OSError, magic.MagicException):
            # Fallback if magic fails
            pass

    # Fallback to mimetypes module
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(str(path))

    # Final fallback: use extension-based detection
    if not mime_type:
        mime_type = _guess_mime_from_extension(extension)

    # Default to application/octet-stream for unknown types
    if not mime_type:
        mime_type = "application/octet-stream"

    # Determine if binary (non-text types)
    is_binary = not (
        mime_type.startswith("text/") or mime_type in ["application/json", "application/xml"]
    )

    return {
        "mime": mime_type,
        "extension": extension,
        "is_binary": is_binary,
    }


def _guess_mime_from_extension(extension: str) -> Optional[str]:
    """Guess MIME type from file extension."""
    extension_map = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "ppt": "application/vnd.ms-powerpoint",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "tiff": "image/tiff",
        "tif": "image/tiff",
        "bmp": "image/bmp",
        "webp": "image/webp",
        "txt": "text/plain",
        "csv": "text/csv",
        "html": "text/html",
        "htm": "text/html",
        "json": "application/json",
        "xml": "application/xml",
        "eml": "message/rfc822",
    }
    return extension_map.get(extension.lower())
