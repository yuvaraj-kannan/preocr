# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.5] - 2026-02-06

### Added
- **Unified OCR_SCORE-Based Confidence Calculation**: New `calculate_confidence_from_signals()` function that aligns confidence scores with OCR_SCORE model for more meaningful confidence values
- **OCR_SCORE Calculation Helper**: Extracted `calculate_ocr_score()` function for reusable pixel-aware scoring model calculation
- **High Image Coverage Detection**: New rule to detect PDFs with >70% image coverage that may contain text in background images, even when extractable text exists
- **Configurable OCR_SCORE Confidence**: Added `use_ocr_score_confidence` flag to Config class (default: True) for optional control

### Changed
- **Improved Image Coverage Detection**: Fixed PyMuPDF to use rendered image sizes (`page.get_image_rects()`) instead of raw dimensions for accurate coverage calculation
- **Library Priority Optimization**: Prioritized PyMuPDF over pdfplumber for image detection (faster ⚡⚡⚡ and more accurate 💯 based on library comparison)
- **Confidence Score Alignment**: Confidence scores now directly reflect OCR_SCORE model (gap reduced from 0.05-0.71 to <0.1)
- **Decision Logic Enhancement**: OpenCV refinement now respects layout analyzer results when OpenCV misses background images
- **Warning Suppression**: Enhanced `suppress_pdf_warnings()` to filter PyMuPDF stderr warnings ("Cannot set gray non-stroke color" messages)

### Fixed
- Fixed PyMuPDF image coverage calculation using raw image dimensions (now uses rendered sizes)
- Fixed OpenCV override issue where it incorrectly classified PDFs with high image coverage as "text_only"
- Fixed confidence score inconsistencies across different decision scenarios
- Suppressed PyMuPDF color pattern warnings that were cluttering output

### Performance
- Faster image detection by prioritizing PyMuPDF (very fast ⚡⚡⚡) over pdfplumber
- More accurate image coverage calculation (73.2% matches expected vs previous incorrect values)

### Accuracy
- **100% accuracy** on test dataset (18/18 files correct)
- **100% precision** - All flagged files actually need OCR
- **100% recall** - All files needing OCR were detected
- **No false positives or false negatives** in test dataset

## [1.0.5] - 2026-02-06

### Added
- **Clean Markdown Output**: Added automatic clean markdown mode when `include_metadata=False` for LLM-ready content without technical metadata
- **Markdown Clean Parameter**: Added `markdown_clean` parameter to `extract_native_data()` for explicit control over markdown formatting
- Clean markdown output excludes file paths, confidence scores, bounding boxes, and other metadata - perfect for LLM consumption

### Changed
- Markdown formatter now automatically uses clean mode when `include_metadata=False` (no need for separate parameter)
- Improved markdown output formatting to respect extraction flags

## [1.0.4] - 2026-02-06

### Fixed
- Fixed PyPI wheel packaging issue: Missing subpackages (core/, utils/, analysis/, probes/, extraction/) now included in distribution
- Added explicit `py.typed` marker file inclusion for type checker support
- Improved package discovery configuration using `packages = {find = {}}` for automatic subpackage detection

## [1.0.3] - 2026-02-06

### Fixed
- Fixed BatchProcessor skipped_files tracking bug

### Changed
- Merge pull request #24 from yuvaraj3855/fix-batch-processor-skipped-files

## [1.0.2] - 2026-02-06

### Fixed
- Improvement
- Bug fixed

### Changed
- Merge pull request #23 from yuvaraj3855/feature/extraction-improvements
- Merge pull request #22 from yuvaraj3855/docs/readme-api-fixes

## [1.0.1] - 2026-02-06

### Fixed
- Fixed unused variable warnings (`table_counter`, `text_width`) in PDF extractor
- Fixed mypy type errors: Added missing `document_type`, `pages_extracted`, `parent_id`, `reading_order`, and `parent_section_id` parameters
- Fixed pydantic import errors in CI/CD workflows by installing dependencies before version extraction
- Improved type annotations for list variables in extraction modules

### Changed
- Disabled `release.yml` workflow to avoid duplication (using `ci-cd-release.yml` exclusively)

## [1.0.0] - 2026-02-05

### Added
- **Structured Data Extraction**: Comprehensive machine-readable document extraction system with support for PDFs, Office documents (DOCX, PPTX, XLSX), and text files
- **Element-Based Structure**: Rich element extraction with classification (Title, NarrativeText, Table, Header, Footer, Image, etc.)
- **Confidence Scoring**: Per-element confidence scores for all extracted content
- **Bounding Boxes**: Precise coordinate information (x0, y0, x1, y1) for all elements
- **Table Extraction**: Advanced table extraction with cell-level metadata and spanning support
- **Form Field Detection**: Form field extraction with semantic naming and type detection
- **Image Detection**: Image location and metadata extraction
- **Section Detection**: Hierarchical section detection with parent-child relationships
- **Reading Order**: Logical reading order for all extracted elements
- **Multiple Output Formats**: Support for Pydantic models, JSON, and Markdown (LLM-ready) output formats
- **Release Management System**: Automated release folder structure with versioned release notes and CI/CD integration

