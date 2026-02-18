#!/usr/bin/env python3
"""
Full dataset benchmark using batch processing with diagram generation.

Processes ALL PDFs in datasets (recursive), records per-file timing,
and generates benchmark diagrams (latency distribution, by file type, etc.).
Uses parallel workers like BatchProcessor.
"""

import json
import multiprocessing
import sys
import time
import statistics
from pathlib import Path
from typing import Optional
from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from preocr import needs_ocr
from preocr.utils.logger import suppress_pdf_warnings


def _get_default_workers() -> int:
    """Auto-detect workers from CPU count. Leaves headroom for OS, caps for memory safety."""
    try:
        cpu_count = multiprocessing.cpu_count()
    except Exception:
        return 2
    # Leave 4 cores for OS, cap at 8 to avoid memory pressure (PDF workers are heavy)
    return max(1, min(cpu_count - 4, 8))


def _process_single_file_timed(
    file_path: str,
    use_cache: bool,
    layout_aware: bool,
    page_level: bool,
) -> dict:
    """Worker that times each file (for benchmark). Must be at module level for pickling."""
    try:
        with suppress_pdf_warnings():
            start = time.perf_counter()
            result = needs_ocr(
                file_path,
                page_level=page_level,
                layout_aware=layout_aware,
                use_cache=use_cache,
            )
            elapsed = time.perf_counter() - start
        result["file_path"] = file_path
        result["time"] = elapsed
        result["error"] = None
        return result
    except Exception as e:
        return {
            "file_path": file_path,
            "needs_ocr": None,
            "time": 0.0,
            "error": str(e),
            "error_type": type(e).__name__,
        }


def _log_result(result: dict, index: int, total: int, max_name_len: int = 52) -> None:
    """Print a single PDF result line."""
    fp = result.get("file_path", "?")
    name = Path(fp).name
    if len(name) > max_name_len:
        name = name[: max_name_len - 3] + "..."
    err = result.get("error")
    if err:
        print(f"  [{index}/{total}] ✗ {name}  ERROR: {err}")
        return
    needs = result.get("needs_ocr")
    ocr_str = "OCR" if needs else "no-OCR"
    ms = (result.get("time") or 0) * 1000
    pages = result.get("page_count")
    extra = f" ({pages} pg)" if pages else ""
    print(f"  [{index}/{total}] {ocr_str:6}  {ms:6.0f}ms  {name}{extra}")


def run_timed_batch(
    directory: Path,
    layout_aware: bool = True,
    page_level: bool = True,
    use_cache: bool = False,
    max_workers: int = 8,
    extensions: tuple = (".pdf",),
    recursive: bool = True,
    max_files: Optional[int] = None,
    max_size_mb: Optional[float] = None,
    verbose: bool = False,
    timeout_seconds: Optional[float] = None,
) -> tuple[list, float]:
    """Run batch with per-file timing. Returns (results, total_wall_time)."""
    pattern = "**/*" if recursive else "*"
    files = []
    for ext in extensions:
        files.extend(directory.glob(f"{pattern}{ext}"))
        files.extend(directory.glob(f"{pattern}{ext.upper()}"))
    files = sorted(set(files))

    # Filter by size (helps on low-spec machines)
    if max_size_mb is not None:
        max_bytes = int(max_size_mb * 1024 * 1024)
        filtered = []
        for f in files:
            try:
                if f.stat().st_size <= max_bytes:
                    filtered.append(f)
            except OSError:
                pass
        files = filtered

    if max_files is not None and max_files > 0:
        files = files[:max_files]

    if not files:
        return [], 0.0

    results = []
    total_files = len(files)
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _process_single_file_timed,
                str(f),
                use_cache,
                layout_aware,
                page_level,
            ): str(f)
            for f in files
        }
        done = 0
        for future in as_completed(futures):
            file_path = str(futures[future])
            try:
                result = future.result(timeout=timeout_seconds) if timeout_seconds else future.result()
            except FuturesTimeoutError:
                result = {
                    "file_path": file_path,
                    "needs_ocr": None,
                    "time": timeout_seconds or 0,
                    "error": f"Timeout after {timeout_seconds}s",
                    "error_type": "TimeoutError",
                }
            results.append(result)
            done += 1
            if verbose:
                _log_result(result, done, total_files)
    total = time.perf_counter() - start
    return results, total


