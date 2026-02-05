"""PDF extraction with structured output."""

from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .. import exceptions
from ..utils.logger import get_logger
from .schemas import (
    ExtractionResult,
    Element,
    Table,
    FormField,
    ElementType,
    BoundingBox,
    TableCell,
    Section,
)
from .base import (
    generate_element_id,
    generate_section_id,
    create_bbox,
    calculate_bbox_from_chars,
    calculate_confidence,
    classify_element_type,
)

PDFProcessingError = exceptions.PDFProcessingError
logger = get_logger(__name__)

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore[assignment]

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


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

    errors = []

    # Try pdfplumber first (better for text and tables)
    if pdfplumber:
        try:
            return _extract_with_pdfplumber(
                path,
                result,
                include_tables,
                include_forms,
                include_metadata,
                include_structure,
                include_images,
                include_bbox,
                pages,
            )
        except Exception as e:
            logger.warning(f"PDF extraction failed with pdfplumber: {e}")
            errors.append(f"pdfplumber extraction failed: {str(e)}")

    # Fallback to PyMuPDF
    if fitz:
        try:
            return _extract_with_pymupdf(
                path,
                result,
                include_tables,
                include_forms,
                include_metadata,
                include_structure,
                include_images,
                include_bbox,
                pages,
            )
        except Exception as e:
            logger.warning(f"PDF extraction failed with PyMuPDF: {e}")
            errors.append(f"pymupdf extraction failed: {str(e)}")

    # Both failed
    result.errors = errors
    result.overall_confidence = 0.0
    return result


def _extract_with_pdfplumber(
    path: Path,
    result: ExtractionResult,
    include_tables: bool,
    include_forms: bool,
    include_metadata: bool,
    include_structure: bool,
    include_images: bool,
    include_bbox: bool,
    pages: Optional[List[int]],
) -> ExtractionResult:
    """Extract using pdfplumber."""
    all_elements = []
    all_tables = []
    all_forms = []
    all_images = []
    all_sections = []
    element_counter = 0
    table_counter = 0
    form_counter = 0
    image_counter = 0
    section_counter = 0
    errors = []

    try:
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            pages_to_process = pages if pages else list(range(1, page_count + 1))

            # Extract metadata
            if include_metadata:
                result.metadata.update({
                    "page_count": page_count,
                    "extraction_method": "pdfplumber",
                })
                if pdf.metadata:
                    result.metadata["pdf_metadata"] = pdf.metadata

            # Process each page
            for page_num in pages_to_process:
                if page_num < 1 or page_num > page_count:
                    continue

                page = pdf.pages[page_num - 1]
                page_width = page.width
                page_height = page.height

                try:
                    # Extract text elements
                    page_elements = _extract_page_elements(
                        page,
                        page_num,
                        page_width,
                        page_height,
                        element_counter,
                        include_bbox,
                    )
                    all_elements.extend(page_elements)
                    element_counter += len(page_elements)

                    # Extract tables
                    if include_tables:
                        page_tables = _extract_page_tables(
                            page,
                            page_num,
                            page_width,
                            page_height,
                            table_counter,
                            include_bbox,
                        )
                        all_tables.extend(page_tables)
                        table_counter += len(page_tables)

                    # Extract images
                    if include_images:
                        page_images = _extract_page_images_pdfplumber(
                            page,
                            page_num,
                            page_width,
                            page_height,
                            image_counter,
                            include_bbox,
                        )
                        all_images.extend(page_images)
                        image_counter += len(page_images)

                except Exception as e:
                    logger.warning(f"Error processing page {page_num}: {e}")
                    errors.append(f"Page {page_num}: {str(e)}")

            # Extract forms using PyMuPDF (if available)
            if include_forms and fitz:
                try:
                    forms = _extract_forms_pymupdf(path, pages_to_process, form_counter, include_bbox)
                    all_forms.extend(forms)
                except Exception as e:
                    logger.warning(f"Form extraction failed: {e}")
                    errors.append(f"Form extraction: {str(e)}")

            # Detect sections
            if include_structure:
                try:
                    sections = _detect_sections(
                        all_elements,
                        all_tables,
                        pages_to_process,
                        section_counter,
                    )
                    all_sections.extend(sections)
                except Exception as e:
                    logger.warning(f"Section detection failed: {e}")
                    errors.append(f"Section detection: {str(e)}")

            # Calculate reading order
            if include_structure:
                reading_order = _calculate_reading_order(all_elements, all_tables)
                result.reading_order = reading_order

    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        errors.append(f"Extraction error: {str(e)}")

    # Populate result
    result.elements = all_elements
    result.tables = all_tables
    result.forms = all_forms
    result.images = all_images
    result.sections = all_sections
    result.errors = errors
    result.pages_extracted = pages_to_process if pages else None

    # Calculate overall confidence
    result.overall_confidence = _calculate_overall_confidence(
        all_elements, all_tables, all_forms, all_images
    )

    # Quality metrics
    result.quality_metrics = {
        "total_elements": len(all_elements),
        "total_tables": len(all_tables),
        "total_forms": len(all_forms),
        "total_images": len(all_images),
        "total_sections": len(all_sections),
        "extraction_method": "pdfplumber",
    }

    return result


