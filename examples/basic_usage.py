"""Basic usage example for PreOCR."""

from pathlib import Path
from preocr import needs_ocr


def main():
    """Demonstrate basic PreOCR usage."""
    # Use real files from the data-source-formats directory
    data_dir = Path(__file__).parent.parent / "data-source-formats"
    
    files = [
        data_dir / "product-manual.pdf",
        data_dir / "Multiturn-ContosoBenefits.pdf",
        data_dir / "structured.docx",
        data_dir / "Scenario_Responses_Friendly.tsv",
    ]

    print("PreOCR - Basic Usage Example\n")
    print("=" * 50)

    for file_path in files:
        if not file_path.exists():
            print(f"\n⚠️  File not found: {file_path.name} (skipping)")
            continue
            
        try:
            result = needs_ocr(str(file_path))

            status = "✅ NO OCR" if not result["needs_ocr"] else "🔍 NEEDS OCR"

            print(f"\nFile: {file_path.name}")
            print(f"Status: {status}")
            print(f"Type: {result['file_type']}")
            print(f"Category: {result['category']}")
            print(f"Confidence: {result['confidence']:.2f}")
            print(f"Reason: {result['reason']}")

            # Show some signals
            signals = result["signals"]
            if signals.get("text_length", 0) > 0:
                print(f"Text length: {signals['text_length']} characters")
            if signals.get("image_entropy") is not None:
                print(f"Image entropy: {signals['image_entropy']:.2f}")

        except FileNotFoundError:
            print(f"\nFile not found: {file_path}")
        except Exception as e:
            print(f"\nError processing {file_path}: {e}")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
