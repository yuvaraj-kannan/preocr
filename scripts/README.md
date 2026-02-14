# Validation and Benchmarking Scripts

This directory contains utility scripts for validating and benchmarking PreOCR.

## Scripts

### `validate_accuracy.py`

Validates PreOCR accuracy by comparing predictions against ground truth labels.

**Usage:**
```bash
# Create ground truth template
python scripts/validate_accuracy.py --create-template /path/to/test/files

# Edit ground_truth.json to set needs_ocr: true/false for each file

# Run validation
python scripts/validate_accuracy.py /path/to/test/files --ground-truth scripts/ground_truth.json
```

**Features:**
- Ground truth template generation
- Accuracy, precision, recall, F1-score calculation
- Confusion matrix (TP, FP, TN, FN)
- Breakdown by file type
- Error analysis

### `benchmark_accuracy.py`

Comprehensive benchmark combining performance timing and accuracy validation.

**Usage:**
```bash
python scripts/benchmark_accuracy.py /path/to/test/files --ground-truth scripts/ground_truth.json
```

**Features:**
- Performance timing (min, max, mean, median, P95)
- Accuracy validation (if ground truth provided)
- Combined reporting
- JSON output support

### `auto_label_ground_truth.py`

Helper script to automatically label ground truth files by checking if they have extractable text.

**Usage:**
```bash
python scripts/auto_label_ground_truth.py scripts/ground_truth.json
```

**Features:**
- Automatically checks PDFs for extractable text
- Labels text files as `needs_ocr: false`
- Labels images as `needs_ocr: true`
- Provides starting point for manual review

## Ground Truth File

`ground_truth.json` is an example ground truth file. See [docs/GROUND_TRUTH_FORMAT.md](../docs/GROUND_TRUTH_FORMAT.md) for format details.

## Documentation

- [Validation Guide](../docs/VALIDATION_GUIDE.md) - Complete validation instructions
- [Ground Truth Format](../docs/GROUND_TRUTH_FORMAT.md) - Ground truth file format
- [Accuracy Validation](../docs/ACCURACY_VALIDATION.md) - Validation status and recommendations