def _extract_with_pymupdf(
    path: Path,
    result: ExtractionResult,
    include_tables: bool,
    include_forms: bool,
    include_metadata: bool,
    include_structure: bool,
    include_images: bool,
    include_bbox: bool,
    pages: Optional[List[int]],
) -> ExtractionResult:
    """Extract using PyMuPDF (fallback)."""
    all_elements = []
    all_tables = []
    all_forms = []
    all_images = []
    all_sections = []
    element_counter = 0
    table_counter = 0
    form_counter = 0
    image_counter = 0
    section_counter = 0
    errors = []

    try:
        doc = fitz.open(path)
        page_count = len(doc)
        pages_to_process = pages if pages else list(range(1, page_count + 1))

        # Extract metadata
        if include_metadata:
            result.metadata.update({
                "page_count": page_count,
                "extraction_method": "pymupdf",
            })
            if doc.metadata:
                result.metadata["pdf_metadata"] = doc.metadata

        # Process each page
        for page_num in pages_to_process:
            if page_num < 1 or page_num > page_count:
                continue

            page = doc[page_num - 1]
            page_rect = page.rect
            page_width = page_rect.width
            page_height = page_rect.height

            try:
                # Extract text elements
                page_elements = _extract_page_elements_pymupdf(
                    page,
                    page_num,
                    page_width,
                    page_height,
                    element_counter,
                    include_bbox,
                )
                all_elements.extend(page_elements)
                element_counter += len(page_elements)

                # Extract forms
                if include_forms:
                    page_forms = _extract_page_forms_pymupdf(
                        page,
                        page_num,
                        page_width,
                        page_height,
                        form_counter,
                        include_bbox,
                    )
                    all_forms.extend(page_forms)
                    form_counter += len(page_forms)

                # Extract images
                if include_images:
                    page_images = _extract_page_images_pymupdf(
                        page,
                        page_num,
                        page_width,
                        page_height,
                        image_counter,
                        include_bbox,
                    )
                    all_images.extend(page_images)
                    image_counter += len(page_images)

            except Exception as e:
                logger.warning(f"Error processing page {page_num}: {e}")
                errors.append(f"Page {page_num}: {str(e)}")

        doc.close()

        # Detect sections
        if include_structure:
            try:
                sections = _detect_sections(
                    all_elements,
                    all_tables,
                    pages_to_process,
                    section_counter,
                )
                all_sections.extend(sections)
            except Exception as e:
                logger.warning(f"Section detection failed: {e}")
                errors.append(f"Section detection: {str(e)}")

        # Calculate reading order
        if include_structure:
            reading_order = _calculate_reading_order(all_elements, all_tables)
            result.reading_order = reading_order

    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        errors.append(f"Extraction error: {str(e)}")

    # Populate result
    result.elements = all_elements
    result.tables = all_tables
    result.forms = all_forms
    result.images = all_images
    result.sections = all_sections
    result.errors = errors
    result.pages_extracted = pages_to_process if pages else None

    # Calculate overall confidence
    result.overall_confidence = _calculate_overall_confidence(
        all_elements, all_tables, all_forms, all_images
    )

    # Quality metrics
    result.quality_metrics = {
        "total_elements": len(all_elements),
        "total_tables": len(all_tables),
        "total_forms": len(all_forms),
        "total_images": len(all_images),
        "total_sections": len(all_sections),
        "extraction_method": "pymupdf",
    }

    return result


