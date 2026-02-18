"""Main planner API: plan_ocr_for_document.

Orchestrates preocr, intent classification, and hybrid decision logic.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.detector import needs_ocr
from ..utils.logger import get_logger
from ..utils import telemetry

from ._extract import extract_per_page_texts
from .config import PlannerConfig
from .decision import decide_page
from .intent import classify_medical_intent
from .models import PageContextSignals, PageOCRDecision

logger = get_logger(__name__)


def plan_ocr_for_document(
    file_path: str,
    per_page_texts: Optional[List[str]] = None,
    per_page_layout_hints: Optional[List[Dict[str, Any]]] = None,
    config: Optional[PlannerConfig] = None,
) -> Dict[str, Any]:
    """
    Return intent-aware OCR plan for a document.

    Uses hybrid decision logic: terminal overrides (failsafe, OCR-critical intent)
    then weighted scoring vs threshold for non-overridden pages.

    Args:
        file_path: Path to the PDF or document file.
        per_page_texts: Optional list of extracted text per page. If None, extracted
            from PDF when possible.
        per_page_layout_hints: Optional list of layout hints per page (e.g. headers).
        config: Optional PlannerConfig. Uses defaults if None.

    Returns:
        Dictionary with:
            - decision_version: str
            - needs_ocr_any: bool
            - pages: List[dict] with needs_ocr, decision_type, reason, confidence, debug
            - pages_needing_ocr: List[int] (0-based indices)
            - overall_confidence: float
            - summary_reason: str
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    cfg = config or PlannerConfig()

    # Step 0: Confidence exit - try fast path first; if confident, skip full planner
    if cfg.confidence_exit_threshold > 0:
        fast_result = needs_ocr(
            str(path),
            page_level=False,
            layout_aware=False,
        )
        if fast_result.get("confidence", 0) >= cfg.confidence_exit_threshold:
            telemetry.emit(
                "planner_confidence_exit",
                {
                    "confidence": fast_result.get("confidence", 0),
                    "needs_ocr": fast_result.get("needs_ocr", True),
                },
            )
            return _build_confidence_exit_result(fast_result, cfg)

    # Step 1: Call preocr for base signals (page_level=True, layout_aware=True)
    pre_result = needs_ocr(
        str(path),
        page_level=True,
        layout_aware=True,
    )

    pages_data = pre_result.get("pages", [])
    layout_data = pre_result.get("layout", {})
    layout_pages = layout_data.get("pages", [])
    if not layout_pages and isinstance(layout_data.get("opencv"), dict):
        layout_pages = layout_data["opencv"].get("pages", [])
    layout_expected = bool(layout_data)

    if not pages_data:
        # No page-level data (e.g. non-PDF or extraction failed)
        return _build_fallback_result(pre_result, cfg)

    # Fast-path: skip planner when preocr says no OCR and all pages have very low image coverage.
    # Future: also require min(text_coverage) > X to avoid edge case where low image + broken
    # text extraction (e.g. scanned doc) slips through.
    if (
        not pre_result.get("needs_ocr", True)
        and cfg.fast_path_image_coverage_threshold > 0
        and layout_pages
        and len(layout_pages) >= len(pages_data)
    ):
        max_img = 0.0
        for lp in layout_pages:
            cov = float(lp.get("image_coverage", 0) or 0)
            max_img = max(max_img, cov)
        if max_img < cfg.fast_path_image_coverage_threshold:
            return _build_fast_path_result(pre_result, pages_data, cfg)

    # Step 2: Get per-page texts
    if per_page_texts is None or len(per_page_texts) == 0:
        if str(path).lower().endswith(".pdf"):
            per_page_texts = extract_per_page_texts(str(path))
        else:
            per_page_texts = []

    # Pad or trim to match page count
    n_pages = len(pages_data)
    if len(per_page_texts) < n_pages:
        per_page_texts = list(per_page_texts) + [""] * (n_pages - len(per_page_texts))
    else:
        per_page_texts = per_page_texts[:n_pages]

    # Step 3: Build PageContextSignals per page
    layout_by_page = {p.get("page_number", i + 1): p for i, p in enumerate(layout_pages)}

    decisions: List[PageOCRDecision] = []
    for i, page_info in enumerate(pages_data):
        page_num = page_info.get("page_number", i + 1)
        layout_page = layout_by_page.get(page_num)

        signals = PageContextSignals.from_preocr_page(
            page_data=page_info,
            layout_page=layout_page,
            page_index=i,
            layout_expected=layout_expected,
        )

        # extraction_failed: only set when extraction explicitly failed (e.g. exception)
        # layout_missing is set in from_preocr_page when layout_expected and no layout

        # Step 4: Classify intent
        page_text = per_page_texts[i] if i < len(per_page_texts) else ""
        hints = None
        if per_page_layout_hints and i < len(per_page_layout_hints):
            hints = per_page_layout_hints[i]
        intent = classify_medical_intent(page_text, hints)

        # Step 5: Decide
        decision = decide_page(signals, intent, cfg)
        decisions.append(decision)

        logger.debug(
            f"Page {page_num}: needs_ocr={decision.needs_ocr} "
            f"type={decision.decision_type} score={decision.debug.get('score', 'N/A')}"
        )

    # Step 6: Aggregate
    pages_needing_ocr = [i for i, d in enumerate(decisions) if d.needs_ocr]
    needs_ocr_any = len(pages_needing_ocr) > 0

    total_conf = sum(d.confidence for d in decisions)
    overall_confidence = total_conf / len(decisions) if decisions else 0.5
    if decisions and (
        all(d.needs_ocr for d in decisions) or all(not d.needs_ocr for d in decisions)
    ):
        overall_confidence = min(overall_confidence + 0.1, 1.0)
    else:
        overall_confidence = max(overall_confidence - 0.1, 0.0)

    override_count = sum(1 for d in decisions if d.decision_type == "terminal_override")
    scored_count = len(decisions) - override_count
    summary_reason = (
        f"OCR required on {len(pages_needing_ocr)} of {len(decisions)} pages "
        f"({override_count} overrides, {scored_count} scored)."
    )

    metrics: Dict[str, Any] = {
        "terminal_override": override_count,
        "scored": scored_count,
    }
    override_reasons: Dict[str, int] = {}
    for d in decisions:
        if d.decision_type == "terminal_override":
            reason = d.debug.get("override_reason", "unknown")
            override_reasons[reason] = override_reasons.get(reason, 0) + 1
    if override_reasons:
        metrics["override_reasons"] = override_reasons

    return {
        "decision_version": cfg.decision_version,
        "needs_ocr_any": needs_ocr_any,
        "pages": [d.to_dict() for d in decisions],
        "pages_needing_ocr": pages_needing_ocr,
        "overall_confidence": round(overall_confidence, 2),
        "summary_reason": summary_reason,
        "metrics": metrics,
    }


