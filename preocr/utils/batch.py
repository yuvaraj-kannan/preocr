"""Enhanced batch processing for PreOCR with parallel processing, caching, and progress tracking."""

import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .. import constants
from ..core.detector import needs_ocr
from .logger import get_logger

Config = constants.Config
logger = get_logger(__name__)

# Try to import tqdm for progress bars, but make it optional
try:
    from tqdm import tqdm

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

    # Create a dummy tqdm class if not available
    class tqdm:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def update(self, n=1):
            pass

        def set_description(self, desc):
            pass


def _process_single_file(
    file_path: str,
    use_cache: bool,
    layout_aware: bool,
    page_level: bool,
    config: Optional[Config] = None,
) -> Dict[str, Any]:
    """
    Process a single file (used by ProcessPoolExecutor).

    This function must be at module level for pickling in multiprocessing.

    Args:
        file_path: Path to file to process
        use_cache: Whether to use caching
        layout_aware: Whether to perform layout analysis
        page_level: Whether to perform page-level analysis
        config: Optional Config object with threshold settings

    Returns:
        Result dictionary with file_path added
    """
    try:
        result = needs_ocr(
            file_path,
            page_level=page_level,
            layout_aware=layout_aware,
            use_cache=use_cache,
            config=config,
        )
        result["file_path"] = file_path
        result["error"] = None
        return result
    except Exception as e:
        # Return error result instead of raising
        return {
            "file_path": file_path,
            "needs_ocr": None,
            "error": str(e),
            "error_type": type(e).__name__,
        }


