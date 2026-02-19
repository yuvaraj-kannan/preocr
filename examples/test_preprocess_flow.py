#!/usr/bin/env python3
"""
Test the prepare_for_ocr flow: needs_ocr -> hints -> prepare_for_ocr.

Run with: python examples/test_preprocess_flow.py
Requires: pip install preocr[layout-refinement]
"""

import tempfile
from pathlib import Path

import numpy as np

from preocr import needs_ocr, prepare_for_ocr


def test_numpy_explicit_steps():
    """Test: numpy array + explicit steps."""
    print("\n--- 1. Numpy array + explicit steps ---")
    img = np.random.randint(0, 256, (100, 200), dtype=np.uint8)
    img[20:80, 50:150] = 255  # Simulate text region
    result = prepare_for_ocr(img, steps=["otsu"])
    print(f"  Input shape: {img.shape}")
    print(f"  Output shape: {result.shape}")
    print(f"  Unique values in output: {len(np.unique(result))}")
    assert isinstance(result, np.ndarray)
    print("  OK")


def test_numpy_with_meta():
    """Test: numpy + return_meta."""
    print("\n--- 2. Numpy array + return_meta ---")
    img = np.zeros((80, 120), dtype=np.uint8)
    img[10:70, 20:100] = 255  # Binary-like
    result, meta = prepare_for_ocr(img, steps=["otsu"], return_meta=True)
    print(f"  applied_steps: {meta['applied_steps']}")
    print(f"  skipped_steps: {meta['skipped_steps']}")
    print(f"  auto_detected: {meta['auto_detected']}")
    assert "skipped_steps" in meta
    print("  OK")


def test_image_file_auto():
    """Test: image file + steps='auto' (full detection-driven flow)."""
    print("\n--- 3. Image file + steps='auto' ---")
    try:
        from PIL import Image
    except ImportError:
        print("  SKIP (Pillow required)")
        return

    # Create a simple grayscale image
    img = Image.new("L", (200, 100), color=200)
    for y in range(20, 80):
        for x in range(30, 170):
            img.putpixel((x, y), 50 if (x + y) % 4 < 2 else 60)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img.save(f.name)
        path = f.name
    try:
        # needs_ocr on image -> typically needs_ocr=True
        ocr_result = needs_ocr(path, layout_aware=True)
        hints = ocr_result.get("hints", {})
        suggest = hints.get("suggest_preprocessing")
        print(f"  needs_ocr: {ocr_result.get('needs_ocr')}")
        print(f"  suggest_preprocessing: {suggest}")

        # Option A: User wires it
        if suggest and suggest is not False:
            result, meta = prepare_for_ocr(
                path, steps=suggest, return_meta=True, mode="quality"
            )
        else:
            result, meta = prepare_for_ocr(
                path, steps=["denoise", "otsu"], return_meta=True
            )
        print(f"  applied_steps: {meta['applied_steps']}")
        print(f"  skipped_steps: {meta['skipped_steps']}")

        # Option B: steps="auto" (convenience)
        result2, meta2 = prepare_for_ocr(path, steps="auto", return_meta=True)
        print(f"  steps='auto' applied: {meta2['applied_steps']}")
        print("  OK")
    finally:
        Path(path).unlink(missing_ok=True)


def test_image_file_fast_mode():
    """Test: mode='fast' skips denoise/rescale."""
    print("\n--- 4. Image file + mode='fast' ---")
    try:
        from PIL import Image
    except ImportError:
        print("  SKIP (Pillow required)")
        return

    img = Image.new("L", (80, 80), color=128)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img.save(f.name)
        path = f.name
    try:
        result, meta = prepare_for_ocr(
            path, steps=["denoise", "deskew", "otsu", "rescale"], mode="fast", return_meta=True
        )
        print(f"  applied_steps: {meta['applied_steps']}")
        assert "denoise" not in meta["applied_steps"]
        assert "rescale" not in meta["applied_steps"]
        print("  OK (denoise/rescale excluded in fast mode)")
    finally:
        Path(path).unlink(missing_ok=True)


def test_steps_none():
    """Test: steps=None returns image unchanged."""
    print("\n--- 5. steps=None (no preprocessing) ---")
    img = np.ones((50, 50), dtype=np.uint8) * 100
    result = prepare_for_ocr(img, steps=None)
    np.testing.assert_array_equal(result, img)
    print("  OK (image unchanged)")


def main():
    print("=" * 60)
    print("prepare_for_ocr flow test")
    print("=" * 60)
    test_numpy_explicit_steps()
    test_numpy_with_meta()
    test_image_file_auto()
    test_image_file_fast_mode()
    test_steps_none()
    print("\n" + "=" * 60)
    print("All flow tests passed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
