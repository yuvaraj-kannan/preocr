# Integration Plan: Combining Unstructured.io & Docugami Features into PreOCR

## Overview

This document outlines how to integrate the best features from Unstructured.io and Docugami into PreOCR's extraction system while maintaining PreOCR's core strengths (speed, page-level detection, cost optimization).

## Architecture Integration

### Current PreOCR Flow

```
Document → needs_ocr() → [Machine-readable?] → extract_native_data()
                              ↓
                         [Needs OCR?] → extract_ocr_data() (future)
```

### Enhanced PreOCR Flow (With Structured Output)

```
Document → needs_ocr() → [Machine-readable?] → extract_native_data()
                              ↓                                    ↓
                         [Needs OCR?]                    Structured Output
                              ↓                         (Element-based + Semantic)
                         extract_ocr_data()              ↓
                         (future)                    Markdown/JSON
                                                      ↓
                                                 LLM/RAG Pipeline
```

## 1. Structured Output Schema Integration

### Step 1: Create Pydantic Models

**File**: `preocr/extraction/schemas.py`

```python
"""Structured output schemas for PreOCR extraction."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal, Any
from enum import Enum
from datetime import datetime

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
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence (from Docugami)")
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
    field_name: Optional[str] = Field(None, description="Semantic field name (e.g., 'company_name')")
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
    elements: List[str] = Field(..., description="Element IDs in this section")
    parent_section_id: Optional[str] = Field(None, description="Parent section ID")
    child_section_ids: List[str] = Field(default_factory=list, description="Child section IDs")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Section detection confidence")

class ExtractionResult(BaseModel):
    """Complete extraction result (hybrid approach)"""
    # Document-level metadata
    file_path: str = Field(..., description="Path to source file")
    file_type: str = Field(..., description="File type: pdf, docx, etc.")
    extraction_method: str = Field(..., description="Extraction method: native or ocr")
    document_type: Optional[str] = Field(None, description="Document classification (invoice, contract, etc.)")
    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Overall extraction confidence")
    
    # Elements (from Unstructured.io approach)
    elements: List[Element] = Field(default_factory=list, description="All extracted elements")
    
    # Structured data
    tables: List[Table] = Field(default_factory=list, description="Extracted tables")
    forms: List[FormField] = Field(default_factory=list, description="Extracted form fields")
    images: List[Element] = Field(default_factory=list, description="Extracted images")
    
    # Hierarchical structure (from Docugami)
    sections: List[Section] = Field(default_factory=list, description="Document sections")
    
    # Reading order (from Docugami)
    reading_order: List[str] = Field(default_factory=list, description="Element IDs in reading order")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    pages_extracted: Optional[List[int]] = Field(None, description="Pages that were extracted")
    
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
                "errors": []
            }
        }
```

## 2. Integration into Existing Extractors

### Step 2: Update PDF Extractor

**File**: `preocr/extraction/pdf_extractor.py`

