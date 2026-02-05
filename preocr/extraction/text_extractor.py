"""Text and HTML extraction with structured output."""

from pathlib import Path
from typing import Dict, List, Optional, Any

from .. import exceptions
from ..utils.logger import get_logger
from .schemas import ExtractionResult, Element, ElementType, BoundingBox
from .base import generate_element_id, create_bbox, calculate_confidence

TextExtractionError = exceptions.TextExtractionError
logger = get_logger(__name__)

# Declare BeautifulSoup as Optional[Any] so mypy knows it can be None
BeautifulSoup: Optional[Any]
try:
    from bs4 import BeautifulSoup as _BeautifulSoup
    BeautifulSoup = _BeautifulSoup
except ImportError:
    BeautifulSoup = None


def extract_text_native_data(
    file_path: str,
    include_metadata: bool = True,
    include_structure: bool = True,
    include_bbox: bool = True,
) -> ExtractionResult:
    """
    Extract structured data from text and HTML files.

    Args:
        file_path: Path to the text/HTML file
        include_metadata: Whether to include document metadata
        include_structure: Whether to detect structure
        include_bbox: Whether to include bounding boxes (approximate)

    Returns:
        ExtractionResult with extracted data
    """
    path = Path(file_path)
    extension = path.suffix.lower()

    result = ExtractionResult(
        file_path=str(path),
        file_type=extension.lstrip(".") if extension else "txt",
        extraction_method="native",
        overall_confidence=0.0,
    )

    if extension in [".html", ".htm"]:
        return _extract_html(path, result, include_metadata, include_structure, include_bbox)
    elif extension == ".csv":
        return _extract_csv(path, result, include_metadata, include_structure, include_bbox)
    else:
        return _extract_plain_text(path, result, include_metadata, include_structure, include_bbox)


def _extract_html(
    path: Path,
    result: ExtractionResult,
    include_metadata: bool,
    include_structure: bool,
    include_bbox: bool,
) -> ExtractionResult:
    """Extract from HTML file."""
    all_elements = []
    element_counter = 0
    errors = []

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if BeautifulSoup is None:
            # Fallback: treat as plain text
            return _extract_plain_text(path, result, include_metadata, include_structure, include_bbox)

        soup = BeautifulSoup(content, "html.parser")

        # Extract metadata
        if include_metadata:
            result.metadata.update({
                "extraction_method": "beautifulsoup4",
            })
            if soup.title:
                result.metadata["title"] = soup.title.string
            if soup.find("meta", {"name": "author"}):
                result.metadata["author"] = soup.find("meta", {"name": "author"}).get("content")

        # Extract structured elements
        line_counter = 0

        # Extract headings
        for heading_tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            for heading in soup.find_all(heading_tag):
                text = heading.get_text(strip=True)
                if not text:
                    continue

                element_id = generate_element_id(f"elem_{element_counter}")
                element_counter += 1

                element_type = ElementType.HEADING
                if heading_tag == "h1":
                    element_type = ElementType.TITLE

                # Approximate bbox based on line number
                if include_bbox:
                    y0 = line_counter * 20.0
                    y1 = y0 + 20.0
                    bbox = create_bbox(0, y0, 800, y1, 1, 800, 1000)
                else:
                    bbox = create_bbox(0, 0, 800, 1000, 1, 800, 1000)

                confidence = calculate_confidence(
                    text_quality=0.9 if len(text) > 10 else 0.7,
                    extraction_method="beautifulsoup4",
                    element_type_certainty=0.9,
                    bbox_accuracy=0.3 if include_bbox else 0.1,
                )

                element = Element(
                    element_id=element_id,
                    element_type=element_type,
                    text=text,
                    bbox=bbox,
                    confidence=confidence,
                    metadata={"tag": heading_tag},
                )

                all_elements.append(element)
                line_counter += 1

        # Extract paragraphs
        for para in soup.find_all("p"):
            text = para.get_text(strip=True)
            if not text:
                continue

            element_id = generate_element_id(f"elem_{element_counter}")
            element_counter += 1

            # Approximate bbox
            if include_bbox:
                y0 = line_counter * 20.0
                y1 = y0 + 20.0
                bbox = create_bbox(0, y0, 800, y1, 1, 800, 1000)
            else:
                bbox = create_bbox(0, 0, 800, 1000, 1, 800, 1000)

            confidence = calculate_confidence(
                text_quality=0.9 if len(text) > 10 else 0.7,
                extraction_method="beautifulsoup4",
                element_type_certainty=0.9,
                bbox_accuracy=0.3 if include_bbox else 0.1,
            )

            element = Element(
                element_id=element_id,
                element_type=ElementType.NARRATIVE_TEXT,
                text=text,
                bbox=bbox,
                confidence=confidence,
                metadata={"tag": "p"},
            )

            all_elements.append(element)
            line_counter += 1

        # Extract list items
        for list_tag in ["ul", "ol"]:
            for list_elem in soup.find_all(list_tag):
                for li in list_elem.find_all("li"):
                    text = li.get_text(strip=True)
                    if not text:
                        continue

                    element_id = generate_element_id(f"elem_{element_counter}")
                    element_counter += 1

                    # Approximate bbox
                    if include_bbox:
                        y0 = line_counter * 20.0
                        y1 = y0 + 20.0
                        bbox = create_bbox(0, y0, 800, y1, 1, 800, 1000)
                    else:
                        bbox = create_bbox(0, 0, 800, 1000, 1, 800, 1000)

                    confidence = calculate_confidence(
                        text_quality=0.9 if len(text) > 10 else 0.7,
                        extraction_method="beautifulsoup4",
                        element_type_certainty=0.8,
                        bbox_accuracy=0.3 if include_bbox else 0.1,
                    )

                    element = Element(
                        element_id=element_id,
                        element_type=ElementType.LIST_ITEM,
                        text=text,
                        bbox=bbox,
                        confidence=confidence,
                        metadata={"tag": "li"},
                    )

                    all_elements.append(element)
                    line_counter += 1

    except Exception as e:
        logger.error(f"HTML extraction error: {e}")
        errors.append(f"Extraction error: {str(e)}")

    # Populate result
    result.elements = all_elements
    result.errors = errors

    # Calculate overall confidence
    all_confidences = [e.confidence for e in all_elements]
    result.overall_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    # Quality metrics
    result.quality_metrics = {
        "total_elements": len(all_elements),
        "extraction_method": "beautifulsoup4",
    }

    return result


