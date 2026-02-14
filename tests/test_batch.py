"""Tests for BatchProcessor."""

import json
import tempfile
from pathlib import Path

import pytest

from preocr.utils.batch import BatchProcessor, BatchResults


def test_batch_processor_initialization():
    """Test BatchProcessor initialization."""
    processor = BatchProcessor()
    assert processor.max_workers > 0
    assert processor.use_cache is True
    assert processor.layout_aware is False
    assert processor.page_level is True
    assert processor.extensions is not None
    assert len(processor.extensions) > 0


def test_batch_processor_custom_settings():
    """Test BatchProcessor with custom settings."""
    processor = BatchProcessor(
        max_workers=2,
        use_cache=False,
        layout_aware=True,
        page_level=False,
        extensions=[".pdf", ".txt"],
        recursive=True,
    )
    assert processor.max_workers == 2
    assert processor.use_cache is False
    assert processor.layout_aware is True
    assert processor.page_level is False
    assert ".pdf" in processor.extensions
    assert ".txt" in processor.extensions
    assert processor.recursive is True


def test_batch_results_initialization():
    """Test BatchResults initialization."""
    results = BatchResults()
    assert results.results == []
    assert results.errors == []
    assert results.start_time is None
    assert results.end_time is None
    assert results.total_files == 0
    assert results.processed_files == 0
    assert results.skipped_files == 0


def test_batch_results_add_result():
    """Test adding results to BatchResults."""
    results = BatchResults()

    # Add successful result
    result1 = {
        "file_path": "/path/to/file1.txt",
        "needs_ocr": False,
        "file_type": "text",
    }
    results.add_result(result1)
    assert len(results.results) == 1
    assert len(results.errors) == 0
    assert results.processed_files == 1

    # Add error result
    result2 = {
        "file_path": "/path/to/file2.txt",
        "error": "Test error",
    }
    results.add_result(result2)
    assert len(results.results) == 1
    assert len(results.errors) == 1
    assert results.processed_files == 2


def test_batch_results_statistics():
    """Test BatchResults statistics."""
    results = BatchResults()
    results.start_time = 1000.0
    results.end_time = 1005.0

    results.add_result({"file_path": "file1.txt", "needs_ocr": True, "file_type": "text"})
    results.add_result({"file_path": "file2.txt", "needs_ocr": False, "file_type": "text"})
    results.add_result({"file_path": "file3.txt", "needs_ocr": True, "file_type": "pdf"})
    results.add_result({"file_path": "file4.txt", "error": "Error message"})

    stats = results.get_statistics()
    assert stats["total_files"] == 4
    assert stats["processed"] == 3
    assert stats["errors"] == 1
    assert stats["needs_ocr"] == 2
    assert stats["no_ocr"] == 1
    assert stats["processing_time"] == 5.0
    assert stats["files_per_second"] == pytest.approx(0.6, rel=0.1)


def test_collect_files_basic():
    """Test _collect_files with basic directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        test_dir = Path(tmpdir)
        (test_dir / "file1.txt").write_text("Test content 1")
        (test_dir / "file2.txt").write_text("Test content 2")
        (test_dir / "file3.pdf").write_text("PDF content")

        processor = BatchProcessor(extensions=[".txt", ".pdf"])
        files, skipped = processor._collect_files(test_dir)

        assert len(files) == 3
        assert skipped == 0
        file_names = [f.name for f in files]
        assert "file1.txt" in file_names
        assert "file2.txt" in file_names
        assert "file3.pdf" in file_names


def test_collect_files_with_resume():
    """Test _collect_files with resume functionality - verifies skipped_files fix."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        test_dir = Path(tmpdir)
        (test_dir / "file1.txt").write_text("Test content 1")
        (test_dir / "file2.txt").write_text("Test content 2")
        (test_dir / "file3.txt").write_text("Test content 3")
        (test_dir / "file4.txt").write_text("Test content 4")

        # Create resume file with file1 and file2 already processed
        resume_file = test_dir / "resume.json"
        resume_data = [
            {"file_path": str(test_dir / "file1.txt"), "needs_ocr": False},
            {"file_path": str(test_dir / "file2.txt"), "needs_ocr": True},
        ]
        resume_file.write_text(json.dumps(resume_data))

        processor = BatchProcessor(
            extensions=[".txt"],
            resume_from=str(resume_file),
        )
        files, skipped = processor._collect_files(test_dir)

        # Should only process file3 and file4, skipping file1 and file2
        assert len(files) == 2
        assert skipped == 2  # This verifies the fix - skipped_files should be tracked
        file_names = [f.name for f in files]
        assert "file1.txt" not in file_names
        assert "file2.txt" not in file_names
        assert "file3.txt" in file_names
        assert "file4.txt" in file_names


def test_collect_files_with_size_filter():
    """Test _collect_files with size filtering."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        # Create files of different sizes
        (test_dir / "small.txt").write_text("x" * 100)  # 100 bytes
        (test_dir / "medium.txt").write_text("x" * 5000)  # 5000 bytes
        (test_dir / "large.txt").write_text("x" * 15000)  # 15000 bytes

        processor = BatchProcessor(
            extensions=[".txt"],
            min_size=1000,  # 1KB minimum
            max_size=10000,  # 10KB maximum
        )
        files, skipped = processor._collect_files(test_dir)

        # Should only include medium.txt (between min and max)
        assert len(files) == 1
        assert files[0].name == "medium.txt"


def test_process_directory_empty():
    """Test process_directory with empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        processor = BatchProcessor()
        results = processor.process_directory(tmpdir, progress=False)

        assert results.total_files == 0
        assert results.skipped_files == 0
        assert len(results.results) == 0
        assert results.start_time is not None
        assert results.end_time is not None


def test_process_directory_with_files():
    """Test process_directory with actual files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        (test_dir / "file1.txt").write_text("This is a test file with enough text content.")
        (test_dir / "file2.txt").write_text("Another test file with sufficient content.")

        processor = BatchProcessor(
            extensions=[".txt"],
            use_cache=False,
            page_level=False,
        )
        results = processor.process_directory(test_dir, progress=False)

        assert results.total_files == 2
        assert results.skipped_files == 0
        assert len(results.results) == 2
        assert all("file_path" in r for r in results.results)
        assert all("needs_ocr" in r for r in results.results)


def test_process_directory_with_resume_tracking():
    """Test that skipped_files is correctly tracked when using resume_from."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)
        (test_dir / "file1.txt").write_text("Test content 1")
        (test_dir / "file2.txt").write_text("Test content 2")
        (test_dir / "file3.txt").write_text("Test content 3")

        # Create resume file
        resume_file = test_dir / "resume.json"
        resume_data = [
            {"file_path": str(test_dir / "file1.txt"), "needs_ocr": False},
        ]
        resume_file.write_text(json.dumps(resume_data))

        processor = BatchProcessor(
            extensions=[".txt"],
            resume_from=str(resume_file),
            use_cache=False,
            page_level=False,
        )
        results = processor.process_directory(test_dir, progress=False)

        # Should process 2 files (file2 and file3), skip 1 (file1)
        assert results.total_files == 2
        assert results.skipped_files == 1  # This is the key test - verifying the fix
        assert len(results.results) == 2
        processed_files = [r["file_path"] for r in results.results]
        assert str(test_dir / "file1.txt") not in processed_files
        assert str(test_dir / "file2.txt") in processed_files
        assert str(test_dir / "file3.txt") in processed_files

        # Verify statistics show skipped files
        stats = results.get_statistics()
        assert stats["skipped"] == 1