def _extract_page_elements(
    page: Any,
    page_num: int,
    page_width: float,
    page_height: float,
    start_counter: int,
    include_bbox: bool,
) -> List[Element]:
    """Extract text elements from a page using pdfplumber."""
    elements = []
    chars = page.chars if hasattr(page, "chars") else []

    if not chars:
        return elements

    # Group chars by text blocks (simple approach: group by proximity)
    text_blocks = _group_chars_into_blocks(chars)

    for idx, block in enumerate(text_blocks):
        element_id = generate_element_id(f"elem_{start_counter + idx}")

        # Extract text
        text = "".join(char.get("text", "") for char in block)

        # Calculate bbox
        if include_bbox:
            bbox = calculate_bbox_from_chars(block, page_num, page_width, page_height)
        else:
            bbox = create_bbox(0, 0, page_width, page_height, page_num, page_width, page_height)

        # Classify element type
        font_size = block[0].get("size", 12) if block else 12
        is_bold = block[0].get("fontname", "").endswith("Bold") if block else False
        position_y = bbox.y0
        is_centered = _is_text_centered(block, page_width)

        element_type = classify_element_type(
            text,
            font_size=font_size,
            is_bold=is_bold,
            position_y=position_y,
            page_height=page_height,
            is_centered=is_centered,
        )

        # Calculate confidence
        confidence = calculate_confidence(
            text_quality=0.9 if len(text) > 10 else 0.7,
            extraction_method="pdfplumber",
            element_type_certainty=0.9,
            bbox_accuracy=0.95 if include_bbox else 0.5,
        )

        element = Element(
            element_id=element_id,
            element_type=element_type,
            text=text,
            bbox=bbox,
            confidence=confidence,
            metadata={"font_size": font_size, "is_bold": is_bold},
        )

        elements.append(element)

    return elements


def _extract_page_elements_pymupdf(
    page: Any,
    page_num: int,
    page_width: float,
    page_height: float,
    start_counter: int,
    include_bbox: bool,
) -> List[Element]:
    """Extract text elements from a page using PyMuPDF."""
    elements = []
    text_dict = page.get_text("dict")

    if not text_dict or "blocks" not in text_dict:
        return elements

    for idx, block in enumerate(text_dict["blocks"]):
        if "lines" not in block:
            continue

        element_id = generate_element_id(f"elem_{start_counter + idx}")

        # Extract text from lines
        text_parts = []
        for line in block["lines"]:
            for span in line.get("spans", []):
                text_parts.append(span.get("text", ""))

        text = "".join(text_parts)

        if not text.strip():
            continue

        # Calculate bbox
        bbox_rect = block.get("bbox", [0, 0, page_width, page_height])
        if include_bbox:
            bbox = create_bbox(
                bbox_rect[0],
                bbox_rect[1],
                bbox_rect[2],
                bbox_rect[3],
                page_num,
                page_width,
                page_height,
            )
        else:
            bbox = create_bbox(0, 0, page_width, page_height, page_num, page_width, page_height)

        # Classify element type
        font_size = 12
        is_bold = False
        if block["lines"] and block["lines"][0].get("spans"):
            span = block["lines"][0]["spans"][0]
            font_size = span.get("size", 12)
            is_bold = "bold" in span.get("font", "").lower()

        element_type = classify_element_type(
            text,
            font_size=font_size,
            is_bold=is_bold,
            position_y=bbox.y0,
            page_height=page_height,
            is_centered=False,
        )

        # Calculate confidence
        confidence = calculate_confidence(
            text_quality=0.8 if len(text) > 10 else 0.6,
            extraction_method="pymupdf",
            element_type_certainty=0.8,
            bbox_accuracy=0.9 if include_bbox else 0.5,
        )

        element = Element(
            element_id=element_id,
            element_type=element_type,
            text=text,
            bbox=bbox,
            confidence=confidence,
            metadata={"font_size": font_size, "is_bold": is_bold},
        )

        elements.append(element)

    return elements