### Changed
- **API Enhancement**: Added `extract_native_data()` function for structured data extraction from machine-readable documents
- **Documentation**: Comprehensive release management documentation and guidelines
- **CI/CD Integration**: Enhanced workflows for automated release file generation and validation

### Fixed
- Improved type safety across all extraction modules
- Enhanced error handling in extraction pipeline

## [0.7.0] - 2026-01-14

### Added
- **Configuration Class**: Added `Config` class for customizable OCR detection thresholds, allowing users to fine-tune sensitivity and decision criteria

## [0.6.0] - 2026-01-14

### Added
- **Major Reorganization**: Implemented comprehensive folder structure reorganization and validation system
- **Enhanced Logging**: Updated logger imports to use centralized logger module

### Changed
- Refactored project structure for better organization and maintainability

## [0.5.3] - 2026-01-10

### Changed
- Refined CI/CD release conditions to include additional skip checks
- Improved release workflow automation

## [0.5.2] - 2026-01-10

### Changed
- Enhanced release workflow with GitHub release creation and version verification
- Improved CI/CD pipeline reliability

## [0.5.1] - 2026-01-07

### Added
- **CI/CD Release Pipeline**: Added automatic version bump and PyPI publishing workflow
- **PyPI Publishing**: Added PyPI API token support as fallback for publishing
- Enhanced batch processing documentation and examples
- Improved README with batch processing feature highlights

### Fixed
- Fixed release workflow permissions and PyPI publishing configuration
- Improved CI/CD workflow version bump detection
- Enhanced test automation workflow documentation

### Changed
- Updated lint workflow to auto-format instead of failing on formatting issues
- Improved batch processing documentation

## [0.5.0] - 2026-01-07

### Added
- **Batch Processing**: Added batch processing functionality with `BatchProcessor` class
- Enhanced batch processing example with argparse and tqdm dependency

### Fixed
- Fixed type annotations in `BatchProcessor` and `BatchResults` classes
- Improved mypy type checking with proper type annotations throughout codebase
- Fixed broken `_extract_html_text` function definition
- Resolved mypy unreachable statement errors with proper type assertions
- Fixed release workflow to handle dynamic version in pyproject.toml

### Changed
- Improved code formatting and style compliance (Black, Ruff)
- Enhanced type safety across all modules

## [0.4.0] - 2024-12-31

### Added
- **Custom Exception Classes**: Added comprehensive exception hierarchy in `preocr/exceptions.py` for better error handling
- **Logging Framework**: Implemented configurable logging system with environment variable support (`PREOCR_LOG_LEVEL`)
- **Caching Support**: Added optional file-based caching for repeated analysis with automatic cache invalidation
- **Progress Callbacks**: Added progress callback support for batch processing operations
- **Type Safety Improvements**: Fixed all type hint inconsistencies (replaced `Dict[str, any]` with `Dict[str, Any]`)
- **CI/CD Pipeline**: Added GitHub Actions workflows for testing, linting, and automated PyPI publishing
- **Pre-commit Hooks**: Configured pre-commit hooks for code quality (Black, Ruff, mypy)
- **Project Documentation**: Added CONTRIBUTING.md, CODE_OF_CONDUCT.md, and py.typed marker file
- **Enhanced Documentation**: Added troubleshooting section and logging configuration to README

### Changed
- **Error Handling**: Replaced bare `except Exception:` with specific exception types throughout codebase
- **Version Management**: Updated `pyproject.toml` to dynamically read version from `preocr/version.py`
- **Type Checking**: Enhanced mypy configuration with stricter type checking settings
- **API Enhancement**: Added `use_cache` and `progress_callback` parameters to `needs_ocr()` function

### Fixed
- Fixed type hint inconsistencies across all modules (19 functions updated)
- Improved error messages with specific exception types and logging
- Enhanced code quality with better error handling patterns

## [0.3.2] - 2024-12-30

### Added
- **Dynamic Confidence Scoring**: Implemented formula-based confidence scores for PDFs (digital and scanned) and OpenCV refinement, providing more granular and accurate confidence levels based on text length, coverage, and ratios.

### Changed
- `preocr/decision.py`: Updated confidence calculation logic to use dynamic formulas instead of fixed thresholds for various PDF scenarios, improving accuracy and granularity of confidence scores.

## [0.3.1] - 2024-12-29

### Changed
- Updated `layout-refinement` dependency to use `opencv-python-headless` (lighter, better for server environments)
- Improved OpenCV layout detection algorithm with adaptive thresholding and better filtering
- Enhanced multi-page analysis: analyzes all pages for small PDFs, smart sampling for large ones
- Improved decision refinement using `layout_type` for more accurate decisions

### Added
- Documentation for libmagic system requirement with OS-specific installation instructions
- Better result structure with OpenCV analysis details in `layout["opencv"]`

### Fixed
- Better handling of missing OpenCV dependencies
- Improved layout display formatting in examples

## [0.3.0] - 2024-12-29

