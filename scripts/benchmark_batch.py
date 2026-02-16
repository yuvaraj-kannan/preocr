#!/usr/bin/env python3
"""
Benchmark BatchProcessor: accuracy and speed for files <= max_size_mb.

Uses BatchProcessor with layout_aware=True, page_level=True for production accuracy.
Validates against ground truth for accuracy metrics.
"""

import json
import sys
import time
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from preocr import BatchProcessor
from preocr.planner.config import PlannerConfig


def load_ground_truth(gt_path: Path) -> dict:
    """Load ground truth: path or basename -> needs_ocr."""
    gt = {}
    with open(gt_path) as f:
        data = json.load(f)
    for item in data if isinstance(data, list) else [data]:
        file_key = item["file"]
        needs_ocr = item["needs_ocr"]
        gt[file_key] = needs_ocr
        gt[Path(file_key).name] = needs_ocr
    return gt


def validate_batch_results(results, ground_truth: dict):
    """Compute accuracy from batch results vs ground truth."""
    validation_results = []
    for r in results:
        filename = Path(r["file_path"]).name
        gt = ground_truth.get(r["file_path"]) or ground_truth.get(filename)
        if gt is None:
            continue
        pred = r.get("needs_ocr")
        if pred is None:
            continue
        validation_results.append({
            "correct": pred == gt,
            "ground_truth": gt,
            "predicted": pred,
            "file": r["file_path"],
        })
    return validation_results


def main():
    import argparse

    root = Path(__file__).resolve().parent.parent
    default_dir = root / "datasets"

    parser = argparse.ArgumentParser(description="Benchmark BatchProcessor (accuracy + speed)")
    parser.add_argument("directory", type=str, default=str(default_dir), nargs="?")
    parser.add_argument("-g", "--ground-truth", type=str, help="Ground truth JSON")
    parser.add_argument("--max-size-mb", type=float, default=0.8, help="Max file size MB (default 0.8)")
    parser.add_argument("--no-cache", action="store_true", help="Disable cache for fair benchmark")
    parser.add_argument("--use-planner", action="store_true", help="Use intent-aware planner instead of needs_ocr")
    parser.add_argument("--domain-mode", type=str, choices=["medical", "generic"], default="generic",
                        help="Planner domain mode when --use-planner (default: generic)")
    args = parser.parse_args()

    directory = Path(args.directory).resolve()
    if not directory.exists():
        print(f"❌ Directory not found: {directory}")
        sys.exit(1)

    max_bytes = int(args.max_size_mb * 1024 * 1024)
    gt_path = Path(args.ground_truth) if args.ground_truth else Path(__file__).parent / "ground_truth_data_source_formats.json"

    print(f"📊 BatchProcessor benchmark (≤{args.max_size_mb} MB)")
    print(f"   Directory: {directory}")
    if args.use_planner:
        print(f"   Mode: Planner (intent-aware) | Domain: {args.domain_mode}")
    else:
        print(f"   Layout-aware: True | Page-level: True")
    print("=" * 80)

    # Run batch
    if args.use_planner:
        planner_config = PlannerConfig(domain_mode=args.domain_mode)
        processor = BatchProcessor(
            max_workers=8,
            use_planner=True,
            planner_config=planner_config,
            use_cache=not args.no_cache,
            max_size=max_bytes,
        )
    else:
        processor = BatchProcessor(
            max_workers=8,
            layout_aware=True,
            page_level=True,
            use_cache=not args.no_cache,
            max_size=max_bytes,
        )

    start = time.perf_counter()
    batch_results = processor.process_directory(directory, progress=True)
    elapsed = time.perf_counter() - start

    results = batch_results.results
    n = len(results)
    errors = len(batch_results.errors)

    # Performance
    print("\n⚡ Performance:")
    print(f"   Files processed: {n} (errors: {errors})")
    print(f"   Total time:      {elapsed:.2f}s")
    if n > 0:
        print(f"   Time per file:   {elapsed/n*1000:.0f}ms")
        print(f"   Throughput:      {n/elapsed:.1f} files/sec")

    # Accuracy (if ground truth)
    if gt_path.exists():
        gt = load_ground_truth(gt_path)
        validation = validate_batch_results(results, gt)
        if validation:
            correct = sum(1 for v in validation if v["correct"])
            total = len(validation)
            tp = sum(1 for v in validation if v["ground_truth"] and v["predicted"])
            fp = sum(1 for v in validation if not v["ground_truth"] and v["predicted"])
            tn = sum(1 for v in validation if not v["ground_truth"] and not v["predicted"])
            fn = sum(1 for v in validation if v["ground_truth"] and not v["predicted"])
            acc = 100 * correct / total
            precision = 100 * tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = 100 * tp / (tp + fn) if (tp + fn) > 0 else 0

            print("\n🎯 Accuracy (files with ground truth):")
            print(f"   Validated: {total} files")
            print(f"   Accuracy:  {acc:.1f}%")
            print(f"   Precision: {precision:.1f}%")
            print(f"   Recall:    {recall:.1f}%")
            print(f"   TP:{tp} FP:{fp} TN:{tn} FN:{fn}")
        else:
            print("\n⚠️  No files matched ground truth")
    else:
        print("\n⚠️  No ground truth file (use -g path)")

    print("=" * 80)


if __name__ == "__main__":
    main()