def _extract_page_tables(
    page: Any,
    page_num: int,
    page_width: float,
    page_height: float,
    start_counter: int,
    include_bbox: bool,
) -> List[Table]:
    """Extract tables from a page using pdfplumber."""
    tables = []
    page_tables = page.extract_tables() if hasattr(page, "extract_tables") else []

    for idx, table_data in enumerate(page_tables):
        if not table_data:
            continue

        table_id = generate_element_id(f"table_{start_counter + idx}")

        # Get table bbox
        table_objects = page.find_tables()
        table_bbox = None
        if table_objects and idx < len(table_objects):
            table_obj = table_objects[idx]
            if hasattr(table_obj, "bbox"):
                bbox_coords = table_obj.bbox
                table_bbox = create_bbox(
                    bbox_coords[0],
                    bbox_coords[1],
                    bbox_coords[2],
                    bbox_coords[3],
                    page_num,
                    page_width,
                    page_height,
                )

        if not table_bbox:
            table_bbox = create_bbox(0, 0, page_width, page_height, page_num, page_width, page_height)

        # Extract cells
        cells = []
        for row_idx, row in enumerate(table_data):
            for col_idx, cell_text in enumerate(row):
                if cell_text is None:
                    continue

                cell_text = str(cell_text).strip()
                if not cell_text:
                    continue

                # Approximate cell bbox
                num_rows = len(table_data)
                num_cols = len(row) if row else 0
                cell_width = page_width / num_cols if num_cols > 0 else page_width
                cell_height = page_height / num_rows if num_rows > 0 else page_height

                cell_bbox = create_bbox(
                    table_bbox.x0 + col_idx * cell_width,
                    table_bbox.y0 + row_idx * cell_height,
                    table_bbox.x0 + (col_idx + 1) * cell_width,
                    table_bbox.y0 + (row_idx + 1) * cell_height,
                    page_num,
                    page_width,
                    page_height,
                )

                cell = TableCell(
                    row=row_idx,
                    col=col_idx,
                    text=cell_text,
                    bbox=cell_bbox,
                    confidence=0.9,
                )

                cells.append(cell)

        if not cells:
            continue

        # Calculate table dimensions
        num_rows = len(table_data)
        num_cols = max(len(row) for row in table_data) if table_data else 0

        table = Table(
            element_id=table_id,
            page_number=page_num,
            bbox=table_bbox,
            rows=num_rows,
            columns=num_cols,
            cells=cells,
            confidence=0.9,
            metadata={"extraction_method": "pdfplumber"},
        )

        tables.append(table)

    return tables


def _extract_forms_pymupdf(
    path: Path,
    pages: List[int],
    start_counter: int,
    include_bbox: bool,
) -> List[FormField]:
    """Extract form fields using PyMuPDF."""
    forms = []

    if not fitz:
        return forms

    try:
        doc = fitz.open(path)
        form_counter = start_counter

        for page_num in pages:
            if page_num < 1 or page_num > len(doc):
                continue

            page = doc[page_num - 1]
            page_rect = page.rect
            page_width = page_rect.width
            page_height = page_rect.height

            widget_list = page.widgets()

            for widget in widget_list:
                field_id = generate_element_id(f"form_{form_counter}")
                form_counter += 1

                field_type = widget.field_type_string
                field_name = widget.field_name
                field_value = widget.field_value

                # Get bbox
                rect = widget.rect
                if include_bbox:
                    bbox = create_bbox(
                        rect.x0,
                        rect.y0,
                        rect.x1,
                        rect.y1,
                        page_num,
                        page_width,
                        page_height,
                    )
                else:
                    bbox = create_bbox(0, 0, page_width, page_height, page_num, page_width, page_height)

                form_field = FormField(
                    element_id=field_id,
                    field_name=field_name,
                    field_type=field_type,
                    value=field_value,
                    bbox=bbox,
                    confidence=0.85,
                    metadata={"extraction_method": "pymupdf"},
                )

                forms.append(form_field)

        doc.close()

    except Exception as e:
        logger.warning(f"Form extraction error: {e}")

    return forms


