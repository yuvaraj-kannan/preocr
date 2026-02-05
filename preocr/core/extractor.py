"""Main API for native data extraction."""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from .. import constants, exceptions
from ..utils import filetype, logger as logger_module
from ..extraction.schemas import ExtractionResult
from ..extraction.pdf_extractor import extract_pdf_native_data
from ..extraction.office_extractor import extract_office_native_data
from ..extraction.text_extractor import extract_text_native_data
from ..extraction.formatters import format_result

Config = constants.Config
get_logger = logger_module.get_logger

logger = get_logger(__name__)


def extract_native_data(
    file_path: Union[str, Path],
    include_tables: bool = True,
    include_forms: bool = True,
    include_metadata: bool = True,
    include_structure: bool = True,
    include_images: bool = True,
    include_bbox: bool = True,
    pages: Optional[List[int]] = None,
    output_format: str = "pydantic",
    config: Optional[Config] = None,
) -> Union[ExtractionResult, Dict[str, Any], str]:
    """
    Extract structured data from machine-readable documents.

    This function extracts structured data from documents that do not require OCR,
    including element classification, tables, forms, images, and metadata.

    Args:
        file_path: Path to the file to extract data from
        include_tables: Whether to extract tables (default: True)
        include_forms: Whether to extract form fields (default: True)
        include_metadata: Whether to include document metadata (default: True)
        include_structure: Whether to detect sections and reading order (default: True)
        include_images: Whether to detect images (default: True)
        include_bbox: Whether to include bounding box coordinates (default: True)
        pages: Optional list of page numbers to extract (1-indexed). If None, extracts all pages.
        output_format: Output format - "pydantic" (default), "json", or "markdown"
        config: Optional Config object (currently unused, reserved for future use)

    Returns:
        ExtractionResult (if output_format="pydantic"), Dict (if "json"), or str (if "markdown")

    Example:
        >>> from preocr import extract_native_data
        >>>
        >>> # Extract all data as Pydantic model
        >>> result = extract_native_data("document.pdf")
        >>> print(result.overall_confidence)
        >>>
        >>> # Extract specific pages as JSON
        >>> json_data = extract_native_data("document.pdf", pages=[1, 2], output_format="json")
        >>>
        >>> # Extract as markdown for LLM consumption
        >>> markdown = extract_native_data("document.pdf", output_format="markdown")
    """
    path = Path(file_path)

    if not path.exists():
        raise exceptions.FileTypeDetectionError(f"File not found: {file_path}")

    # Detect file type
    file_info = filetype.detect_file_type(str(path))
    mime_type = file_info.get("mime", "")
    extension = file_info.get("extension", "").lower()

    # Determine file type category
    if mime_type == "application/pdf" or extension == "pdf":
        file_type_category = "pdf"
    elif mime_type.startswith("application/vnd.openxmlformats") or extension in ["docx", "pptx", "xlsx"]:
        file_type_category = "office"
    elif mime_type.startswith("text/") or extension in ["txt", "html", "htm", "csv"]:
        file_type_category = "text"
    else:
        file_type_category = "unknown"

    # Route to appropriate extractor
    if file_type_category == "pdf":
        result = extract_pdf_native_data(
            str(path),
            include_tables=include_tables,
            include_forms=include_forms,
            include_metadata=include_metadata,
            include_structure=include_structure,
            include_images=include_images,
            include_bbox=include_bbox,
            pages=pages,
        )
    elif file_type_category == "office":
        result = extract_office_native_data(
            str(path),
            include_tables=include_tables,
            include_metadata=include_metadata,
            include_structure=include_structure,
            include_bbox=include_bbox,
        )
    elif file_type_category == "text":
        result = extract_text_native_data(
            str(path),
            include_metadata=include_metadata,
            include_structure=include_structure,
            include_bbox=include_bbox,
        )
    else:
        result = ExtractionResult(
            file_path=str(path),
            file_type=extension or "unknown",
            extraction_method="native",
            overall_confidence=0.0,
            errors=[f"Unsupported file type: {file_type_category}"],
        )

    # Format output
    return format_result(result, output_format=output_format)

