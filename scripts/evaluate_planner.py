#!/usr/bin/env python3
"""
Evaluate the intent-aware OCR planner against ground truth.

Supports:
- Document-level ground truth (file -> needs_ocr)
- Page-level ground truth (file -> pages -> needs_ocr_gt)
- Threshold sweep (0.4, 0.5, 0.6, 0.7, 0.8) for operating point selection
- Baseline (preocr) vs planner comparison
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add scripts to path for standalone run
sys.path.insert(0, str(Path(__file__).parent))

from preocr import needs_ocr, plan_ocr_for_document
from preocr.planner.config import PlannerConfig


def load_ground_truth(file_path: str) -> List[Dict[str, Any]]:
    """Load ground truth from JSON. Supports document-level and page-level format."""
    with open(file_path, "r") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [{"file": k, "needs_ocr": v} for k, v in data.items()]
    return []


def evaluate_threshold(
    scores: List[float],
    ground_truth: List[bool],
    threshold: float,
) -> Dict[str, float]:
    """Compute precision, recall, F1 for a given threshold."""
    preds = [1 if s >= threshold else 0 for s in scores]
    tp = sum(1 for p, g in zip(preds, ground_truth) if p == 1 and g)
    fp = sum(1 for p, g in zip(preds, ground_truth) if p == 1 and not g)
    fn = sum(1 for p, g in zip(preds, ground_truth) if p == 0 and g)
    tn = sum(1 for p, g in zip(preds, ground_truth) if p == 0 and not g)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(ground_truth) if ground_truth else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
    }


def run_evaluation(
    directory: Path,
    ground_truth_file: str,
    layout_aware: bool = True,
    thresholds: Optional[List[float]] = None,
    domain_mode: str = "generic",
) -> Dict[str, Any]:
    """
    Run full evaluation: baseline (preocr), planner, and threshold sweep.

    Returns results for baseline, planner (default threshold), and per-threshold.
    """
    gt_list = load_ground_truth(ground_truth_file)
    if not gt_list:
        return {"error": "No ground truth entries loaded"}

    thresholds = thresholds or [0.4, 0.5, 0.6, 0.7, 0.8]

    baseline_preds: List[bool] = []
    planner_preds: List[bool] = []
    planner_scores: List[float] = []
    gt_labels: List[bool] = []

    for item in gt_list:
        file_path = item.get("file", "")
        if not file_path:
            continue
        path = directory / Path(file_path).name
        if not path.exists():
            path = Path(file_path)
        if not path.exists():
            continue

        needs_ocr_gt = item.get("needs_ocr")
        if needs_ocr_gt is None:
            continue

        gt_labels.append(needs_ocr_gt)
        try:
            base_result = needs_ocr(str(path), layout_aware=layout_aware, page_level=False)
            baseline_preds.append(base_result["needs_ocr"])
        except Exception:
            baseline_preds.append(True)

        try:
            cfg = PlannerConfig(domain_mode=domain_mode)
            plan_result = plan_ocr_for_document(str(path), config=cfg)
            planner_preds.append(plan_result["needs_ocr_any"])
            scores = [p.get("debug", {}).get("score", 0.5) for p in plan_result.get("pages", [])]
            planner_scores.append(max(scores) if scores else 0.5)
        except Exception:
            planner_preds.append(True)
            planner_scores.append(0.5)

    if not gt_labels:
        return {"error": "No valid ground truth labels to evaluate"}

    # Ensure all lists same length (page-level might have mismatches)
    n = len(gt_labels)
    baseline_preds = baseline_preds[:n] + [True] * (n - len(baseline_preds))
    planner_preds = planner_preds[:n] + [True] * (n - len(planner_preds))
    planner_scores = planner_scores[:n] + [0.5] * (n - len(planner_scores))

    # Baseline metrics (use actual predictions)
    baseline_preds_binary = [1 if p else 0 for p in baseline_preds]
    baseline_metrics = evaluate_threshold(baseline_preds_binary, gt_labels, 0.5)

    # Planner metrics (use actual needs_ocr_any predictions, not re-thresholded scores)
    planner_preds_binary = [1 if p else 0 for p in planner_preds]
    planner_metrics = evaluate_threshold(planner_preds_binary, gt_labels, 0.5)

    cfg = PlannerConfig()
    default_threshold = cfg.get_decision_threshold()

    # Threshold sweep (only meaningful when scores exist; uses scores for simulated threshold)
    sweep_results = {}
    for t in thresholds:
        sweep_results[str(t)] = evaluate_threshold(planner_scores, gt_labels, t)

    return {
        "n_samples": n,
        "baseline": baseline_metrics,
        "planner": planner_metrics,
        "planner_threshold": default_threshold,
        "threshold_sweep": sweep_results,
    }


def main():
    """CLI for evaluation."""
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate OCR planner against ground truth")
    parser.add_argument(
        "directory",
        type=str,
        help="Directory containing test files",
    )
    parser.add_argument(
        "--ground-truth",
        "-g",
        type=str,
        default="ground_truth.json",
        help="Path to ground truth JSON",
    )
    parser.add_argument(
        "--layout-aware",
        action="store_true",
        default=True,
        help="Use layout-aware analysis",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output JSON file",
    )
    parser.add_argument(
        "--domain-mode",
        type=str,
        choices=["medical", "generic"],
        default="generic",
        help="Planner domain mode: medical (intent overrides) or generic (scoring only)",
    )

    args = parser.parse_args()
    directory = Path(args.directory)
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        sys.exit(1)

    gt_path = Path(args.ground_truth)
    if not gt_path.is_absolute():
        gt_path = directory.parent / args.ground_truth
    if not gt_path.exists():
        gt_path = Path(args.ground_truth)
    if not gt_path.exists():
        print(f"Error: Ground truth file not found: {args.ground_truth}")
        sys.exit(1)

    results = run_evaluation(
        directory,
        str(gt_path),
        layout_aware=args.layout_aware,
        domain_mode=args.domain_mode,
    )

    if "error" in results:
        print(f"Error: {results['error']}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("OCR Planner Evaluation")
    print("=" * 60)
    print(f"\nSamples: {results['n_samples']}")
    print("\nBaseline (preocr):")
    b = results["baseline"]
    print(f"  Precision: {b['precision']:.2%}, Recall: {b['recall']:.2%}, F1: {b['f1']:.2%}")
    print("\nPlanner (default threshold):")
    p = results["planner"]
    print(f"  Precision: {p['precision']:.2%}, Recall: {p['recall']:.2%}, F1: {p['f1']:.2%}")
    print("\nThreshold sweep:")
    for t, m in results["threshold_sweep"].items():
        print(f"  {t}: P={m['precision']:.2%} R={m['recall']:.2%} F1={m['f1']:.2%}")
    print("=" * 60)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
