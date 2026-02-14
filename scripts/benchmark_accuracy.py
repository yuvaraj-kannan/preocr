#!/usr/bin/env python3
"""
Comprehensive benchmark script that measures both performance AND accuracy.

This script combines performance benchmarking with accuracy validation.
"""

import json
import time
import statistics
from pathlib import Path
from typing import Dict, Optional
from collections import defaultdict

from preocr import needs_ocr
from validate_accuracy import AccuracyValidator


def benchmark_with_accuracy(
    directory: Path,
    ground_truth_file: Optional[str] = None,
    layout_aware: bool = False,
    page_level: bool = False,
    max_files: Optional[int] = None,
    max_size_mb: Optional[float] = None,
) -> Dict:
    """
    Benchmark both performance and accuracy.

    Args:
        directory: Directory containing files to benchmark
        ground_truth_file: Path to ground truth JSON file (optional)
        layout_aware: Whether to use layout-aware analysis
        page_level: Whether to use page-level analysis
        max_files: Maximum number of files to process

    Returns:
        Dictionary with benchmark and accuracy results
    """
    # Get files
    extensions = [
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".tiff",
        ".tif",
        ".docx",
        ".pptx",
        ".xlsx",
        ".txt",
    ]
    files = []
    for ext in extensions:
        files.extend(directory.glob(f"*{ext}"))
        files.extend(directory.glob(f"*{ext.upper()}"))

    files = sorted(set(files))
    if max_size_mb is not None:
        max_bytes = max_size_mb * 1024 * 1024
        files = [f for f in files if f.stat().st_size <= max_bytes]
    if max_files:
        files = files[:max_files]

    if not files:
        return {"error": "No files found"}

    print(f"📊 Benchmarking {len(files)} files...")
    print("=" * 80)

    # Performance benchmarking
    performance_results = []
    for i, file_path in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {file_path.name}...", end=" ", flush=True)

        result = {
            "file": str(file_path),
            "file_name": file_path.name,
            "size_mb": file_path.stat().st_size / (1024 * 1024),
        }

        # Time the analysis
        start = time.perf_counter()
        try:
            ocr_result = needs_ocr(file_path, layout_aware=layout_aware, page_level=page_level)
            elapsed = time.perf_counter() - start

            result.update(
                {
                    "time": elapsed,
                    "needs_ocr": ocr_result["needs_ocr"],
                    "confidence": ocr_result["confidence"],
                    "reason_code": ocr_result["reason_code"],
                    "file_type": ocr_result.get("file_type", "unknown"),
                    "error": None,
                }
            )

            if ocr_result.get("file_type") == "pdf":
                result["page_count"] = ocr_result.get("page_count", 0)

            print(f"✅ {elapsed*1000:.0f}ms")
        except Exception as e:
            result["error"] = str(e)
            print(f"❌ Error: {e}")

        performance_results.append(result)

    # Accuracy validation (if ground truth provided)
    accuracy_metrics = None
    if ground_truth_file and Path(ground_truth_file).exists():
        print("\n📊 Validating accuracy...")
        validator = AccuracyValidator(ground_truth_file)
        validation_results = validator.validate_directory(
            directory, layout_aware=layout_aware, page_level=page_level
        )
        accuracy_metrics = validator.calculate_metrics(validation_results)

    # Calculate performance statistics
    valid_times = [r["time"] for r in performance_results if r.get("time") is not None]
    if valid_times:
        perf_stats = {
            "min": min(valid_times),
            "max": max(valid_times),
            "mean": statistics.mean(valid_times),
            "median": statistics.median(valid_times),
            "p95": (
                sorted(valid_times)[int(len(valid_times) * 0.95)]
                if len(valid_times) > 1
                else valid_times[0]
            ),
        }
    else:
        perf_stats = {}

    # Group by file type
    by_type = defaultdict(list)
    for r in performance_results:
        if r.get("file_type"):
            by_type[r["file_type"]].append(r)

    return {
        "total_files": len(files),
        "performance": {
            "statistics": perf_stats,
            "results": performance_results,
            "by_type": {
                ft: {
                    "count": len(results),
                    "avg_time": statistics.mean([r["time"] for r in results if r.get("time")]),
                    "median_time": statistics.median([r["time"] for r in results if r.get("time")]),
                }
                for ft, results in by_type.items()
            },
        },
        "accuracy": accuracy_metrics,
    }


