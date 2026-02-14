"""Output formatters for extraction results."""

from typing import Union, Dict, Any, Optional
from .schemas import ExtractionResult, Table, ElementType


def format_result(
    result: ExtractionResult,
    output_format: str = "pydantic",
    markdown_clean: Optional[bool] = None,
    include_metadata: bool = True,
) -> Union[ExtractionResult, Dict[str, Any], str]:
    """
    Format extraction result based on output format.

    Args:
        result: ExtractionResult to format
        output_format: "pydantic", "json", or "markdown"
        markdown_clean: If True and output_format="markdown", output only content without metadata.
                       If None (default), automatically uses clean mode when include_metadata=False
        include_metadata: Whether metadata was included in extraction (affects markdown formatting)

    Returns:
        Formatted result based on output_format
    """
    if output_format == "pydantic":
        return result
    elif output_format == "json":
        return format_as_json(result)
    elif output_format == "markdown":
        # Auto-detect clean mode: if include_metadata=False, use clean mode unless explicitly set
        if markdown_clean is None:
            markdown_clean = not include_metadata
        return format_as_markdown(result, clean=markdown_clean)
    else:
        raise ValueError(
            f"Unknown output format: {output_format}. Use 'pydantic', 'json', or 'markdown'"
        )


def format_as_json(result: ExtractionResult) -> Dict[str, Any]:
    """Format result as JSON-serializable dictionary."""
    return result.model_dump(mode="json")


def format_as_markdown(result: ExtractionResult, clean: bool = False) -> str:
    """
    Format result as LLM-ready markdown.

    Args:
        result: ExtractionResult to format
        clean: If True, output only content without metadata (file paths, confidence scores, etc.)
               If False, include all metadata (default: False for backward compatibility)

    Returns:
        Markdown string
    """
    lines = []

    # If clean mode, skip all metadata and just output content
    if clean:
        return _format_as_clean_markdown(result)

    # Document header
    lines.append(f"# Document: {result.file_path}")
    lines.append("")
    lines.append(f"**File Type:** {result.file_type}")
    lines.append(f"**Extraction Method:** {result.extraction_method}")
    if result.document_type:
        lines.append(f"**Document Type:** {result.document_type}")
    lines.append(f"**Overall Confidence:** {result.overall_confidence:.2%}")
    lines.append("")

    # Metadata
    if result.metadata:
        lines.append("## Metadata")
        for key, value in result.metadata.items():
            lines.append(f"- **{key}:** {value}")
        lines.append("")

    # Sections
    if result.sections:
        lines.append("## Sections")
        for section in result.sections:
            lines.append(f"### {section.section_type.title()} (Page {section.page_number})")
            lines.append(f"**Confidence:** {section.confidence:.2%}")
            if section.metadata:
                for key, value in section.metadata.items():
                    lines.append(f"- **{key}:** {value}")
            lines.append("")

    # Tables
    if result.tables:
        lines.append("## Tables")
        for table in result.tables:
            lines.append(f"### Table {table.element_id} (Page {table.page_number})")
            lines.append(f"**Confidence:** {table.confidence:.2%}")
            lines.append(f"**Dimensions:** {table.rows} rows × {table.columns} columns")
            lines.append("")

            # Format table as markdown
            table_md = _format_table_as_markdown(table)
            lines.append(table_md)
            lines.append("")

    # Forms
    if result.forms:
        lines.append("## Form Fields")
        for form in result.forms:
            lines.append(f"### {form.field_name or form.element_id}")
            lines.append(f"**Type:** {form.field_type}")
            if form.value:
                lines.append(f"**Value:** {form.value}")
            lines.append(f"**Confidence:** {form.confidence:.2%}")
            lines.append("")

    # Images
    if result.images:
        lines.append("## Images")
        for img in result.images:
            lines.append(f"### Image {img.element_id}")
            lines.append(f"**Page:** {img.bbox.page_number}")
            lines.append(f"**Confidence:** {img.confidence:.2%}")
            if img.metadata:
                width = img.metadata.get("width", "unknown")
                height = img.metadata.get("height", "unknown")
                lines.append(f"**Dimensions:** {width} × {height}")
            lines.append("")

    # Elements (text content)
    if result.elements:
        lines.append("## Content")
        lines.append("")

        # Group by page
        elements_by_page: Dict[int, list] = {}
        for elem in result.elements:
            page_num = elem.bbox.page_number
            if page_num not in elements_by_page:
                elements_by_page[page_num] = []
            elements_by_page[page_num].append(elem)

        # Sort pages
        for page_num in sorted(elements_by_page.keys()):
            page_elements = elements_by_page[page_num]

            # Sort by reading order if available
            if result.reading_order:
                page_elements.sort(
                    key=lambda e: (
                        result.reading_order.index(e.element_id)
                        if e.element_id in result.reading_order
                        else 9999
                    )
                )

            lines.append(f"### Page {page_num}")
            lines.append("")

            for elem in page_elements:
                if elem.element_type == ElementType.TITLE:
                    lines.append(f"# {elem.text}")
                    lines.append("")
                elif elem.element_type == ElementType.HEADING:
                    lines.append(f"## {elem.text}")
                    lines.append("")
                elif elem.element_type == ElementType.NARRATIVE_TEXT:
                    if elem.text:
                        lines.append(elem.text)
                        lines.append("")
                elif elem.element_type == ElementType.LIST_ITEM:
                    if elem.text:
                        lines.append(f"- {elem.text}")
                elif elem.text:
                    lines.append(elem.text)
                    lines.append("")

    # Errors
    if result.errors:
        lines.append("## Errors")
        for error in result.errors:
            lines.append(f"- {error}")
        lines.append("")

    return "\n".join(lines)


