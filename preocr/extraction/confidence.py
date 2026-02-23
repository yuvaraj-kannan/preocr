"""Enhanced confidence scoring for extraction quality."""

import re
from typing import Any, Dict, List, Tuple

from .schemas import Element, Table, TableCell, FormField

# Weights for combined score (must sum to 1.0)
WEIGHT_BASE = 0.4
WEIGHT_PATTERN = 0.2
WEIGHT_NUMERIC = 0.2
WEIGHT_EMPTY = 0.1
WEIGHT_LAYOUT = 0.1

_NUMERIC_RE = re.compile(r"^[\d\s.,\-+%]+$")

# Lab report / invoice style header keywords
_HEADER_KEYWORDS = [
    "no.",
    "no",
    "#",
    "investigation",
    "observed value",
    "reference",
    "price",
    "quantity",
    "subtotal",
    "item",
    "description",
    "unit",
]


def _row_looks_like_header(cells: List[TableCell]) -> bool:
    """Check if row looks like a header row."""
    if len(cells) < 3:
        return False
    row_text = " ".join((c.text or "").lower() for c in cells if c.text)
    return any(kw in row_text for kw in _HEADER_KEYWORDS) and len(cells) <= 5


def _row_looks_like_data(cells: List[TableCell]) -> bool:
    """Check if row looks like data (starts with number, has 3+ columns)."""
    if len(cells) < 3:
        return False
    first = (cells[0].text or "").strip()
    return first.replace(".", "").replace("-", "").isdigit() or bool(first and first[0].isdigit())


def compute_enhanced_confidence(
    elements: List[Element],
    tables: List[Table],
    forms: List[FormField],
    images: List[Element],
) -> Tuple[float, Dict[str, Any]]:
    """
    Compute enhanced confidence from structural quality metrics.

    Returns (overall_confidence, breakdown_dict).
    Shift: from average of element confidences to structural quality metric.
    """
    breakdown: Dict[str, float] = {}
    scores: List[float] = []

    # Base: per-element/table average
    for elem in elements:
        scores.append(elem.confidence)
    for table in tables:
        if not table.metadata.get("is_decorative", False):
            scores.append(table.confidence)
    for form in forms:
        scores.append(form.confidence)
    for img in images:
        scores.append(img.confidence)

    base = sum(scores) / len(scores) if scores else 0.0
    breakdown["base"] = round(base, 2)

    if not scores:
        breakdown.update(pattern=1.0, numeric=1.0, empty=1.0, layout=1.0)
        return (0.0, breakdown)

    # Pattern, numeric, empty, layout: from non-decorative tables only
    pattern_scores: List[float] = []
    numeric_scores: List[float] = []
    empty_scores: List[float] = []
    layout_scores: List[float] = []

    for table in tables:
        if table.metadata.get("is_decorative", False) or not table.cells:
            continue

        rows: Dict[int, List[TableCell]] = {}
        for cell in table.cells:
            r = cell.row
            if r not in rows:
                rows[r] = []
            rows[r].append(cell)

        # Pattern: % rows matching header or data
        matching = 0
        for row_cells in rows.values():
            row_cells_sorted = sorted(row_cells, key=lambda c: c.col)
            if _row_looks_like_header(row_cells_sorted) or _row_looks_like_data(row_cells_sorted):
                matching += 1
        total_rows = len(rows)
        pattern_scores.append(matching / total_rows if total_rows else 1.0)

        # Numeric: % of numeric-looking cells that parse
        numeric_like = 0
        parse_ok = 0
        for cell in table.cells:
            t = (cell.text or "").strip()
            if not t:
                continue
            if _NUMERIC_RE.match(t):
                numeric_like += 1
                try:
                    float(t.replace(",", "").replace(" ", ""))
                    parse_ok += 1
                except (ValueError, TypeError):
                    pass
        numeric_scores.append(parse_ok / numeric_like if numeric_like else 1.0)

        # Empty: penalty for high % empty
        total_cells = len(table.cells)
        empty_cells = sum(1 for c in table.cells if not (c.text or "").strip())
        empty_ratio = empty_cells / total_cells if total_cells else 0.0
        if empty_ratio <= 0.2:
            empty_score = 1.0
        elif empty_ratio <= 0.5:
            empty_score = 1.0 - (empty_ratio - 0.2) * 0.5
        else:
            empty_score = max(0.0, 0.85 - (empty_ratio - 0.5))
        empty_scores.append(empty_score)

        # Layout: column count consistency
        col_counts = [len(row_cells) for row_cells in rows.values()]
        if len(set(col_counts)) <= 1:
            layout_scores.append(1.0)
        else:
            layout_scores.append(0.7)  # Small penalty for inconsistent columns

    pattern = sum(pattern_scores) / len(pattern_scores) if pattern_scores else 1.0
    numeric = sum(numeric_scores) / len(numeric_scores) if numeric_scores else 1.0
    empty = sum(empty_scores) / len(empty_scores) if empty_scores else 1.0
    layout = sum(layout_scores) / len(layout_scores) if layout_scores else 1.0

    breakdown["pattern"] = round(pattern, 2)
    breakdown["numeric"] = round(numeric, 2)
    breakdown["empty"] = round(empty, 2)
    breakdown["layout"] = round(layout, 2)

    overall = (
        WEIGHT_BASE * base
        + WEIGHT_PATTERN * pattern
        + WEIGHT_NUMERIC * numeric
        + WEIGHT_EMPTY * empty
        + WEIGHT_LAYOUT * layout
    )
    overall = round(min(max(overall, 0.0), 1.0), 2)

    return overall, breakdown
