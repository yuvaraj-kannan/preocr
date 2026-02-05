"""Page-level detection for multi-page documents."""

from typing import Any, Dict

from .. import constants, reason_codes
from ..core.decision import decide
from ..core.signals import collect_signals
from ..utils.filetype import FileTypeInfo

MIN_TEXT_LENGTH = constants.MIN_TEXT_LENGTH
ReasonCode = constants.ReasonCode
get_reason_description = reason_codes.get_reason_description


def analyze_pdf_pages(
    file_path: str,
    file_info: FileTypeInfo,
    pdf_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Analyze PDF pages individually for page-level OCR detection.

    Args:
        file_path: Path to the PDF file
        file_info: File type information
        pdf_result: PDF extraction result with page-level data

    Returns:
        Dictionary with page-level analysis:
            - overall_needs_ocr: Boolean for entire document
            - overall_confidence: Overall confidence score
            - overall_reason_code: Overall reason code
            - pages: List of page-level results
    """
    if "pages" not in pdf_result or not pdf_result.get("pages"):
        # Fallback to document-level analysis
        signals = collect_signals(file_path, file_info, pdf_result)
        needs_ocr, reason, confidence, category, reason_code = decide(signals)

        return {
            "overall_needs_ocr": needs_ocr,
            "overall_confidence": confidence,
            "overall_reason_code": reason_code,
            "overall_reason": reason,
            "pages": [],
            "page_count": pdf_result.get("page_count", 0),
            "pages_needing_ocr": 1 if needs_ocr else 0,
            "pages_with_text": 1 if not needs_ocr else 0,
        }

    pages_data = pdf_result["pages"]
    page_results = []
    pages_needing_ocr = 0
    pages_with_text = 0
    total_confidence = 0.0

    for page_info in pages_data:
        page_num = page_info["page_number"]
        page_text_len = page_info["text_length"]
        page_needs_ocr = page_text_len < MIN_TEXT_LENGTH

        # Determine page-level reason code
        if page_needs_ocr:
            reason_code = ReasonCode.PDF_PAGE_SCANNED
            confidence = 0.8 if page_text_len == 0 else 0.6
            pages_needing_ocr += 1
        else:
            reason_code = ReasonCode.PDF_PAGE_DIGITAL
            confidence = 0.95
            pages_with_text += 1

        total_confidence += confidence

        page_results.append(
            {
                "page_number": page_num,
                "needs_ocr": page_needs_ocr,
                "text_length": page_text_len,
                "confidence": confidence,
                "reason_code": reason_code,
                "reason": get_reason_description(reason_code),
            }
        )

    # Calculate overall document status
    total_pages = len(pages_data)
    overall_needs_ocr = pages_needing_ocr > 0

    # Determine overall reason code
    if pages_needing_ocr == 0:
        overall_reason_code = ReasonCode.PDF_DIGITAL
    elif pages_with_text == 0:
        overall_reason_code = ReasonCode.PDF_SCANNED
    else:
        overall_reason_code = ReasonCode.PDF_MIXED

    # Calculate overall confidence
    if total_pages > 0:
        overall_confidence = total_confidence / total_pages
        # Adjust confidence based on consistency
        if pages_needing_ocr == 0 or pages_with_text == 0:
            overall_confidence = min(overall_confidence + 0.1, 1.0)  # More confident if consistent
        else:
            overall_confidence = max(overall_confidence - 0.1, 0.0)  # Less confident if mixed
    else:
        overall_confidence = 0.5

    return {
        "overall_needs_ocr": overall_needs_ocr,
        "overall_confidence": round(overall_confidence, 2),
        "overall_reason_code": overall_reason_code,
        "overall_reason": get_reason_description(overall_reason_code),
        "pages": page_results,
        "page_count": total_pages,
        "pages_needing_ocr": pages_needing_ocr,
        "pages_with_text": pages_with_text,
    }
