"""Tests for preprocess module."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

# Preprocess requires opencv (layout-refinement extra); skip tests if not available
pytest.importorskip("cv2", reason="opencv-python-headless required for preprocess tests")
pytest.importorskip("numpy")

from preocr.preprocess import PreprocessConfig, prepare_for_ocr
from preocr.preprocess.pipeline import (
    DEFAULT_STEPS,
    PIPELINE_ORDER,
    _apply_guardrails,
    _apply_mode_filter,
    _normalize_steps,
    _order_steps,
)


def test_pipeline_order():
    """PIPELINE_ORDER is correct and immutable."""
    assert PIPELINE_ORDER == ["denoise", "deskew", "otsu", "rescale"]


def test_order_steps():
    """Steps are sorted by PIPELINE_ORDER."""
    ordered = _order_steps(["otsu", "denoise", "deskew"])
    assert ordered == ["denoise", "deskew", "otsu"]


def test_apply_mode_filter_quality():
    """Quality mode keeps all steps."""
    steps = ["denoise", "deskew", "otsu", "rescale"]
    filtered = _apply_mode_filter(steps, "quality")
    assert filtered == steps


def test_apply_mode_filter_fast():
    """Fast mode excludes denoise and rescale."""
    steps = ["denoise", "deskew", "otsu", "rescale"]
    filtered = _apply_mode_filter(steps, "fast")
    assert filtered == ["deskew", "otsu"]


def test_apply_guardrails_without_auto_fix():
    """Otsu without denoise does not auto-add when auto_fix=False."""
    steps = ["otsu"]
    result = _apply_guardrails(steps, PreprocessConfig(auto_fix=False))
    assert result == ["otsu"]


def test_apply_guardrails_with_auto_fix():
    """Otsu without denoise auto-adds denoise when auto_fix=True."""
    steps = ["otsu"]
    result = _apply_guardrails(steps, PreprocessConfig(auto_fix=True))
    assert "denoise" in result
    assert "otsu" in result
    assert result.index("denoise") < result.index("otsu")


def test_normalize_steps_list():
    """List steps normalize correctly."""
    names, kwargs = _normalize_steps(["deskew", "otsu"])
    assert names == ["deskew", "otsu"]
    assert kwargs == {}


def test_normalize_steps_dict():
    """Dict steps normalize to names and kwargs_map."""
    steps = {"deskew": {"angle": 2.3}, "denoise": {"h": 12}}
    names, kwargs = _normalize_steps(steps)
    assert set(names) == {"deskew", "denoise"}
    assert kwargs.get("deskew") == {"angle": 2.3}
    assert kwargs.get("denoise") == {"h": 12}


def test_prepare_for_ocr_steps_none():
    """steps=None returns image unchanged."""
    img = np.zeros((50, 50), dtype=np.uint8)
    img[10:40, 10:40] = 255
    result = prepare_for_ocr(img, steps=None)
    np.testing.assert_array_equal(result, img)


def test_prepare_for_ocr_explicit_steps():
    """Explicit steps are applied."""
    img = np.random.randint(0, 256, (100, 100), dtype=np.uint8)
    result = prepare_for_ocr(img, steps=["otsu"])
    assert isinstance(result, np.ndarray)
    assert result.shape == img.shape or (result.shape[:2] == img.shape[:2])


def test_prepare_for_ocr_return_meta():
    """return_meta=True returns (img, meta)."""
    img = np.zeros((50, 50), dtype=np.uint8)
    img[10:40, 10:40] = 255
    result, meta = prepare_for_ocr(img, steps=["otsu"], return_meta=True)
    assert "applied_steps" in meta
    assert "skipped_steps" in meta
    assert "auto_detected" in meta
    assert meta["auto_detected"] is False


def test_prepare_for_ocr_binary_skip():
    """Otsu skips when image already binary."""
    img = np.zeros((50, 50), dtype=np.uint8)
    img[10:40, 10:40] = 255
    result, meta = prepare_for_ocr(img, steps=["otsu"], return_meta=True)
    assert "otsu" in meta["skipped_steps"]


def test_prepare_for_ocr_mode_fast():
    """Fast mode excludes denoise and rescale from pipeline."""
    img = np.random.randint(0, 256, (80, 80), dtype=np.uint8)
    result, meta = prepare_for_ocr(img, steps=["denoise", "deskew", "otsu"], mode="fast", return_meta=True)
    assert "denoise" not in meta["applied_steps"]
    assert "rescale" not in meta["applied_steps"]


def test_prepare_for_ocr_numpy_auto_fallback():
    """numpy + steps='auto' uses DEFAULT_STEPS (no needs_ocr)."""
    img = np.random.randint(0, 256, (50, 50), dtype=np.uint8)
    result, meta = prepare_for_ocr(img, steps="auto", return_meta=True)
    assert meta["auto_detected"] is False


def test_prepare_for_ocr_with_image_file():
    """Prepare from image file."""
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow required for image file test")

    img = Image.new("L", (32, 32), color=128)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img.save(f.name)
        temp_path = f.name
    try:
        result = prepare_for_ocr(temp_path, steps=["otsu"])
        assert isinstance(result, np.ndarray)
    finally:
        Path(temp_path).unlink()


def test_prepare_for_ocr_file_not_found():
    """Raises FileNotFoundError for missing file."""
    with pytest.raises(FileNotFoundError):
        prepare_for_ocr("/nonexistent/path.png", steps=["otsu"])


def test_prepare_for_ocr_unsupported_file_type():
    """Raises ValueError for unsupported file type."""
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
        f.write(b"data")
        temp_path = f.name
    try:
        with pytest.raises(ValueError, match="Unsupported file type"):
            prepare_for_ocr(temp_path, steps=["otsu"])
    finally:
        Path(temp_path).unlink()
