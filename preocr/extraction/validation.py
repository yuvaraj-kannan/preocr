"""Extraction validation layer with schema, integrity, and table checks."""

import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .schemas import Element, Table, TableCell, ExtractionResult

SeverityType = Literal["info", "warning", "error"]

# Severity mapping for downstream automation
_SEVERITY_MAP: Dict[str, SeverityType] = {
    "missing_ref_ranges": "warning",
    "numeric_parse_failures": "warning",
    "column_inconsistent": "warning",
    "reading_order_mismatch": "error",
    "duplicate_element_ids": "error",
    "required_field_missing": "error",
}


class ValidationFlag(BaseModel):
    """Single validation flag with severity for downstream automation."""

    code: str = Field(..., description="Flag code (e.g., column_inconsistent)")
    severity: SeverityType = Field(..., description="Severity level")
    message: Optional[str] = Field(None, description="Human-readable description")


def _flag(code: str, message: Optional[str] = None) -> ValidationFlag:
    """Create a ValidationFlag with severity from mapping."""
    severity = _SEVERITY_MAP.get(code, "info")
    return ValidationFlag(code=code, severity=severity, message=message)


class ValidationResult(BaseModel):
    """Result of extraction validation (non-blocking)."""

    status: str = Field(..., description="VALID, WARNING, or ERROR")
    errors: List[str] = Field(default_factory=list, description="Error messages")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    flags: List[ValidationFlag] = Field(default_factory=list, description="Structured flags")


def validate_extraction(
    elements: List[Element],
    tables: List[Table],
    reading_order: Optional[List[str]] = None,
    file_path: str = "",
    extraction_method: str = "",
    pages_extracted: Optional[List[int]] = None,
) -> ValidationResult:
    """
    Validate extraction before populating result.

    Non-blocking: flags bad data but does not reject. Downstream can decide.
    """
    flags: List[ValidationFlag] = []
    errors: List[str] = []
    warnings: List[str] = []

    # Schema: element_id uniqueness
    elem_ids = [e.element_id for e in elements]
    table_ids = [t.element_id for t in tables]
    all_ids = elem_ids + table_ids
    if len(all_ids) != len(set(all_ids)):
        dupe_flag = _flag("duplicate_element_ids", "Duplicate element_ids detected")
        flags.append(dupe_flag)
        errors.append("Duplicate element_ids in extraction result")

    # Schema: reading_order IDs exist in elements + tables
    if reading_order:
        elem_id_set = set(elem_ids) | set(table_ids)
        missing = [rid for rid in reading_order if rid not in elem_id_set]
        if missing:
            flag = _flag(
                "reading_order_mismatch",
                f"Reading order references missing IDs: {missing[:5]}{'...' if len(missing) > 5 else ''}",
            )
            flags.append(flag)
            errors.append(f"Reading order references {len(missing)} non-existent element IDs")

    # Integrity: file_path non-empty
    if not file_path or not file_path.strip():
        flag = _flag("required_field_missing", "file_path is empty")
        flags.append(flag)
        errors.append("file_path is required and non-empty")

    # Integrity: extraction_method valid
    if extraction_method not in ("native", "ocr", "pdfplumber", "pymupdf"):
        flag = _flag("required_field_missing", f"Invalid extraction_method: {extraction_method}")
        flags.append(flag)
        warnings.append(f"Unusual extraction_method: {extraction_method}")

    # Table validation: column consistency
    for table in tables:
        if table.metadata.get("is_decorative"):
            continue
        if not table.cells:
            continue
        rows: Dict[int, List[TableCell]] = {}
        for cell in table.cells:
            r = cell.row
            if r not in rows:
                rows[r] = []
            rows[r].append(cell)
        if rows:
            col_counts = [len(row_cells) for row_cells in rows.values()]
            if len(set(col_counts)) > 1:
                flag = _flag(
                    "column_inconsistent",
                    f"Table {table.element_id} has inconsistent column counts: {col_counts}",
                )
                flags.append(flag)
                warnings.append(f"Table {table.element_id}: column count varies by row")

    # Table validation: numeric fields
    _NUMERIC_RE = re.compile(r"^[\d\s.,\-+%]+$")
    for table in tables:
        if table.metadata.get("is_decorative"):
            continue
        parse_failures = 0
        numeric_like = 0
        for cell in table.cells:
            t = (cell.text or "").strip()
            if not t:
                continue
            if _NUMERIC_RE.match(t):
                numeric_like += 1
                try:
                    float(t.replace(",", "").replace(" ", ""))
                except (ValueError, TypeError):
                    parse_failures += 1
        if numeric_like > 0 and parse_failures > 0:
            flag = _flag(
                "numeric_parse_failures",
                f"Table {table.element_id}: {parse_failures}/{numeric_like} numeric-like cells failed to parse",
            )
            flags.append(flag)
            warnings.append(f"Table {table.element_id}: numeric parse failures")

    # Ref ranges: lab-report style (e.g. "10-20", "3.5 - 5.5")
    _REF_RANGE_RE = re.compile(r"[\d.]+\s*[-–]\s*[\d.]+")
    for table in tables:
        if table.metadata.get("is_decorative"):
            continue
        # Typically ref range is in last column
        rows_by_idx: Dict[int, List[TableCell]] = {}
        for cell in table.cells:
            r = cell.row
            if r not in rows_by_idx:
                rows_by_idx[r] = []
            rows_by_idx[r].append(cell)
        # Check last column of data rows for ref-like content
        missing_ref_rows = 0
        for row_idx, row_cells in sorted(rows_by_idx.items()):
            if not row_cells:
                continue
            last_cell = max(row_cells, key=lambda c: c.col)
            text = (last_cell.text or "").strip()
            # If cell looks like it should have ref (short, might have numbers)
            if len(text) < 50 and not _REF_RANGE_RE.search(text) and text and not text.isdigit():
                missing_ref_rows += 1
        if missing_ref_rows > 2:
            flag = _flag(
                "missing_ref_ranges",
                f"Table {table.element_id}: {missing_ref_rows} rows may have missing reference ranges",
            )
            flags.append(flag)
            warnings.append(f"Table {table.element_id}: possible missing ref ranges")

    # Determine status
    has_errors = any(f.severity == "error" for f in flags) or bool(errors)
    has_warnings = any(f.severity == "warning" for f in flags) or bool(warnings)
    if has_errors:
        status = "ERROR"
    elif has_warnings:
        status = "WARNING"
    else:
        status = "VALID"

    return ValidationResult(status=status, errors=errors, warnings=warnings, flags=flags)