def _format_as_clean_markdown(result: ExtractionResult) -> str:
    """
    Format result as clean markdown with only content (no metadata).
    Perfect for LLM consumption - just the text content.
    """
    lines = []

    # Tables - just the table content
    if result.tables:
        for table in result.tables:
            table_md = _format_table_as_markdown(table)
            lines.append(table_md)
            lines.append("")

    # Forms - just field names and values
    if result.forms:
        for form in result.forms:
            if form.field_name and form.value:
                lines.append(f"**{form.field_name}:** {form.value}")
            elif form.value:
                lines.append(form.value)
            lines.append("")

    # Elements (text content) - main content
    if result.elements:
        # Group by page
        elements_by_page: Dict[int, list] = {}
        for elem in result.elements:
            page_num = elem.bbox.page_number
            if page_num not in elements_by_page:
                elements_by_page[page_num] = []
            elements_by_page[page_num].append(elem)

        # Sort pages
        for page_num in sorted(elements_by_page.keys()):
            page_elements = elements_by_page[page_num]

            # Sort by reading order if available
            if result.reading_order:
                page_elements.sort(
                    key=lambda e: (
                        result.reading_order.index(e.element_id)
                        if e.element_id in result.reading_order
                        else 9999
                    )
                )

            for elem in page_elements:
                if elem.element_type == ElementType.TITLE:
                    lines.append(f"# {elem.text}")
                    lines.append("")
                elif elem.element_type == ElementType.HEADING:
                    lines.append(f"## {elem.text}")
                    lines.append("")
                elif elem.element_type == ElementType.NARRATIVE_TEXT:
                    if elem.text:
                        lines.append(elem.text)
                        lines.append("")
                elif elem.element_type == ElementType.LIST_ITEM:
                    if elem.text:
                        lines.append(f"- {elem.text}")
                elif elem.text:
                    lines.append(elem.text)
                    lines.append("")

    return "\n".join(lines).strip()


def _format_table_as_markdown(table: Table) -> str:
    """Format a table as markdown table."""
    if not table.cells:
        return "*(Empty table)*"

    # Build table structure
    num_rows = table.rows
    num_cols = table.columns

    # Create 2D grid
    grid = [["" for _ in range(num_cols)] for _ in range(num_rows)]

    for cell in table.cells:
        if cell.row < num_rows and cell.col < num_cols:
            grid[cell.row][cell.col] = cell.text or ""

    # Format as markdown table
    lines = []

    # Header row
    if grid:
        header = "| " + " | ".join(grid[0]) + " |"
        lines.append(header)
        separator = "| " + " | ".join(["---"] * num_cols) + " |"
        lines.append(separator)

        # Data rows
        for row in grid[1:]:
            row_text = "| " + " | ".join(row) + " |"
            lines.append(row_text)

    return "\n".join(lines)
