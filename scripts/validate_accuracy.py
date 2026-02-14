#!/usr/bin/env python3
"""
Accuracy validation script for PreOCR.

This script validates PreOCR accuracy by comparing predictions against ground truth labels.
It calculates precision, recall, F1-score, and overall accuracy metrics.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

from preocr import needs_ocr


class AccuracyValidator:
    """Validates PreOCR accuracy against ground truth labels."""

    def __init__(self, ground_truth_file: Optional[str] = None):
        """
        Initialize validator.

        Args:
            ground_truth_file: Path to JSON file with ground truth labels
        """
        self.ground_truth: Dict[str, bool] = {}
        if ground_truth_file and Path(ground_truth_file).exists():
            self.load_ground_truth(ground_truth_file)

    def load_ground_truth(self, file_path: str) -> None:
        """Load ground truth labels from JSON file."""
        with open(file_path, "r") as f:
            data = json.load(f)
            if isinstance(data, dict):
                self.ground_truth = data
            elif isinstance(data, list):
                # Convert list format to dict, using both full path and filename as keys
                self.ground_truth = {}
                for item in data:
                    file_key = item["file"]
                    needs_ocr = item["needs_ocr"]
                    # Store by full path
                    self.ground_truth[file_key] = needs_ocr
                    # Also store by filename for easier matching
                    filename = Path(file_key).name
                    if filename not in self.ground_truth:
                        self.ground_truth[filename] = needs_ocr

    def validate_file(
        self, file_path: Path, layout_aware: bool = False, page_level: bool = False
    ) -> Dict:
        """
        Validate a single file against ground truth.

        Args:
            file_path: Path to file to validate
            layout_aware: Whether to use layout-aware analysis
            page_level: Whether to use page-level analysis

        Returns:
            Dictionary with validation results
        """
        file_str = str(file_path)
        file_abs = str(file_path.resolve())
        filename = file_path.name

        # Get ground truth label - try multiple matching strategies
        ground_truth_needs_ocr = (
            self.ground_truth.get(file_str)  # Original path
            or self.ground_truth.get(file_abs)  # Absolute path
            or self.ground_truth.get(filename)  # Just filename
        )

        # Also try matching with normalized paths
        if ground_truth_needs_ocr is None:
            for key, value in self.ground_truth.items():
                if Path(key).resolve() == file_path.resolve():
                    ground_truth_needs_ocr = value
                    break

        if ground_truth_needs_ocr is None:
            return {
                "file": file_str,
                "error": "No ground truth label found",
                "skipped": True,
            }

        # Get PreOCR prediction
        try:
            result = needs_ocr(file_path, layout_aware=layout_aware, page_level=page_level)
            predicted_needs_ocr = result["needs_ocr"]
            confidence = result["confidence"]
            reason_code = result["reason_code"]

            # Compare
            is_correct = predicted_needs_ocr == ground_truth_needs_ocr

            return {
                "file": file_str,
                "ground_truth": ground_truth_needs_ocr,
                "predicted": predicted_needs_ocr,
                "correct": is_correct,
                "confidence": confidence,
                "reason_code": reason_code,
                "file_type": result.get("file_type", "unknown"),
                "skipped": False,
            }
        except Exception as e:
            return {
                "file": file_str,
                "error": str(e),
                "skipped": True,
            }

    def validate_directory(
        self,
        directory: Path,
        layout_aware: bool = False,
        page_level: bool = False,
        extensions: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Validate all files in a directory.

        Args:
            directory: Directory containing files to validate
            layout_aware: Whether to use layout-aware analysis
            page_level: Whether to use page-level analysis
            extensions: List of file extensions to process (e.g., [".pdf", ".png"])

        Returns:
            List of validation results
        """
        if extensions is None:
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

        results = []
        files = []
        for ext in extensions:
            files.extend(directory.glob(f"*{ext}"))
            files.extend(directory.glob(f"*{ext.upper()}"))

        files = sorted(set(files))

        print(f"Validating {len(files)} files...")
        for i, file_path in enumerate(files, 1):
            print(f"[{i}/{len(files)}] {file_path.name}...", end=" ", flush=True)
            result = self.validate_file(file_path, layout_aware=layout_aware, page_level=page_level)
            results.append(result)
            if result.get("skipped"):
                print("⏭️  Skipped")
            elif result.get("correct"):
                print("✅ Correct")
            else:
                print(f"❌ Wrong (GT: {result['ground_truth']}, Pred: {result['predicted']})")

        return results

    def calculate_metrics(self, results: List[Dict]) -> Dict:
        """
        Calculate accuracy metrics from validation results.

        Args:
            results: List of validation results

        Returns:
            Dictionary with accuracy metrics
        """
        # Filter out skipped files
        valid_results = [r for r in results if not r.get("skipped")]

        if not valid_results:
            return {
                "total_files": len(results),
                "validated_files": 0,
                "skipped_files": len(results),
                "error": "No valid results to calculate metrics",
            }

        # Count true positives, false positives, true negatives, false negatives
        tp = 0  # True Positive: Predicted needs OCR, actually needs OCR
        fp = 0  # False Positive: Predicted needs OCR, actually doesn't need OCR
        tn = 0  # True Negative: Predicted no OCR, actually doesn't need OCR
        fn = 0  # False Negative: Predicted no OCR, actually needs OCR

        for result in valid_results:
            gt = result["ground_truth"]
            pred = result["predicted"]

            if pred and gt:
                tp += 1
            elif pred and not gt:
                fp += 1
            elif not pred and not gt:
                tn += 1
            elif not pred and gt:
                fn += 1

        # Calculate metrics
        total = len(valid_results)
        correct = tp + tn
        accuracy = (correct / total * 100) if total > 0 else 0.0

        # Precision: Of all predicted "needs OCR", how many actually need OCR?
        precision = (tp / (tp + fp) * 100) if (tp + fp) > 0 else 0.0

        # Recall: Of all files that need OCR, how many did we catch?
        recall = (tp / (tp + fn) * 100) if (tp + fn) > 0 else 0.0

        # F1 Score: Harmonic mean of precision and recall
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        # Breakdown by file type
        by_type = defaultdict(
            lambda: {"total": 0, "correct": 0, "tp": 0, "fp": 0, "tn": 0, "fn": 0}
        )
        for result in valid_results:
            file_type = result.get("file_type", "unknown")
            by_type[file_type]["total"] += 1
            if result["correct"]:
                by_type[file_type]["correct"] += 1

            gt = result["ground_truth"]
            pred = result["predicted"]
            if pred and gt:
                by_type[file_type]["tp"] += 1
            elif pred and not gt:
                by_type[file_type]["fp"] += 1
            elif not pred and not gt:
                by_type[file_type]["tn"] += 1
            elif not pred and gt:
                by_type[file_type]["fn"] += 1

        # Calculate accuracy by type
        by_type_accuracy = {}
        for file_type, stats in by_type.items():
            total = stats["total"]
            correct = stats["correct"]
            by_type_accuracy[file_type] = {
                "accuracy": (correct / total * 100) if total > 0 else 0.0,
                "total": total,
                "correct": correct,
                "precision": (
                    (stats["tp"] / (stats["tp"] + stats["fp"]) * 100)
                    if (stats["tp"] + stats["fp"]) > 0
                    else 0.0
                ),
                "recall": (
                    (stats["tp"] / (stats["tp"] + stats["fn"]) * 100)
                    if (stats["tp"] + stats["fn"]) > 0
                    else 0.0
                ),
            }

        return {
            "total_files": len(results),
            "validated_files": len(valid_results),
            "skipped_files": len(results) - len(valid_results),
            "confusion_matrix": {
                "true_positive": tp,
                "false_positive": fp,
                "true_negative": tn,
                "false_negative": fn,
            },
            "metrics": {
                "accuracy": round(accuracy, 2),
                "precision": round(precision, 2),
                "recall": round(recall, 2),
                "f1_score": round(f1, 2),
            },
            "by_type": by_type_accuracy,
        }

    def print_report(self, metrics: Dict, results: List[Dict]) -> None:
        """Print validation report."""
        print("\n" + "=" * 80)
        print("📊 ACCURACY VALIDATION RESULTS")
        print("=" * 80)

        print("\n📁 Files:")
        print(f"   Total: {metrics['total_files']}")
        print(f"   Validated: {metrics['validated_files']}")
        if metrics["skipped_files"] > 0:
            print(f"   Skipped: {metrics['skipped_files']}")

        if "error" in metrics:
            print(f"\n❌ Error: {metrics['error']}")
            return

        # Confusion matrix
        cm = metrics["confusion_matrix"]
        print("\n📊 Confusion Matrix:")
        print(
            f"   True Positive (TP):  {cm['true_positive']:3} - Correctly identified as needing OCR"
        )
        print(
            f"   False Positive (FP): {cm['false_positive']:3} - Incorrectly flagged as needing OCR"
        )
        print(
            f"   True Negative (TN):  {cm['true_negative']:3} - Correctly identified as not needing OCR"
        )
        print(f"   False Negative (FN): {cm['false_negative']:3} - Missed files that need OCR")

        # Overall metrics
        m = metrics["metrics"]
        print("\n🎯 Overall Metrics:")
        print(f"   Accuracy:  {m['accuracy']:.2f}%")
        print(f"   Precision: {m['precision']:.2f}%")
        print(f"   Recall:    {m['recall']:.2f}%")
        print(f"   F1-Score:  {m['f1_score']:.2f}%")

        # Breakdown by file type
        if metrics["by_type"]:
            print("\n📋 Accuracy by File Type:")
            for file_type, stats in sorted(metrics["by_type"].items()):
                print(
                    f"   {file_type:12} {stats['accuracy']:5.1f}% ({stats['correct']}/{stats['total']} files)"
                )
                print(
                    f"                  Precision: {stats['precision']:.1f}%, Recall: {stats['recall']:.1f}%"
                )

        # Show errors
        errors = [r for r in results if not r.get("skipped") and not r.get("correct")]
        if errors:
            print(f"\n❌ Incorrect Predictions ({len(errors)} files):")
            for error in errors[:10]:  # Show first 10
                file_name = Path(error["file"]).name
                print(
                    f"   {file_name:40} GT: {error['ground_truth']}, Pred: {error['predicted']}, "
                    f"Conf: {error['confidence']:.2f}"
                )
            if len(errors) > 10:
                print(f"   ... and {len(errors) - 10} more errors")

        print("\n" + "=" * 80)


