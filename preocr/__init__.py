"""PreOCR - A fast, CPU-only library that detects whether files need OCR processing."""

from .core.detector import needs_ocr
from .core.extractor import extract_native_data
from .utils.batch import BatchProcessor, BatchResults
from .version import __version__

# Backward compatibility: expose modules for direct import
# This allows old imports like "from preocr import detector" to still work
from . import constants, exceptions, reason_codes
from .analysis import layout_analyzer, opencv_layout, page_detection
from .core import decision, detector, signals, extractor
from .probes import image_probe, office_probe, pdf_probe, text_probe
from .utils import batch, cache, filetype, logger

# Export Config for easy access
Config = constants.Config

__all__ = [
    # Main API
    "needs_ocr",
    "extract_native_data",
    "__version__",
    "BatchProcessor",
    "BatchResults",
    "Config",
    # Modules (for backward compatibility)
    "constants",
    "exceptions",
    "reason_codes",
    "batch",
    "cache",
    "filetype",
    "logger",
    "decision",
    "detector",
    "signals",
    "extractor",
    "layout_analyzer",
    "opencv_layout",
    "page_detection",
    "image_probe",
    "office_probe",
    "pdf_probe",
    "text_probe",
]
