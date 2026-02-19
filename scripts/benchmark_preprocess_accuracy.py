#!/usr/bin/env python3
"""
Benchmark preprocess (prepare_for_ocr) with accuracy validation.

Runs needs_ocr for accuracy, then prepare_for_ocr on files needing OCR
to validate the full detection → preprocess pipeline.
"""

import json
import sys
import time
import statistics
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from preocr import needs_ocr, prepare_for_ocr
from validate_accuracy import AccuracyValidator


def benchmark_preprocess_with_accuracy(
    directory: Path,
    ground_truth_file: Optional[str] = None,
    layout_aware: bool = True,
    page_level: bool = True,
    max_files: Optional[int] = None,
    max_size_mb: Optional[float] = None,
    preprocess_mode: str = "quality",
) -> Dict:
    """
    Benchmark needs_ocr accuracy + prepare_for_ocr on files that need OCR.

    Args:
        directory: Directory containing files
        ground_truth_file: Path to ground truth JSON
        layout_aware: Layout-aware analysis
        page_level: Page-level analysis
        max_files: Max files to process
        max_size_mb: Max file size in MB
        preprocess_mode: "quality" or "fast"

    Returns:
        Dictionary with accuracy and preprocess results
    """
    extensions = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"]
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

    print(f"📊 Benchmarking {len(files)} files (accuracy + preprocess)")
    print("=" * 80)

    # Phase 1: needs_ocr for accuracy (validate our file set)
    accuracy_results = []
    if ground_truth_file and Path(ground_truth_file).exists():
        print("\n📋 Phase 1: Accuracy validation (needs_ocr)")
        validator = AccuracyValidator(ground_truth_file)
        for i, file_path in enumerate(files, 1):
            print(f"[{i}/{len(files)}] {file_path.name}...", end=" ", flush=True)
            result = validator.validate_file(
                file_path, layout_aware=layout_aware, page_level=page_level
            )
            accuracy_results.append(result)
            if result.get("skipped"):
                print("⏭️  Skipped")
            elif result.get("correct"):
                print("✅ Correct")
            else:
                print(f"❌ Wrong (GT: {result['ground_truth']}, Pred: {result['predicted']})")
        accuracy_metrics = validator.calculate_metrics(accuracy_results)
    else:
        accuracy_metrics = None
        print("\n⚠️  No ground truth – accuracy validation skipped")

    # Phase 2: prepare_for_ocr on files needing OCR
    print("\n🔄 Phase 2: Preprocess (prepare_for_ocr) on files needing OCR")
    preprocess_results = []
    needs_ocr_files = [
        f for f in files
        if _file_needs_ocr(f, accuracy_results, layout_aware, page_level)
    ]

    if not needs_ocr_files:
        print("   No files need OCR – preprocess phase skipped")
    else:
        print(f"   Processing {len(needs_ocr_files)} files with steps='auto'...")
        for i, file_path in enumerate(needs_ocr_files, 1):
            print(f"   [{i}/{len(needs_ocr_files)}] {file_path.name}...", end=" ", flush=True)
            result = {"file": str(file_path), "success": False, "time": None, "error": None}
            try:
                start = time.perf_counter()
                out, meta = prepare_for_ocr(
                    file_path,
                    steps="auto",
                    mode=preprocess_mode,
                    return_meta=True,
                )
                elapsed = time.perf_counter() - start
                result["success"] = True
                result["time"] = elapsed
                result["applied_steps"] = meta.get("applied_steps", [])
                result["skipped_steps"] = meta.get("skipped_steps", [])
                if isinstance(out, list):
                    result["pages"] = len(out)
                    result["shapes"] = [list(o.shape) for o in out[:3]]  # First 3 pages
                else:
                    result["shapes"] = [list(out.shape)]
                print(f"✅ {elapsed*1000:.0f}ms")
            except Exception as e:
                result["error"] = str(e)
                print(f"❌ {e}")
            preprocess_results.append(result)

    # Preprocess stats
    preprocess_stats = {}
    valid_preprocess = [r for r in preprocess_results if r.get("success") and r.get("time")]
    if valid_preprocess:
        times = [r["time"] for r in valid_preprocess]
        preprocess_stats = {
            "files_processed": len(needs_ocr_files),
            "success": len(valid_preprocess),
            "failed": len(needs_ocr_files) - len(valid_preprocess),
            "min_ms": min(times) * 1000,
            "max_ms": max(times) * 1000,
            "mean_ms": statistics.mean(times) * 1000,
            "median_ms": statistics.median(times) * 1000,
        }

    return {
        "total_files": len(files),
        "accuracy": accuracy_metrics,
        "accuracy_results": accuracy_results if accuracy_results else None,
        "preprocess": {
            "stats": preprocess_stats,
            "results": preprocess_results,
        },
    }


