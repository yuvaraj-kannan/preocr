"""Preprocessing step implementations."""

from preocr.preprocess.steps.deskew import _deskew
from preocr.preprocess.steps.denoise import _denoise
from preocr.preprocess.steps.otsu import _otsu_binarize
from preocr.preprocess.steps.rescale import _rescale_to_dpi

SUPPORTED_STEPS = {
    "denoise": _denoise,
    "deskew": _deskew,
    "otsu": _otsu_binarize,
    "rescale": _rescale_to_dpi,
}

__all__ = [
    "_deskew",
    "_denoise",
    "_otsu_binarize",
    "_rescale_to_dpi",
    "SUPPORTED_STEPS",
]
