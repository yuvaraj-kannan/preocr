# Structured Output Comparison: Unstructured.io vs Docugami

## Executive Summary

This document compares Unstructured.io and Docugami's structured output approaches to identify best practices and features to incorporate into PreOCR.

## 1. Unstructured.io Analysis

### Structured Output Format

**Core Concept**: Element-based partitioning with metadata

```json
{
  "type": "NarrativeText",
  "element_id": "abc123",
  "text": "This is a paragraph of text.",
  "metadata": {
    "filename": "document.pdf",
    "file_directory": "/path/to/file",
    "last_modified": "2024-01-15T10:30:00",
    "filetype": "application/pdf",
    "page_number": 1,
    "coordinates": {
      "points": [
        [100.0, 200.0],
        [500.0, 200.0],
      ],
      "system": "PixelSpace",
      "layout_width": 612.0,
      "layout_height": 792.0
    },
    "languages": ["eng"]
  }
}
```

**Element Types**:
- `NarrativeText` - Paragraphs, body text
- `Title` - Headers, titles
- `Table` - Tables with structure
- `FigureCaption` - Image captions
- `ListItem` - List items
- `PageBreak` - Page breaks
- `Header` - Document headers
- `Footer` - Document footers

### Pros ✅

1. **Rich Metadata**
   - Bounding box coordinates (x, y points)
   - Page numbers
   - Layout dimensions
   - Language detection
   - File metadata

2. **Element Classification**
   - Semantic element types (Title, NarrativeText, etc.)
   - Clear distinction between content types
   - Supports downstream processing

3. **Coordinate System**
   - Precise bounding boxes
   - Multiple coordinate systems supported
   - Layout-aware positioning

4. **LLM-Ready**
   - Clean text extraction
   - Structured metadata for context
   - Easy to convert to markdown

5. **Unified API**
   - Same format for PDFs, images, Office docs
   - Consistent structure across file types

### Cons ❌

1. **Limited Table Structure**
   - Tables extracted as text blocks
   - Cell-level structure not always preserved
   - No row/column relationships

2. **No Form Field Extraction**
   - Doesn't extract PDF form fields
   - No checkbox/radio button detection

3. **No Confidence Scores**
   - Binary extraction (success/fail)
   - No quality metrics per element

4. **No Reading Order**
   - Elements not ordered by reading flow
   - May need post-processing

5. **No Semantic Relationships**
   - No parent-child relationships
   - No section hierarchy

### Key Features to Adopt

1. ✅ **Element-based structure** - Classify content types
2. ✅ **Rich metadata** - Bounding boxes, page numbers, coordinates
3. ✅ **Multiple element types** - Title, NarrativeText, Table, etc.
4. ✅ **Coordinate system** - Precise positioning

## 2. Docugami Analysis

### Structured Output Format

**Core Concept**: XML-based semantic understanding with hierarchical structure

```xml
<Document>
  <Metadata>
    <DocumentType>Invoice</DocumentType>
    <Confidence>0.95</Confidence>
    <ExtractionMethod>native</ExtractionMethod>
  </Metadata>
  <Sections>
    <Section type="header" page="1">
      <Field name="company_name" confidence="0.98">
        <Text>ABC Corporation</Text>
        <BBox x0="100" y0="50" x1="300" y1="80"/>
      </Field>
      <Field name="date" confidence="0.92">
        <Text>2024-01-15</Text>
        <BBox x0="400" y0="50" x1="500" y1="80"/>
      </Field>
    </Section>
    <Section type="table" page="1" id="items_table">
      <Table>
        <Row>
          <Cell row="0" col="0" confidence="0.95">
            <Text>Item 1</Text>
            <BBox x0="100" y0="200" x1="200" y1="220"/>
          </Cell>
          <Cell row="0" col="1" confidence="0.97">
            <Text>$100.00</Text>
            <BBox x0="200" y0="200" x1="300" y1="220"/>
          </Cell>
        </Row>
      </Table>
    </Section>
  </Sections>
  <Relationships>
    <Relationship type="parent" from="items_table" to="header"/>
  </Relationships>
</Document>
```

