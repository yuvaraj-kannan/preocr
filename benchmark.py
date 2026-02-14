#!/usr/bin/env python3
"""Benchmark script for PreOCR performance analysis."""

import time
import statistics
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from preocr import needs_ocr
from preocr.analysis.opencv_layout import analyze_with_opencv


def format_time(seconds: float) -> str:
    """Format time in seconds to readable string."""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    return f"{seconds:.2f}s"


def benchmark_file(file_path: Path) -> Dict:
    """Benchmark a single file."""
    result = {
        "file": file_path.name,
        "size_mb": file_path.stat().st_size / (1024 * 1024),
        "fast_path_time": None,
        "opencv_time": None,
        "total_time": None,
        "confidence": None,
        "needs_ocr": None,
        "page_count": None,
        "opencv_triggered": False,
    }

    # Test fast path (heuristics only)
    start = time.perf_counter()
    fast_result = needs_ocr(file_path, layout_aware=False)
    fast_time = time.perf_counter() - start

    result["fast_path_time"] = fast_time
    result["confidence"] = fast_result["confidence"]
    result["needs_ocr"] = fast_result["needs_ocr"]

    # Get page count if PDF
    if fast_result.get("file_type") == "pdf":
        result["page_count"] = fast_result.get("signals", {}).get("page_count", 0)

    # Always test OpenCV for benchmark (force analysis)
    # Check if OpenCV is available first
    try:
        import cv2  # noqa: F401
        import numpy as np  # noqa: F401
        import fitz  # noqa: F401

        opencv_available = True
    except ImportError:
        opencv_available = False
        result["opencv_time"] = None
        result["opencv_triggered"] = False
        result["opencv_error"] = "OpenCV dependencies not installed"

    if opencv_available:
        start = time.perf_counter()
        opencv_result = analyze_with_opencv(str(file_path))
        opencv_time = time.perf_counter() - start

        if opencv_result:
            result["opencv_time"] = opencv_time
            result["opencv_triggered"] = True
            result["pages_analyzed"] = opencv_result.get("total_pages", 0)
        else:
            result["opencv_time"] = None
            result["opencv_triggered"] = False
            result["opencv_error"] = "OpenCV analysis returned None"

    # Test full pipeline (with layout_aware=True)
    start = time.perf_counter()
    needs_ocr(file_path, layout_aware=True)
    total_time = time.perf_counter() - start

    result["total_time"] = total_time

    return result


def run_benchmark(pdf_dir: Path, max_files: int = None) -> List[Dict]:
    """Run benchmark on PDF files in directory."""
    pdf_files = list(pdf_dir.glob("*.pdf"))

    if max_files:
        pdf_files = pdf_files[:max_files]

    if not pdf_files:
        print(f"❌ No PDF files found in {pdf_dir}")
        return []

    print(f"📊 Benchmarking {len(pdf_files)} PDF files...")
    print("=" * 80)

    results = []
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"[{i}/{len(pdf_files)}] {pdf_file.name}...", end=" ", flush=True)
        try:
            result = benchmark_file(pdf_file)
            results.append(result)
            print(f"✅ {format_time(result['total_time'])}")
        except Exception as e:
            print(f"❌ Error: {e}")

    return results


def analyze_results(results: List[Dict]) -> Dict:
    """Analyze benchmark results and generate statistics."""
    stats = {
        "total_files": len(results),
        "fast_path": {},
        "opencv": {},
        "total": {},
        "by_page_count": defaultdict(list),
        "by_confidence": defaultdict(list),
    }

    fast_times = [r["fast_path_time"] for r in results if r["fast_path_time"]]
    opencv_times = [r["opencv_time"] for r in results if r["opencv_time"]]
    total_times = [r["total_time"] for r in results if r["total_time"]]

    if fast_times:
        stats["fast_path"] = {
            "min": min(fast_times),
            "max": max(fast_times),
            "mean": statistics.mean(fast_times),
            "median": statistics.median(fast_times),
            "p95": (
                sorted(fast_times)[int(len(fast_times) * 0.95)]
                if len(fast_times) > 1
                else fast_times[0]
            ),
        }

    if opencv_times:
        stats["opencv"] = {
            "min": min(opencv_times),
            "max": max(opencv_times),
            "mean": statistics.mean(opencv_times),
            "median": statistics.median(opencv_times),
            "p95": (
                sorted(opencv_times)[int(len(opencv_times) * 0.95)]
                if len(opencv_times) > 1
                else opencv_times[0]
            ),
        }

    if total_times:
        stats["total"] = {
            "min": min(total_times),
            "max": max(total_times),
            "mean": statistics.mean(total_times),
            "median": statistics.median(total_times),
            "p95": (
                sorted(total_times)[int(len(total_times) * 0.95)]
                if len(total_times) > 1
                else total_times[0]
            ),
        }

    # Group by page count
    for r in results:
        if r.get("page_count"):
            stats["by_page_count"][r["page_count"]].append(r)

    # Group by confidence range
    for r in results:
        if r.get("confidence") is not None:
            conf_range = f"{int(r['confidence'] * 10) * 10}%"
            stats["by_confidence"][conf_range].append(r)

    return stats


