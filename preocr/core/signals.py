"""Signal collection and aggregation for OCR detection."""

from pathlib import Path
from typing import Any, Dict, Optional

from ..utils.filetype import FileTypeInfo


def collect_signals(
    file_path: str,
    file_info: FileTypeInfo,
    text_result: Optional[Dict[str, Any]] = None,
    image_result: Optional[Dict[str, Any]] = None,
    layout_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Collect and aggregate all detection signals.

    Args:
        file_path: Path to the file being analyzed
        file_info: File type information from filetype.detect_file_type()
        text_result: Text extraction result (from text_probe, pdf_probe, or office_probe)
        image_result: Image analysis result (from image_probe)
        layout_result: Layout analysis result (from layout_analyzer, optional)

    Returns:
        Dictionary containing all collected signals:
            - mime: MIME type
            - extension: File extension
            - is_binary: Whether file is binary
            - text_length: Length of extracted text (0 if none)
            - image_entropy: Image entropy (if image)
            - file_size: File size in bytes
            - has_text: Boolean indicating if meaningful text was found
            - layout_type: Layout type from layout analysis (if available)
            - is_mixed_content: Whether content is mixed (if available)
            - text_coverage: Text coverage percentage (if available)
            - image_coverage: Image coverage percentage (if available)
    """
    path = Path(file_path)
    file_size = path.stat().st_size if path.exists() else 0

    text_length = 0
    if text_result:
        text_length = text_result.get("text_length", 0)

    image_entropy = None
    if image_result:
        image_entropy = image_result.get("entropy")

    signals_dict = {
        "mime": file_info.get("mime", "application/octet-stream"),
        "extension": file_info.get("extension", ""),
        "is_binary": file_info.get("is_binary", True),
        "text_length": text_length,
        "image_entropy": image_entropy,
        "file_size": file_size,
        "has_text": text_length > 0,
    }

    # Add layout signals if available
    if layout_result:
        signals_dict["layout_type"] = layout_result.get("layout_type", "unknown")
        signals_dict["is_mixed_content"] = layout_result.get("is_mixed_content", False)
        signals_dict["text_coverage"] = layout_result.get("text_coverage", 0.0)
        signals_dict["image_coverage"] = layout_result.get("image_coverage", 0.0)
        signals_dict["has_images"] = layout_result.get("has_images", False)
        signals_dict["text_density"] = layout_result.get("text_density", 0.0)

    return signals_dict