### Added
- **Hybrid pipeline with OpenCV refinement**: Adaptive pipeline that uses fast heuristics for clear cases and OpenCV layout analysis for edge cases
- **Layout-aware detection**: Analyze document layout to detect text regions, image regions, and mixed content
- **Automatic confidence-based refinement**: Low confidence decisions (< 0.9) automatically trigger OpenCV analysis for improved accuracy
- **OpenCV layout analysis module**: Detects text/image regions using computer vision techniques
- **Decision refinement**: Combines heuristics and OpenCV results for better accuracy (92-95% vs 85-90%)
- Optional `layout-refinement` extra dependency for OpenCV support
- New `layout_aware` parameter to `needs_ocr()` function for explicit layout analysis

### Changed
- Improved accuracy for edge cases through hybrid pipeline approach
- Most files stay fast (< 1 second) while edge cases get better analysis (1-2 seconds)
- Decision engine now supports OpenCV-based refinement for low-confidence cases

### Performance
- Clear cases (90%): < 1 second (heuristics only)
- Edge cases (10%): 1-2 seconds (heuristics + OpenCV)
- Overall accuracy: 92-95% (improved from 85-90%)

### Installation
```bash
# Basic installation
pip install preocr

# With OpenCV refinement (recommended)
pip install preocr[layout-refinement]
```

## [0.2.0] - 2024-12-28

### Added
- **Page-level detection**: Analyze PDFs page-by-page to identify which pages need OCR
- **Reason codes**: Structured reason codes (e.g., `PDF_DIGITAL`, `IMAGE_FILE`) for programmatic decision handling
- **Enhanced confidence scoring**: Improved confidence calculation with page-level analysis support
- New `page_level` parameter to `needs_ocr()` function for PDF page-level analysis
- `reason_code` field in API response for structured decision tracking
- Support for mixed PDFs (some pages digital, some scanned)

### Changed
- Decision engine now returns reason codes in addition to human-readable reasons
- Confidence scores are more nuanced based on page-level analysis
- API response structure enhanced with `reason_code` field

### Example Usage
```python
# Page-level analysis
result = needs_ocr("document.pdf", page_level=True)
for page in result["pages"]:
    if page["needs_ocr"]:
        print(f"Page {page['page_number']} needs OCR: {page['reason']}")

# Reason codes
if result["reason_code"] == "PDF_MIXED":
    # Handle mixed PDF (some pages need OCR, some don't)
    pass
```

## [0.1.1] - 2024-12-28

### Changed
- Updated GitHub URLs in package metadata to point to correct repository
- Fixed license format in pyproject.toml (use string instead of table)
- Removed deprecated license classifier

## [0.1.0] - 2024-12-28

### Added
- Initial release
- File type detection using python-magic with fallback to mimetypes
- Text extraction probes for PDF, Office documents (DOCX, PPTX, XLSX), and plain text files
- Image analysis with entropy calculation
- Decision engine to determine if OCR is needed
- Main API: `needs_ocr()` function
- Comprehensive test suite
- Documentation and examples

[Unreleased]: https://github.com/yuvaraj3855/preocr/compare/v1.0.5...HEAD
[1.0.5]: https://github.com/yuvaraj3855/preocr/releases/tag/v1.0.5
[1.0.4]: https://github.com/yuvaraj3855/preocr/releases/tag/v1.0.4
[1.0.3]: https://github.com/yuvaraj3855/preocr/releases/tag/v1.0.3
[1.0.2]: https://github.com/yuvaraj3855/preocr/releases/tag/v1.0.2
[1.0.1]: https://github.com/yuvaraj3855/preocr/releases/tag/v1.0.1
[1.0.0]: https://github.com/yuvaraj3855/preocr/releases/tag/v1.0.0
[0.7.0]: https://github.com/yuvaraj3855/preocr/releases/tag/v0.7.0
[0.6.0]: https://github.com/yuvaraj3855/preocr/releases/tag/v0.6.0
[0.5.3]: https://github.com/yuvaraj3855/preocr/releases/tag/v0.5.3
[0.5.2]: https://github.com/yuvaraj3855/preocr/releases/tag/v0.5.2
[0.5.1]: https://github.com/yuvaraj3855/preocr/releases/tag/v0.5.1
[0.5.0]: https://github.com/yuvaraj3855/preocr/releases/tag/v0.5.0
[0.4.0]: https://github.com/yuvaraj3855/preocr/releases/tag/v0.4.0
[0.3.2]: https://github.com/yuvaraj3855/preocr/releases/tag/v0.3.2
[0.3.1]: https://github.com/yuvaraj3855/preocr/releases/tag/v0.3.1
[0.3.0]: https://github.com/yuvaraj3855/preocr/releases/tag/v0.3.0
[0.2.0]: https://github.com/yuvaraj3855/preocr/releases/tag/v0.2.0
[0.1.1]: https://github.com/yuvaraj3855/preocr/releases/tag/v0.1.1
[0.1.0]: https://github.com/yuvaraj3855/preocr/releases/tag/v0.1.0

