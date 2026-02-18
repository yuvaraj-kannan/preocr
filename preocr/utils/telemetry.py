"""Structured telemetry for PreOCR pipeline.

Enable via PREOCR_TELEMETRY=1 or by passing telemetry_callback to needs_ocr.

Events logged (when enabled):
- % docs skipping OpenCV (confidence exit, strong digital)
- % docs using hard scan shortcut
- % docs using digital guard exit
- % docs escalated to planner (vs confidence exit)
- Per-stage timing
"""

import json
import os
import time
from typing import Any, Callable, Dict, Optional

from .logger import get_logger

logger = get_logger(__name__)

_TELEMETRY_ENABLED = os.environ.get("PREOCR_TELEMETRY", "").lower() in ("1", "true", "yes")


def is_telemetry_enabled() -> bool:
    """Return True if telemetry logging is enabled."""
    return _TELEMETRY_ENABLED


def emit(event: str, data: Dict[str, Any]) -> None:
    """
    Emit a structured telemetry event.
    Logs as JSON when PREOCR_TELEMETRY=1 for dashboards/alerting.
    """
    if not _TELEMETRY_ENABLED:
        return
    payload = {"event": event, **data}
    try:
        logger.info("preocr_telemetry: %s", json.dumps(payload))
    except Exception:
        pass


def emit_with_callback(
    callback: Optional[Callable[[str, Dict[str, Any]], None]],
    event: str,
    data: Dict[str, Any],
) -> None:
    """Emit event to callback if provided, and to standard telemetry if enabled."""
    if callback:
        try:
            callback(event, data)
        except Exception:
            pass
    emit(event, data)


class TelemetryContext:
    """Context manager to time a stage and emit elapsed time."""

    def __init__(
        self,
        stage: str,
        callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ):
        self.stage = stage
        self.callback = callback
        self.start: float = 0.0

    def __enter__(self) -> "TelemetryContext":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        elapsed = time.perf_counter() - self.start
        data = {"stage": self.stage, "elapsed_seconds": round(elapsed, 4)}
        emit_with_callback(self.callback, "stage_timing", data)