def _build_confidence_exit_result(
    fast_result: Dict[str, Any], cfg: PlannerConfig
) -> Dict[str, Any]:
    """Build result when confidence exit applies: fast path was confident enough."""
    needs_ocr = fast_result.get("needs_ocr", True)
    conf = fast_result.get("confidence", 0.85)
    page_count = fast_result.get("signals", {}).get("page_count", 1) or 1
    pages = [
        {
            "page_number": i + 1,
            "needs_ocr": needs_ocr,
            "decision_type": "confidence_exit",
            "reason": f"Confidence exit: {conf:.2f} >= {cfg.confidence_exit_threshold}; skipped planner.",
            "confidence": conf,
            "decision_version": cfg.decision_version,
            "debug": {
                "terminal_override": False,
                "confidence_exit": True,
                "score": 1.0 if needs_ocr else 0.0,
                "components": {
                    "intent": 0,
                    "image_dominance": 0.5 if needs_ocr else 0,
                    "text_weakness": 0.5 if needs_ocr else 0,
                    "failsafe_boost": 0,
                },
            },
        }
        for i in range(page_count)
    ]
    return {
        "decision_version": cfg.decision_version,
        "needs_ocr_any": needs_ocr,
        "pages": pages,
        "pages_needing_ocr": list(range(page_count)) if needs_ocr else [],
        "overall_confidence": round(conf, 2),
        "summary_reason": f"Confidence exit ({conf:.2f}); skipped planner.",
        "metrics": {"terminal_override": 0, "scored": 0, "confidence_exit": page_count},
    }


def _build_fallback_result(pre_result: Dict[str, Any], cfg: PlannerConfig) -> Dict[str, Any]:
    """Build result when no page-level data is available."""
    needs_ocr = pre_result.get("needs_ocr", True)
    return {
        "decision_version": cfg.decision_version,
        "needs_ocr_any": needs_ocr,
        "pages": [],
        "pages_needing_ocr": [0] if needs_ocr else [],
        "overall_confidence": pre_result.get("confidence", 0.5),
        "summary_reason": "No page-level data; using document-level decision.",
        "metrics": {"terminal_override": 1 if needs_ocr else 0, "scored": 0},
    }


def _build_fast_path_result(
    pre_result: Dict[str, Any],
    pages_data: List[Dict[str, Any]],
    cfg: PlannerConfig,
) -> Dict[str, Any]:
    """Build result when fast-path applies: preocr no OCR + very low image coverage."""
    n_pages = len(pages_data)
    pages = [
        {
            "page_number": p.get("page_number", i + 1),
            "needs_ocr": False,
            "decision_type": "fast_path",
            "reason": "PreOCR no OCR + low image coverage; skipped planner scoring.",
            "confidence": pre_result.get("confidence", 0.85),
            "decision_version": cfg.decision_version,
            "debug": {
                "score": 0.0,
                "components": {
                    "intent": 0,
                    "image_dominance": 0,
                    "text_weakness": 0,
                    "failsafe_boost": 0,
                },
                "terminal_override": False,
                "fast_path": True,
            },
        }
        for i, p in enumerate(pages_data)
    ]
    return {
        "decision_version": cfg.decision_version,
        "needs_ocr_any": False,
        "pages": pages,
        "pages_needing_ocr": [],
        "overall_confidence": round(pre_result.get("confidence", 0.85), 2),
        "summary_reason": f"Fast-path: preocr no OCR, image coverage < {cfg.fast_path_image_coverage_threshold}%; skipped scoring.",
        "metrics": {"terminal_override": 0, "scored": 0, "fast_path": n_pages},
    }