def _file_needs_ocr(
    file_path: Path,
    accuracy_results: List[Dict],
    layout_aware: bool,
    page_level: bool,
) -> bool:
    """Determine if file needs OCR from accuracy results or by running needs_ocr."""
    for r in accuracy_results:
        if Path(r["file"]).name == file_path.name:
            return r.get("ground_truth", r.get("predicted", False))
    # No ground truth – run needs_ocr
    try:
        result = needs_ocr(file_path, layout_aware=layout_aware, page_level=page_level)
        return result.get("needs_ocr", False)
    except Exception:
        return False


def print_report(results: Dict) -> None:
    """Print benchmark report."""
    print("\n" + "=" * 80)
    print("📊 PREPROCESS + ACCURACY BENCHMARK REPORT")
    print("=" * 80)

    # Accuracy
    accuracy = results.get("accuracy")
    if accuracy and "error" not in accuracy:
        print("\n🎯 needs_ocr Accuracy:")
        metrics = accuracy["metrics"]
        print(f"   Accuracy:  {metrics['accuracy']:.2f}%")
        print(f"   Precision: {metrics['precision']:.2f}%")
        print(f"   Recall:    {metrics['recall']:.2f}%")
        print(f"   F1:        {metrics['f1_score']:.2f}%")
    elif accuracy and "error" in accuracy:
        print(f"\n⚠️  Accuracy: {accuracy['error']}")
    else:
        print("\n⚠️  Accuracy: not run (no ground truth)")

    # Preprocess
    preprocess = results.get("preprocess", {})
    stats = preprocess.get("stats", {})
    if stats:
        print("\n🔄 prepare_for_ocr (files needing OCR):")
        print(f"   Processed: {stats.get('success', 0)}/{stats.get('files_processed', 0)}")
        if stats.get("failed"):
            print(f"   Failed:    {stats['failed']}")
        print(f"   Latency:   min={stats.get('min_ms', 0):.0f}ms  max={stats.get('max_ms', 0):.0f}ms  median={stats.get('median_ms', 0):.0f}ms")
    else:
        print("\n🔄 prepare_for_ocr: no files needing OCR (or phase skipped)")

    print("=" * 80)


def main():
    import argparse

    root = Path(__file__).resolve().parent.parent
    default_gt = root / "scripts" / "ground_truth_data_source_formats.json"

    parser = argparse.ArgumentParser(
        description="Benchmark preprocess (prepare_for_ocr) with accuracy validation"
    )
    parser.add_argument("directory", type=str, default=str(root / "datasets"), nargs="?")
    parser.add_argument(
        "--ground-truth", "-g",
        type=str,
        default=str(default_gt),
        help="Ground truth JSON",
    )
    parser.add_argument("--layout-aware", action="store_true", default=True)
    parser.add_argument("--no-layout-aware", action="store_true", dest="no_layout")
    parser.add_argument("--page-level", action="store_true", default=True)
    parser.add_argument("--max-files", type=int, help="Max files to process")
    parser.add_argument("--max-size-mb", type=float, help="Max file size (MB)")
    parser.add_argument(
        "--preprocess-mode",
        choices=["quality", "fast"],
        default="quality",
        help="prepare_for_ocr mode",
    )
    parser.add_argument("-o", "--output", type=str, help="Output JSON")

    args = parser.parse_args()
    layout_aware = not args.no_layout

    directory = Path(args.directory).resolve()
    if not directory.exists():
        print(f"❌ Directory not found: {directory}")
        sys.exit(1)

    results = benchmark_preprocess_with_accuracy(
        directory,
        ground_truth_file=args.ground_truth,
        layout_aware=layout_aware,
        page_level=args.page_level,
        max_files=args.max_files,
        max_size_mb=args.max_size_mb,
        preprocess_mode=args.preprocess_mode,
    )

    if "error" in results:
        print(f"❌ {results['error']}")
        sys.exit(1)

    print_report(results)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n✅ Results saved: {args.output}")


if __name__ == "__main__":
    main()
