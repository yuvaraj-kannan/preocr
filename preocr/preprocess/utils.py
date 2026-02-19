"""Preprocess utilities: load image, PDF page to array."""

from pathlib import Path
from typing import Any, List, Optional, Union, cast

import numpy as np

# Optional deps - declare as Optional for mypy
cv2: Optional[Any] = None
_np: Optional[Any] = None
fitz: Optional[Any] = None
Image: Optional[Any] = None

try:
    import cv2 as _cv2
    import numpy as _np_mod
    cv2 = _cv2
    _np = _np_mod
except ImportError:
    pass

try:
    import fitz as _fitz  # PyMuPDF
    fitz = _fitz
except ImportError:
    pass

try:
    from PIL import Image as _PilImage
    Image = _PilImage
except ImportError:
    pass


def _ensure_opencv() -> None:
    """Raise clear error if OpenCV not available."""
    if cv2 is None or _np is None:
        raise ImportError(
            "opencv-python-headless and numpy are required for preprocessing. "
            "Install with: pip install preocr[layout-refinement]"
        )


def _load_image(path: Union[str, Path]) -> np.ndarray:
    """Load image file as numpy array (grayscale for downstream steps)."""
    _ensure_opencv()
    assert cv2 is not None  # ensured by _ensure_opencv
    if Image is None:
        img = cv2.imread(str(path))
        if img is None:
            raise OSError(f"Could not read image: {path}")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cast(np.ndarray, gray.astype(np.uint8))

    with Image.open(path) as pil_img:
        arr = np.array(pil_img.convert("L"), dtype=np.uint8)
    return cast(np.ndarray, arr)


def _load_array(arr: np.ndarray) -> np.ndarray:
    """Convert numpy array to grayscale uint8 if needed."""
    _ensure_opencv()
    assert cv2 is not None  # ensured by _ensure_opencv
    if arr.dtype != np.uint8:
        arr = arr.astype(np.uint8)
    if len(arr.shape) == 3:
        if arr.shape[2] == 3:
            return cast(np.ndarray, cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY))
        if arr.shape[2] == 4:
            return cast(np.ndarray, cv2.cvtColor(arr, cv2.COLOR_RGBA2GRAY))
    return arr


def _pdf_page_to_array(
    file_path: Union[str, Path],
    page_indices: List[int],
    dpi: int = 300,
) -> List[np.ndarray]:
    """
    Render PDF pages to numpy arrays.

    Uses zoom = dpi/72 to tie scale to target DPI.
    Respects page_indices - only render requested pages.
    """
    _ensure_opencv()
    assert cv2 is not None  # ensured by _ensure_opencv
    if fitz is None:
        raise ImportError(
            "PyMuPDF (fitz) is required for PDF preprocessing. "
            "Install with: pip install pymupdf"
        )

    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    doc = fitz.open(str(file_path))
    images = []
    try:
        for idx in page_indices:
            if idx < 0 or idx >= len(doc):
                continue
            page = doc[idx]
            pix = page.get_pixmap(matrix=matrix)
            img_array = np.frombuffer(pix.samples, dtype=np.uint8)

            if pix.n == 1:
                img = img_array.reshape(pix.height, pix.width)
            else:
                img = img_array.reshape(pix.height, pix.width, pix.n)
                if pix.n == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
                elif pix.n == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            images.append(img.astype(np.uint8))
    finally:
        doc.close()

    return images


def _is_pdf(path: Union[str, Path]) -> bool:
    """Check if path is a PDF by extension or content."""
    p = Path(path)
    if p.suffix.lower() == ".pdf":
        return True
    # Could add MIME check via filetype.detect_file_type
    return False


def _is_image_file(path: Union[str, Path]) -> bool:
    """Check if path is an image file by extension."""
    ext = Path(path).suffix.lower()
    return ext in {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp", ".gif"}