**JSON Equivalent** (for API):
```json
{
  "document_type": "Invoice",
  "confidence": 0.95,
  "extraction_method": "native",
  "sections": [
    {
      "type": "header",
      "page": 1,
      "fields": [
        {
          "name": "company_name",
          "text": "ABC Corporation",
          "confidence": 0.98,
          "bbox": {"x0": 100, "y0": 50, "x1": 300, "y1": 80}
        }
      ]
    },
    {
      "type": "table",
      "page": 1,
      "id": "items_table",
      "rows": [
        {
          "cells": [
            {
              "row": 0,
              "col": 0,
              "text": "Item 1",
              "confidence": 0.95,
              "bbox": {"x0": 100, "y0": 200, "x1": 200, "y1": 220}
            }
          ]
        }
      ]
    }
  ],
  "relationships": [
    {"type": "parent", "from": "items_table", "to": "header"}
  ]
}
```

### Pros ✅

1. **Semantic Understanding**
   - Document type classification
   - Field-level extraction with names
   - Semantic relationships between elements

2. **Confidence Scores**
   - Per-element confidence
   - Overall document confidence
   - Extraction method tracking

3. **Hierarchical Structure**
   - Sections and subsections
   - Parent-child relationships
   - Logical document structure

4. **Field Extraction**
   - Named fields (company_name, date, amount)
   - Form field detection
   - Structured data extraction

5. **Table Structure**
   - Row/column relationships
   - Cell-level extraction
   - Table metadata

6. **Document Intelligence**
   - Understands document context
   - Adapts extraction based on document type
   - Relationship mapping

### Cons ❌

1. **Complexity**
   - More complex to implement
   - Requires ML models for classification
   - Higher computational overhead

2. **XML-Heavy**
   - XML format less common in modern APIs
   - JSON conversion needed
   - More verbose

3. **Document Type Dependent**
   - Requires training for each document type
   - Less generic than Unstructured.io
   - May need customization

4. **Slower Processing**
   - More analysis required
   - Semantic understanding takes time
   - Not ideal for high-throughput

5. **Less Flexible**
   - Structured around document types
   - Harder to adapt to new formats
   - Requires domain knowledge

### Key Features to Adopt

1. ✅ **Confidence scores** - Per-element and overall
2. ✅ **Semantic relationships** - Parent-child, sections
3. ✅ **Field extraction** - Named fields with types
4. ✅ **Document classification** - Understand document type
5. ✅ **Hierarchical structure** - Sections and subsections

## 3. Comparison Matrix

| Feature | Unstructured.io | Docugami | PreOCR (Current) | Recommendation |
|---------|----------------|----------|------------------|----------------|
| **Element Types** | ✅ Rich (8+ types) | ✅ Rich (semantic) | ⚠️ Basic | **Adopt** - Add element classification |
| **Bounding Boxes** | ✅ Excellent | ✅ Excellent | ✅ Planned | **Keep** - Already planned |
| **Confidence Scores** | ❌ No | ✅ Excellent | ⚠️ Basic | **Adopt** - Per-element confidence |
| **Table Structure** | ⚠️ Basic | ✅ Excellent | ✅ Planned | **Enhance** - Add row/col relationships |
| **Form Fields** | ❌ No | ✅ Yes | ✅ Planned | **Keep** - Already planned |
| **Semantic Relationships** | ❌ No | ✅ Yes | ❌ No | **Adopt** - Add parent-child |
| **Document Classification** | ⚠️ Basic | ✅ Excellent | ❌ No | **Consider** - Future feature |
| **Field Extraction** | ❌ No | ✅ Yes | ❌ No | **Consider** - Medium priority |
| **Reading Order** | ⚠️ Implicit | ✅ Explicit | ❌ No | **Adopt** - Add reading order |
| **Metadata Richness** | ✅ Excellent | ✅ Excellent | ⚠️ Basic | **Enhance** - Add more metadata |
| **LLM-Ready Format** | ✅ Yes (markdown) | ⚠️ XML (needs conversion) | ❌ No | **Adopt** - Add markdown output |
| **Hierarchical Structure** | ❌ Flat | ✅ Hierarchical | ❌ Flat | **Adopt** - Add sections |
| **Processing Speed** | ✅ Fast | ⚠️ Slower | ✅ Fast | **Maintain** - Keep speed advantage |

## 4. Recommended PreOCR Structured Output Format

### Hybrid Approach (Best of Both)