def _extract_page_forms_pymupdf(
    page: Any,
    page_num: int,
    page_width: float,
    page_height: float,
    start_counter: int,
    include_bbox: bool,
) -> List[FormField]:
    """Extract form fields from a page using PyMuPDF."""
    forms = []
    widget_list = page.widgets()
    form_counter = start_counter

    for widget in widget_list:
        field_id = generate_element_id(f"form_{form_counter}")
        form_counter += 1

        field_type = widget.field_type_string
        field_name = widget.field_name
        field_value = widget.field_value

        # Get bbox
        rect = widget.rect
        if include_bbox:
            bbox = create_bbox(
                rect.x0,
                rect.y0,
                rect.x1,
                rect.y1,
                page_num,
                page_width,
                page_height,
            )
        else:
            bbox = create_bbox(0, 0, page_width, page_height, page_num, page_width, page_height)

        form_field = FormField(
            element_id=field_id,
            field_name=field_name,
            field_type=field_type,
            value=field_value,
            bbox=bbox,
            confidence=0.85,
            metadata={"extraction_method": "pymupdf"},
        )

        forms.append(form_field)

    return forms


def _extract_page_images_pdfplumber(
    page: Any,
    page_num: int,
    page_width: float,
    page_height: float,
    start_counter: int,
    include_bbox: bool,
) -> List[Element]:
    """Extract images from a page using pdfplumber."""
    images = []
    page_images = page.images if hasattr(page, "images") else []

    for idx, img in enumerate(page_images):
        image_id = generate_element_id(f"img_{start_counter + idx}")

        # Get image bbox
        x0 = img.get("x0", 0)
        y0 = img.get("top", img.get("y0", 0))
        x1 = img.get("x1", page_width)
        y1 = img.get("bottom", img.get("y1", page_height))

        if include_bbox:
            bbox = create_bbox(x0, y0, x1, y1, page_num, page_width, page_height)
        else:
            bbox = create_bbox(0, 0, page_width, page_height, page_num, page_width, page_height)

        image_element = Element(
            element_id=image_id,
            element_type=ElementType.IMAGE,
            text=None,
            bbox=bbox,
            confidence=0.9,
            metadata={
                "width": img.get("width", 0),
                "height": img.get("height", 0),
                "extraction_method": "pdfplumber",
            },
        )

        images.append(image_element)

    return images


def _extract_page_images_pymupdf(
    page: Any,
    page_num: int,
    page_width: float,
    page_height: float,
    start_counter: int,
    include_bbox: bool,
) -> List[Element]:
    """Extract images from a page using PyMuPDF."""
    images = []
    image_list = page.get_images()

    for idx, img_index in enumerate(image_list):
        image_id = generate_element_id(f"img_{start_counter + idx}")

        # Get image bbox (approximate)
        image_rects = page.get_image_bbox(img_index[0])
        if image_rects:
            rect = image_rects
            if include_bbox:
                bbox = create_bbox(
                    rect.x0,
                    rect.y0,
                    rect.x1,
                    rect.y1,
                    page_num,
                    page_width,
                    page_height,
                )
            else:
                bbox = create_bbox(0, 0, page_width, page_height, page_num, page_width, page_height)
        else:
            bbox = create_bbox(0, 0, page_width, page_height, page_num, page_width, page_height)

        image_element = Element(
            element_id=image_id,
            element_type=ElementType.IMAGE,
            text=None,
            bbox=bbox,
            confidence=0.9,
            metadata={
                "image_index": img_index[0],
                "extraction_method": "pymupdf",
            },
        )

        images.append(image_element)

    return images


