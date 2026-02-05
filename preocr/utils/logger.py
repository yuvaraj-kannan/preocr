"""Logging configuration for PreOCR library."""

import logging
import os

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
