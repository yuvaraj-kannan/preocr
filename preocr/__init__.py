"""PreOCR - A fast, CPU-only library that detects whether files need OCR processing."""

from .core.detector import needs_ocr
from .core.extractor import extract_native_data
from .planner import intent_refinement, plan_ocr_for_document
from .preprocess import PreprocessConfig, prepare_for_ocr
from .utils.batch import BatchProcessor, BatchResults
from .version import __version__

# Backward compatibility: expose modules for direct import
# This allows old imports like "from preocr import detector" to still work
from . import constants, exceptions, reason_codes
from .analysis import layout_analyzer, opencv_layout, page_detection
from .core import decision, detector, signals, extractor
from . import preprocess
from .probes import image_probe, office_probe, pdf_probe, text_probe
from .utils import batch, cache, filetype, logger
from .reporting import generate_html_report, ReportConfig

# Export Config for easy access
Config = constants.Config

__all__ = [
    # Main API
    "needs_ocr",
    "extract_native_data",
    "prepare_for_ocr",
    "plan_ocr_for_document",
    "intent_refinement",
    "__version__",
    "BatchProcessor",
    "BatchResults",
    "Config",
    "PreprocessConfig",
    "generate_html_report",
    "ReportConfig",
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
    "preprocess",
    "image_probe",
    "office_probe",
    "pdf_probe",
    "text_probe",
    "reporting",
]