def generate_diagram(results: list, total_wall: float, output_path: Path) -> None:
    """Generate benchmark diagrams using matplotlib."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("⚠️  matplotlib not installed. Install with: pip install matplotlib")
        return

    valid = [r for r in results if r.get("time") is not None and r.get("error") is None]
    if not valid:
        print("⚠️  No valid results for diagram")
        return

    times = [r["time"] * 1000 for r in valid]
    by_type = defaultdict(list)
    for r in valid:
        ft = r.get("file_type") or Path(r["file_path"]).suffix.lower().lstrip(".") or "unknown"
        by_type[ft].append(r["time"] * 1000)

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # 1. Latency distribution (histogram)
    ax1 = axes[0, 0]
    ax1.hist(times, bins=min(50, len(times)), edgecolor="black", alpha=0.7)
    ax1.set_xlabel("Time (ms)")
    ax1.set_ylabel("Count")
    ax1.set_title("Latency Distribution")
    ax1.axvline(statistics.median(times), color="red", linestyle="--", label=f"Median: {statistics.median(times):.0f}ms")
    ax1.legend()

    # 2. By file type (bar chart)
    ax2 = axes[0, 1]
    types = sorted(by_type.keys())
    counts = [len(by_type[t]) for t in types]
    avg_times = [statistics.mean(by_type[t]) for t in types]
    x = np.arange(len(types))
    width = 0.35
    ax2.bar(x - width / 2, counts, width, label="Count")
    ax2_twin = ax2.twinx()
    ax2_twin.bar(x + width / 2, avg_times, width, color="orange", alpha=0.7, label="Avg ms")
    ax2.set_xticks(x)
    ax2.set_xticklabels(types)
    ax2.set_ylabel("File count")
    ax2_twin.set_ylabel("Avg time (ms)")
    ax2.set_title("By File Type")
    ax2.legend(loc="upper left")
    ax2_twin.legend(loc="upper right")

    # 3. Summary stats (text)
    ax3 = axes[1, 0]
    ax3.axis("off")
    stats_text = f"""
    Benchmark Summary
    ─────────────────
    Total files:     {len(results)}
    Valid:           {len(valid)}
    Errors:          {len(results) - len(valid)}

    Wall time:       {total_wall:.2f}s
    Throughput:      {len(valid) / total_wall:.1f} files/sec

    Latency (ms):
      Min:           {min(times):.0f}
      Max:           {max(times):.0f}
      Mean:          {statistics.mean(times):.0f}
      Median:        {statistics.median(times):.0f}
      P95:           {sorted(times)[min(int(len(times) * 0.95), len(times) - 1)]:.0f}

    OCR Decision:
      Needs OCR:     {sum(1 for r in valid if r.get('needs_ocr'))}
      No OCR:        {sum(1 for r in valid if not r.get('needs_ocr'))}
    """
    ax3.text(0.1, 0.5, stats_text, fontsize=11, family="monospace", verticalalignment="center")

    # 4. Time vs file size (scatter, if we have size)
    ax4 = axes[1, 1]
    sizes = []
    times_s = []
    for r in valid:
        p = Path(r["file_path"])
        if p.exists():
            sizes.append(p.stat().st_size / (1024 * 1024))
            times_s.append(r["time"] * 1000)
    if sizes and times_s:
        ax4.scatter(sizes, times_s, alpha=0.5)
        ax4.set_xlabel("File size (MB)")
        ax4.set_ylabel("Time (ms)")
        ax4.set_title("Time vs File Size")
    else:
        ax4.text(0.5, 0.5, "Size data unavailable", ha="center", va="center")
        ax4.set_title("Time vs File Size")

    plt.suptitle("PreOCR Batch Benchmark - Full Dataset", fontsize=14)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"📊 Diagram saved: {output_path}")


def main():
    import argparse

    root = Path(__file__).resolve().parent.parent
    default_dir = root / "datasets"

    parser = argparse.ArgumentParser(description="Full dataset benchmark with diagram")
    parser.add_argument("directory", type=str, default=str(default_dir), nargs="?")
    parser.add_argument("--layout-aware", action="store_true", default=True, help="Layout-aware (default)")
    parser.add_argument("--no-layout-aware", action="store_true", dest="no_layout", help="Disable layout-aware")
    parser.add_argument("--page-level", action="store_true", default=True)
    parser.add_argument("--no-cache", action="store_true", default=True, help="No cache for fair benchmark")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        metavar="N",
        help=f"Parallel workers (default: auto from CPU count, currently {_get_default_workers()})",
    )
    parser.add_argument("--max-files", type=int, default=None, help="Limit files (e.g. 30 for quick run on laptop)")
    parser.add_argument("--max-size-mb", type=float, default=None, help="Skip files larger than N MB")
    parser.add_argument("--recursive", action="store_true", default=True, help="Scan subdirs (default)")
    parser.add_argument("--no-recursive", action="store_true", dest="no_recursive", help="Top-level only")
    parser.add_argument("-o", "--output", type=str, help="Output JSON for results")
    parser.add_argument("--diagram", type=str, default="benchmark_diagram.png", help="Output diagram path")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show PDF-wise log")
    parser.add_argument(
        "--timeout",
        type=float,
        default=60,
        metavar="SEC",
        help="Per-file timeout in seconds (default 60, 0=no limit)",
    )

    args = parser.parse_args()
    layout_aware = not args.no_layout
    workers = args.workers if args.workers is not None else _get_default_workers()

    directory = Path(args.directory).resolve()
    if not directory.exists():
        print(f"❌ Directory not found: {directory}")
        sys.exit(1)

    print("📊 PreOCR Full Dataset Benchmark (Batch)")
    print(f"   Directory: {directory}")
    print(f"   Layout-aware: {layout_aware} | Page-level: {args.page_level}")
    workers_src = "auto" if args.workers is None else "manual"
    print(f"   Workers: {workers} ({workers_src}) | Cache: {not args.no_cache}")
    if args.max_files:
        print(f"   Max files: {args.max_files}")
    if args.max_size_mb:
        print(f"   Max size: {args.max_size_mb} MB")
    if args.timeout and args.timeout > 0:
        print(f"   Per-file timeout: {args.timeout}s")
    print("=" * 80)
    if args.verbose:
        print("\n📄 PDF-wise log:\n")

    results, total = run_timed_batch(
        directory,
        layout_aware=layout_aware,
        page_level=args.page_level,
        use_cache=not args.no_cache,
        max_workers=workers,
        recursive=not args.no_recursive,
        max_files=args.max_files,
        max_size_mb=args.max_size_mb,
        verbose=args.verbose,
        timeout_seconds=args.timeout if args.timeout > 0 else None,
    )

    valid = [r for r in results if r.get("time") is not None and r.get("error") is None]
    times = [r["time"] * 1000 for r in valid]

    print(f"\n⚡ Results: {len(valid)}/{len(results)} files (errors: {len(results) - len(valid)})")
    print(f"   Total wall time: {total:.2f}s")
    if valid:
        print(f"   Throughput:      {len(valid) / total:.1f} files/sec")
        print(f"   Latency (ms):    min={min(times):.0f} max={max(times):.0f} mean={statistics.mean(times):.0f} median={statistics.median(times):.0f}")
        needs = sum(1 for r in valid if r.get("needs_ocr"))
        print(f"   OCR decision:    needs_ocr={needs} no_ocr={len(valid) - needs}")

    # Generate diagram
    diagram_path = Path(args.diagram)
    if not diagram_path.is_absolute():
        diagram_path = Path(__file__).parent / diagram_path
    generate_diagram(results, total, diagram_path)

    if args.output:
        out = {
            "total_files": len(results),
            "valid": len(valid),
            "total_wall_seconds": total,
            "results": results,
        }
        with open(args.output, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\n✅ Results saved: {args.output}")

    print("=" * 80)


if __name__ == "__main__":
    main()
