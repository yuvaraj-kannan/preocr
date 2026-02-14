#!/usr/bin/env python3
"""
Helper script to automatically label ground truth files by checking if they have extractable text.
This is a starting point - you should review and correct the labels manually.
"""

import json
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("❌ Error: pdfplumber not installed. Install with: pip install pdfplumber")
    sys.exit(1)


def check_pdf_has_text(file_path: Path) -> bool:
    """Check if PDF has extractable text."""
    try:
        with pdfplumber.open(file_path) as pdf:
            if len(pdf.pages) == 0:
                return False
            # Check first few pages for text
            text = ""
            for page in pdf.pages[:3]:  # Check first 3 pages
                page_text = page.extract_text()
                if page_text:
                    text += page_text
            # If we have substantial text (more than 50 chars), it's likely digital
            return len(text.strip()) > 50
    except Exception as e:
        print(f"⚠️  Warning: Could not check {file_path.name}: {e}")
        return None


def auto_label_ground_truth(ground_truth_file: str) -> None:
    """Auto-label ground truth file by checking files."""
    with open(ground_truth_file, "r") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print("❌ Error: Ground truth file must be a JSON array")
        sys.exit(1)

    print(f"🔍 Analyzing {len(data)} files...\n")

    for i, item in enumerate(data, 1):
        file_path = Path(item["file"])

        # Skip if already labeled
        if item.get("needs_ocr") is not None:
            print(f"[{i}/{len(data)}] {file_path.name} - Already labeled: {item['needs_ocr']}")
            continue

        # Determine label based on file type
        if file_path.suffix.lower() == ".txt":
            # Text files never need OCR
            item["needs_ocr"] = False
            item["notes"] = "Text file - auto-labeled"
            print(f"[{i}/{len(data)}] {file_path.name} - ✅ Labeled: False (text file)")

        elif file_path.suffix.lower() == ".pdf":
            # Check PDF for extractable text
            if not file_path.exists():
                print(f"[{i}/{len(data)}] {file_path.name} - ⚠️  File not found")
                continue

            has_text = check_pdf_has_text(file_path)
            if has_text is True:
                item["needs_ocr"] = False
                item["notes"] = "PDF with extractable text - auto-labeled"
                print(f"[{i}/{len(data)}] {file_path.name} - ✅ Labeled: False (has text)")
            elif has_text is False:
                item["needs_ocr"] = True
                item["notes"] = "PDF without extractable text (likely scanned) - auto-labeled"
                print(f"[{i}/{len(data)}] {file_path.name} - ✅ Labeled: True (no text)")
            else:
                print(f"[{i}/{len(data)}] {file_path.name} - ⚠️  Could not determine")

        else:
            # Images and other files - assume they need OCR
            item["needs_ocr"] = True
            item["notes"] = f"{file_path.suffix} file - auto-labeled (assumed needs OCR)"
            print(f"[{i}/{len(data)}] {file_path.name} - ✅ Labeled: True ({file_path.suffix})")

    # Save updated file
    with open(ground_truth_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\n✅ Updated {ground_truth_file}")
    print("⚠️  Please review the labels and correct any mistakes manually!")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python auto_label_ground_truth.py <ground_truth.json>")
        sys.exit(1)

    auto_label_ground_truth(sys.argv[1])