class BatchResults:
    """Container for batch processing results."""

    def __init__(self) -> None:
        self.results: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.total_files: int = 0
        self.processed_files: int = 0
        self.skipped_files: int = 0

    def add_result(self, result: Dict[str, Any]) -> None:
        """Add a result to the batch."""
        if result.get("error"):
            self.errors.append(result)
        else:
            self.results.append(result)
        self.processed_files += 1

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the batch processing."""
        total = len(self.results) + len(self.errors)
        needs_ocr_count = sum(1 for r in self.results if r.get("needs_ocr") is True)
        no_ocr_count = sum(1 for r in self.results if r.get("needs_ocr") is False)
        error_count = len(self.errors)

        # Page-level statistics
        total_pages = sum(r.get("page_count", 0) for r in self.results)
        total_pages_needing_ocr = sum(r.get("pages_needing_ocr", 0) for r in self.results)
        total_pages_with_text = sum(r.get("pages_with_text", 0) for r in self.results)
        files_with_pages = sum(1 for r in self.results if r.get("page_count", 0) > 0)

        # Group by file type
        by_type: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"total": 0, "needs_ocr": 0, "pages": 0, "pages_needing_ocr": 0}
        )
        for result in self.results:
            file_type = result.get("file_type", "unknown")
            by_type[file_type]["total"] += 1
            if result.get("needs_ocr"):
                by_type[file_type]["needs_ocr"] += 1
            by_type[file_type]["pages"] += result.get("page_count", 0)
            by_type[file_type]["pages_needing_ocr"] += result.get("pages_needing_ocr", 0)

        # Group by reason code
        by_reason: Dict[str, int] = defaultdict(int)
        for result in self.results:
            reason_code = result.get("reason_code", "UNKNOWN")
            by_reason[reason_code] += 1

        processing_time = None
        if self.start_time and self.end_time:
            processing_time = self.end_time - self.start_time

        return {
            "total_files": total,
            "processed": len(self.results),
            "errors": error_count,
            "skipped": self.skipped_files,
            "needs_ocr": needs_ocr_count,
            "no_ocr": no_ocr_count,
            "total_pages": total_pages,
            "total_pages_needing_ocr": total_pages_needing_ocr,
            "total_pages_with_text": total_pages_with_text,
            "files_with_pages": files_with_pages,
            "by_type": dict(by_type),
            "by_reason": dict(by_reason),
            "processing_time": processing_time,
            "files_per_second": (
                len(self.results) / processing_time
                if processing_time and processing_time > 0
                else None
            ),
        }

    def print_summary(self) -> None:
        """Print a formatted summary of results."""
        stats = self.get_statistics()

        print("\n" + "=" * 80)
        print("BATCH PROCESSING SUMMARY")
        print("=" * 80)

        print(f"\nTotal files found: {self.total_files}")
        print(f"Files processed: {stats['processed']}")
        if stats["skipped"] > 0:
            print(f"Files skipped (cached/resumed): {stats['skipped']}")
        if stats["errors"] > 0:
            print(f"Files with errors: {stats['errors']}")

        if stats["processed"] > 0:
            print("\nOCR Decision:")
            print(
                f"  Files needing OCR: {stats['needs_ocr']} ({stats['needs_ocr'] / stats['processed'] * 100:.1f}%)"
            )
            print(
                f"  Files ready (no OCR): {stats['no_ocr']} ({stats['no_ocr'] / stats['processed'] * 100:.1f}%)"
            )

            # Page-level statistics
            if stats.get("total_pages", 0) > 0:
                print("\nPage-Level Statistics:")
                print(f"  Total pages processed: {stats['total_pages']}")
                print(
                    f"  Pages needing OCR: {stats['total_pages_needing_ocr']} ({stats['total_pages_needing_ocr'] / stats['total_pages'] * 100:.1f}%)"
                )
                print(
                    f"  Pages ready (no OCR): {stats['total_pages_with_text']} ({stats['total_pages_with_text'] / stats['total_pages'] * 100:.1f}%)"
                )
                print(f"  Files with pages: {stats['files_with_pages']}")

        if stats["processing_time"]:
            print("\nPerformance:")
            time_seconds = stats["processing_time"]
            if time_seconds < 60:
                time_str = f"{time_seconds:.2f} seconds"
            elif time_seconds < 3600:
                minutes = int(time_seconds // 60)
                seconds = time_seconds % 60
                time_str = f"{minutes}m {seconds:.1f}s"
            else:
                hours = int(time_seconds // 3600)
                minutes = int((time_seconds % 3600) // 60)
                seconds = time_seconds % 60
                time_str = f"{hours}h {minutes}m {seconds:.1f}s"
            print(f"  Total time: {time_str}")
            if stats["files_per_second"]:
                print(f"  Processing speed: {stats['files_per_second']:.2f} files/sec")

        if stats["by_type"]:
            print("\nBreakdown by file type:")
            for file_type, type_stats in sorted(stats["by_type"].items()):
                pct = (
                    type_stats["needs_ocr"] / type_stats["total"] * 100
                    if type_stats["total"] > 0
                    else 0
                )
                page_info = ""
                if type_stats.get("pages", 0) > 0:
                    page_info = f", {type_stats['pages']} pages ({type_stats['pages_needing_ocr']} need OCR)"
                print(
                    f"  {file_type:12} {type_stats['total']:3} files, "
                    f"{type_stats['needs_ocr']:2} need OCR ({pct:5.1f}%){page_info}"
                )

        if stats["errors"] > 0:
            print(f"\nErrors ({stats['errors']} files):")
            for error in self.errors[:10]:  # Show first 10 errors
                print(f"  {Path(error['file_path']).name}: {error.get('error', 'Unknown error')}")
            if stats["errors"] > 10:
                print(f"  ... and {stats['errors'] - 10} more errors")

        print("\n" + "=" * 80)


class BatchProcessor:
    """Enhanced batch processor with parallel processing, caching, and progress tracking."""

    def __init__(
        self,
        max_workers: Optional[int] = None,
        use_cache: bool = True,
        layout_aware: bool = False,
        page_level: bool = True,  # Enable page-level by default for better insights
        extensions: Optional[List[str]] = None,
        min_size: Optional[int] = None,
        max_size: Optional[int] = None,
        recursive: bool = False,
        resume_from: Optional[str] = None,
        # Threshold customization parameters
        min_text_length: Optional[int] = None,
        min_office_text_length: Optional[int] = None,
        layout_refinement_threshold: Optional[float] = None,
        high_confidence: Optional[float] = None,
        medium_confidence: Optional[float] = None,
        low_confidence: Optional[float] = None,
        config: Optional[Config] = None,
    ) -> None:
        """
        Initialize batch processor.

        Args:
            max_workers: Maximum number of parallel workers (default: CPU count)
            use_cache: Enable caching to skip already-processed files
            layout_aware: Perform layout analysis for PDFs
            page_level: Perform page-level analysis for PDFs
            extensions: List of file extensions to process (e.g., [".pdf", ".png"])
                       If None, processes common document/image formats
            min_size: Minimum file size in bytes (None = no limit)
            max_size: Maximum file size in bytes (None = no limit)
            recursive: Scan subdirectories recursively
            resume_from: Path to JSON file with previous results to resume from
            min_text_length: Minimum text length threshold (overrides config if provided)
            min_office_text_length: Minimum office text length threshold (overrides config if provided)
            layout_refinement_threshold: Layout refinement threshold (overrides config if provided)
            high_confidence: High confidence threshold (overrides config if provided)
            medium_confidence: Medium confidence threshold (overrides config if provided)
            low_confidence: Low confidence threshold (overrides config if provided)
            config: Optional Config object with threshold settings. If provided, individual
                   threshold parameters override config values.
        """
        import multiprocessing

        self.max_workers = max_workers or multiprocessing.cpu_count()
        self.use_cache = use_cache
        self.layout_aware = layout_aware
        self.page_level = page_level
        self.extensions = extensions
        self.min_size = min_size
        self.max_size = max_size
        self.recursive = recursive
        self.resume_from = resume_from

        # Handle config: use provided config or create from individual parameters
        if config is None:
            config = Config()

        # Override config values with individual parameters if provided
        if min_text_length is not None:
            config.min_text_length = min_text_length
        if min_office_text_length is not None:
            config.min_office_text_length = min_office_text_length
        if layout_refinement_threshold is not None:
            config.layout_refinement_threshold = layout_refinement_threshold
        if high_confidence is not None:
            config.high_confidence = high_confidence
        if medium_confidence is not None:
            config.medium_confidence = medium_confidence
        if low_confidence is not None:
            config.low_confidence = low_confidence

        self.config = config

        # Default extensions if not specified
        if self.extensions is None:
            default_extensions = [
                ".pdf",
                ".png",
                ".jpg",
                ".jpeg",
                ".tiff",
                ".tif",
                ".bmp",
                ".gif",
                ".docx",
                ".pptx",
                ".xlsx",
                ".txt",
                ".html",
                ".htm",
            ]
            self.extensions = default_extensions

        # Normalize extensions (lowercase, with dot)
        # At this point, self.extensions is guaranteed to be a List[str] (not None)
        assert self.extensions is not None  # Help mypy understand type narrowing
        self.extensions = [
            ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in self.extensions
        ]

        # Track already processed files for resume
        self._processed_files: Set[str] = set()
        if resume_from and Path(resume_from).exists():
            self._load_resume_file(resume_from)

    def _load_resume_file(self, resume_file: str) -> None:
        """Load previously processed files from resume file."""
        import json

        try:
            with open(resume_file, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    # List of results
                    for result in data:
                        if "file_path" in result:
                            self._processed_files.add(result["file_path"])
                elif isinstance(data, dict) and "results" in data:
                    # BatchResults-like structure
                    for result in data.get("results", []):
                        if "file_path" in result:
                            self._processed_files.add(result["file_path"])
            logger.info(f"Loaded {len(self._processed_files)} files from resume file")
        except Exception as e:
            logger.warning(f"Failed to load resume file: {e}")

    def _collect_files(self, directory: Union[str, Path]) -> Tuple[List[Path], int]:
        """
        Collect files to process from directory.

        Args:
            directory: Directory to scan

        Returns:
            Tuple of (list of file paths to process, number of skipped files)
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        if not dir_path.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")

        files: List[Path] = []

        # Build pattern for glob
        if self.recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        # Collect all matching files
        # self.extensions is guaranteed to be List[str] after __init__ (never None)
        assert self.extensions is not None  # Help mypy understand type narrowing
        for ext in self.extensions:
            # Case-insensitive matching
            files.extend(dir_path.glob(f"{pattern}{ext}"))
            files.extend(dir_path.glob(f"{pattern}{ext.upper()}"))

        # Remove duplicates and sort
        files = sorted(set(files))

        # Filter by size
        if self.min_size is not None or self.max_size is not None:
            filtered_files = []
            for file_path in files:
                try:
                    size = file_path.stat().st_size
                    if self.min_size is not None and size < self.min_size:
                        continue
                    if self.max_size is not None and size > self.max_size:
                        continue
                    filtered_files.append(file_path)
                except OSError:
                    # Skip files we can't stat
                    continue
            files = filtered_files

        # Filter out already processed files (for resume) and count skipped
        skipped_count = 0
        if self._processed_files:
            all_files_count = len(files)
            files = [f for f in files if str(f) not in self._processed_files]
            skipped_count = all_files_count - len(files)

        return files, skipped_count

    def process_directory(
        self,
        directory: Union[str, Path],
        progress: bool = True,
    ) -> BatchResults:
        """
        Process all files in a directory.

        Args:
            directory: Directory to process
            progress: Show progress bar (requires tqdm)

        Returns:
            BatchResults object with all results
        """
        results = BatchResults()
        results.start_time = time.time()

        # Collect files
        files, skipped_count = self._collect_files(directory)
        results.total_files = len(files)
        results.skipped_files = skipped_count

        if not files:
            logger.info("No files found to process")
            results.end_time = time.time()
            return results

        logger.info(f"Processing {len(files)} files with {self.max_workers} workers")

        # Prepare arguments for worker function
        process_args = [
            (
                str(file_path),
                self.use_cache,
                self.layout_aware,
                self.page_level,
                self.config,
            )
            for file_path in files
        ]

        # Process files
        if progress and TQDM_AVAILABLE:
            with tqdm(
                total=len(files),
                desc="Processing",
                unit="file",
                unit_scale=False,
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{percentage:3.0f}%] "
                "{elapsed}<{remaining}, {rate_fmt}",
                ncols=100,
            ) as pbar:
                with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                    # Submit all tasks
                    future_to_file = {
                        executor.submit(_process_single_file, *args): args[0]
                        for args in process_args
                    }

                    # Process completed tasks
                    for future in as_completed(future_to_file):
                        file_path = future_to_file[future]
                        try:
                            result = future.result()
                            results.add_result(result)
                            # Update progress bar with current file name and page info
                            file_name = Path(file_path).name[:40]
                            status = "✓" if not result.get("error") else "✗"

                            # Show page information if available
                            page_info = ""
                            if result.get("page_count"):
                                page_count = result.get("page_count", 0)
                                pages_needing_ocr = result.get("pages_needing_ocr", 0)
                                pages_with_text = result.get("pages_with_text", 0)
                                if page_count > 0:
                                    page_info = f" ({page_count} pages"
                                    if pages_needing_ocr > 0 or pages_with_text > 0:
                                        page_info += f", {pages_needing_ocr} need OCR, {pages_with_text} ready"
                                    page_info += ")"

                            desc = f"Processing [{status}] {file_name}{page_info}"
                            pbar.set_description(desc, refresh=False)
                            pbar.update(1)
                        except Exception as e:
                            logger.error(f"Unexpected error processing {file_path}: {e}")
                            results.add_result(
                                {
                                    "file_path": file_path,
                                    "error": str(e),
                                    "error_type": type(e).__name__,
                                }
                            )
                            file_name = Path(file_path).name[:50]
                            pbar.set_description(f"Processing [✗] {file_name}", refresh=False)
                            pbar.update(1)
        else:
            # Process without progress bar
            if progress and not TQDM_AVAILABLE:
                logger.warning(
                    "Progress bar requested but tqdm not installed. Install with: pip install tqdm"
                )

            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_file = {
                    executor.submit(_process_single_file, *args): args[0] for args in process_args
                }

                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        result = future.result()
                        results.add_result(result)
                        if not progress:
                            logger.debug(f"Processed {file_path}")
                    except Exception as e:
                        logger.error(f"Unexpected error processing {file_path}: {e}")
                        results.add_result(
                            {
                                "file_path": file_path,
                                "error": str(e),
                                "error_type": type(e).__name__,
                            }
                        )

        results.end_time = time.time()
        return results