def print_report(stats: Dict, results: List[Dict]):
    """Print benchmark report."""
    print("\n" + "=" * 80)
    print("📊 BENCHMARK RESULTS")
    print("=" * 80)

    print(f"\n📁 Total Files: {stats['total_files']}")
    opencv_count = len([r for r in results if r.get("opencv_triggered")])
    fast_only = len([r for r in results if not r.get("opencv_triggered")])
    print(f"   - With OpenCV: {opencv_count}")
    print(f"   - Fast path only: {fast_only}")

    if opencv_count == 0 and any(r.get("opencv_error") for r in results):
        print("\n⚠️  Note: OpenCV dependencies not installed.")
        print("   Install with: pip install preocr[layout-refinement]")
        print("   Or manually: pip install opencv-python-headless numpy PyMuPDF")

    # Fast path statistics
    if stats["fast_path"]:
        fp = stats["fast_path"]
        print("\n⚡ Fast Path (Heuristics Only):")
        print(f"   Min:    {format_time(fp['min'])}")
        print(f"   Max:    {format_time(fp['max'])}")
        print(f"   Mean:   {format_time(fp['mean'])}")
        print(f"   Median: {format_time(fp['median'])}")
        print(f"   P95:    {format_time(fp['p95'])}")

    # OpenCV statistics
    if stats["opencv"]:
        ocv = stats["opencv"]
        print("\n🔬 OpenCV Layout Analysis:")
        print(f"   Min:    {format_time(ocv['min'])}")
        print(f"   Max:    {format_time(ocv['max'])}")
        print(f"   Mean:   {format_time(ocv['mean'])}")
        print(f"   Median: {format_time(ocv['median'])}")
        print(f"   P95:    {format_time(ocv['p95'])}")

    # Total pipeline statistics
    if stats["total"]:
        tot = stats["total"]
        print("\n🎯 Total Pipeline (Heuristics + OpenCV):")
        print(f"   Min:    {format_time(tot['min'])}")
        print(f"   Max:    {format_time(tot['max'])}")
        print(f"   Mean:   {format_time(tot['mean'])}")
        print(f"   Median: {format_time(tot['median'])}")
        print(f"   P95:    {format_time(tot['p95'])}")

    # By page count
    if stats["by_page_count"]:
        print("\n📄 Performance by Page Count:")
        for page_count in sorted(stats["by_page_count"].keys()):
            page_results = stats["by_page_count"][page_count]
            opencv_times = [r["opencv_time"] for r in page_results if r.get("opencv_time")]
            if opencv_times:
                avg_time = statistics.mean(opencv_times)
                print(
                    f"   {page_count} page(s): {format_time(avg_time)} avg ({len(opencv_times)} files)"
                )

    # Summary recommendations
    print("\n💡 Summary:")
    if stats["fast_path"] and stats["opencv"]:
        fast_median = stats["fast_path"]["median"]
        opencv_median = stats["opencv"]["median"]
        opencv_p95 = stats["opencv"]["p95"]

        print(f"   - Fast path: {format_time(fast_median)} (median)")
        print(
            f"   - OpenCV analysis: {format_time(opencv_median)} (median), {format_time(opencv_p95)} (P95)"
        )
        print(
            f"   - Recommended timing: Fast path < 1s, OpenCV {format_time(opencv_median)}-{format_time(opencv_p95)}"
        )

    print("=" * 80)


def main():
    """Main benchmark function."""
    import sys

    # Default to Downloads directory, or use command line argument
    if len(sys.argv) > 1:
        pdf_dir = Path(sys.argv[1])
    else:
        pdf_dir = Path("/home/yuvarajk/Downloads")

    max_files = int(sys.argv[2]) if len(sys.argv) > 2 else None

    if not pdf_dir.exists():
        print(f"❌ Directory not found: {pdf_dir}")
        return

    results = run_benchmark(pdf_dir, max_files)

    if not results:
        print("❌ No results to analyze")
        return

    stats = analyze_results(results)
    print_report(stats, results)


if __name__ == "__main__":
    main()