def _detect_sections(
    elements: List[Element],
    tables: List[Table],
    pages: List[int],
    start_counter: int,
) -> List[Section]:
    """Detect document sections (header, body, footer)."""
    sections = []
    section_counter = start_counter

    if not elements:
        return sections

    # Group elements by page
    elements_by_page: Dict[int, List[Element]] = {}
    for elem in elements:
        page_num = elem.bbox.page_number
        if page_num not in elements_by_page:
            elements_by_page[page_num] = []
        elements_by_page[page_num].append(elem)

    # Detect header/footer/body per page
    for page_num in pages:
        page_elements = elements_by_page.get(page_num, [])

        if not page_elements:
            continue

        # Get page height from first element
        page_height = page_elements[0].bbox.layout_height or 800

        # Detect header (top 15% of page)
        header_threshold = page_height * 0.15
        header_elements = [
            elem for elem in page_elements if elem.bbox.y0 < header_threshold
        ]

        # Detect footer (bottom 15% of page)
        footer_threshold = page_height * 0.85
        footer_elements = [
            elem for elem in page_elements if elem.bbox.y1 > footer_threshold
        ]

        # Body elements (middle)
        body_elements = [
            elem
            for elem in page_elements
            if elem not in header_elements and elem not in footer_elements
        ]

        # Create sections
        if header_elements:
            section_id = generate_section_id(f"section_{section_counter}")
            section_counter += 1
            sections.append(
                Section(
                    section_id=section_id,
                    section_type="header",
                    page_number=page_num,
                    start_page=page_num,
                    end_page=page_num,
                    elements=[e.element_id for e in header_elements],
                    confidence=0.8,
                    metadata={"is_repeated": False},
                )
            )

        if body_elements:
            section_id = generate_section_id(f"section_{section_counter}")
            section_counter += 1
            sections.append(
                Section(
                    section_id=section_id,
                    section_type="body",
                    page_number=page_num,
                    start_page=page_num,
                    end_page=page_num,
                    elements=[e.element_id for e in body_elements],
                    confidence=0.9,
                    metadata={"content_density": len(body_elements) / max(len(page_elements), 1)},
                )
            )

        if footer_elements:
            section_id = generate_section_id(f"section_{section_counter}")
            section_counter += 1
            sections.append(
                Section(
                    section_id=section_id,
                    section_type="footer",
                    page_number=page_num,
                    start_page=page_num,
                    end_page=page_num,
                    elements=[e.element_id for e in footer_elements],
                    confidence=0.8,
                    metadata={"is_repeated": False},
                )
            )

    return sections


def _calculate_reading_order(
    elements: List[Element],
    tables: List[Table],
) -> List[str]:
    """Calculate reading order for elements."""
    # Simple reading order: sort by page, then by y position, then by x position
    all_items = []

    # Add elements
    for elem in elements:
        all_items.append((elem.bbox.page_number, elem.bbox.y0, elem.bbox.x0, elem.element_id))

    # Add tables
    for table in tables:
        all_items.append((table.page_number, table.bbox.y0, table.bbox.x0, table.element_id))

    # Sort by page, then y, then x
    all_items.sort(key=lambda x: (x[0], x[1], x[2]))

    return [item[3] for item in all_items]


def _calculate_overall_confidence(
    elements: List[Element],
    tables: List[Table],
    forms: List[FormField],
    images: List[Element],
) -> float:
    """Calculate overall confidence score."""
    all_confidences = []

    for elem in elements:
        all_confidences.append(elem.confidence)

    for table in tables:
        all_confidences.append(table.confidence)

    for form in forms:
        all_confidences.append(form.confidence)

    for img in images:
        all_confidences.append(img.confidence)

    if not all_confidences:
        return 0.0

    return sum(all_confidences) / len(all_confidences)


def _group_chars_into_blocks(chars: List[Dict[str, Any]], threshold: float = 5.0) -> List[List[Dict[str, Any]]]:
    """Group characters into text blocks based on proximity."""
    if not chars:
        return []

    blocks = []
    current_block = [chars[0]]

    for i in range(1, len(chars)):
        prev_char = chars[i - 1]
        curr_char = chars[i]

        # Check if characters are close (same line)
        prev_y = prev_char.get("top", prev_char.get("y0", 0))
        curr_y = curr_char.get("top", curr_char.get("y0", 0))

        if abs(curr_y - prev_y) < threshold:
            current_block.append(curr_char)
        else:
            blocks.append(current_block)
            current_block = [curr_char]

    if current_block:
        blocks.append(current_block)

    return blocks


def _is_text_centered(chars: List[Dict[str, Any]], page_width: float) -> bool:
    """Check if text is centered on the page."""
    if not chars:
        return False

    x0 = min(char.get("x0", 0) for char in chars)
    x1 = max(char.get("x1", 0) for char in chars)
    text_width = x1 - x0
    text_center = (x0 + x1) / 2
    page_center = page_width / 2

    # Consider centered if within 10% of page center
    return abs(text_center - page_center) < page_width * 0.1

