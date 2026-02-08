"""Logging configuration for PreOCR library."""

import logging
import os
import warnings
from contextlib import contextmanager
from typing import Iterator

# Default log level
_DEFAULT_LOG_LEVEL = logging.WARNING

# Environment variable to control log level
_LOG_LEVEL_ENV = "PREOCR_LOG_LEVEL"


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(_get_log_level())

        # Create console handler if no handlers exist
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(_get_log_level())

            # Create formatter
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

    return logger


def _get_log_level() -> int:
    """
    Get log level from environment variable or default.

    Returns:
        Log level integer
    """
    log_level_str = os.environ.get(_LOG_LEVEL_ENV, "").upper()

    if log_level_str == "DEBUG":
        return logging.DEBUG
    elif log_level_str == "INFO":
        return logging.INFO
    elif log_level_str == "WARNING":
        return logging.WARNING
    elif log_level_str == "ERROR":
        return logging.ERROR
    elif log_level_str == "CRITICAL":
        return logging.CRITICAL
    else:
        return _DEFAULT_LOG_LEVEL


def set_log_level(level: int) -> None:
    """
    Set log level for all PreOCR loggers.

    Args:
        level: Log level (logging.DEBUG, logging.INFO, etc.)
    """
    logger = logging.getLogger("preocr")
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)


@contextmanager
def suppress_pdf_warnings() -> Iterator[None]:
    """
    Context manager to suppress common PDF library warnings.

    Suppresses warnings from pdfplumber, PyMuPDF, and other PDF processing libraries
    that are not critical for functionality (e.g., "Cannot set gray non-stroke color").

    Note: PyMuPDF prints some warnings directly to stderr, which we filter.

    Example:
        >>> with suppress_pdf_warnings():
        ...     result = extract_pdf_text("file.pdf")
    """
    import sys
    
    # Create a filter class for stderr that suppresses PyMuPDF color warnings
    class StderrFilter:
        def __init__(self, original_stderr):
            self.original_stderr = original_stderr
        
        def write(self, text: str) -> int:
            # Filter out PyMuPDF color warnings
            if "Cannot set gray" in text or "invalid float value" in text or "/'Pat" in text:
                return len(text)  # Pretend we wrote it (suppress)
            return self.original_stderr.write(text)
        
        def flush(self):
            self.original_stderr.flush()
        
        def __getattr__(self, name):
            return getattr(self.original_stderr, name)
    
    # Suppress Python warnings
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        warnings.filterwarnings("ignore", message=".*gray.*non-stroke.*color.*")
        warnings.filterwarnings("ignore", message=".*invalid float value.*")
        warnings.filterwarnings("ignore", message=".*Pat.*")
        
        # Redirect stderr to filter
        original_stderr = sys.stderr
        filtered_stderr = StderrFilter(original_stderr)
        sys.stderr = filtered_stderr
        
        # Also suppress warnings from pdfplumber/PyMuPDF modules via logging
        try:
            import pdfplumber  # noqa: F401
            pdfplumber_logger = logging.getLogger("pdfplumber")
            original_pdfplumber_level = pdfplumber_logger.level
            pdfplumber_logger.setLevel(logging.ERROR)
        except ImportError:
            pdfplumber_logger = None
            original_pdfplumber_level = None
        
        try:
            import fitz  # PyMuPDF  # noqa: F401
            pymupdf_logger = logging.getLogger("fitz")
            pymupdf_original_level = pymupdf_logger.level
            pymupdf_logger.setLevel(logging.ERROR)
        except ImportError:
            pymupdf_logger = None
            pymupdf_original_level = None
        
        try:
            yield
        finally:
            # Restore original stderr
            sys.stderr = original_stderr
            # Restore original log levels
            if pdfplumber_logger and original_pdfplumber_level is not None:
                pdfplumber_logger.setLevel(original_pdfplumber_level)
            if pymupdf_logger and pymupdf_original_level is not None:
                pymupdf_logger.setLevel(pymupdf_original_level)