```python
"""PDF extraction with structured output."""

from typing import Dict, List, Optional, Any
from pathlib import Path
from ..extraction.schemas import (
    ExtractionResult, Element, Table, FormField, ElementType,
    BoundingBox, TableCell, Section
)

def extract_pdf_native_data(
    file_path: str,
    include_tables: bool = True,
    include_forms: bool = True,
    include_metadata: bool = True,
    include_structure: bool = True,
    include_images: bool = True,
    include_bbox: bool = True,
    pages: Optional[List[int]] = None,
) -> ExtractionResult:
    """
    Extract structured data from PDF with element classification and confidence.
    
    Combines:
    - Unstructured.io: Element-based structure, rich metadata
    - Docugami: Confidence scores, semantic relationships, sections
    """
    path = Path(file_path)
    
    # Initialize result
    result = ExtractionResult(
        file_path=str(path),
        file_type="pdf",
        extraction_method="native",
        overall_confidence=0.0,
    )
    
    # Extract using pdfplumber/PyMuPDF
    with pdfplumber.open(path) as pdf:
        page_count = len(pdf.pages)
        pages_to_process = pages or list(range(1, page_count + 1))
        
        all_elements = []
        all_tables = []
        all_forms = []
        all_images = []
        all_sections = []
        element_counter = 0
        
        for page_num in pages_to_process:
            page = pdf.pages[page_num - 1]
            
            # Extract elements with classification
            page_elements = _extract_page_elements(
                page, page_num, element_counter, include_bbox
            )
            all_elements.extend(page_elements)
            element_counter += len(page_elements)
            
            # Extract tables with structure
            if include_tables:
                page_tables = _extract_tables_with_structure(
                    page, page_num, element_counter, include_bbox
                )
                all_tables.extend(page_tables)
                element_counter += len(page_tables)
            
            # Extract forms
            if include_forms:
                page_forms = _extract_forms_with_structure(
                    page, page_num, element_counter, include_bbox
                )
                all_forms.extend(page_forms)
                element_counter += len(page_forms)
            
            # Extract images
            if include_images:
                page_images = _extract_images_with_structure(
                    page, page_num, element_counter, include_bbox
                )
                all_images.extend(page_images)
                element_counter += len(page_images)
            
            # Detect sections (headers, footers, body)
            if include_structure:
                page_sections = _detect_sections(
                    page, page_num, all_elements, all_tables
                )
                all_sections.extend(page_sections)
        
        # Calculate reading order
        reading_order = _calculate_reading_order(all_elements)
        
        # Calculate overall confidence
        overall_confidence = _calculate_overall_confidence(
            all_elements, all_tables, all_forms
        )
        
        # Build result
        result.elements = all_elements
        result.tables = all_tables
        result.forms = all_forms
        result.images = all_images
        result.sections = all_sections
        result.reading_order = reading_order
        result.overall_confidence = overall_confidence
        result.pages_extracted = pages_to_process
        
        # Add metadata
        if include_metadata:
            result.metadata = _extract_document_metadata(pdf)
    
    return result

def _extract_page_elements(
    page, page_num: int, start_id: int, include_bbox: bool
) -> List[Element]:
    """Extract page elements with classification (Unstructured.io style)."""
    elements = []
    element_id = start_id
    
    # Extract text blocks
    chars = page.chars if hasattr(page, "chars") else []
    if chars:
        # Group into text blocks
        text_blocks = _group_chars_into_blocks(chars)
        
        for block in text_blocks:
            # Classify element type
            element_type = _classify_text_element(block["text"])
            
            # Calculate confidence
            confidence = _calculate_text_confidence(block)
            
            # Create bounding box
            bbox = BoundingBox(
                x0=block["x0"],
                y0=block["y0"],
                x1=block["x1"],
                y1=block["y1"],
                page_number=page_num,
                coordinate_system="PDF",
                layout_width=page.width,
                layout_height=page.height,
            )
            
            element = Element(
                element_id=f"elem_{element_id:06d}",
                element_type=element_type,
                text=block["text"],
                bbox=bbox,
                confidence=confidence,
                metadata={
                    "font_size": block.get("size"),
                    "font_name": block.get("fontname"),
                },
            )
            elements.append(element)
            element_id += 1
    
    return elements

def _classify_text_element(text: str) -> ElementType:
    """Classify text element type (Unstructured.io style)."""
    text_upper = text.upper().strip()
    
    # Title detection
    if len(text) < 100 and text_upper == text:
        return ElementType.TITLE
    
    # Heading detection
    if len(text) < 200 and any(text.startswith(f"{i}.") for i in range(1, 10)):
        return ElementType.HEADING
    
    # List item detection
    if text.strip().startswith(("-", "•", "*", "1.", "2.", "3.")):
        return ElementType.LIST_ITEM
    
    # Default to narrative text
    return ElementType.NARRATIVE_TEXT

def _calculate_text_confidence(block: Dict) -> float:
    """Calculate confidence for text extraction (Docugami style)."""
    # Base confidence from text quality
    confidence = 0.9
    
    # Adjust based on font size (larger = more confident)
    if "size" in block:
        if block["size"] > 12:
            confidence += 0.05
        elif block["size"] < 8:
            confidence -= 0.1
    
    # Adjust based on text length (longer = more confident)
    if len(block.get("text", "")) > 50:
        confidence += 0.03
    
    return min(confidence, 1.0)

def _extract_tables_with_structure(
    page, page_num: int, start_id: int, include_bbox: bool
) -> List[Table]:
    """Extract tables with structure and confidence."""
    tables = []
    table_id = start_id
    
    extracted_tables = page.extract_tables() if hasattr(page, "extract_tables") else []
    
    for table_idx, table_data in enumerate(extracted_tables):
        # Extract table bounding box
        table_bbox = _get_table_bbox(page, table_idx)
        
        # Build cells with confidence
        cells = []
        for row_idx, row in enumerate(table_data):
            for col_idx, cell_text in enumerate(row):
                if cell_text:
                    cell_bbox = _get_cell_bbox(page, table_idx, row_idx, col_idx)
                    cell_confidence = _calculate_cell_confidence(cell_text)
                    
                    cell = TableCell(
                        row=row_idx,
                        col=col_idx,
                        text=str(cell_text),
                        bbox=cell_bbox,
                        confidence=cell_confidence,
                    )
                    cells.append(cell)
        
        # Calculate table confidence
        table_confidence = _calculate_table_confidence(cells)
        
        table = Table(
            element_id=f"table_{table_id:06d}",
            page_number=page_num,
            bbox=table_bbox,
            rows=len(table_data),
            columns=len(table_data[0]) if table_data else 0,
            cells=cells,
            confidence=table_confidence,
        )
        tables.append(table)
        table_id += 1
    
    return tables

def _detect_sections(
    page, page_num: int, elements: List[Element], tables: List[Table]
) -> List[Section]:
    """Detect document sections (Docugami style)."""
    sections = []
    
    # Detect header (top 15% of page)
    header_elements = [
        e.element_id for e in elements
        if e.bbox.y0 < page.height * 0.15
    ]
    if header_elements:
        sections.append(Section(
            section_id=f"section_header_p{page_num}",
            section_type="header",
            page_number=page_num,
            elements=header_elements,
            confidence=0.85,
        ))
    
    # Detect footer (bottom 15% of page)
    footer_elements = [
        e.element_id for e in elements
        if e.bbox.y1 > page.height * 0.85
    ]
    if footer_elements:
        sections.append(Section(
            section_id=f"section_footer_p{page_num}",
            section_type="footer",
            page_number=page_num,
            elements=footer_elements,
            confidence=0.85,
        ))
    
    # Detect body section
    body_elements = [
        e.element_id for e in elements
        if page.height * 0.15 <= e.bbox.y0 <= page.height * 0.85
    ]
    if body_elements:
        sections.append(Section(
            section_id=f"section_body_p{page_num}",
            section_type="body",
            page_number=page_num,
            elements=body_elements,
            confidence=0.90,
        ))
    
    return sections

def _calculate_reading_order(elements: List[Element]) -> List[str]:
    """Calculate reading order (Docugami style)."""
    # Sort by page, then by y0 (top to bottom), then by x0 (left to right)
    sorted_elements = sorted(
        elements,
        key=lambda e: (e.bbox.page_number, e.bbox.y0, e.bbox.x0)
    )
    
    # Assign reading order index
    for idx, element in enumerate(sorted_elements):
        element.reading_order = idx
    
    return [e.element_id for e in sorted_elements]

def _calculate_overall_confidence(
    elements: List[Element],
    tables: List[Table],
    forms: List[FormField],
) -> float:
    """Calculate overall extraction confidence (Docugami style)."""
    if not elements and not tables and not forms:
        return 0.0
    
    confidences = []
    
    # Element confidences
    if elements:
        confidences.extend([e.confidence for e in elements])
    
    # Table confidences
    if tables:
        confidences.extend([t.confidence for t in tables])
    
    # Form confidences
    if forms:
        confidences.extend([f.confidence for f in forms])
    
    # Weighted average (more elements = higher weight)
    if confidences:
        return sum(confidences) / len(confidences)
    
    return 0.0
```