```python
from pydantic import BaseModel
from typing import List, Optional, Dict, Literal
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

class BoundingBox(BaseModel):
    """Bounding box coordinates"""
    x0: float
    y0: float
    x1: float
    y1: float
    page_number: int
    coordinate_system: str = "PDF"  # PDF, PixelSpace, etc.

class Element(BaseModel):
    """Base element structure"""
    element_id: str
    element_type: ElementType
    text: Optional[str] = None
    bbox: BoundingBox
    confidence: float  # Per-element confidence (from Docugami)
    metadata: Dict[str, any] = {}
    parent_id: Optional[str] = None  # Semantic relationship (from Docugami)
    children_ids: List[str] = []  # Child elements

class TableCell(BaseModel):
    """Table cell structure"""
    row: int
    col: int
    text: str
    bbox: BoundingBox
    confidence: float
    rowspan: int = 1
    colspan: int = 1

class Table(BaseModel):
    """Table structure"""
    element_id: str
    element_type: Literal[ElementType.TABLE] = ElementType.TABLE
    page_number: int
    bbox: BoundingBox
    rows: int
    columns: int
    cells: List[TableCell]
    confidence: float
    metadata: Dict[str, any] = {}

class FormField(BaseModel):
    """Form field structure"""
    element_id: str
    element_type: Literal[ElementType.FORM_FIELD] = ElementType.FORM_FIELD
    field_name: Optional[str] = None  # Semantic name (from Docugami)
    field_type: str  # "text", "checkbox", "radio", etc.
    value: Optional[str] = None
    bbox: BoundingBox
    confidence: float

class Section(BaseModel):
    """Document section (hierarchical structure from Docugami)"""
    section_id: str
    section_type: str  # "header", "body", "footer", "table", etc.
    page_number: int
    elements: List[str]  # Element IDs in this section
    parent_section_id: Optional[str] = None
    child_section_ids: List[str] = []

class ExtractionResult(BaseModel):
    """Complete extraction result"""
    # Document-level metadata
    file_path: str
    file_type: str
    extraction_method: str  # "native" or "ocr"
    document_type: Optional[str] = None  # Classification (from Docugami)
    overall_confidence: float
    
    # Elements (from Unstructured.io approach)
    elements: List[Element]
    
    # Structured data
    tables: List[Table]
    forms: List[FormField]
    images: List[Element]
    
    # Hierarchical structure (from Docugami)
    sections: List[Section]
    
    # Reading order
    reading_order: List[str]  # Element IDs in reading order
    
    # Metadata
    metadata: Dict[str, any] = {}
    pages_extracted: Optional[List[int]] = None
    
    # Errors
    errors: List[str] = []
```

### Example Output

```json
{
  "file_path": "invoice.pdf",
  "file_type": "pdf",
  "extraction_method": "native",
  "document_type": "Invoice",
  "overall_confidence": 0.94,
  "elements": [
    {
      "element_id": "elem_001",
      "element_type": "Title",
      "text": "INVOICE",
      "bbox": {
        "x0": 100.0,
        "y0": 50.0,
        "x1": 300.0,
        "y1": 80.0,
        "page_number": 1,
        "coordinate_system": "PDF"
      },
      "confidence": 0.98,
      "metadata": {
        "font_size": 24,
        "font_name": "Arial-Bold"
      },
      "parent_id": null,
      "children_ids": []
    },
    {
      "element_id": "elem_002",
      "element_type": "Table",
      "bbox": {
        "x0": 100.0,
        "y0": 200.0,
        "x1": 500.0,
        "y1": 400.0,
        "page_number": 1,
        "coordinate_system": "PDF"
      },
      "confidence": 0.95,
      "parent_id": "section_body",
      "children_ids": ["cell_001", "cell_002"]
    }
  ],
  "tables": [
    {
      "element_id": "table_001",
      "element_type": "Table",
      "page_number": 1,
      "bbox": {
        "x0": 100.0,
        "y0": 200.0,
        "x1": 500.0,
        "y1": 400.0,
        "page_number": 1,
        "coordinate_system": "PDF"
      },
      "rows": 5,
      "columns": 3,
      "cells": [
        {
          "row": 0,
          "col": 0,
          "text": "Item",
          "bbox": {
            "x0": 100.0,
            "y0": 200.0,
            "x1": 200.0,
            "y1": 220.0,
            "page_number": 1,
            "coordinate_system": "PDF"
          },
          "confidence": 0.97,
          "rowspan": 1,
          "colspan": 1
        }
      ],
      "confidence": 0.95,
      "metadata": {}
    }
  ],
  "sections": [
    {
      "section_id": "section_header",
      "section_type": "header",
      "page_number": 1,
      "elements": ["elem_001"],
      "parent_section_id": null,
      "child_section_ids": []
    },
    {
      "section_id": "section_body",
      "section_type": "body",
      "page_number": 1,
      "elements": ["table_001"],
      "parent_section_id": null,
      "child_section_ids": []
    }
  ],
  "reading_order": ["elem_001", "table_001"],
  "metadata": {
    "page_count": 1,
    "extraction_timestamp": "2024-01-15T10:30:00Z"
  },
  "pages_extracted": [1],
  "errors": []
}
```

