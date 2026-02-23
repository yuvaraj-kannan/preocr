"""Base classes and utilities for extraction."""

import uuid
from typing import List, Optional, Dict, Any

from .. import exceptions
from .schemas import BoundingBox, ElementType

ExtractionError = exceptions.PreOCRError


def generate_element_id(prefix: str = "elem") -> str:
    """Generate a unique element ID."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def generate_section_id(prefix: str = "section") -> str:
    """Generate a unique section ID."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def create_bbox(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    page_number: int,
    layout_width: Optional[float] = None,
    layout_height: Optional[float] = None,
    coordinate_system: str = "PDF",
) -> BoundingBox:
    """Create a bounding box with standard parameters."""
    return BoundingBox(
        x0=x0,
        y0=y0,
        x1=x1,
        y1=y1,
        page_number=page_number,
        coordinate_system=coordinate_system,
        layout_width=layout_width,
        layout_height=layout_height,
    )


def calculate_bbox_from_chars(
    chars: List[Dict[str, Any]],
    page_number: int,
    page_width: Optional[float] = None,
    page_height: Optional[float] = None,
) -> Optional[BoundingBox]:
    """Calculate bounding box from a list of character positions."""
    if not chars:
        return None

    x0 = min(char.get("x0", 0) for char in chars)
    y0 = min(char.get("top", char.get("y0", 0)) for char in chars)
    x1 = max(char.get("x1", 0) for char in chars)
    y1 = max(char.get("bottom", char.get("y1", 0)) for char in chars)

    return create_bbox(
        x0, y0, x1, y1, page_number, layout_width=page_width, layout_height=page_height
    )


def calculate_confidence(
    text_quality: float = 0.9,
    extraction_method: str = "pdfplumber",
    element_type_certainty: float = 0.9,
    bbox_accuracy: float = 0.95,
) -> float:
    """
    Calculate confidence score for an element.

    Args:
        text_quality: Quality of text (0.0-1.0), based on font size and clarity
        extraction_method: Method used ("pymupdf" = 0.9, "pdfplumber" = 0.8)
        element_type_certainty: How certain we are about classification (0.0-1.0)
        bbox_accuracy: How well-defined the bbox is (0.0-1.0)

    Returns:
        Confidence score between 0.0 and 1.0
    """
    method_score = 0.9 if extraction_method == "pymupdf" else 0.8

    # Weighted average
    confidence = (
        text_quality * 0.3 + method_score * 0.3 + element_type_certainty * 0.2 + bbox_accuracy * 0.2
    )

    return min(max(confidence, 0.0), 1.0)


def classify_element_type(
    text: Optional[str],
    font_size: Optional[float] = None,
    is_bold: bool = False,
    position_y: Optional[float] = None,
    page_height: Optional[float] = None,
    is_centered: bool = False,
) -> ElementType:
    """
    Classify element type based on characteristics.

    Args:
        text: Text content
        font_size: Font size in points
        is_bold: Whether text is bold
        position_y: Y position on page
        page_height: Total page height
        is_centered: Whether text is centered

    Returns:
        ElementType classification
    """
    if not text:
        return ElementType.NARRATIVE_TEXT

    # Title: Large font, centered, near top
    if font_size and font_size > 16 and is_centered:
        if position_y and page_height and position_y < page_height * 0.2:
            return ElementType.TITLE

    # Heading: Medium-large font, bold
    if font_size and font_size > 12 and is_bold:
        return ElementType.HEADING

    # Default to narrative text
    return ElementType.NARRATIVE_TEXT
