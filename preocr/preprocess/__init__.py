"""Intelligent OCR Conditioning Layer.

Detection-aware adaptive preprocessing. Apply only what's suggested by needs_ocr(),
in safe order, with guardrails and observability.
"""

from preocr.preprocess.pipeline import PreprocessConfig, prepare_for_ocr

__all__ = ["prepare_for_ocr", "PreprocessConfig"]