## 5. Features to Add to PreOCR

### Phase 1: Core Structured Output (High Priority)

1. **Element Classification** (from Unstructured.io)
   - Add element types: Title, NarrativeText, Table, Header, Footer, etc.
   - Classify each extracted piece of content
   - Enable semantic understanding

2. **Per-Element Confidence** (from Docugami)
   - Confidence score for each element
   - Overall document confidence
   - Extraction method tracking

3. **Rich Metadata** (from Unstructured.io)
   - Bounding boxes with coordinate system
   - Page numbers
   - Layout dimensions
   - Font information (if available)

4. **Reading Order** (from Docugami)
   - Order elements by reading flow
   - Top-to-bottom, left-to-right
   - Critical for LLM processing

### Phase 2: Advanced Features (Medium Priority)

5. **Hierarchical Structure** (from Docugami)
   - Sections and subsections
   - Parent-child relationships
   - Logical document organization

6. **Semantic Relationships** (from Docugami)
   - Link related elements
   - Table-to-header relationships
   - Image-to-caption relationships

7. **Document Classification** (from Docugami)
   - Detect document type (invoice, contract, etc.)
   - Adapt extraction strategy
   - Enable specialized processing

8. **Field Extraction** (from Docugami)
   - Named fields (company_name, date, amount)
   - Semantic field identification
   - Structured data extraction

### Phase 3: LLM Integration (High Priority)

9. **Markdown Output** (from Unstructured.io)
   - Convert to markdown format
   - LLM-ready structure
   - Preserve formatting and hierarchy

10. **JSON Schema Export**
    - Export Pydantic models as JSON Schema
    - Enable validation
    - API documentation

## 6. Implementation Priority

### Immediate (Next Release)
- ✅ Element classification (Title, NarrativeText, Table, etc.)
- ✅ Per-element confidence scores
- ✅ Rich bounding box metadata
- ✅ Reading order detection

### Short-term (3-6 months)
- ✅ Hierarchical sections
- ✅ Semantic relationships
- ✅ Markdown output format
- ✅ JSON Schema export

### Long-term (6-12 months)
- ✅ Document classification
- ✅ Field extraction
- ✅ Advanced semantic understanding

## 7. Pros/Cons Summary

### Unstructured.io Approach

**Pros**:
- Simple, flat structure
- Fast processing
- Rich metadata
- LLM-ready markdown
- Unified format across file types

**Cons**:
- No confidence scores
- No semantic relationships
- Limited table structure
- No form field extraction

**Best For**: General document processing, LLM pipelines, fast extraction

### Docugami Approach

**Pros**:
- Semantic understanding
- Confidence scores
- Hierarchical structure
- Field extraction
- Document classification

**Cons**:
- More complex
- Slower processing
- Requires ML models
- Less flexible

**Best For**: Structured documents, forms, invoices, contracts

### PreOCR Hybrid Approach

**Pros**:
- Combines best of both
- Fast processing (from Unstructured.io)
- Semantic understanding (from Docugami)
- Confidence scores
- LLM-ready output

**Cons**:
- More complex to implement
- Requires careful design
- May need iteration

**Best For**: Comprehensive document processing, production systems

## 8. Recommendations

1. **Start with Unstructured.io structure** - Simple, fast, proven
2. **Add Docugami confidence scores** - Critical for production
3. **Implement reading order** - Essential for LLM processing
4. **Add hierarchical sections** - Enables better understanding
5. **Provide markdown output** - LLM integration
6. **Keep PreOCR speed advantage** - Don't sacrifice performance

## 9. Conclusion

Both Unstructured.io and Docugami have valuable approaches:

- **Unstructured.io**: Best for general extraction, LLM integration, speed
- **Docugami**: Best for semantic understanding, structured documents, quality

**PreOCR should adopt a hybrid approach**:
- Use Unstructured.io's element-based structure
- Add Docugami's confidence scores and semantic relationships
- Maintain PreOCR's speed advantage
- Enable LLM integration with markdown output

This creates a **best-in-class structured output format** that combines:
- ✅ Fast processing
- ✅ Rich metadata
- ✅ Semantic understanding
- ✅ LLM-ready output
- ✅ Production-quality confidence scores

