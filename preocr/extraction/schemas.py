"""Structured output schemas for PreOCR extraction."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal, Any
from enum import Enum


class ElementType(str, Enum):
    """Element types inspired by Unstructured.io"""

    NARRATIVE_TEXT = "NarrativeText"
    TITLE = "Title"
    HEADING = "Heading"
    TABLE = "Table"
    TABLE_CELL = "TableCell"
    LIST_ITEM = "ListItem"
    HEADER = "Header"
    FOOTER = "Footer"
    IMAGE = "Image"
    FORM_FIELD = "FormField"
    PAGE_BREAK = "PageBreak"
    FIGURE_CAPTION = "FigureCaption"


class BoundingBox(BaseModel):
    """Bounding box coordinates (from Unstructured.io)"""

    x0: float = Field(..., description="Left coordinate")
    y0: float = Field(..., description="Top coordinate")
    x1: float = Field(..., description="Right coordinate")
    y1: float = Field(..., description="Bottom coordinate")
    page_number: int = Field(..., description="Page number (1-indexed)")
    coordinate_system: str = Field(default="PDF", description="Coordinate system")
    layout_width: Optional[float] = Field(None, description="Page width")
    layout_height: Optional[float] = Field(None, description="Page height")


class Element(BaseModel):
    """Base element structure (combines Unstructured.io + Docugami)"""

    element_id: str = Field(..., description="Unique element identifier")
    element_type: ElementType = Field(..., description="Type of element")
    text: Optional[str] = Field(None, description="Extracted text content")
    bbox: BoundingBox = Field(..., description="Bounding box coordinates")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Extraction confidence (from Docugami)"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    parent_id: Optional[str] = Field(None, description="Parent element ID (semantic relationship)")
    children_ids: List[str] = Field(default_factory=list, description="Child element IDs")
    reading_order: Optional[int] = Field(None, description="Reading order index")


class TableCell(BaseModel):
    """Table cell structure (enhanced with confidence)"""

    row: int = Field(..., description="Row index (0-indexed)")
    col: int = Field(..., description="Column index (0-indexed)")
    text: str = Field(..., description="Cell text content")
    bbox: BoundingBox = Field(..., description="Cell bounding box")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Cell extraction confidence")
    rowspan: int = Field(default=1, description="Number of rows spanned")
    colspan: int = Field(default=1, description="Number of columns spanned")


class Table(BaseModel):
    """Table structure (from Unstructured.io + Docugami confidence)"""

    element_id: str = Field(..., description="Unique table identifier")
    element_type: Literal[ElementType.TABLE] = ElementType.TABLE
    page_number: int = Field(..., description="Page number")
    bbox: BoundingBox = Field(..., description="Table bounding box")
    rows: int = Field(..., description="Number of rows")
    columns: int = Field(..., description="Number of columns")
    cells: List[TableCell] = Field(..., description="Table cells")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Table extraction confidence")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Table metadata")


class FormField(BaseModel):
    """Form field structure (from Docugami semantic naming)"""

    element_id: str = Field(..., description="Unique field identifier")
    element_type: Literal[ElementType.FORM_FIELD] = ElementType.FORM_FIELD
    field_name: Optional[str] = Field(
        None, description="Semantic field name (e.g., 'company_name')"
    )
    field_type: str = Field(..., description="Field type: text, checkbox, radio, etc.")
    value: Optional[str] = Field(None, description="Field value")
    bbox: BoundingBox = Field(..., description="Field bounding box")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Field extraction confidence")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Field metadata")


class Section(BaseModel):
    """Document section (hierarchical structure from Docugami)"""

    section_id: str = Field(..., description="Unique section identifier")
    section_type: str = Field(..., description="Section type: header, body, footer, table, etc.")
    page_number: int = Field(..., description="Page number")
    start_page: int = Field(..., description="Starting page number")
    end_page: int = Field(..., description="Ending page number")
    elements: List[str] = Field(..., description="Element IDs in this section")
    parent_section_id: Optional[str] = Field(None, description="Parent section ID")
    child_section_ids: List[str] = Field(default_factory=list, description="Child section IDs")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Section detection confidence")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Section metadata")


class ExtractionResult(BaseModel):
    """Complete extraction result (hybrid approach)"""

    # Document-level metadata
    file_path: str = Field(..., description="Path to source file")
    file_type: str = Field(..., description="File type: pdf, docx, etc.")
    extraction_method: str = Field(..., description="Extraction method: native or ocr")
    document_type: Optional[str] = Field(
        None, description="Document classification (invoice, contract, etc.)"
    )
    overall_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Overall extraction confidence"
    )

    # Elements (from Unstructured.io approach)
    elements: List[Element] = Field(default_factory=list, description="All extracted elements")

    # Structured data
    tables: List[Table] = Field(default_factory=list, description="Extracted tables")
    forms: List[FormField] = Field(default_factory=list, description="Extracted form fields")
    images: List[Element] = Field(default_factory=list, description="Extracted images")

    # Hierarchical structure (from Docugami)
    sections: List[Section] = Field(default_factory=list, description="Document sections")

    # Reading order (from Docugami)
    reading_order: List[str] = Field(
        default_factory=list, description="Element IDs in reading order"
    )

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    pages_extracted: Optional[List[int]] = Field(None, description="Pages that were extracted")

    # Quality metrics
    quality_metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Extraction quality metrics"
    )

    # Errors
    errors: List[str] = Field(default_factory=list, description="Extraction errors")

    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "invoice.pdf",
                "file_type": "pdf",
                "extraction_method": "native",
                "document_type": "Invoice",
                "overall_confidence": 0.94,
                "elements": [],
                "tables": [],
                "forms": [],
                "images": [],
                "sections": [],
                "reading_order": [],
                "metadata": {},
                "pages_extracted": [1],
                "quality_metrics": {},
                "errors": [],
            }
        }