def create_ground_truth_template(directory: Path, output_file: str = "ground_truth.json") -> None:
    """
    Create a template ground truth file for manual labeling.

    Args:
        directory: Directory containing files to create template for
        output_file: Output JSON file path
    """
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

    template = []
    for file_path in files:
        template.append(
            {
                "file": str(file_path),
                "needs_ocr": None,  # Set to True or False manually
                "notes": "",  # Optional notes
            }
        )

    with open(output_file, "w") as f:
        json.dump(template, f, indent=2)

    print(f"✅ Created ground truth template: {output_file}")
    print(f"   Found {len(files)} files")
    print("   Please edit the file and set 'needs_ocr' to True or False for each file")


def main():
    """Main validation function."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate PreOCR accuracy")
    parser.add_argument(
        "directory", type=str, help="Directory containing files to validate", nargs="?"
    )
    parser.add_argument(
        "--ground-truth",
        "-g",
        type=str,
        help="Path to ground truth JSON file",
        default="ground_truth.json",
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
        "--create-template",
        action="store_true",
        help="Create a ground truth template file",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output JSON file for results",
    )

    args = parser.parse_args()

    if args.create_template:
        if not args.directory:
            print("❌ Error: --create-template requires a directory")
            sys.exit(1)
        create_ground_truth_template(Path(args.directory), args.ground_truth)
        return

    if not args.directory:
        print("❌ Error: Directory required")
        parser.print_help()
        sys.exit(1)

    directory = Path(args.directory)
    if not directory.exists():
        print(f"❌ Error: Directory not found: {directory}")
        sys.exit(1)

    # Initialize validator
    validator = AccuracyValidator(args.ground_truth)

    if not validator.ground_truth:
        print(f"⚠️  Warning: No ground truth file found at {args.ground_truth}")
        print(f"   Create one with: python validate_accuracy.py --create-template {directory}")
        print("   Or provide one with: --ground-truth <path>")
        sys.exit(1)

    # Validate files
    results = validator.validate_directory(
        directory, layout_aware=args.layout_aware, page_level=args.page_level
    )

    # Calculate metrics
    metrics = validator.calculate_metrics(results)

    # Print report
    validator.print_report(metrics, results)

    # Save results if requested
    if args.output:
        output_data = {
            "metrics": metrics,
            "results": results,
        }
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)
        print(f"\n✅ Results saved to: {args.output}")


if __name__ == "__main__":
    main()
