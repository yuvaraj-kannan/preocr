"""Extraction module for structured output."""

from .schemas import (
    ElementType,
    BoundingBox,
    Element,
    TableCell,
    Table,
    FormField,
    Section,
    ExtractionResult,
)
from .base import (
    generate_element_id,
    generate_section_id,
    create_bbox,
    calculate_bbox_from_chars,
    calculate_confidence,
    classify_element_type,
    ExtractionError,
)
from .pdf_extractor import extract_pdf_native_data
from .office_extractor import extract_office_native_data
from .text_extractor import extract_text_native_data
from .formatters import format_result, format_as_json, format_as_markdown

__all__ = [
    # Schemas
    "ElementType",
    "BoundingBox",
    "Element",
    "TableCell",
    "Table",
    "FormField",
    "Section",
    "ExtractionResult",
    # Utilities
    "generate_element_id",
    "generate_section_id",
    "create_bbox",
    "calculate_bbox_from_chars",
    "calculate_confidence",
    "classify_element_type",
    "ExtractionError",
    # Extractors
    "extract_pdf_native_data",
    "extract_office_native_data",
    "extract_text_native_data",
    # Formatters
    "format_result",
    "format_as_json",
    "format_as_markdown",
]