## 3. Markdown Output Format

### Step 3: Add Markdown Converter

**File**: `preocr/extraction/formatters.py`

```python
"""Output formatters for PreOCR extraction results."""

from typing import Optional
from ..extraction.schemas import ExtractionResult, ElementType

def to_markdown(result: ExtractionResult) -> str:
    """
    Convert extraction result to markdown format (Unstructured.io style).
    Perfect for LLM consumption.
    """
    lines = []
    
    # Document header
    if result.document_type:
        lines.append(f"# {result.document_type}")
        lines.append("")
    
    # Process elements in reading order
    element_map = {e.element_id: e for e in result.elements}
    
    for element_id in result.reading_order:
        if element_id in element_map:
            element = element_map[element_id]
            lines.append(_element_to_markdown(element))
    
    # Add tables
    for table in result.tables:
        lines.append(_table_to_markdown(table))
    
    # Add images
    for image in result.images:
        lines.append(_image_to_markdown(image))
    
    return "\n".join(lines)

def _element_to_markdown(element) -> str:
    """Convert element to markdown."""
    if element.element_type == ElementType.TITLE:
        return f"# {element.text}\n"
    elif element.element_type == ElementType.HEADING:
        return f"## {element.text}\n"
    elif element.element_type == ElementType.LIST_ITEM:
        return f"- {element.text}\n"
    else:
        return f"{element.text}\n"

def _table_to_markdown(table) -> str:
    """Convert table to markdown."""
    lines = [f"\n## Table on Page {table.page_number}\n"]
    
    # Build table structure
    max_row = max(cell.row for cell in table.cells) if table.cells else 0
    max_col = max(cell.col for cell in table.cells) if table.cells else 0
    
    # Create grid
    grid = [[None] * (max_col + 1) for _ in range(max_row + 1)]
    for cell in table.cells:
        grid[cell.row][cell.col] = cell.text
    
    # Convert to markdown table
    if grid:
        # Header row
        header = "| " + " | ".join(str(cell or "") for cell in grid[0]) + " |"
        separator = "| " + " | ".join(["---"] * len(grid[0])) + " |"
        lines.append(header)
        lines.append(separator)
        
        # Data rows
        for row in grid[1:]:
            row_str = "| " + " | ".join(str(cell or "") for cell in row) + " |"
            lines.append(row_str)
    
    lines.append("")
    return "\n".join(lines)

def _image_to_markdown(image) -> str:
    """Convert image to markdown."""
    bbox = image.bbox
    return f"![Image](bbox: {bbox.x0},{bbox.y0},{bbox.x1},{bbox.y1}, page: {bbox.page_number})\n"
```

