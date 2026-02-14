#!/usr/bin/env python3
"""
Benchmark baseline (preocr) vs planner on a directory of PDFs.

Runs without ground truth: reports agreement rate, per-method decision counts,
and per-file results. Supports recursive discovery for nested dirs (e.g. benchmarkdata/0/*.pdf).
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from preocr import needs_ocr, plan_ocr_for_document
from preocr.planner.config import PlannerConfig


def find_pdfs(directory: Path, recursive: bool = True) -> List[Path]:
    """Find all PDF files in directory, optionally recursively."""
    if recursive:
        return sorted(directory.rglob("*.pdf"))
    return sorted(directory.glob("*.pdf"))


def run_benchmark(
    directory: Path,
    domain_mode: str = "generic",
    recursive: bool = True,
    max_files: Optional[int] = None,
    log_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run baseline and planner on all PDFs. No ground truth required.
    """
    pdf_files = find_pdfs(directory, recursive)
    if max_files:
        pdf_files = pdf_files[:max_files]

    if not pdf_files:
        return {"error": f"No PDF files found in {directory}", "n_files": 0}

    n_total = len(pdf_files)
    cfg = PlannerConfig(domain_mode=domain_mode)
    baseline_decisions: List[Dict[str, Any]] = []
    planner_decisions: List[Dict[str, Any]] = []
    agreement_count = 0
    baseline_needs_ocr_count = 0
    planner_needs_ocr_count = 0
    total_baseline_time = 0.0
    total_planner_time = 0.0

    def _log(msg: str) -> None:
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
        print(msg, flush=True)
        if log_file:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line)

    for i, pdf_path in enumerate(pdf_files):
        try:
            rel_path = pdf_path.relative_to(directory)
        except ValueError:
            rel_path = pdf_path.name

        _log(f"[{i+1}/{n_total}] {rel_path}...")

        try:
            # Baseline: page_level=True, layout_aware=True (fair comparison with planner)
            t0 = time.perf_counter()
            base_result = needs_ocr(str(pdf_path), layout_aware=True, page_level=True)
            t1 = time.perf_counter()
            baseline_needs = base_result["needs_ocr"]
            total_baseline_time += t1 - t0
            if baseline_needs:
                baseline_needs_ocr_count += 1

            # Planner
            t2 = time.perf_counter()
            plan_result = plan_ocr_for_document(str(pdf_path), config=cfg)
            t3 = time.perf_counter()
            planner_needs = plan_result["needs_ocr_any"]
            total_planner_time += t3 - t2
            if planner_needs:
                planner_needs_ocr_count += 1

            if baseline_needs == planner_needs:
                agreement_count += 1

            baseline_decisions.append({
                "file": str(rel_path),
                "needs_ocr": baseline_needs,
                "time_s": round(t1 - t0, 3),
                "page_level": True,
                "layout_aware": True,
            })
            planner_decisions.append({
                "file": str(rel_path),
                "needs_ocr": planner_needs,
                "time_s": round(t3 - t2, 3),
                "pages_needing_ocr": plan_result.get("pages_needing_ocr", []),
                "decision_version": plan_result.get("decision_version", ""),
            })

            base_time = round(t1 - t0, 2)
            plan_time = round(t3 - t2, 2)
            _log(f"  -> baseline: needs_ocr={baseline_needs} ({base_time}s) | planner: needs_ocr={planner_needs} ({plan_time}s) | agree={baseline_needs == planner_needs}")

        except Exception as e:
            _log(f"  -> ERROR: {e}")
            baseline_decisions.append({"file": str(rel_path), "error": str(e), "needs_ocr": None})
            planner_decisions.append({"file": str(rel_path), "error": str(e), "needs_ocr": None})

    n = len(pdf_files)
    return {
        "n_files": n,
        "directory": str(directory),
        "domain_mode": domain_mode,
        "recursive": recursive,
        "summary": {
            "agreement_count": agreement_count,
            "agreement_rate": round(agreement_count / n, 4) if n else 0,
            "baseline_needs_ocr_count": baseline_needs_ocr_count,
            "planner_needs_ocr_count": planner_needs_ocr_count,
            "baseline_avg_time_s": round(total_baseline_time / n, 3) if n else 0,
            "planner_avg_time_s": round(total_planner_time / n, 3) if n else 0,
            "total_baseline_time_s": round(total_baseline_time, 2),
            "total_planner_time_s": round(total_planner_time, 2),
        },
        "baseline_decisions": baseline_decisions,
        "planner_decisions": planner_decisions,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Benchmark planner vs baseline on PDFs")
    parser.add_argument(
        "directory",
        type=str,
        help="Directory containing PDFs (searched recursively by default)",
    )
    parser.add_argument(
        "--domain-mode",
        type=str,
        choices=["medical", "generic"],
        default="generic",
        help="Planner domain mode",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not search subdirectories",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Limit number of files to process",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output JSON file",
    )
    parser.add_argument(
        "--log",
        "-l",
        type=str,
        help="Log file for progress (also prints to stdout)",
    )

    args = parser.parse_args()
    directory = Path(args.directory)
    if not directory.exists():
        print(f"Error: Directory not found: {directory}")
        sys.exit(1)

    print(f"\nBenchmarking PDFs in {directory} (recursive={not args.no_recursive})...")
    if args.log:
        with open(args.log, "w", encoding="utf-8") as f:
            f.write(f"Benchmark started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Directory: {directory}, domain_mode: {args.domain_mode}\n\n")
    results = run_benchmark(
        directory,
        domain_mode=args.domain_mode,
        recursive=not args.no_recursive,
        max_files=args.max_files,
        log_file=args.log,
    )

    if "error" in results:
        print(f"Error: {results['error']}")
        sys.exit(1)

    s = results["summary"]
    n = results["n_files"]
    print("\n" + "=" * 60)
    print("OCR Planner Benchmark")
    print("=" * 60)
    print(f"\nFiles processed: {n}")
    print(f"\nBaseline (preocr, page_level=True, layout_aware=True):")
    print(f"  Flagged needs_ocr: {s['baseline_needs_ocr_count']} ({100*s['baseline_needs_ocr_count']/n:.1f}%)")
    print(f"  Avg time/file: {s['baseline_avg_time_s']}s")
    print(f"\nPlanner ({args.domain_mode}):")
    print(f"  Flagged needs_ocr: {s['planner_needs_ocr_count']} ({100*s['planner_needs_ocr_count']/n:.1f}%)")
    print(f"  Avg time/file: {s['planner_avg_time_s']}s")
    print(f"\nAgreement: {s['agreement_count']}/{n} ({100*s['agreement_rate']:.1f}%)")
    print("=" * 60)

    if args.output:
        # Optionally omit per-file details for large outputs
        out = {k: v for k, v in results.items() if k != "baseline_decisions" and k != "planner_decisions"}
        out["baseline_decisions"] = results["baseline_decisions"]
        out["planner_decisions"] = results["planner_decisions"]
        with open(args.output, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
