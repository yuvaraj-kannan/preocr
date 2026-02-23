"""Output formatters for extraction results."""

import re
from typing import Union, Dict, Any, Optional
from .schemas import ExtractionResult, Table, ElementType


def format_result(
    result: ExtractionResult,
    output_format: str = "pydantic",
    markdown_clean: Optional[bool] = None,
    include_metadata: bool = True,
    markdown_structured: bool = False,
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
        return format_as_markdown(result, clean=markdown_clean, structured=markdown_structured)
    else:
        raise ValueError(
            f"Unknown output format: {output_format}. Use 'pydantic', 'json', or 'markdown'"
        )


def format_as_json(result: ExtractionResult) -> Dict[str, Any]:
    """Format result as JSON-serializable dictionary."""
    return result.model_dump(mode="json")


def format_as_markdown(result: ExtractionResult, clean: bool = False, structured: bool = False) -> str:
    """
    Format result as LLM-ready markdown.

    Args:
        result: ExtractionResult to format
        clean: If True, output only content without metadata (file paths, confidence scores, etc.)
               If False, include all metadata (default: False for backward compatibility)
        structured: If True and clean=True, use markdown structure (bold labels, headers)

    Returns:
        Markdown string
    """
    lines = []

    # If clean mode, skip all metadata and just output content
    if clean:
        return _format_as_clean_markdown(result, structured=structured)

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


def _format_as_clean_markdown(result: ExtractionResult, structured: bool = False) -> str:
    """
    Format result as clean markdown with only content (no metadata).
    Perfect for LLM consumption - just the text content.

    Args:
        result: ExtractionResult to format
        structured: If True, use markdown structure (bold labels, headers, tables)
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

            elem_texts = []
            for elem in page_elements:
                if elem.element_type == ElementType.TITLE:
                    elem_texts.append(("title", f"# {elem.text}"))
                elif elem.element_type == ElementType.HEADING:
                    elem_texts.append(("heading", f"## {elem.text}"))
                elif elem.element_type == ElementType.NARRATIVE_TEXT:
                    if elem.text:
                        elem_texts.append(("narrative", elem.text))
                elif elem.element_type == ElementType.LIST_ITEM:
                    if elem.text:
                        elem_texts.append(("list", f"- {elem.text}"))
                elif elem.text:
                    elem_texts.append(("other", elem.text))

            if structured:
                lines.extend(_structure_markdown_lines(elem_texts))
            else:
                for _, text in elem_texts:
                    lines.append(text)
                    lines.append("")

    return "\n".join(lines).strip()


def _count_numeric_cells(row: list) -> int:
    """Count cells that look numeric (digits, decimals, with optional units like %)."""
    numeric = 0
    for cell in row:
        s = str(cell).strip()
        if not s:
            continue
        # Remove common unit suffixes for purity check
        cleaned = re.sub(r"[%µ°]", "", s).replace(",", ".")
        if re.match(r"^-?[\d.]+$", cleaned) or (
            len(cleaned) <= 15 and any(c.isdigit() for c in cleaned)
        ):
            numeric += 1
    return numeric


def _avg_cell_word_count(row: list) -> float:
    """Average words per cell (header cells tend to be 1-3 words)."""
    if not row:
        return 0.0
    total = sum(len(str(c).split()) for c in row if str(c).strip())
    return total / max(1, len([c for c in row if str(c).strip()]))


def _is_table_header(row: list) -> bool:
    """
    Structural header detection: no domain keywords.
    Header rows: high alphabetic ratio, low numeric ratio, short cells.
    Exclude label rows: cells ending with ":" are key-value labels, not headers.
    """
    if len(row) < 3:
        return False
    if any(str(c).strip().endswith(":") for c in row):
        return False
    all_text = " ".join(str(c).strip() for c in row)
    alpha_count = sum(1 for c in all_text if c.isalpha())
    digit_count = sum(1 for c in all_text if c.isdigit())
    total_relevant = alpha_count + digit_count
    if total_relevant == 0:
        return False
    alpha_ratio = alpha_count / total_relevant
    numeric_ratio = digit_count / total_relevant
    numeric_cells = _count_numeric_cells(row)
    avg_words = _avg_cell_word_count(row)
    return (
        alpha_ratio > 0.6
        and numeric_ratio < 0.2
        and numeric_cells <= 1
        and avg_words <= 4.0
    )


def _is_table_row(row: list) -> bool:
    """
    Structural data row detection: has numeric content, 3+ columns.
    No domain assumptions - pattern-based.
    """
    if len(row) < 3:
        return False
    numeric_cells = _count_numeric_cells(row)
    # Data rows typically have at least one numeric cell
    if numeric_cells < 1:
        first = str(row[0]).strip() if row else ""
        if first and (first.replace(".", "").isdigit() or first[0:1].isdigit()):
            return True
        return False
    # First column often has index/number
    first = str(row[0]).strip() if row else ""
    starts_with_digit = first.replace(".", "").replace("-", "").isdigit()
    return numeric_cells >= 1 or starts_with_digit


def _row_has_text_only(row: list) -> bool:
    """Row has no numeric values - text/labels only."""
    return _count_numeric_cells(row) == 0


def _row_is_label_row(row: list) -> bool:
    """
    Row is mostly labels: at most first column is numeric (index), rest is text.
    Used for merge: [No, Investigation, (Abbr)] can have numeric in col 0.
    """
    if len(row) < 2:
        return False
    numeric = _count_numeric_cells(row)
    first = str(row[0]).strip() if row else ""
    first_is_index = first.replace(".", "").isdigit()
    return numeric <= 1 and (numeric == 0 or first_is_index)


def _row_has_numeric(row: list) -> bool:
    """Row has at least one numeric-like cell."""
    return _count_numeric_cells(row) >= 1


def _merged_improves_alignment(
    prev_row: list, next_row: list, merged: list, target_cols: int = 5
) -> bool:
    """
    Merging improves table alignment: combined row has consistent column count.
    """
    prev_cols = len(prev_row)
    next_cols = len(next_row)
    merged_cols = len(merged)
    if merged_cols < 3 or merged_cols > 10:
        return False
    return merged_cols >= prev_cols and merged_cols >= next_cols


def _try_merge_rows(prev_row: list, next_row: list) -> Optional[list]:
    """
    Generic merge: row1 label-only + row2 numeric -> single aligned row.
    Label row: mostly text, at most index in col 0. Pattern-based, no keywords.
    """
    if not prev_row or not next_row:
        return None
    if not _row_is_label_row(prev_row) or not _row_has_numeric(next_row):
        return None
    p, n = len(prev_row), len(next_row)
    merged = None
    if p == 3 and n == 3:
        merged = [
            prev_row[0],
            str(prev_row[1]).strip() + " " + str(prev_row[2]).strip(),
            next_row[0],
            next_row[1],
            next_row[2],
        ]
    elif p >= 2 and n >= 2:
        merged = (
            prev_row[:-1]
            + [str(prev_row[-1]).strip() + " " + str(next_row[0]).strip()]
            + list(next_row[1:])
        )
    if merged and _merged_improves_alignment(prev_row, next_row, merged):
        return merged
    return None


def _looks_like_section_header(text: str) -> bool:
    """
    Generic heuristic: short standalone phrase that could be a section/category header.
    Avoids domain-specific keyword lists.
    """
    t = text.strip()
    if len(t) > 50 or not t or t.endswith(":"):
        return False
    # Exclude values: contains digits, slashes (e.g. dates, "25 Years/Female")
    if re.search(r"[\d/]", t):
        return False
    # Exclude ALL CAPS (often acronyms, names: SELF, VAPI)
    if t.isupper() and len(t) > 1:
        return False
    # Short phrase, 1-5 words
    words = t.split()
    if len(words) > 5:
        return False
    return True


def _structure_markdown_lines(elem_texts: list) -> list:
    """
    Apply markdown structure: bold labels, section headers, key-value pairs, tables.
    """
    lines = []
    i = 0

    while i < len(elem_texts):
        typ, text = elem_texts[i]
        text_stripped = text.strip()
        text_lower = text_stripped.lower()

        # Title or heading - keep as is
        if typ in ("title", "heading"):
            lines.append(text)
            lines.append("")
            i += 1
            continue

        # Section header: generic standalone short phrase (no domain keywords)
        if typ == "narrative" and _looks_like_section_header(text_stripped):
            lines.append(f"### {text_stripped}")
            lines.append("")
            i += 1
            continue

        # Table detection: collect consecutive table-like elements
        block_lines = [p.strip() for p in text_stripped.split("\n") if p.strip()]
        if len(block_lines) >= 3 and not any(
            ln.endswith(":") for ln in block_lines
        ) and (_is_table_header(block_lines) or _is_table_row(block_lines)):
            table_rows = []
            header_row = None
            j = i
            while j < len(elem_texts):
                _, row_text = elem_texts[j]
                row_cells = [p.strip() for p in row_text.strip().split("\n") if p.strip()]
                has_label_pattern = any(c.endswith(":") for c in row_cells)
                if (
                    len(row_cells) >= 3
                    and not has_label_pattern
                    and (_is_table_header(row_cells) or _is_table_row(row_cells))
                ):
                    if _is_table_header(row_cells) and not table_rows:
                        header_row = row_cells
                        j += 1
                    else:
                        merged = (
                            _try_merge_rows(table_rows[-1], row_cells)
                            if table_rows
                            else None
                        )
                        if merged:
                            table_rows.pop()
                            table_rows.append(merged)
                        else:
                            if len(row_cells) == 4 and header_row and len(header_row) == 5:
                                first = str(row_cells[0])
                                m = re.match(r"^(\d+)\s+(.+)$", first)
                                if m:
                                    row_cells = [
                                        m.group(1),
                                        m.group(2),
                                        row_cells[1],
                                        row_cells[2],
                                        row_cells[3],
                                    ]
                            table_rows.append(row_cells)
                        j += 1
                elif header_row and not table_rows:
                    # Header found, next may be section divider - skip non-table to find data rows
                    next_typ, next_t = elem_texts[j]
                    next_cells = [p.strip() for p in next_t.strip().split("\n") if p.strip()]
                    if len(next_cells) < 3 or (
                        not _is_table_header(next_cells) and not _is_table_row(next_cells)
                    ):
                        if _looks_like_section_header(next_t.strip()):
                            j += 1
                            continue
                    break
                else:
                    break
            i = j
            if header_row or table_rows:
                if header_row and table_rows:
                    lines.append(_rows_to_markdown_table([header_row] + table_rows))
                elif header_row:
                    lines.append(_rows_to_markdown_table([header_row]))
                else:
                    lines.append(_rows_to_markdown_table(table_rows))
                lines.append("")
                continue

        # Label: value - same element has "Label:\nValue" or multiple pairs
        if "\n" in text_stripped:
            block_lines_inner = [p.strip() for p in text_stripped.split("\n") if p.strip()]
            if block_lines_inner:
                formatted = []
                j = 0
                while j < len(block_lines_inner):
                    line = block_lines_inner[j]
                    if line.endswith(":") and j + 1 < len(block_lines_inner) and len(block_lines_inner[j + 1]) < 80:
                        formatted.append(f"**{line.rstrip(':')}** {block_lines_inner[j + 1]}")
                        j += 2
                    else:
                        formatted.append(line)
                        j += 1
                if formatted:
                    lines.extend(formatted)
                    lines.append("")
                    i += 1
                    continue

        # Label: value - current ends with :, next element is value
        if text_stripped.endswith(":") and i + 1 < len(elem_texts):
            next_typ, next_text = elem_texts[i + 1]
            next_stripped = next_text.strip()
            if (
                len(next_stripped) < 80
                and not next_stripped.endswith(":")
                and not _looks_like_section_header(next_stripped)
            ):
                label = text_stripped.rstrip(":")
                lines.append(f"**{label}** {next_stripped}")
                lines.append("")
                i += 2
                continue

        # List item
        if typ == "list":
            lines.append(text)
            if i + 1 >= len(elem_texts) or elem_texts[i + 1][0] != "list":
                lines.append("")
            i += 1
            continue

        # Default
        lines.append(text_stripped)
        lines.append("")
        i += 1

    return lines


def _rows_to_markdown_table(rows: list) -> str:
    """Convert list of row cells to markdown table."""
    if not rows:
        return ""
    max_cols = max(len(r) for r in rows)
    padded = [row + [""] * (max_cols - len(row)) for row in rows]
    # Trim trailing empty columns
    while max_cols > 1 and all(not str(r[max_cols - 1]).strip() for r in padded):
        max_cols -= 1
        padded = [r[:max_cols] for r in padded]
    lines = []
    for idx, row in enumerate(padded):
        row_str = "| " + " | ".join(str(c) for c in row[:max_cols]) + " |"
        lines.append(row_str)
        if idx == 0:
            lines.append("| " + " | ".join("---" for _ in range(max_cols)) + " |")
    return "\n".join(lines)


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