## 4. Integration Points

### Step 4: Update Main API

**File**: `preocr/core/extractor.py`

```python
"""Main extraction API with structured output."""

from typing import Union, Optional, List
from pathlib import Path
from ..extraction.schemas import ExtractionResult
from ..extraction.formatters import to_markdown
from ..extraction import pdf_extractor, office_extractor, text_extractor

def extract_native_data(
    file_path: Union[str, Path],
    include_tables: bool = True,
    include_forms: bool = True,
    include_metadata: bool = True,
    include_structure: bool = True,
    include_images: bool = True,
    include_bbox: bool = True,
    pages: Optional[List[int]] = None,
    output_format: str = "json",  # "json", "markdown", "pydantic"
) -> Union[ExtractionResult, str, dict]:
    """
    Extract structured data from machine-readable documents.
    
    Combines best features:
    - Unstructured.io: Element-based structure, rich metadata
    - Docugami: Confidence scores, semantic relationships, sections
    
    Args:
        output_format: "json" (dict), "markdown" (string), "pydantic" (ExtractionResult)
    """
    path = Path(file_path)
    
    # Detect file type and route
    file_info = detect_file_type(str(path))
    
    if file_info["mime"] == "application/pdf":
        result = pdf_extractor.extract_pdf_native_data(
            str(path),
            include_tables=include_tables,
            include_forms=include_forms,
            include_metadata=include_metadata,
            include_structure=include_structure,
            include_images=include_images,
            include_bbox=include_bbox,
            pages=pages,
        )
    elif "officedocument" in file_info["mime"]:
        result = office_extractor.extract_office_native_data(
            str(path),
            include_tables=include_tables,
            include_metadata=include_metadata,
            include_structure=include_structure,
        )
    else:
        result = text_extractor.extract_text_native_data(
            str(path),
            include_structure=include_structure,
            include_metadata=include_metadata,
        )
    
    # Format output
    if output_format == "markdown":
        return to_markdown(result)
    elif output_format == "json":
        return result.model_dump()
    else:  # pydantic
        return result
```