def _extract_csv(
    path: Path,
    result: ExtractionResult,
    include_metadata: bool,
    include_structure: bool,
    include_bbox: bool,
) -> ExtractionResult:
    """Extract from CSV file (treated as table-like)."""
    from .schemas import Table, TableCell

    all_tables = []
    errors = []

    try:
        import csv

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            result.errors = ["CSV file is empty"]
            return result

        # Extract metadata
        if include_metadata:
            result.metadata.update({
                "extraction_method": "csv",
                "row_count": len(rows),
            })

        # Create table from CSV
        table_id = generate_element_id("table_0")
        cells = []

        for row_idx, row in enumerate(rows):
            for col_idx, cell_value in enumerate(row):
                cell_text = str(cell_value).strip()
                if not cell_text:
                    continue

                # Approximate cell bbox
                if include_bbox:
                    cell_width = 100.0
                    cell_height = 20.0
                    cell_bbox = create_bbox(
                        col_idx * cell_width,
                        row_idx * cell_height,
                        (col_idx + 1) * cell_width,
                        (row_idx + 1) * cell_height,
                        1,
                        1000,
                        1000,
                    )
                else:
                    cell_bbox = create_bbox(0, 0, 1000, 1000, 1, 1000, 1000)

                cell_obj = TableCell(
                    row=row_idx,
                    col=col_idx,
                    text=cell_text,
                    bbox=cell_bbox,
                    confidence=0.9,
                )

                cells.append(cell_obj)

        if cells:
            num_rows = len(rows)
            num_cols = max(len(row) for row in rows) if rows else 0

            table_bbox = create_bbox(0, 0, num_cols * 100.0, num_rows * 20.0, 1, 1000, 1000)

            table_obj = Table(
                element_id=table_id,
                page_number=1,
                bbox=table_bbox,
                rows=num_rows,
                columns=num_cols,
                cells=cells,
                confidence=0.9,
                metadata={"extraction_method": "csv"},
            )

            all_tables.append(table_obj)

    except Exception as e:
        logger.error(f"CSV extraction error: {e}")
        errors.append(f"Extraction error: {str(e)}")

    # Populate result
    result.tables = all_tables
    result.errors = errors

    # Calculate overall confidence
    all_confidences = [t.confidence for t in all_tables]
    result.overall_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    # Quality metrics
    result.quality_metrics = {
        "total_tables": len(all_tables),
        "extraction_method": "csv",
    }

    return result


def _extract_plain_text(
    path: Path,
    result: ExtractionResult,
    include_metadata: bool,
    include_structure: bool,
    include_bbox: bool,
) -> ExtractionResult:
    """Extract from plain text file."""
    all_elements = []
    element_counter = 0
    errors = []

    try:
        # Try different encodings
        encodings = ["utf-8", "latin-1", "cp1252", "iso-8859-1"]
        text = ""
        encoding = None

        for enc in encodings:
            try:
                with open(path, "r", encoding=enc) as f:
                    text = f.read()
                    encoding = enc
                    break
            except (UnicodeDecodeError, UnicodeError):
                continue

        if not text:
            # Last resort: try binary read
            try:
                with open(path, "rb") as f:
                    raw = f.read()
                    text = raw.decode("utf-8", errors="ignore")
                    encoding = "utf-8"
            except Exception as e:
                logger.warning(f"Text extraction failed: {e}")
                errors.append(f"Text extraction failed: {str(e)}")

        # Extract metadata
        if include_metadata:
            result.metadata.update({
                "extraction_method": "plain_text",
                "encoding": encoding,
            })

        # Split into lines and create elements
        lines = text.split("\n")
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            element_id = generate_element_id(f"elem_{element_counter}")
            element_counter += 1

            # Approximate bbox
            if include_bbox:
                y0 = line_idx * 20.0
                y1 = y0 + 20.0
                bbox = create_bbox(0, y0, 800, y1, 1, 800, 1000)
            else:
                bbox = create_bbox(0, 0, 800, 1000, 1, 800, 1000)

            confidence = calculate_confidence(
                text_quality=0.9 if len(line) > 10 else 0.7,
                extraction_method="plain_text",
                element_type_certainty=0.9,
                bbox_accuracy=0.3 if include_bbox else 0.1,
            )

            element = Element(
                element_id=element_id,
                element_type=ElementType.NARRATIVE_TEXT,
                text=line,
                bbox=bbox,
                confidence=confidence,
                metadata={"line_number": line_idx + 1},
            )

            all_elements.append(element)

    except Exception as e:
        logger.error(f"Plain text extraction error: {e}")
        errors.append(f"Extraction error: {str(e)}")

    # Populate result
    result.elements = all_elements
    result.errors = errors

    # Calculate overall confidence
    all_confidences = [e.confidence for e in all_elements]
    result.overall_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

    # Quality metrics
    result.quality_metrics = {
        "total_elements": len(all_elements),
        "extraction_method": "plain_text",
    }

    return result

