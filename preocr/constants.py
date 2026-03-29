"""Constants and configuration for preocr."""

from dataclasses import dataclass
from typing import Optional

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

# Confidence band for tiered refinement (refined thresholds)
# >= 0.90: immediate exit (skip OpenCV)
# 0.75-0.90: skip OpenCV unless image-heavy
# 0.50-0.75: sample 2-3 pages (light refinement)
# < 0.50: full refinement
CONFIDENCE_EXIT_THRESHOLD = 0.90
CONFIDENCE_LIGHT_REFINEMENT_MIN = 0.50
# In 0.75-0.90 confidence band: skip OpenCV unless image_coverage > this (%)
# Tunable per domain (e.g. financial PDFs vs product manuals)
SKIP_OPENCV_IMAGE_GUARD = 50.0

# Hard Digital Check: extractable text >= this → NO OCR (early exit)
HARD_DIGITAL_TEXT_THRESHOLD = 20

# Hard Scan Check: image_coverage >= this AND text_length <= hard_scan_text_max → OCR
HARD_SCAN_IMAGE_COVERAGE_MIN = 80.0
HARD_SCAN_TEXT_MAX = 20

# Hard Scan Shortcut: stricter check for obvious scans - direct exit, no layout/OpenCV
HARD_SCAN_SHORTCUT_IMAGE_MIN = 85.0
HARD_SCAN_SHORTCUT_TEXT_MAX = 10


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
        confidence_exit_threshold: Skip OpenCV entirely when confidence >= this. Default: 0.90.
        confidence_light_refinement_min: Use light refinement (2-3 pages) when confidence
            in [this, confidence_exit_threshold). Full refinement when < this. Default: 0.50.
        skip_opencv_image_guard: In 0.75-0.90 band, skip OpenCV unless image_coverage > this (%).
            Default 50. Tunable per domain.

        high_confidence: Threshold for high confidence decisions. Default: 0.9.

        medium_confidence: Threshold for medium confidence decisions. Default: 0.7.

        low_confidence: Threshold for low confidence decisions. Default: 0.5.

        use_ocr_score_confidence: If True, use OCR_SCORE-based confidence calculation when available.
                                  This aligns confidence scores with the scoring model for more
                                  meaningful confidence values. Default: True.

        skip_opencv_if_file_size_mb: Skip OpenCV refinement if file_size_mb >= this. None = disabled.
        skip_opencv_if_page_count: Skip OpenCV if page_count >= this. None = disabled.
        skip_opencv_text_coverage_min: With page_count: require text_coverage >= this (0-100). None = no check.
        skip_opencv_confidence_min: Only skip if initial confidence >= this. None = no check.
        skip_opencv_max_image_coverage: Never skip when image_coverage > this. None = no guard.

        digital_bias_text_coverage_min: Force needs_ocr=False when text_coverage >= this. None = disabled.
        digital_bias_image_coverage_max: With above: require image_coverage <= this. None = disabled.
        table_bias_text_density_min: For mixed layout: treat as digital when text_density >= this. None = disabled.
        table_bias_text_coverage_min: With above: require text_coverage >= this. None = disabled.
        ocr_score_text_weight: Weight for normalized text strength in OCR score. None = use 0.35.
        ocr_score_image_weight: Weight for image_ratio (image coverage) in OCR score. None = use 0.35.
        ocr_score_noise_weight: Weight for text-layer noise (non-printable / unicode noise). None = use 0.20.
        ocr_score_font_weight: Weight for font signal (embedded fonts). None = use 0.10.

        ocr_decision_threshold: Central threshold for deciding needs_ocr from OCR score (0.0-1.0).
                               Higher score = more likely to need OCR. Default: 0.5.
        ocr_score_low_band_max: Upper bound of the "confidently no OCR" band. Scores <= this
                               are treated as digital unless strong counter-signals exist.
                               Default: 0.30.
        ocr_score_high_band_min: Lower bound of the "confidently needs OCR" band. Scores >= this
                                are treated as needing OCR unless strong counter-signals exist.
                                Default: 0.70.

        hard_digital_text_threshold: Hard Digital Check - if text_length >= this, NO OCR (early exit). Default: 20.
        hard_scan_image_coverage_min: Hard Scan Check - if image_coverage >= this AND text_length <= hard_scan_text_max, OCR. Default: 80.
        hard_scan_text_max: Hard Scan Check - max text_length for hard scan. Default: 20.
        variance_page_escalation_threshold: Only run full page-level when variance(page_scores) > this.
            When variance <= threshold, use doc-level for all pages (speed win for uniform docs). 0 = disabled.

    Example:
        >>> # Use default thresholds
        >>> config = Config()
        >>>
        >>> # Customize for image-heavy domain (e.g. product manuals)
        >>> config = Config(skip_opencv_image_guard=60.0)
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
    confidence_exit_threshold: float = CONFIDENCE_EXIT_THRESHOLD
    confidence_light_refinement_min: float = CONFIDENCE_LIGHT_REFINEMENT_MIN
    skip_opencv_image_guard: float = SKIP_OPENCV_IMAGE_GUARD
    high_confidence: float = HIGH_CONFIDENCE
    medium_confidence: float = MEDIUM_CONFIDENCE
    low_confidence: float = LOW_CONFIDENCE
    use_ocr_score_confidence: bool = True
    skip_opencv_if_file_size_mb: Optional[float] = None
    skip_opencv_if_page_count: Optional[int] = None
    skip_opencv_text_coverage_min: Optional[float] = None
    skip_opencv_confidence_min: Optional[float] = None
    skip_opencv_max_image_coverage: Optional[float] = None
    digital_bias_text_coverage_min: Optional[float] = 65.0
    digital_bias_image_coverage_max: Optional[float] = 50.0
    table_bias_text_density_min: Optional[float] = 1.5
    table_bias_text_coverage_min: Optional[float] = 40.0
    ocr_score_text_weight: Optional[float] = None
    ocr_score_image_weight: Optional[float] = None
    ocr_score_noise_weight: Optional[float] = None
    ocr_score_font_weight: Optional[float] = None
    ocr_decision_threshold: float = 0.5
    ocr_score_low_band_max: float = 0.30
    ocr_score_high_band_min: float = 0.70
    hard_digital_text_threshold: int = HARD_DIGITAL_TEXT_THRESHOLD
    hard_scan_image_coverage_min: float = HARD_SCAN_IMAGE_COVERAGE_MIN
    hard_scan_text_max: int = HARD_SCAN_TEXT_MAX
    variance_page_escalation_threshold: float = 0.2  # 0 = disabled (legacy: variance)
    variance_page_escalation_std: float = (
        0.18  # Enable full page-level when std(page_scores) > this
    )

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

        # Ensure OCR score thresholds and bands are within [0, 1]
        for name, value in [
            ("ocr_decision_threshold", self.ocr_decision_threshold),
            ("ocr_score_low_band_max", self.ocr_score_low_band_max),
            ("ocr_score_high_band_min", self.ocr_score_high_band_min),
        ]:
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0")

        if (
            not self.ocr_score_low_band_max
            <= self.ocr_decision_threshold
            <= self.ocr_score_high_band_min
        ):
            raise ValueError(
                "OCR score thresholds must be ordered: "
                "ocr_score_low_band_max <= ocr_decision_threshold <= ocr_score_high_band_min"
            )

    @classmethod
    def for_scanned_documents(cls) -> "Config":
        """
        Config preset for domains with mostly scanned documents.
        
        Optimizes for:
        - Higher OCR detection rate (low threshold)
        - Strict digital criteria (high bar to skip OCR)
        - Good for: medical PDFs, legal documents, historical scans
        
        Use when: Your document mix is 60%+ scanned/image-heavy
        
        Returns:
            Config optimized for scanned document detection
        """
        return cls(
            min_text_length=50,  # Stricter text requirement
            min_office_text_length=150,  # Office docs need more text
            ocr_score_low_band_max=0.25,  # Lower threshold for "needs OCR" band
            ocr_score_high_band_min=0.65,  # Aggressive OCR detection
            ocr_decision_threshold=0.45,  # Favor OCR decision
            # Digital bias: harder to satisfy (requires high text + low images)
            digital_bias_text_coverage_min=75.0,  # Strict: 75% text minimum
            digital_bias_image_coverage_max=20.0,  # Strict: max 20% images
            # Skip OpenCV to save compute (scans are obvious)
            skip_opencv_if_file_size_mb=50.0,
            skip_opencv_if_page_count=100,
        )

    @classmethod
    def for_cost_optimization(cls) -> "Config":
        """
        Config preset for aggressive OCR skipping to minimize costs.
        
        Optimizes for:
        - Maximize digital PDF detection (skip more OCR runs)
        - Lower confidence thresholds (faster decisions)
        - Good for: high-volume batch processing, e-commerce, SaaS workflows
        
        Use when: Your primary goal is cost reduction, tolerate some false negatives
        
        Returns:
            Config optimized for cost savings
        """
        return cls(
            min_text_length=20,  # Very lenient text requirement
            min_office_text_length=50,  # Office docs: bare minimum
            ocr_score_low_band_max=0.40,  # Generous "digital" band
            ocr_score_high_band_min=0.75,  # High threshold for OCR
            ocr_decision_threshold=0.55,  # Favor skipping OCR
            # Aggressive digital bias
            digital_bias_text_coverage_min=50.0,
            digital_bias_image_coverage_max=70.0,
            # Skip layout analysis on larger files
            skip_opencv_if_file_size_mb=20.0,
            skip_opencv_if_page_count=50,
            confidence_light_refinement_min=0.40,  # Skip heavy refinement
        )

    @classmethod
    def for_tables_and_forms(cls) -> "Config":
        """
        Config preset for structured data extraction (tables, forms, fields).
        
        Optimizes for:
        - Conservative OCR detection (high bar to skip OCR)
        - Table/form-aware decision logic
        - Good for: financial reports, tax forms, invoices, data extraction
        
        Use when: You need tables/forms extracted accurately; false negatives are worse than false positives
        
        Returns:
            Config optimized for structured data preservation
        """
        return cls(
            min_text_length=100,  # Conservative: need real content
            min_office_text_length=200,  # Office docs: substantial content
            ocr_score_low_band_max=0.20,  # Low "confident digital" band
            ocr_score_high_band_min=0.60,  # Lower threshold, favor OCR
            ocr_decision_threshold=0.40,  # Aggressive OCR detection
            # Strict digital bias for tables
            digital_bias_text_coverage_min=80.0,
            digital_bias_image_coverage_max=10.0,
            # Enable table bias to detect tables/forms
            table_bias_text_density_min=1.5,
            table_bias_text_coverage_min=50.0,
            # Always run layout analysis for accuracy
            skip_opencv_if_file_size_mb=None,
            confidence_light_refinement_min=0.0,  # Always refine
        )

    @classmethod
    def for_mixed_content(cls) -> "Config":
        """
        Config preset for balanced processing of mixed document types.
        
        Optimizes for:
        - Balanced OCR/no-OCR decisions
        - Moderate refinement (balance speed and accuracy)
        - Good for: general document pipelines, unknown mixed sources
        
        Use when: You don't know your document distribution in advance
        
        Returns:
            Config with balanced thresholds
        """
        return cls(
            min_text_length=75,
            min_office_text_length=125,
            ocr_score_low_band_max=0.30,
            ocr_score_high_band_min=0.70,
            ocr_decision_threshold=0.50,  # Default middle ground
            digital_bias_text_coverage_min=65.0,
            digital_bias_image_coverage_max=50.0,
            skip_opencv_if_file_size_mb=100.0,
            skip_opencv_if_page_count=200,
        )

    @classmethod
    def high_precision(cls) -> "Config":
        """
        Config preset for maximum accuracy (slower, higher confidence thresholds).
        
        Optimizes for:
        - High confidence in every decision
        - Full layout/OpenCV analysis always
        - Good for: critical documents, compliance, validation workflows
        
        Use when: Accuracy matters more than speed; cost isn't a concern
        
        Returns:
            Config prioritizing decision quality over speed
        """
        return cls(
            min_text_length=150,
            min_office_text_length=250,
            confidence_exit_threshold=0.95,  # Only exit on very high confidence
            confidence_light_refinement_min=0.60,  # Always refine if below 0.60
            ocr_score_low_band_max=0.20,
            ocr_score_high_band_min=0.80,  # High bar for both decisions
            ocr_decision_threshold=0.50,
            skip_opencv_if_file_size_mb=None,  # Never skip layout analysis
            skip_opencv_if_page_count=None,
            digital_bias_text_coverage_min=85.0,  # Very high bar
            digital_bias_image_coverage_max=5.0,
        )


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
