"""Pipeline orchestration for OCR conditioning."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import numpy as np

from preocr.preprocess.steps import SUPPORTED_STEPS
from preocr.preprocess.utils import (
    _ensure_opencv,
    _is_image_file,
    _is_pdf,
    _load_array,
    _load_image,
    _pdf_page_to_array,
)
from preocr.utils.logger import get_logger

fitz: Optional[Any] = None
try:
    import fitz as _fitz
    fitz = _fitz
except ImportError:
    pass

logger = get_logger(__name__)

PIPELINE_ORDER = ["denoise", "deskew", "otsu", "rescale"]
DEFAULT_STEPS = ["denoise", "deskew", "otsu"]


@dataclass
class PreprocessConfig:
    """Configuration for preprocessing pipeline."""

    auto_fix: bool = False  # When True, auto-add denoise if otsu requested without it


def _normalize_steps(
    steps: Union[List[str], Tuple[str, ...], Dict[str, Any]]
) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """
    Normalize steps from list or dict format.

    Returns:
        (step_names, kwargs_map). kwargs_map maps step name -> params for that step.
    """
    if isinstance(steps, dict):
        step_names = [k for k in steps.keys() if k in SUPPORTED_STEPS]
        kwargs_map = {k: v if isinstance(v, dict) else {} for k, v in steps.items() if k in SUPPORTED_STEPS}
        return step_names, kwargs_map
    if isinstance(steps, (list, tuple)):
        step_names = [s for s in steps if s in SUPPORTED_STEPS]
        return step_names, {}
    return [], {}  # type: ignore[unreachable]


def _apply_guardrails(
    step_names: List[str],
    config: Optional[PreprocessConfig] = None,
    from_hints: bool = False,
) -> List[str]:
    """
    Apply guardrails: otsu precondition.
    If otsu in steps but denoise not, auto-add denoise when config.auto_fix else log warning.
    When from_hints=True (steps came from needs_ocr), skip warning—trust detector's choice.
    """
    cfg = config or PreprocessConfig()
    if "otsu" in step_names and "denoise" not in step_names:
        if cfg.auto_fix:
            step_names = list(dict.fromkeys(["denoise"] + step_names))
        elif not from_hints:
            logger.warning(
                "Otsu requested without denoise; Otsu on noisy grayscale may degrade quality. "
                "Consider adding denoise or set config.auto_fix=True."
            )
    return step_names


def _apply_mode_filter(step_names: List[str], mode: str) -> List[str]:
    """
    Filter steps by mode. Fast mode: exclude denoise, rescale; deskew gets severe_only.
    Returns filtered step names. severe_only for deskew is passed via kwargs at execution.
    """
    if mode == "quality":
        return step_names
    if mode == "fast":
        filtered = [s for s in step_names if s not in ("denoise", "rescale")]
        return filtered
    return step_names


def _order_steps(step_names: List[str]) -> List[str]:
    """Sort steps by PIPELINE_ORDER."""
    def key(s: str) -> int:
        try:
            return PIPELINE_ORDER.index(s)
        except ValueError:
            return 999
    return sorted(step_names, key=key)


def _execute_pipeline(
    img: np.ndarray,
    ordered_steps: List[str],
    kwargs_map: Dict[str, Dict[str, Any]],
    mode: str,
    dpi: int,
) -> Tuple[np.ndarray, List[str], List[str]]:
    """Execute pipeline sequentially. Returns (img, applied, skipped)."""
    applied: List[str] = []
    skipped: List[str] = []
    current_img = img

    for name in ordered_steps:
        if name not in SUPPORTED_STEPS:
            continue
        step_fn = SUPPORTED_STEPS[name]
        kwargs = dict(kwargs_map.get(name, {}))

        # Mode-specific kwargs
        if name == "deskew" and mode == "fast":
            kwargs["severe_only"] = True
        if name == "rescale":
            kwargs.setdefault("target_dpi", dpi)

        result_img, did_apply = step_fn(current_img, **kwargs)  # type: ignore[operator]
        if did_apply:
            applied.append(name)
            current_img = result_img
        else:
            skipped.append(name)

    return current_img, applied, skipped


def prepare_for_ocr(
    source: Union[str, Path, np.ndarray],
    steps: Optional[Union[str, List[str], Dict[str, Any]]] = None,
    mode: str = "quality",
    return_meta: bool = False,
    pages: Optional[List[int]] = None,
    output_format: str = "numpy",
    dpi: int = 300,
    config: Optional[PreprocessConfig] = None,
) -> Union[np.ndarray, List[np.ndarray], Tuple[Any, Dict[str, Any]]]:
    """
    Prepare image(s) for OCR using detection-aware adaptive preprocessing.

    When steps=None: no preprocessing, return image as-is.
    When steps="auto": call needs_ocr() for file-based sources to get hints; for numpy array, use DEFAULT_STEPS.
    When steps=["deskew", ...]: explicit steps from user or hints.

    Args:
        source: File path (str/Path) or numpy array (H,W) or (H,W,C)
        steps: None (skip), "auto" (detection-driven), or list/dict of step names
        mode: "quality" (full adaptive) or "fast" (skip denoise, rescale; deskew only if severe)
        return_meta: If True, return (img, meta) with applied_steps, skipped_steps, auto_detected
        pages: For PDFs, 1-indexed page numbers to process. None = all pages.
        output_format: "numpy" (default) - return ndarray(s)
        dpi: Target DPI for rescale step (default 300)
        config: PreprocessConfig with auto_fix for otsu precondition

    Returns:
        Processed image(s) as numpy array or list of arrays. If return_meta, tuple (img, meta).
    """
    _ensure_opencv()

    # steps=None -> no preprocessing
    if steps is None:
        imgs = _load_source(source, pages, dpi)
        result: Union[np.ndarray, List[np.ndarray]] = imgs
        if return_meta:
            empty_meta: Dict[str, Any] = {"applied_steps": [], "skipped_steps": [], "auto_detected": False}
            return (result, empty_meta)
        return result

    # steps="auto" -> fetch hints for file-based; DEFAULT_STEPS for array
    auto_detected = False
    resolved_steps: Union[List[str], Dict[str, Any]]
    if steps == "auto":
        if isinstance(source, np.ndarray):
            resolved_steps = DEFAULT_STEPS
        elif isinstance(source, (str, Path)):
            from preocr.core.detector import needs_ocr
            needs_ocr_result = needs_ocr(str(source), page_level=False, layout_aware=True)
            hints = needs_ocr_result.get("hints", {}) or {}
            suggested = hints.get("suggest_preprocessing")
            if suggested is False or suggested is None:
                resolved_steps = DEFAULT_STEPS
            elif isinstance(suggested, (list, tuple)):
                resolved_steps = list(suggested)
                auto_detected = True
            else:
                resolved_steps = DEFAULT_STEPS
        else:
            resolved_steps = DEFAULT_STEPS  # type: ignore[unreachable]
    else:
        resolved_steps = cast(Union[List[str], Dict[str, Any]], steps)

    step_names, kwargs_map = _normalize_steps(resolved_steps)
    step_names = _apply_guardrails(step_names, config, from_hints=auto_detected)
    step_names = _apply_mode_filter(step_names, mode)
    ordered = _order_steps(step_names)

    imgs_raw = _load_source(source, pages, dpi)
    is_list = isinstance(imgs_raw, list)
    img_list: List[np.ndarray] = (
        list(imgs_raw) if is_list else [cast(np.ndarray, imgs_raw)]
    )

    processed: List[np.ndarray] = []
    all_applied: List[str] = []
    all_skipped: List[str] = []

    for img in img_list:
        # Convert to grayscale for pipeline
        img_arr: np.ndarray = _load_array(img) if len(img.shape) == 3 else img
        out_img, applied, skipped = _execute_pipeline(img_arr, ordered, kwargs_map, mode, dpi)
        processed.append(out_img)
        all_applied = applied  # Last page wins for meta; could merge
        all_skipped = skipped

    if return_meta:
        result_meta: Dict[str, Any] = {
            "applied_steps": all_applied,
            "skipped_steps": all_skipped,
            "auto_detected": auto_detected,
        }
        if is_list:
            return (processed, result_meta)
        return (processed[0], result_meta)
    if is_list:
        return processed
    return processed[0]


def _load_source(
    source: Union[str, Path, np.ndarray],
    pages: Optional[List[int]],
    dpi: int,
) -> Union[np.ndarray, List[np.ndarray]]:
    """Load source into image(s)."""
    if isinstance(source, np.ndarray):
        return _load_array(source)

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if _is_pdf(path):
        if fitz is None:
            raise ImportError("PyMuPDF (fitz) is required for PDF preprocessing. Install with: pip install pymupdf")
        doc = fitz.open(str(path))
        total = len(doc)
        doc.close()
        if pages is not None:
            indices = [p - 1 for p in pages if 1 <= p <= total]  # 1-indexed -> 0-indexed
        else:
            indices = list(range(total))
        return _pdf_page_to_array(path, indices, dpi=dpi)

    if _is_image_file(path):
        return _load_image(path)

    raise ValueError(f"Unsupported file type for preprocessing: {path.suffix}")
