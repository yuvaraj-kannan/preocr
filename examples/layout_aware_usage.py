"""Example: Using layout-aware detection for improved accuracy."""

from pathlib import Path
from preocr import needs_ocr


def main():
    """Demonstrate layout-aware OCR detection."""
    
    # Use a real PDF file from the data-source-formats directory
    sample_file = Path(__file__).parent.parent / "data-source-formats" / "product-manual.pdf"
    
    if not sample_file.exists():
        print(f"Error: Sample file not found: {sample_file}")
        print("Please ensure the data-source-formats directory contains PDF files.")
        return

    # Example 1: Basic usage (no layout analysis)
    print("=" * 60)
    print("Example 1: Basic Detection (No Layout Analysis)")
    print("=" * 60)
    print(f"File: {sample_file.name}")
    result = needs_ocr(str(sample_file))
    print(f"Needs OCR: {result['needs_ocr']}")
    print(f"Reason: {result['reason']}")
    print(f"Confidence: {result['confidence']}")
    print()

    # Example 2: Layout-aware detection (improved accuracy)
    print("=" * 60)
    print("Example 2: Layout-Aware Detection")
    print("=" * 60)
    print(f"File: {sample_file.name}")
    result = needs_ocr(str(sample_file), layout_aware=True)
    print(f"Needs OCR: {result['needs_ocr']}")
    print(f"Reason: {result['reason']}")
    print(f"Confidence: {result['confidence']}")

    if "layout" in result:
        layout = result["layout"]
        print("\nLayout Analysis:")
        print(f"  Layout Type: {layout['layout_type']}")
        print(f"  Text Coverage: {layout['text_coverage']}%")
        print(f"  Image Coverage: {layout['image_coverage']}%")
        print(f"  Has Images: {layout['has_images']}")
        print(f"  Is Mixed Content: {layout['is_mixed_content']}")
        print(f"  Text Density: {layout['text_density']}")
    print()

    # Example 3: Layout-aware with page-level analysis
    print("=" * 60)
    print("Example 3: Layout-Aware + Page-Level Analysis")
    print("=" * 60)
    print(f"File: {sample_file.name}")
    result = needs_ocr(str(sample_file), page_level=True, layout_aware=True)
    print(f"Needs OCR: {result['needs_ocr']}")
    print(f"Reason: {result['reason']}")

    if "pages" in result and "layout" in result:
        print("\nPage-Level Layout Analysis:")
        for page in result["pages"]:
            page_num = page["page_number"]
            needs_ocr_page = page["needs_ocr"]

            # Find corresponding layout data
            layout_pages = result["layout"].get("pages", [])
            layout_page = next((p for p in layout_pages if p["page_number"] == page_num), None)

            if layout_page:
                print(f"\n  Page {page_num}:")
                print(f"    Needs OCR: {needs_ocr_page}")
                print(f"    Layout Type: {layout_page['layout_type']}")
                print(f"    Text Coverage: {layout_page['text_coverage']}%")
                print(f"    Image Coverage: {layout_page['image_coverage']}%")
                print(f"    Is Mixed: {layout_page['is_mixed_content']}")


if __name__ == "__main__":
    main()
