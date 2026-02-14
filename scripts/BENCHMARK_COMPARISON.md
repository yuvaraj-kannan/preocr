# Benchmark Comparison (Fresh Run)

## 1. benchmark_with_accuracy — datasets (17 files, ground truth)

| Metric | Value |
|--------|-------|
| **Overall accuracy** | **100.00%** |
| **PDF accuracy** | **9/9 (100%)** |
| Mean time | 644 ms |
| Median time | 102 ms |
| False positives | 0 |
| Confusion matrix | TP: 0, FP: 0, TN: 9, FN: 0 |

---

## 2. benchmark_planner — datasets (30 PDFs)

| Metric | Value |
|--------|-------|
| **Agreement** | **30/30 (100%)** |
| Baseline needs_ocr | 0 |
| Planner needs_ocr | 0 |
| Baseline avg time/file | 5.876 s |
| Planner avg time/file | 7.164 s |

---

## 3. Summary

| Benchmark | Dataset | Files | Accuracy / Agreement |
|-----------|---------|-------|----------------------|
| benchmark_accuracy | datasets | 17 | **100%** (9/9 PDFs correct) |
| benchmark_planner | datasets | 30 | **100%** (30/30 agree) |

**Previous baseline (pre FP fix):** datasets 77.78%, benchmark_planner 90% agreement (3 disagreements).
