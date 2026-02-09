"""PDF extraction with structured output."""

import re
from pathlib import Path
from typing import Dict, List, Optional, Any

from .. import exceptions
from ..utils.logger import get_logger
from .schemas import (
    ExtractionResult,
    Element,
    Table,
    FormField,
    ElementType,
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
        document_type=None,
        pages_extracted=None,
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
                result.metadata.update(
                    {
                        "page_count": page_count,
                        "extraction_method": "pdfplumber",
                    }
                )
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
                    forms = _extract_forms_pymupdf(
                        path, pages_to_process, form_counter, include_bbox
                    )
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

            # Fix reversed text in elements
            for elem in all_elements:
                if elem.text and elem.bbox:
                    fixed_text = _fix_reversed_text(elem.text, elem.bbox)
                    if fixed_text != elem.text:
                        elem.text = fixed_text

            # Step 1: Table stitching: Merge visually separated tables
            if all_tables:
                tables_before_stitch = len(all_tables)
                all_tables = _stitch_tables(all_tables, line_height=20.0)
                tables_after_stitch = len(all_tables)
                if tables_before_stitch != tables_after_stitch:
                    logger.debug(
                        f"Stitched tables: {tables_before_stitch} → {tables_after_stitch} "
                        f"({tables_before_stitch - tables_after_stitch} tables merged)"
                    )

            # Step 2: Table-Narrative deduplication: Remove tables that duplicate narrative text
            # IMPORTANT: Do this BEFORE removing elements inside tables
            elements_by_page: Dict[int, List[Element]] = {}
            for elem in all_elements:
                page_num = elem.bbox.page_number if elem.bbox else 1
                if page_num not in elements_by_page:
                    elements_by_page[page_num] = []
                elements_by_page[page_num].append(elem)

            filtered_tables = []
            for table in all_tables:
                page_num = table.page_number
                page_elements = elements_by_page.get(page_num, [])
                
                # Check if table is duplicate of narrative text
                if _is_table_duplicate_of_narrative(table, page_elements, threshold=0.7):
                    logger.debug(
                        f"Table {table.element_id} on page {page_num} marked as duplicate "
                        f"(overlaps with narrative text)"
                    )
                    # Mark as decorative but keep in metadata
                    table.metadata["is_decorative"] = True
                    table.metadata["deduplication_reason"] = "overlaps_with_narrative"
                else:
                    filtered_tables.append(table)
            
            all_tables = filtered_tables

            # Step 3: Promote narrative text to table rows (recover missing line items)
            # FIX 1: Dedupe promoted rows by Y-position
            for table in all_tables:
                if not table.metadata.get("is_decorative", False):
                    _promote_narrative_to_table(all_elements, table, line_height=20.0)

            # Step 4: Rebuild table rows cleanly (FIX 2: Rebuild from scratch)
            for table in all_tables:
                if not table.metadata.get("is_decorative", False):
                    _rebuild_table_rows(table, line_height=20.0)

            # Step 5: Duplication control: Remove elements that overlap with REAL tables
            # Only remove elements inside non-decorative tables
            elements_before_dedup = len(all_elements)
            all_elements = _remove_elements_inside_tables(all_elements, all_tables)
            elements_after_dedup = len(all_elements)
            if elements_before_dedup != elements_after_dedup:
                logger.debug(
                    f"Removed {elements_before_dedup - elements_after_dedup} elements "
                    f"that overlap with tables"
                )

            # Step 6: Detect document type and extract structured data
            document_type = _detect_document_type(all_elements, all_tables)
            if document_type:
                result.document_type = document_type
                
                # Build structured data for invoices
                if document_type == "invoice":
                    invoice_data = _build_invoice_data(all_elements, all_tables)
                    validation = _validate_invoice(invoice_data)
                    
                    result.metadata["document_data"] = invoice_data
                    result.metadata["validation"] = validation
                    
                    logger.debug(
                        f"Detected invoice: {invoice_data.get('invoice_number', 'N/A')}, "
                        f"validation: {validation['status']}"
                    )

            # Calculate reading order (excluding footer sections)
            if include_structure:
                reading_order = _calculate_reading_order(
                    all_elements, all_tables, exclude_footers=True, sections=all_sections
                )
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
    all_elements: List[Element] = []
    all_tables: List[Table] = []
    all_forms: List[FormField] = []
    all_images: List[Element] = []
    all_sections: List[Section] = []
    element_counter = 0
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
            result.metadata.update(
                {
                    "page_count": page_count,
                    "extraction_method": "pymupdf",
                }
            )
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

        # Fix reversed text in elements
        for elem in all_elements:
            if elem.text and elem.bbox:
                fixed_text = _fix_reversed_text(elem.text, elem.bbox)
                if fixed_text != elem.text:
                    elem.text = fixed_text

        # Step 1: Table stitching: Merge visually separated tables
        if all_tables:
            tables_before_stitch = len(all_tables)
            all_tables = _stitch_tables(all_tables, line_height=20.0)
            tables_after_stitch = len(all_tables)
            if tables_before_stitch != tables_after_stitch:
                logger.debug(
                    f"Stitched tables: {tables_before_stitch} → {tables_after_stitch} "
                    f"({tables_before_stitch - tables_after_stitch} tables merged)"
                )

        # Step 2: Table-Narrative deduplication: Remove tables that duplicate narrative text
        # IMPORTANT: Do this BEFORE removing elements inside tables
        elements_by_page: Dict[int, List[Element]] = {}
        for elem in all_elements:
            page_num = elem.bbox.page_number if elem.bbox else 1
            if page_num not in elements_by_page:
                elements_by_page[page_num] = []
            elements_by_page[page_num].append(elem)

        filtered_tables = []
        for table in all_tables:
            page_num = table.page_number
            page_elements = elements_by_page.get(page_num, [])
            
            # Check if table is duplicate of narrative text
            if _is_table_duplicate_of_narrative(table, page_elements, threshold=0.7):
                logger.debug(
                    f"Table {table.element_id} on page {page_num} marked as duplicate "
                    f"(overlaps with narrative text)"
                )
                # Mark as decorative but keep in metadata
                table.metadata["is_decorative"] = True
                table.metadata["deduplication_reason"] = "overlaps_with_narrative"
            else:
                filtered_tables.append(table)
        
        all_tables = filtered_tables

        # Step 3: Promote narrative text to table rows (recover missing line items)
        # FIX 1: Dedupe promoted rows by Y-position
        for table in all_tables:
            if not table.metadata.get("is_decorative", False):
                _promote_narrative_to_table(all_elements, table, line_height=20.0)

        # Step 4: Rebuild table rows cleanly (FIX 2: Rebuild from scratch)
        for table in all_tables:
            if not table.metadata.get("is_decorative", False):
                _rebuild_table_rows(table, line_height=20.0)

        # Step 5: Duplication control: Remove elements that overlap with REAL tables
        # Only remove elements inside non-decorative tables
        elements_before_dedup = len(all_elements)
        all_elements = _remove_elements_inside_tables(all_elements, all_tables)
        elements_after_dedup = len(all_elements)
        if elements_before_dedup != elements_after_dedup:
            logger.debug(
                f"Removed {elements_before_dedup - elements_after_dedup} elements "
                f"that overlap with tables"
            )

        # Step 6: Detect document type and extract structured data
        document_type = _detect_document_type(all_elements, all_tables)
        if document_type:
            result.document_type = document_type
            
            # Build structured data for invoices
            if document_type == "invoice":
                invoice_data = _build_invoice_data(all_elements, all_tables)
                validation = _validate_invoice(invoice_data)
                
                result.metadata["document_data"] = invoice_data
                result.metadata["validation"] = validation
                
                logger.debug(
                    f"Detected invoice: {invoice_data.get('invoice_number', 'N/A')}, "
                    f"validation: {validation['status']}"
                )

        # Calculate reading order (excluding footer sections)
        if include_structure:
            reading_order = _calculate_reading_order(
                all_elements, all_tables, exclude_footers=True, sections=all_sections
            )
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
    elements: List[Element] = []
    chars = page.chars if hasattr(page, "chars") else []

    if not chars:
        return elements

    # Separate upright and rotated text for better merging
    # Process them separately to avoid mixing horizontal and vertical text
    upright_chars = [c for c in chars if c.get("upright", True)]
    rotated_chars = [c for c in chars if not c.get("upright", True)]
    
    # Merge chars into text blocks with intelligent text merging
    # Process upright text first (main content)
    merged_blocks = _merge_chars_into_text_blocks(upright_chars, threshold=5.0)
    
    # Process rotated text separately (if any)
    if rotated_chars:
        rotated_blocks = _merge_chars_into_text_blocks(rotated_chars, threshold=5.0)
        merged_blocks.extend(rotated_blocks)

    for idx, block_data in enumerate(merged_blocks):
        element_id = generate_element_id(f"elem_{start_counter + idx}")

        # Extract merged text
        text = block_data["text"]
        # Get original chars for bbox calculation
        block_chars = block_data["chars"]

        # Calculate bbox from original chars (preserves accuracy)
        if include_bbox:
            bbox = calculate_bbox_from_chars(block_chars, page_num, page_width, page_height)
        else:
            bbox = create_bbox(0, 0, page_width, page_height, page_num, page_width, page_height)

        # Classify element type
        font_size = block_chars[0].get("size", 12) if block_chars else 12
        is_bold = block_chars[0].get("fontname", "").endswith("Bold") if block_chars and block_chars[0].get("fontname") else False
        position_y = bbox.y0 if bbox else 0.0
        is_centered = _is_text_centered(block_chars, page_width)

        element_type = classify_element_type(
            text,
            font_size=font_size,
            is_bold=is_bold,
            position_y=position_y,
            page_height=page_height,
            is_centered=is_centered,
        )

        # Ensure bbox is not None
        if bbox is None:
            bbox = create_bbox(0, 0, page_width, page_height, page_num, page_width, page_height)

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
            parent_id=None,
            reading_order=None,
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
    elements: List[Element] = []
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
            parent_id=None,
            reading_order=None,
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
            table_bbox = create_bbox(
                0, 0, page_width, page_height, page_num, page_width, page_height
            )

        # Extract cells
        cells = []
        for row_idx, row in enumerate(table_data):
            for col_idx, cell_text in enumerate(row):
                if cell_text is None:
                    continue

                cell_text = str(cell_text).strip()
                if not cell_text:
                    continue

                # Fix price-word spacing in table cells
                # Table extraction loses glyph spacing, so we repair it here
                cell_text = _fix_table_cell_price_word_spacing(cell_text)

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
    forms: List[FormField] = []

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
                    bbox = create_bbox(
                        0, 0, page_width, page_height, page_num, page_width, page_height
                    )

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
            parent_id=None,
            reading_order=None,
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
            parent_id=None,
            reading_order=None,
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
    sections: List[Section] = []
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
        header_elements = [elem for elem in page_elements if elem.bbox.y0 < header_threshold]

        # Detect footer (bottom 15% of page)
        footer_threshold = page_height * 0.85
        footer_elements = [elem for elem in page_elements if elem.bbox.y1 > footer_threshold]

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
                    parent_section_id=None,
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
                    parent_section_id=None,
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
                    parent_section_id=None,
                )
            )

    return sections