## 5. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-4)

1. **Week 1**: Create schemas module
   - ✅ Define Pydantic models
   - ✅ Add element types
   - ✅ Add bounding box structure

2. **Week 2**: Update PDF extractor
   - ✅ Integrate element classification
   - ✅ Add confidence calculation
   - ✅ Add bounding box extraction

3. **Week 3**: Add section detection
   - ✅ Header/footer detection
   - ✅ Body section detection
   - ✅ Section relationships

4. **Week 4**: Reading order calculation
   - ✅ Sort elements by reading flow
   - ✅ Assign reading order indices

### Phase 2: Enhancement (Weeks 5-8)

5. **Week 5**: Markdown formatter
   - ✅ Convert to markdown
   - ✅ Preserve structure
   - ✅ Include metadata

6. **Week 6**: Confidence scoring
   - ✅ Per-element confidence
   - ✅ Overall confidence
   - ✅ Quality metrics

7. **Week 7**: Semantic relationships
   - ✅ Parent-child links
   - ✅ Section-element relationships
   - ✅ Table-header relationships

8. **Week 8**: Testing & validation
   - ✅ Unit tests
   - ✅ Integration tests
   - ✅ Performance benchmarks

### Phase 3: Advanced Features (Future)

9. **Document classification** (Docugami)
   - Detect document type
   - Adapt extraction strategy

10. **Field extraction** (Docugami)
    - Named fields
    - Semantic field identification

## 6. Key Benefits of Integration

### From Unstructured.io:
- ✅ **Element-based structure** - Clean, semantic element types
- ✅ **Rich metadata** - Bounding boxes, page numbers, coordinates
- ✅ **LLM-ready** - Markdown output format
- ✅ **Unified format** - Consistent across file types

### From Docugami:
- ✅ **Confidence scores** - Per-element and overall quality metrics
- ✅ **Semantic relationships** - Parent-child, sections
- ✅ **Hierarchical structure** - Sections and subsections
- ✅ **Reading order** - Logical document flow

### PreOCR Advantages Maintained:
- ✅ **Speed** - Fast processing maintained
- ✅ **Page-level** - Granular page-by-page extraction
- ✅ **Cost optimization** - Skip OCR when not needed
- ✅ **CPU-only** - No GPU dependency

## 7. Example Usage

```python
from preocr import extract_native_data

# Extract with structured output
result = extract_native_data(
    "invoice.pdf",
    pages=[1, 2],  # Specific pages
    output_format="pydantic"  # Get Pydantic model
)

# Access structured data
print(f"Document type: {result.document_type}")
print(f"Confidence: {result.overall_confidence}")
print(f"Tables: {len(result.tables)}")
print(f"Elements: {len(result.elements)}")

# Access elements with confidence
for element in result.elements:
    print(f"{element.element_type}: {element.text[:50]} (confidence: {element.confidence})")

# Get markdown for LLM
markdown = extract_native_data(
    "invoice.pdf",
    output_format="markdown"
)
# Feed directly to LLM

# Get JSON for API
json_data = extract_native_data(
    "invoice.pdf",
    output_format="json"
)
# Use in REST API
```

## 8. Migration Strategy

### Backward Compatibility

The existing extraction functions remain unchanged. New structured output is additive:

```python
# Old way (still works)
result = extract_native_data("file.pdf")
# Returns dict

# New way (structured)
result = extract_native_data("file.pdf", output_format="pydantic")
# Returns ExtractionResult model

# Markdown for LLM
markdown = extract_native_data("file.pdf", output_format="markdown")
# Returns string
```

## 9. Conclusion

This integration plan combines:
- **Unstructured.io's** element-based structure and rich metadata
- **Docugami's** confidence scores and semantic understanding
- **PreOCR's** speed and page-level granularity

Result: A **best-in-class structured output format** that:
- ✅ Maintains PreOCR's speed advantage
- ✅ Provides production-quality confidence scores
- ✅ Enables LLM integration with markdown
- ✅ Supports semantic understanding
- ✅ Preserves all existing functionality