def print_comprehensive_report(results: Dict) -> None:
    """Print comprehensive benchmark and accuracy report."""
    print("\n" + "=" * 80)
    print("📊 COMPREHENSIVE BENCHMARK REPORT")
    print("=" * 80)

    # Performance section
    perf = results.get("performance", {})
    stats = perf.get("statistics", {})

    if stats:
        print("\n⚡ Performance Metrics:")
        print(f"   Total files: {results['total_files']}")
        print(f"   Min time:    {stats['min']*1000:.0f}ms")
        print(f"   Max time:    {stats['max']*1000:.0f}ms")
        print(f"   Mean time:   {stats['mean']*1000:.0f}ms")
        print(f"   Median time: {stats['median']*1000:.0f}ms")
        print(f"   P95 time:    {stats['p95']*1000:.0f}ms")

        # By file type
        by_type = perf.get("by_type", {})
        if by_type:
            print("\n📋 Performance by File Type:")
            for file_type, type_stats in sorted(by_type.items()):
                print(
                    f"   {file_type:12} {type_stats['count']:3} files, "
                    f"avg: {type_stats['avg_time']*1000:.0f}ms, "
                    f"median: {type_stats['median_time']*1000:.0f}ms"
                )

    # Accuracy section
    accuracy = results.get("accuracy")
    if accuracy and "error" not in accuracy:
        print("\n🎯 Accuracy Metrics:")
        metrics = accuracy["metrics"]
        print(f"   Overall Accuracy: {metrics['accuracy']:.2f}%")
        print(f"   Precision:        {metrics['precision']:.2f}%")
        print(f"   Recall:           {metrics['recall']:.2f}%")
        print(f"   F1-Score:         {metrics['f1_score']:.2f}%")

        cm = accuracy["confusion_matrix"]
        print("\n   Confusion Matrix:")
        print(f"     TP: {cm['true_positive']}, FP: {cm['false_positive']}")
        print(f"     TN: {cm['true_negative']}, FN: {cm['false_negative']}")

        if accuracy.get("by_type"):
            print("\n   Accuracy by File Type:")
            for file_type, type_stats in sorted(accuracy["by_type"].items()):
                print(
                    f"     {file_type:12} {type_stats['accuracy']:.1f}% "
                    f"({type_stats['correct']}/{type_stats['total']} files)"
                )
    elif accuracy and "error" in accuracy:
        print(f"\n⚠️  Accuracy validation skipped: {accuracy['error']}")
    else:
        print("\n⚠️  Accuracy validation skipped (no ground truth file)")

    print("\n" + "=" * 80)


def main():
    """Main benchmark function."""
    import argparse

    parser = argparse.ArgumentParser(description="Comprehensive benchmark (performance + accuracy)")
    parser.add_argument("directory", type=str, help="Directory containing files to benchmark")
    parser.add_argument(
        "--ground-truth",
        "-g",
        type=str,
        help="Path to ground truth JSON file for accuracy validation",
    )
    parser.add_argument(
        "--layout-aware",
        action="store_true",
        help="Use layout-aware analysis",
    )
    parser.add_argument(
        "--page-level",
        action="store_true",
        help="Use page-level analysis",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        help="Maximum number of files to process",
    )
    parser.add_argument(
        "--max-size-mb",
        type=float,
        help="Only process files <= this size in MB (e.g. 0.5 for 500KB)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output JSON file for results",
    )

    args = parser.parse_args()

    directory = Path(args.directory)
    if not directory.exists():
        print(f"❌ Error: Directory not found: {directory}")
        return

    # Run benchmark
    results = benchmark_with_accuracy(
        directory,
        ground_truth_file=args.ground_truth,
        layout_aware=args.layout_aware,
        page_level=args.page_level,
        max_files=args.max_files,
        max_size_mb=args.max_size_mb,
    )

    if "error" in results:
        print(f"❌ Error: {results['error']}")
        return

    # Print report
    print_comprehensive_report(results)

    # Save results if requested
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n✅ Results saved to: {args.output}")


if __name__ == "__main__":
    main()