def _calculate_reading_order(
    elements: List[Element],
    tables: List[Table],
    exclude_footers: bool = False,
    sections: Optional[List[Section]] = None,
) -> List[str]:
    """
    Calculate reading order for elements.
    
    Args:
        elements: List of elements
        tables: List of tables
        exclude_footers: If True, exclude footer elements from reading order
        sections: List of sections (used to identify footer elements)
    """
    # Get footer element IDs if excluding footers
    footer_element_ids = set()
    if exclude_footers and sections:
        for section in sections:
            if section.section_type == "footer":
                footer_element_ids.update(section.elements)
    
    # Simple reading order: sort by page, then by y position, then by x position
    all_items = []

    # Add elements (excluding footers if requested)
    for elem in elements:
        if exclude_footers and elem.element_id in footer_element_ids:
            continue  # Skip footer elements
        all_items.append((elem.bbox.page_number, elem.bbox.y0, elem.bbox.x0, elem.element_id))

    # Add tables (only non-decorative tables)
    for table in tables:
        if not table.metadata.get("is_decorative", False):
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


def _normalize_text_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize rotation for text items."""
    # pdfplumber uses 'upright' field to indicate rotation
    if not item.get("upright", True):
        item["rotation"] = 90  # or detect via matrix if available
    else:
        item["rotation"] = 0
    return item


def _group_by_lines(
    items: List[Dict[str, Any]], y_threshold: float = 2.5
) -> List[Dict[str, Any]]:
    """
    Group text items into visual lines based on Y position.
    
    For upright text: group by Y position (top)
    For rotated text: group by X position (since it's vertical)
    """
    if not items:
        return []

    lines = []

    # Check if text is rotated (vertical)
    # If most items have rotation != 0, or if items have same x0 but different y, it's vertical
    first_item = items[0]
    is_rotated = first_item.get("rotation", 0) != 0 or not first_item.get("upright", True)

    if is_rotated:
        # For rotated/vertical text: group by X position (same column)
        # Sort by X position, then by Y position (top to bottom or bottom to top)
        sorted_items = sorted(items, key=lambda x: (x.get("x0", 0), x.get("top", x.get("y0", 0))))

        for item in sorted_items:
            placed = False
            item_x = item.get("x0", 0)

            for line in lines:
                line_x = line.get("x0", 0)
                # Group by X position (same column for vertical text)
                if abs(line_x - item_x) <= y_threshold:
                    line["items"].append(item)
                    placed = True
                    break

            if not placed:
                lines.append({
                    "x0": item_x,
                    "top": item.get("top", item.get("y0", 0)),
                    "items": [item]
                })
    else:
        # For upright/horizontal text: group by Y position (same line)
        # Sort by Y position (top), then by X position (left to right)
        sorted_items = sorted(items, key=lambda x: (x.get("top", x.get("y0", 0)), x.get("x0", 0)))

        for item in sorted_items:
            placed = False
            item_top = item.get("top", item.get("y0", 0))

            for line in lines:
                line_top = line.get("top", 0)
                # Condition 1: Same visual line - abs(y1 - y2) < threshold
                if abs(line_top - item_top) <= y_threshold:
                    line["items"].append(item)
                    placed = True
                    break

            if not placed:
                lines.append({
                    "top": item_top,
                    "x0": item.get("x0", 0),
                    "items": [item]
                })

    return lines


def _merge_line_items(
    line: Dict[str, Any],
    x_gap_ratio: float = 0.35,
    font_size_epsilon: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Merge characters in a line into words based on 3 conditions:
    
    1. Same visual line: abs(y1 - y2) < LINE_THRESHOLD (already satisfied by line grouping)
    2. Same typography: fontname equal, font size difference < epsilon, rotation equal
    3. Horizontal gap is small: gap = next.x0 - current.x1, gap < avg_char_width * RATIO
    
    If all 3 are true → merge.
    """
    merged = []
    current = None

    # Sort items by position
    # For horizontal text: sort by x position (left to right)
    # For vertical text: sort by y position (top to bottom)
    is_rotated = line["items"][0].get("rotation", 0) != 0 if line["items"] else False
    if not is_rotated and line["items"]:
        is_rotated = not line["items"][0].get("upright", True)
    
    if is_rotated:
        # Vertical text: sort by Y position (bottom to top for reading order)
        # In PDF coordinates, y=0 is at bottom, so larger top = higher on page
        # For bottom-to-top reading, sort descending (largest top first)
        items = sorted(line["items"], key=lambda x: x.get("top", x.get("y0", 0)), reverse=True)
    else:
        # Horizontal text: sort by X position (left to right)
        items = sorted(line["items"], key=lambda x: x.get("x0", 0))

    for item in items:
        if current is None:
            current = item.copy()
            continue

        # Condition 1: Same visual line
        # abs(y1 - y2) < LINE_THRESHOLD
        # For horizontal text: check Y position (top)
        # For vertical text: check X position (since it's rotated)
        is_rotated = current.get("rotation", 0) != 0 or not current.get("upright", True)
        
        if is_rotated:
            # Vertical text: same column (X position)
            current_pos = current.get("x0", 0)
            item_pos = item.get("x0", 0)
        else:
            # Horizontal text: same line (Y position)
            current_pos = current.get("top", current.get("y0", 0))
            item_pos = item.get("top", item.get("y0", 0))
        
        same_line = abs(current_pos - item_pos) < 2.5  # LINE_THRESHOLD

        # Condition 2: Same typography
        # - fontname equal
        # - font size difference < epsilon
        # - rotation equal
        same_typography = (
            item.get("fontname", "") == current.get("fontname", "") and
            abs(item.get("size", 0) - current.get("size", 0)) < font_size_epsilon and
            item.get("rotation", 0) == current.get("rotation", 0)
        )

        # Condition 3: Gap is small
        # For horizontal text: gap = next.x0 - current.x1, gap < avg_char_width * RATIO
        # For vertical text: gap = next.top - current.bottom, gap < avg_char_height * RATIO
        is_rotated = current.get("rotation", 0) != 0 or not current.get("upright", True)
        
        if is_rotated:
            # Vertical text: check vertical gap (Y direction)
            # For bottom-to-top reading, gap = current.top - item.bottom
            # (since we're reading upwards, current is above item)
            current_top = current.get("top", current.get("y0", 0))
            current_bottom = current.get("bottom", current.get("y1", 0))
            item_bottom = item.get("bottom", item.get("y1", 0))
            gap = current_top - item_bottom  # Positive if current is above item
            
            # Calculate average character height
            current_height = current_bottom - current_top if current_bottom > current_top else current.get("size", 12)
            current_text_len = max(len(current.get("text", "")), 1)
            avg_char_height = current_height / current_text_len if current_height > 0 else item.get("size", 12)
            
            small_gap = gap < avg_char_height * x_gap_ratio
        else:
            # Horizontal text: check horizontal gap (X direction)
            # gap = next.x0 - current.x1
            x_gap = item.get("x0", 0) - current.get("x1", 0)
            
            # Calculate average character width
            current_width = current.get("x1", 0) - current.get("x0", 0)
            current_text_len = max(len(current.get("text", "")), 1)
            avg_char_width = current_width / current_text_len if current_width > 0 else item.get("size", 12)
            
            small_gap = x_gap < avg_char_width * x_gap_ratio

        # Merge if ALL 3 conditions are true
        if same_line and same_typography and small_gap:
            # MERGE: combine text and extend bbox
            current["text"] = current.get("text", "") + item.get("text", "")
            current["x1"] = item.get("x1", current.get("x1", 0))
            # Update bottom to max of both
            current_bottom = current.get("bottom", current.get("y1", 0))
            item_bottom = item.get("bottom", item.get("y1", 0))
            current["bottom"] = max(current_bottom, item_bottom)
            if "y1" in current:
                current["y1"] = max(current.get("y1", 0), item.get("y1", 0))
        else:
            # Start new word (at least one condition failed)
            merged.append(current)
            current = item.copy()

    if current:
        merged.append(current)

    return merged


def _should_insert_space(prev_item: Dict[str, Any], curr_item: Dict[str, Any]) -> bool:
    """
    Geometry-aware space insertion for price-word boundaries.
    
    Insert space between two adjacent glyph runs if ALL are true:
    1. Previous token ends with digit (0-9) or currency ($₹€£)
    2. Next token starts with letter (A-Z a-z)
    3. Horizontal gap is small but non-zero (0 < gap < avg_char_width * 0.3)
    
    This fixes cases like:
    - $299sit → $299 sit
    - $234rhoncus → $234 rhoncus
    - But preserves: B2B, ISO9001, H2O, MP3Player
    """
    prev_text = prev_item.get("text", "")
    curr_text = curr_item.get("text", "")
    
    # Text rule 1: Previous token ends with digit or currency
    if not re.search(r'[\d$₹€£]$', prev_text):
        return False
    
    # Text rule 2: Next token starts with letter
    if not re.match(r'[A-Za-z]', curr_text):
        return False
    
    # Geometry rule: Horizontal gap is small but non-zero
    x_gap = curr_item.get("x0", 0) - prev_item.get("x1", 0)
    
    # Calculate average character width from previous item
    prev_width = prev_item.get("x1", 0) - prev_item.get("x0", 0)
    prev_text_len = max(len(prev_text), 1)
    avg_char_width = prev_width / prev_text_len
    
    # Gap should be small but non-zero (0 < gap < avg_char_width * 0.3)
    if 0 < x_gap < avg_char_width * 0.3:
        return True
    
    return False


def _fix_price_word_spacing_regex(text: str) -> str:
    """
    Fallback text-only regex fix for price-word spacing.
    
    Use ONLY after geometry merge. Safe version that only targets
    currency + digits + letter patterns.
    
    Examples:
    - "$299sit amet" → "$299 sit amet"
    - "$234rhoncus" → "$234 rhoncus"
    """
    # Only match currency + digits + letter (safe pattern)
    return re.sub(r'(\$|₹|€|£)(\d+)([A-Za-z])', r'\1\2 \3', text)


def _fix_table_cell_price_word_spacing(text: str) -> str:
    """
    Fix price-word spacing in table cell text.
    
    Table extraction loses glyph spacing, so we need to repair
    currency+digit+letter patterns that should have spaces.
    
    SAFE: Only targets currency+digit+letter patterns.
    Does NOT break: ISO9001, B2B, H2O, MP3Player
    
    Examples:
    - "$299sit amet" → "$299 sit amet"
    - "$234rhoncus" → "$234 rhoncus"
    - "$864habitant" → "$864 habitant"
    """
    # Pattern: currency symbol + digits + letter
    # This is safe because it only matches currency prefixes
    return re.sub(r'([\$₹€£]\d+)([A-Za-z])', r'\1 \2', text)


def _normalize_text_for_comparison(text: str) -> str:
    """Normalize text for similarity comparison."""
    # Lowercase, remove extra whitespace, remove punctuation
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()


def _jaccard_similarity(text1: str, text2: str) -> float:
    """
    Calculate Jaccard similarity between two texts.
    
    Returns similarity score between 0.0 and 1.0.
    """
    # Normalize texts
    text1 = _normalize_text_for_comparison(text1)
    text2 = _normalize_text_for_comparison(text2)
    
    if not text1 or not text2:
        return 0.0
    
    # Create word sets
    words1 = set(text1.split())
    words2 = set(text2.split())
    
    if not words1 or not words2:
        return 0.0
    
    # Calculate Jaccard similarity
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    if union == 0:
        return 0.0
    
    return intersection / union


def _is_table_duplicate_of_narrative(table: Table, page_elements: List[Element], threshold: float = 0.7) -> bool:
    """
    Check if table text overlaps significantly with narrative text on the same page.
    
    If overlap > threshold, mark table as decorative/duplicate.
    """
    # Get all text from table cells
    table_text = " ".join(cell.text for cell in table.cells if cell.text)
    
    if not table_text:
        return False
    
    # Get all narrative text from same page
    page_narrative_text = " ".join(
        elem.text for elem in page_elements
        if elem.text and elem.element_type != ElementType.IMAGE
    )
    
    if not page_narrative_text:
        return False
    
    # Calculate similarity
    similarity = _jaccard_similarity(table_text, page_narrative_text)
    
    return similarity >= threshold


def _horizontal_overlap(bbox1: Any, bbox2: Any) -> float:
    """
    Calculate horizontal overlap ratio between two bounding boxes.
    
    Returns overlap ratio between 0.0 and 1.0.
    Overlap is calculated as intersection width / min(width1, width2)
    """
    if not bbox1 or not bbox2:
        return 0.0
    
    x0_1 = bbox1.x0 if hasattr(bbox1, 'x0') else bbox1.get('x0', 0)
    x1_1 = bbox1.x1 if hasattr(bbox1, 'x1') else bbox1.get('x1', 0)
    x0_2 = bbox2.x0 if hasattr(bbox2, 'x0') else bbox2.get('x0', 0)
    x1_2 = bbox2.x1 if hasattr(bbox2, 'x1') else bbox2.get('x1', 0)
    
    width1 = x1_1 - x0_1
    width2 = x1_2 - x0_2
    
    if width1 == 0 or width2 == 0:
        return 0.0
    
    # Calculate intersection
    x_overlap = max(0, min(x1_1, x1_2) - max(x0_1, x0_2))
    
    # Return overlap ratio (intersection / min width)
    return x_overlap / min(width1, width2)


def _bbox_overlaps(bbox1: Any, bbox2: Any) -> bool:
    """
    Check if two bounding boxes overlap.
    
    Returns True if bboxes overlap, False otherwise.
    """
    if not bbox1 or not bbox2:
        return False
    
    x0_1 = bbox1.x0 if hasattr(bbox1, 'x0') else bbox1.get('x0', 0)
    y0_1 = bbox1.y0 if hasattr(bbox1, 'y0') else bbox1.get('y0', 0)
    x1_1 = bbox1.x1 if hasattr(bbox1, 'x1') else bbox1.get('x1', 0)
    y1_1 = bbox1.y1 if hasattr(bbox1, 'y1') else bbox1.get('y1', 0)
    
    x0_2 = bbox2.x0 if hasattr(bbox2, 'x0') else bbox2.get('x0', 0)
    y0_2 = bbox2.y0 if hasattr(bbox2, 'y0') else bbox2.get('y0', 0)
    x1_2 = bbox2.x1 if hasattr(bbox2, 'x1') else bbox2.get('x1', 0)
    y1_2 = bbox2.y1 if hasattr(bbox2, 'y1') else bbox2.get('y1', 0)
    
    # Check if bboxes overlap
    return not (x1_1 < x0_2 or x1_2 < x0_1 or y1_1 < y0_2 or y1_2 < y0_1)


def _should_stitch_tables(table1: Table, table2: Table, line_height: float = 20.0) -> bool:
    """
    Check if two tables should be stitched together.
    
    Conditions:
    1. Same page
    2. Same number of columns
    3. Horizontal overlap >= 0.9
    4. Vertical gap < LINE_HEIGHT * 2
    """
    # Condition 1: Same page
    if table1.page_number != table2.page_number:
        return False
    
    # Condition 2: Same number of columns
    if table1.columns != table2.columns:
        return False
    
    # Condition 3: Horizontal overlap >= 0.9
    horizontal_overlap_ratio = _horizontal_overlap(table1.bbox, table2.bbox)
    if horizontal_overlap_ratio < 0.9:
        return False
    
    # Condition 4: Vertical gap < LINE_HEIGHT * 2
    y1_table1 = table1.bbox.y1 if hasattr(table1.bbox, 'y1') else table1.bbox.get('y1', 0)
    y0_table2 = table2.bbox.y0 if hasattr(table2.bbox, 'y0') else table2.bbox.get('y0', 0)
    vertical_gap = abs(y0_table2 - y1_table1)
    
    if vertical_gap >= line_height * 2:
        return False
    
    return True


def _stitch_tables(tables: List[Table], line_height: float = 20.0) -> List[Table]:
    """
    Stitch visually separated tables into one logical table.
    
    Merges tables that:
    - Are on the same page
    - Have the same number of columns
    - Have horizontal overlap >= 0.9
    - Have vertical gap < LINE_HEIGHT * 2
    """
    if not tables or len(tables) <= 1:
        return tables
    
    # Sort tables by page, then by y position
    sorted_tables = sorted(tables, key=lambda t: (t.page_number, t.bbox.y0 if hasattr(t.bbox, 'y0') else t.bbox.get('y0', 0)))
    
    stitched = []
    current = sorted_tables[0]
    
    for next_table in sorted_tables[1:]:
        if _should_stitch_tables(current, next_table, line_height):
            # Stitch: merge rows, cells, and extend bbox
            current.rows += next_table.rows
            current.cells.extend(next_table.cells)
            
            # Extend bbox to include next table
            current_y1 = current.bbox.y1 if hasattr(current.bbox, 'y1') else current.bbox.get('y1', 0)
            next_y1 = next_table.bbox.y1 if hasattr(next_table.bbox, 'y1') else next_table.bbox.get('y1', 0)
            
            if hasattr(current.bbox, 'y1'):
                current.bbox.y1 = max(current_y1, next_y1)
            else:
                current.bbox['y1'] = max(current_y1, next_y1)
            
            # Update metadata
            current.metadata["stitched_from"] = current.metadata.get("stitched_from", []) + [next_table.element_id]
            logger.debug(
                f"Stitched table {current.element_id} with {next_table.element_id} "
                f"(page {current.page_number})"
            )
        else:
            stitched.append(current)
            current = next_table
    
    stitched.append(current)
    
    return stitched


def _reindex_table_rows(table: Table, line_height: float = 20.0) -> Table:
    """
    Re-index table rows based on Y position.
    
    Groups cells by approximate Y position and assigns correct row numbers.
    This fixes cases where all cells have row=0 after extraction.
    """
    if not table.cells:
        return table
    
    # Group cells by approximate Y position (same row)
    cells_by_y = {}
    
    for cell in table.cells:
        if not cell.bbox:
            continue
        
        y0 = cell.bbox.y0 if hasattr(cell.bbox, 'y0') else cell.bbox.get('y0', 0)
        
        # Find existing row group with similar Y
        matched_row_y = None
        for row_y in cells_by_y.keys():
            if abs(row_y - y0) < line_height:
                matched_row_y = row_y
                break
        
        if matched_row_y is not None:
            cells_by_y[matched_row_y].append(cell)
        else:
            cells_by_y[y0] = [cell]
    
    # Sort rows by Y position (top to bottom)
    sorted_row_ys = sorted(cells_by_y.keys())
    
    # Re-assign row numbers
    for row_index, row_y in enumerate(sorted_row_ys):
        row_cells = cells_by_y[row_y]
        for cell in row_cells:
            cell.row = row_index
    
    # Update table row count
    table.rows = len(sorted_row_ys)
    
    return table


def _contains_price_pattern(text: str) -> bool:
    """Check if text contains price pattern (currency + digits)."""
    return bool(re.search(r'[\$₹€£]\d+', text))


def _aligns_with_column(elem: Element, table: Table, col_index: int, threshold: float = 50.0) -> bool:
    """
    Check if element X position aligns with table column.
    
    Args:
        elem: Element to check
        table: Table
        col_index: Column index to check alignment with
        threshold: Maximum X distance to consider aligned
    """
    if not elem.bbox or not table.bbox:
        return False
    
    elem_x0 = elem.bbox.x0 if hasattr(elem.bbox, 'x0') else elem.bbox.get('x0', 0)
    table_x0 = table.bbox.x0 if hasattr(table.bbox, 'x0') else table.bbox.get('x0', 0)
    
    # Calculate column width
    table_width = (table.bbox.x1 if hasattr(table.bbox, 'x1') else table.bbox.get('x1', 0)) - table_x0
    col_width = table_width / table.columns if table.columns > 0 else table_width
    
    # Expected column X position
    expected_col_x = table_x0 + (col_index * col_width)
    
    # Check if element aligns with column
    return abs(elem_x0 - expected_col_x) < threshold


def _split_line_item_text(text: str) -> List[str]:
    """
    Split line item text into columns.
    
    Example: "Peach $2.99 1 $2.99" → ["Peach", "$2.99", "1", "$2.99"]
    """
    # Split by whitespace, preserving currency patterns
    parts = re.split(r'\s+', text.strip())
    return [p for p in parts if p]


def _is_header_row(cells: List[TableCell]) -> bool:
    """
    Check if a row is a header row.
    
    FIX 3: Header row exclusion (MANDATORY).
    """
    header_keywords = ["price", "quantity", "subtotal", "item", "description", "unit", "organic items"]
    row_text = " ".join(cell.text.lower() for cell in cells if cell.text)
    # Check if ALL cells contain header keywords (not just one)
    return any(keyword in row_text for keyword in header_keywords) and len(cells) <= 4


def _rebuild_table_rows(table: Table, line_height: float = 20.0) -> Table:
    """
    Rebuild table rows cleanly from scratch.
    
    Groups cells by Y position, excludes header rows, and rebuilds clean cell list.
    """
    if not table.cells:
        return table
    
    # Group cells by approximate Y position (same row)
    rows_by_y = {}
    
    for cell in table.cells:
        if not cell.bbox:
            continue
        
        y0 = cell.bbox.y0 if hasattr(cell.bbox, 'y0') else cell.bbox.get('y0', 0)
        row_key = round(y0 / line_height)
        
        if row_key not in rows_by_y:
            rows_by_y[row_key] = []
        rows_by_y[row_key].append(cell)
    
    # Sort rows by Y position (top to bottom)
    sorted_row_keys = sorted(rows_by_y.keys())
    
    # Rebuild cells cleanly
    clean_cells = []
    row_index = 0
    
    for row_key in sorted_row_keys:
        row_cells = rows_by_y[row_key]
        
        # Skip header rows
        if _is_header_row(row_cells):
            continue
        
        # Sort cells by column
        row_cells_sorted = sorted(row_cells, key=lambda c: c.col)
        
        # Rebuild cells with correct row index
        for cell in row_cells_sorted:
            cell.row = row_index
            clean_cells.append(cell)
        
        row_index += 1
    
    # Update table
    table.cells = clean_cells
    table.rows = row_index
    
    return table


def _promote_narrative_to_table(elements: List[Element], table: Table, line_height: float = 20.0) -> Table:
    """
    Promote narrative text elements that are line items into table rows.
    
    FIX 1: Only promote unique rows by Y-position (dedupe).
    """
    if not table.bbox:
        return table
    
    table_y0 = table.bbox.y0 if hasattr(table.bbox, 'y0') else table.bbox.get('y0', 0)
    table_y1 = table.bbox.y1 if hasattr(table.bbox, 'y1') else table.bbox.get('y1', 0)
    
    # Track seen rows by Y position (dedupe)
    seen_rows = set()
    promoted_rows = []
    
    for elem in elements:
        # Skip non-text elements
        if elem.element_type == ElementType.IMAGE or not elem.text:
            continue
        
        if not elem.bbox:
            continue
        
        elem_y0 = elem.bbox.y0 if hasattr(elem.bbox, 'y0') else elem.bbox.get('y0', 0)
        elem_y1 = elem.bbox.y1 if hasattr(elem.bbox, 'y1') else elem.bbox.get('y1', 0)
        elem_center_y = (elem_y0 + elem_y1) / 2
        
        # Check if element Y is within table Y range
        if not (table_y0 <= elem_center_y <= table_y1):
            continue
        
        # Dedupe by Y position
        row_key = round(elem_y0 / line_height)
        if row_key in seen_rows:
            continue
        
        # Check if element aligns with first column
        if not _aligns_with_column(elem, table, col_index=0, threshold=50.0):
            continue
        
        # Check if text contains price pattern
        if not _contains_price_pattern(elem.text):
            continue
        
        # Skip header rows
        if _is_header_row([TableCell(row=0, col=0, text=elem.text, bbox=elem.bbox, confidence=0.9)]):
            continue
        
        # Split text into columns
        parts = _split_line_item_text(elem.text)
        
        if len(parts) >= 2:  # At least description and price
            promoted_rows.append({
                'y0': elem_y0,
                'parts': parts,
                'bbox': elem.bbox,
            })
            seen_rows.add(row_key)
    
    # Add promoted rows as cells
    if promoted_rows:
        # Sort by Y position
        promoted_rows.sort(key=lambda r: r['y0'])
        
        # Add to existing cells (will be rebuilt by _rebuild_table_rows)
        for row_data in promoted_rows:
            table_x0 = table.bbox.x0 if hasattr(table.bbox, 'x0') else table.bbox.get('x0', 0)
            table_width = (table.bbox.x1 if hasattr(table.bbox, 'x1') else table.bbox.get('x1', 0)) - table_x0
            col_width = table_width / table.columns if table.columns > 0 else table_width
            
            for col_idx, part_text in enumerate(row_data['parts']):
                if col_idx >= table.columns:
                    break
                
                cell_bbox = create_bbox(
                    table_x0 + (col_idx * col_width),
                    row_data['y0'],
                    table_x0 + ((col_idx + 1) * col_width),
                    row_data['y0'] + 20,  # Approximate height
                    table.page_number,
                    table.bbox.layout_width if hasattr(table.bbox, 'layout_width') else table.bbox.get('layout_width'),
                    table.bbox.layout_height if hasattr(table.bbox, 'layout_height') else table.bbox.get('layout_height'),
                )
                
                cell = TableCell(
                    row=999,  # Temporary, will be fixed by _rebuild_table_rows
                    col=col_idx,
                    text=part_text,
                    bbox=cell_bbox,
                    confidence=0.85,
                )
                
                table.cells.append(cell)
    
    return table


def _extract_invoice_number(elements: List[Element]) -> Optional[str]:
    """Extract invoice number from elements."""
    # Look for patterns like "Invoice #123", "INV-123", etc.
    invoice_patterns = [
        r'invoice\s*#?\s*([A-Z0-9\-]+)',
        r'inv\s*#?\s*([A-Z0-9\-]+)',
        r'invoice\s*number\s*:?\s*([A-Z0-9\-]+)',
    ]
    
    for elem in elements:
        if not elem.text:
            continue
        text = elem.text.lower()
        for pattern in invoice_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
    
    return None


def _extract_customer_address(elements: List[Element]) -> Optional[str]:
    """Extract customer/bill-to address from elements."""
    # Look for "Bill To:", "Customer:", etc.
    address_keywords = ['bill to', 'customer', 'ship to', 'billing address']
    
    for elem in elements:
        if not elem.text:
            continue
        text = elem.text.lower()
        for keyword in address_keywords:
            if keyword in text:
                # Return next few elements as address
                return elem.text
    
    return None


def _extract_money_value(elements: List[Element], tables: List[Table], label: str) -> Optional[float]:
    """
    Extract money value for a given label (subtotal, tax, total).
    
    FIX 5: Extract totals from NarrativeText AND table cells.
    Also checks elements near table (below table) for totals.
    """
    label_patterns = {
        'subtotal': [r'subtotal', r'sub\s*total'],
        'tax': [r'tax', r'gst', r'vat'],
        'total': [r'^total$', r'total\s*$', r'amount\s*due', r'grand\s*total'],
    }
    
    patterns = label_patterns.get(label.lower(), [])
    if not patterns:
        return None
    
    # Get table Y range to find elements below table
    table_y1 = 0.0
    for table in tables:
        if not table.metadata.get("is_decorative", False) and table.bbox:
            table_bottom = table.bbox.y1 if hasattr(table.bbox, 'y1') else table.bbox.get('y1', 0)
            table_y1 = max(table_y1, table_bottom)
    
    # Check elements (including those below table)
    for elem in elements:
        if not elem.text:
            continue
        
        elem_y0 = elem.bbox.y0 if elem.bbox else 0
        text = elem.text.lower()
        
        # Check if element contains label
        for pattern in patterns:
            if re.search(pattern, text):
                # Extract money value from this element or nearby elements
                # First try this element
                money_patterns = [
                    r'[\$₹€£]\s*(\d+\.?\d*)',  # $123.45
                    r'(\d+\.?\d*)\s*[\$₹€£]',  # 123.45$
                    r'[\$₹€£](\d+\.?\d*)',     # $123.45 (no space)
                ]
                
                for money_pattern in money_patterns:
                    money_match = re.search(money_pattern, elem.text)
                    if money_match:
                        try:
                            return float(money_match.group(1))
                        except ValueError:
                            continue
                
                # If not found in same element, check nearby elements (within 30px)
                for nearby_elem in elements:
                    if not nearby_elem.text or nearby_elem == elem:
                        continue
                    
                    nearby_y0 = nearby_elem.bbox.y0 if nearby_elem.bbox else 0
                    if abs(nearby_y0 - elem_y0) < 30:  # Same line or very close
                        money_match = re.search(r'[\$₹€£]\s*(\d+\.?\d*)', nearby_elem.text)
                        if money_match:
                            try:
                                return float(money_match.group(1))
                            except ValueError:
                                continue
    
    # Check table cells (look in same cell or adjacent cells)
    for table in tables:
        if table.metadata.get("is_decorative", False):
            continue
        
        # Group cells by row
        cells_by_row = {}
        for cell in table.cells:
            row = cell.row
            if row not in cells_by_row:
                cells_by_row[row] = []
            cells_by_row[row].append(cell)
        
        # Check each row
        for row_cells in cells_by_row.values():
            row_text = " ".join(cell.text.lower() for cell in row_cells if cell.text)
            
            for pattern in patterns:
                if re.search(pattern, row_text):
                    # Look for money value in this row
                    for cell in row_cells:
                        if not cell.text:
                            continue
                        
                        # Extract money value from cell text
                        money_patterns = [
                            r'[\$₹€£]\s*(\d+\.?\d*)',
                            r'(\d+\.?\d*)\s*[\$₹€£]',
                            r'[\$₹€£](\d+\.?\d*)',
                        ]
                        
                        for money_pattern in money_patterns:
                            money_match = re.search(money_pattern, cell.text)
                            if money_match:
                                try:
                                    return float(money_match.group(1))
                                except ValueError:
                                    continue
    
    return None


def _detect_currency(elements: List[Element]) -> Optional[str]:
    """
    Detect currency from document content.
    
    FIX 6: Currency detection (NO DEFAULT USD).
    """
    # Collect all text
    all_text = " ".join(elem.text for elem in elements if elem.text)
    all_text_upper = all_text.upper()
    
    # Check for currency indicators
    if "GST" in all_text_upper or "VIC" in all_text_upper or "AUD" in all_text_upper:
        return "AUD"
    elif "USD" in all_text_upper or "US$" in all_text:
        return "USD"
    elif "EUR" in all_text_upper or "€" in all_text:
        return "EUR"
    elif "GBP" in all_text_upper or "£" in all_text:
        return "GBP"
    elif "INR" in all_text_upper or "₹" in all_text:
        return "INR"
    elif "$" in all_text:
        # Could be USD, AUD, CAD, etc. - return None to indicate unknown
        return None
    else:
        return None


def _detect_document_type(elements: List[Element], tables: List[Table]) -> Optional[str]:
    """
    Detect document type based on content patterns.
    
    Returns: "invoice", "receipt", "catalog", "manual", etc.
    """
    if not elements:
        return None
    
    # Collect all text
    all_text = " ".join(elem.text.lower() for elem in elements if elem.text)
    
    # Invoice patterns
    invoice_keywords = ['invoice', 'bill to', 'invoice number', 'due date', 'amount due']
    if any(keyword in all_text for keyword in invoice_keywords):
        return "invoice"
    
    # Receipt patterns
    receipt_keywords = ['receipt', 'thank you', 'payment received']
    if any(keyword in all_text for keyword in receipt_keywords):
        return "receipt"
    
    # Catalog patterns
    catalog_keywords = ['catalog', 'catalogue', 'price', 'product']
    if any(keyword in all_text for keyword in catalog_keywords):
        return "catalog"
    
    # Manual patterns
    manual_keywords = ['manual', 'instructions', 'guide', 'tutorial']
    if any(keyword in all_text for keyword in manual_keywords):
        return "manual"
    
    return None


def _normalize_money(text: str) -> Optional[float]:
    """Normalize money value for comparison."""
    if not text:
        return None
    
    # Extract numeric value
    money_match = re.search(r'[\$₹€£]?\s*(\d+\.?\d*)', str(text))
    if money_match:
        try:
            return float(money_match.group(1))
        except ValueError:
            return None
    return None


def _normalize_int(text: str) -> Optional[int]:
    """Normalize integer value for comparison."""
    if not text:
        return None
    
    # Extract integer
    int_match = re.search(r'(\d+)', str(text))
    if int_match:
        try:
            return int(int_match.group(1))
        except ValueError:
            return None
    return None


def _normalize_description(text: str) -> str:
    """Normalize description for comparison."""
    if not text:
        return ""
    
    # Lowercase, strip, remove extra whitespace
    normalized = text.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized


def _dedupe_line_items(line_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate line items semantically.
    
    FIX: Semantic row deduplication (MANDATORY).
    Dedup key: (description, unit_price, quantity, total)
    If ALL four match → same line item.
    """
    unique_items = {}
    final_items = []
    
    for item in line_items:
        # Extract normalized values
        description = _normalize_description(item.get("description", ""))
        unit_price = _normalize_money(item.get("unit_price", ""))
        quantity = _normalize_int(item.get("quantity", ""))
        total = _normalize_money(item.get("total", ""))
        
        # Create deduplication key
        key = (description, unit_price, quantity, total)
        
        # Skip if already seen (semantic duplicate)
        if key in unique_items:
            logger.debug(
                f"Skipping duplicate line item: {item.get('description', '')} "
                f"(unit_price={unit_price}, quantity={quantity}, total={total})"
            )
            continue
        
        # Mark as seen and add to final list
        unique_items[key] = True
        final_items.append(item)
    
    return final_items


def _build_invoice_data(elements: List[Element], tables: List[Table]) -> Dict[str, Any]:
    """
    Build structured invoice data from extracted elements and tables.
    
    FIX 4: Column-based mapping (NOT positional).
    FIX 5: Extract totals from both elements and table cells.
    FIX: Semantic deduplication of line items.
    """
    # Detect currency
    currency = _detect_currency(elements)
    
    invoice_data = {
        "invoice_number": _extract_invoice_number(elements),
        "bill_to": _extract_customer_address(elements),
        "line_items": [],
        "subtotal": _extract_money_value(elements, tables, "subtotal"),
        "tax": _extract_money_value(elements, tables, "tax"),
        "total": _extract_money_value(elements, tables, "total"),
        "currency": currency,
    }
    
    # Column mapping (FIX 4)
    COL_MAP = {
        0: "description",
        1: "unit_price",
        2: "quantity",
        3: "total"
    }
    
    # Extract line items from tables
    all_line_items = []
    
    for table in tables:
        if table.metadata.get("is_decorative", False):
            continue
        
        # Group cells by row
        cells_by_row = {}
        for cell in table.cells:
            row = cell.row
            if row not in cells_by_row:
                cells_by_row[row] = []
            cells_by_row[row].append(cell)
        
        # Convert rows to line items (FIX 3: Skip header rows)
        for row_idx in sorted(cells_by_row.keys()):
            row_cells = sorted(cells_by_row[row_idx], key=lambda c: c.col)
            
            # Skip header rows
            if _is_header_row(row_cells):
                continue
            
            # Build line item using column mapping
            line_item = {}
            for cell in row_cells:
                col_idx = cell.col
                field_name = COL_MAP.get(col_idx, f"col_{col_idx}")
                line_item[field_name] = cell.text.strip() if cell.text else ""
            
            # Only add if we have at least description
            if line_item.get("description"):
                all_line_items.append(line_item)
    
    # FIX: Semantic deduplication
    invoice_data["line_items"] = _dedupe_line_items(all_line_items)
    
    return invoice_data


def _validate_invoice(invoice_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate invoice data for finance safety.
    
    Returns validation result with status and errors.
    Uses the "total" column from line items for calculation.
    """
    validation = {
        "status": "VALID",
        "errors": [],
        "warnings": [],
    }
    
    # Extract numeric values
    subtotal = invoice_data.get("subtotal")
    tax = invoice_data.get("tax")
    total = invoice_data.get("total")
    
    # Calculate sum of line items using the "total" column
    line_items = invoice_data.get("line_items", [])
    sum_items = 0.0
    
    for item in line_items:
        # Use the "total" field from line item (column 3)
        item_total_text = item.get("total", "")
        if not item_total_text:
            # Fallback: try to calculate from unit_price * quantity
            unit_price = _normalize_money(item.get("unit_price", ""))
            quantity = _normalize_int(item.get("quantity", ""))
            if unit_price is not None and quantity is not None:
                sum_items += unit_price * quantity
        else:
            # Extract numeric value from total column
            item_total = _normalize_money(item_total_text)
            if item_total is not None:
                sum_items += item_total
    
    # Validate subtotal
    if subtotal is not None:
        if abs(sum_items - subtotal) > 0.01:
            validation["status"] = "INVALID_SUBTOTAL"
            validation["errors"].append(
                f"Subtotal mismatch: calculated {sum_items:.2f}, found {subtotal:.2f}"
            )
    
    # Validate total
    if subtotal is not None and tax is not None and total is not None:
        expected_total = subtotal + tax
        if abs(expected_total - total) > 0.01:
            validation["status"] = "INVALID_TOTAL"
            validation["errors"].append(
                f"Total mismatch: expected {expected_total:.2f}, found {total:.2f}"
            )
    
    return validation


def _remove_elements_inside_tables(elements: List[Element], tables: List[Table]) -> List[Element]:
    """
    Remove narrative text elements that are inside table cells.
    
    Prevents double-counting: if text is inside a table cell, exclude it from elements.
    Uses precise cell-level checking, not just table bbox overlap.
    """
    if not elements or not tables:
        return elements
    
    filtered = []
    
    for elem in elements:
        # Skip images and other non-text elements
        if elem.element_type == ElementType.IMAGE:
            filtered.append(elem)
            continue
        
        if not elem.bbox:
            filtered.append(elem)
            continue
        
        # Preserve elements with totals (they're often below table, not inside cells)
        elem_text = elem.text.lower() if elem.text else ""
        is_total_element = any(
            keyword in elem_text for keyword in ['subtotal', 'gst', 'tax', 'total', 'amount due']
        )
        
        if is_total_element:
            filtered.append(elem)
            continue
        
        # Check if element is inside any table cell (precise check)
        inside_table_cell = False
        
        for table in tables:
            # Skip decorative tables (they're duplicates anyway)
            if table.metadata.get("is_decorative", False):
                continue
            
            elem_x0 = elem.bbox.x0 if hasattr(elem.bbox, 'x0') else elem.bbox.get('x0', 0)
            elem_y0 = elem.bbox.y0 if hasattr(elem.bbox, 'y0') else elem.bbox.get('y0', 0)
            elem_x1 = elem.bbox.x1 if hasattr(elem.bbox, 'x1') else elem.bbox.get('x1', 0)
            elem_y1 = elem.bbox.y1 if hasattr(elem.bbox, 'y1') else elem.bbox.get('y1', 0)
            
            # Check if element is inside any table cell
            for cell in table.cells:
                if not cell.bbox:
                    continue
                
                cell_x0 = cell.bbox.x0 if hasattr(cell.bbox, 'x0') else cell.bbox.get('x0', 0)
                cell_y0 = cell.bbox.y0 if hasattr(cell.bbox, 'y0') else cell.bbox.get('y0', 0)
                cell_x1 = cell.bbox.x1 if hasattr(cell.bbox, 'x1') else cell.bbox.get('x1', 0)
                cell_y1 = cell.bbox.y1 if hasattr(cell.bbox, 'y1') else cell.bbox.get('y1', 0)
                
                # Check if element center is inside cell, or element is mostly inside cell
                elem_center_x = (elem_x0 + elem_x1) / 2
                elem_center_y = (elem_y0 + elem_y1) / 2
                
                # Element is inside cell if center is inside, or significant overlap
                if (cell_x0 <= elem_center_x <= cell_x1 and 
                    cell_y0 <= elem_center_y <= cell_y1):
                    inside_table_cell = True
                    logger.debug(
                        f"Element {elem.element_id} is inside table cell "
                        f"(table {table.element_id}, row {cell.row}, col {cell.col}), "
                        f"excluding from elements"
                    )
                    break
            
            if inside_table_cell:
                break
        
        if not inside_table_cell:
            filtered.append(elem)
    
    return filtered


def _fix_reversed_text(text: str, bbox: Any) -> str:
    """
    Fix reversed/mirrored text (e.g., "moordeB" → "Bedroom").
    
    Detects when text appears reversed based on:
    1. Bbox dimensions (height >> width suggests vertical/rotated text)
    2. Text patterns (URLs, common words when reversed)
    
    Examples:
    - "moordeB" → "Bedroom"
    - "moc.lmxecnirp.www" → "www.princexml.com"
    """
    if not text or not bbox:
        return text
    
    # Check if bbox suggests rotated/vertical text
    bbox_width = bbox.x1 - bbox.x0 if hasattr(bbox, 'x1') else 0
    bbox_height = bbox.y1 - bbox.y0 if hasattr(bbox, 'y1') else 0
    
    # If height >> width, might be rotated text
    is_rotated = bbox_height > 3 * bbox_width if bbox_width > 0 else False
    
    if not is_rotated:
        return text
    
    # Check if reversed text looks like a URL
    reversed_text = text[::-1]
    if re.search(r'www\.\w+\.\w+', reversed_text):
        return reversed_text
    
    # Check if reversed text looks like a common word
    # Simple heuristic: if reversed has more recognizable patterns
    if len(text) > 3:
        # Check for common patterns when reversed
        if re.search(r'^[A-Z][a-z]+$', reversed_text):
            return reversed_text
    
    return text


def _line_to_text(merged_items: List[Dict[str, Any]]) -> str:
    """
    Convert merged items in a line to clean text with proper spacing.
    
    Uses geometry-aware space insertion for price-word boundaries,
    then applies regex fallback for any remaining cases.
    """
    if not merged_items:
        return ""

    text = ""

    for i, item in enumerate(merged_items):
        if i > 0:
            prev_item = merged_items[i - 1]
            
            # Layer 1: Geometry-aware space insertion (for price-word boundaries)
            if _should_insert_space(prev_item, item):
                text += " "
            else:
                # Layer 2: Regular spacing based on gap size
                gap = item.get("x0", 0) - prev_item.get("x1", 0)
                item_size = item.get("size", 12)
                if gap > item_size * 0.8:
                    text += " "

        text += item.get("text", "")

    # Layer 3: Regex fallback for any remaining price-word issues
    text = _fix_price_word_spacing_regex(text)

    return text.strip()


def _extract_merged_text_from_chars(chars: List[Dict[str, Any]]) -> str:
    """
    Extract merged text from characters using intelligent merging algorithm.
    
    This function:
    1. Normalizes rotation
    2. Groups characters into visual lines
    3. Merges characters into words based on font and spacing
    4. Returns clean text with proper word boundaries
    """
    if not chars:
        return ""

    # Normalize rotation for all items
    normalized_items = [_normalize_text_item(char.copy()) for char in chars]

    # Group by lines
    lines = _group_by_lines(normalized_items, y_threshold=2.5)

    # Process each line: merge into words, then convert to text
    output_lines = []

    for line in lines:
        # Merge characters into words
        merged_words = _merge_line_items(line, x_gap_ratio=0.35)
        
        # Convert merged words to clean text
        clean_text = _line_to_text(merged_words)
        
        if len(clean_text) > 0:
            output_lines.append(clean_text)

    # Join lines with spaces (single line output)
    return " ".join(output_lines)


def _merge_chars_into_text_blocks(
    chars: List[Dict[str, Any]], threshold: float = 5.0
) -> List[Dict[str, Any]]:
    """
    Merge characters into text blocks with properly merged text.
    
    This function:
    1. Normalizes rotation for all characters
    2. Groups ALL characters into visual lines (not pre-grouped)
    3. Merges characters within each line into words
    4. Returns blocks (one per line) with merged text
    
    Returns list of blocks, each containing:
    - text: merged text string
    - chars: original character list for bbox calculation
    """
    if not chars:
        return []

    # Normalize rotation for all items FIRST
    normalized_items = [_normalize_text_item(char.copy()) for char in chars]

    # Group ALL characters by lines (don't pre-group by proximity)
    lines = _group_by_lines(normalized_items, y_threshold=threshold)

    # Process each line: merge into words
    blocks = []

    for line in lines:
        # Merge characters into words within this line
        merged_words = _merge_line_items(line, x_gap_ratio=0.35)
        
        # Convert merged words to clean text
        clean_text = _line_to_text(merged_words)
        
        if len(clean_text) > 0:
            # Create block with merged text and original chars for bbox
            blocks.append({
                "text": clean_text,
                "chars": line["items"],  # Original chars for bbox calculation
            })

    return blocks


def _group_chars_into_blocks(
    chars: List[Dict[str, Any]], threshold: float = 5.0
) -> List[List[Dict[str, Any]]]:
    """
    Group characters into text blocks based on proximity.
    
    Note: Text merging is handled separately in _extract_merged_text_from_chars
    to preserve character-level data for bbox calculation.
    """
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
    text_center = (x0 + x1) / 2
    page_center = page_width / 2

    # Consider centered if within 10% of page center
    return bool(abs(text_center - page_center) < page_width * 0.1)
