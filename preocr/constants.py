"""Constants and configuration for preocr."""

from dataclasses import dataclass

# Minimum text length to consider a file as having meaningful text
MIN_TEXT_LENGTH = 50

# Minimum text length for office documents to skip OCR
MIN_OFFICE_TEXT_LENGTH = 100

# File type categories
CATEGORY_STRUCTURED = "structured"
CATEGORY_UNSTRUCTURED = "unstructured"

# Confidence thresholds
HIGH_CONFIDENCE = 0.9
MEDIUM_CONFIDENCE = 0.7
LOW_CONFIDENCE = 0.5

# Confidence threshold for triggering OpenCV layout analysis
# If initial confidence is below this, use OpenCV for refinement
LAYOUT_REFINEMENT_THRESHOLD = 0.9


@dataclass
class Config:
    """
    Configuration class for PreOCR thresholds and settings.

    This class allows customization of decision thresholds for OCR detection.
    All thresholds are optional and default to optimized values for general use.

    Attributes:
        min_text_length: Minimum text length to consider a file as having meaningful text.
                        Files with less text will be flagged as needing OCR.
                        Default: 50 characters.

        min_office_text_length: Minimum text length for office documents to skip OCR.
                               Office documents with less text will be flagged as needing OCR.
                               Default: 100 characters.

        layout_refinement_threshold: Confidence threshold for triggering OpenCV layout analysis.
                                    If initial confidence is below this, use OpenCV for refinement.
                                    Default: 0.9 (90%).

        high_confidence: Threshold for high confidence decisions. Default: 0.9.

        medium_confidence: Threshold for medium confidence decisions. Default: 0.7.

        low_confidence: Threshold for low confidence decisions. Default: 0.5.

        use_ocr_score_confidence: If True, use OCR_SCORE-based confidence calculation when available.
                                  This aligns confidence scores with the scoring model for more
                                  meaningful confidence values. Default: True.

    Example:
        >>> # Use default thresholds
        >>> config = Config()
        >>>
        >>> # Customize thresholds for stricter detection
        >>> strict_config = Config(
        ...     min_text_length=100,
        ...     min_office_text_length=200,
        ...     layout_refinement_threshold=0.85
        ... )
    """

    min_text_length: int = MIN_TEXT_LENGTH
    min_office_text_length: int = MIN_OFFICE_TEXT_LENGTH
    layout_refinement_threshold: float = LAYOUT_REFINEMENT_THRESHOLD
    high_confidence: float = HIGH_CONFIDENCE
    medium_confidence: float = MEDIUM_CONFIDENCE
    low_confidence: float = LOW_CONFIDENCE
    use_ocr_score_confidence: bool = True

    def __post_init__(self) -> None:
        """Validate threshold values."""
        if self.min_text_length < 0:
            raise ValueError("min_text_length must be >= 0")
        if self.min_office_text_length < 0:
            raise ValueError("min_office_text_length must be >= 0")
        if not 0.0 <= self.layout_refinement_threshold <= 1.0:
            raise ValueError("layout_refinement_threshold must be between 0.0 and 1.0")
        if not 0.0 <= self.high_confidence <= 1.0:
            raise ValueError("high_confidence must be between 0.0 and 1.0")
        if not 0.0 <= self.medium_confidence <= 1.0:
            raise ValueError("medium_confidence must be between 0.0 and 1.0")
        if not 0.0 <= self.low_confidence <= 1.0:
            raise ValueError("low_confidence must be between 0.0 and 1.0")

        # Ensure confidence thresholds are in order
        if not (self.low_confidence <= self.medium_confidence <= self.high_confidence):
            raise ValueError("Confidence thresholds must be ordered: low <= medium <= high")


# Reason codes for structured decision tracking
class ReasonCode:
    """Structured reason codes for OCR detection decisions."""

    # No OCR needed
    TEXT_FILE = "TEXT_FILE"
    OFFICE_WITH_TEXT = "OFFICE_WITH_TEXT"
    PDF_DIGITAL = "PDF_DIGITAL"
    STRUCTURED_DATA = "STRUCTURED_DATA"
    HTML_WITH_TEXT = "HTML_WITH_TEXT"

    # OCR needed
    IMAGE_FILE = "IMAGE_FILE"
    OFFICE_NO_TEXT = "OFFICE_NO_TEXT"
    PDF_SCANNED = "PDF_SCANNED"
    HTML_MINIMAL = "HTML_MINIMAL"
    UNKNOWN_BINARY = "UNKNOWN_BINARY"
    UNRECOGNIZED_TYPE = "UNRECOGNIZED_TYPE"

    # Page-level codes
    PDF_PAGE_DIGITAL = "PDF_PAGE_DIGITAL"
    PDF_PAGE_SCANNED = "PDF_PAGE_SCANNED"
    PDF_MIXED = "PDF_MIXED"
