"""
Example: Using PreOCR Config Templates

This example shows how to use the built-in config presets for different scenarios.
Config templates make it easy to tune PreOCR for your specific use case without
manually adjusting individual thresholds.
"""

from preocr import needs_ocr, Config


def example_cost_optimization():
    """
    Example 1: Cost Optimization
    
    Goal: Maximize digital PDF detection to minimize OCR costs
    Use case: High-volume batch processing where some false negatives are acceptable
    """
    print("\n" + "="*70)
    print("Example 1: Cost Optimization Preset")
    print("="*70)
    
    config = Config.for_cost_optimization()
    
    result = needs_ocr(
        "document.pdf",
        config=config
    )
    
    print(f"Result: {'Needs OCR' if result['needs_ocr'] else 'Digital (skip OCR)'}")
    print(f"Confidence: {result['confidence']:.1%}")
    print("\n✅ Use this preset when:")
    print("   - You process thousands of documents daily")
    print("   - Minimizing OCR API calls matters")
    print("   - Some missed scans are acceptable")


def example_scanned_documents():
    """
    Example 2: Scanned Documents
    
    Goal: Detect scanned PDFs reliably (high OCR detection rate)
    Use case: Medical, legal, historical documents that are frequently scanned
    """
    print("\n" + "="*70)
    print("Example 2: Scanned Documents Preset")
    print("="*70)
    
    config = Config.for_scanned_documents()
    
    result = needs_ocr(
        "scanned_medical_record.pdf",
        config=config
    )
    
    print(f"Result: {'Needs OCR' if result['needs_ocr'] else 'Digital (skip OCR)'}")
    print(f"Confidence: {result['confidence']:.1%}")
    print("\n✅ Use this preset when:")
    print("   - Your documents are 60%+ scanned/image-heavy")
    print("   - Missing scans is worse than false positives")
    print("   - You work with medical, legal, or historical documents")


def example_tables_and_forms():
    """
    Example 3: Tables and Forms
    
    Goal: Conservative detection to preserve structured data integrity
    Use case: Financial reports, tax forms, invoices, data extraction workflows
    """
    print("\n" + "="*70)
    print("Example 3: Tables and Forms Preset")
    print("="*70)
    
    config = Config.for_tables_and_forms()
    
    result = needs_ocr(
        "invoice.pdf",
        config=config
    )
    
    print(f"Result: {'Needs OCR' if result['needs_ocr'] else 'Digital (skip OCR)'}")
    print(f"Confidence: {result['confidence']:.1%}")
    print("\n✅ Use this preset when:")
    print("   - You extract tables, forms, or structured data")
    print("   - Accuracy is critical")
    print("   - False positives (unnecessary OCR) are cheaper than false negatives")


def example_high_precision():
    """
    Example 4: High Precision
    
    Goal: Maximum accuracy in every decision
    Use case: Compliance, validation, critical workflows
    """
    print("\n" + "="*70)
    print("Example 4: High Precision Preset")
    print("="*70)
    
    config = Config.high_precision()
    
    result = needs_ocr(
        "compliance_document.pdf",
        config=config,
        layout_aware=True  # High precision also benefits from layout analysis
    )
    
    print(f"Result: {'Needs OCR' if result['needs_ocr'] else 'Digital (skip OCR)'}")
    print(f"Confidence: {result['confidence']:.1%}")
    print("\n✅ Use this preset when:")
    print("   - Accuracy matters more than speed or cost")
    print("   - Processing compliance or audit documents")
    print("   - You can afford longer processing times")


def example_batch_processing():
    """
    Example 5: Batch Processing with Presets
    
    Goal: Process multiple files with consistent config
    """
    print("\n" + "="*70)
    print("Example 5: Batch Processing with Presets")
    print("="*70)
    
    from pathlib import Path
    
    # Use cost optimization for batch processing
    config = Config.for_cost_optimization()
    
    pdf_files = [
        "report1.pdf",
        "report2.pdf",
        "report3.pdf",
    ]
    
    results = []
    for pdf_file in pdf_files:
        try:
            result = needs_ocr(pdf_file, config=config)
            results.append({
                "file": Path(pdf_file).name,
                "needs_ocr": result["needs_ocr"],
                "confidence": result["confidence"]
            })
        except FileNotFoundError:
            print(f"⚠️  File not found: {pdf_file}")
    
    # Print summary
    print(f"\nAnalyzed {len(results)} files with {config.__class__.__name__}")
    digital_count = sum(1 for r in results if not r["needs_ocr"])
    ocr_count = len(results) - digital_count
    
    print(f"Digital (skip OCR): {digital_count}")
    print(f"Needs OCR: {ocr_count}")


def example_cli_usage():
    """
    CLI Usage Examples
    
    You can also use config presets from the command line!
    """
    print("\n" + "="*70)
    print("CLI Usage Examples")
    print("="*70)
    print("""
# Check a single file with cost optimization preset
preocr check document.pdf -c cost-optimization --verbose

# Check with scanned documents preset
preocr check document.pdf -c scanned-documents --format json

# Batch analyze with high precision preset
preocr batch-analyze ./docs -r -c high-precision --format csv --output results.csv

# Use tables-and-forms preset for structured data
preocr batch-analyze ./invoices -c tables-and-forms --format table

Available presets:
  - default: Balanced thresholds (original behavior)
  - scanned-documents: Strict OCR detection for scanned PDFs
  - cost-optimization: Aggressive digital detection to skip OCR
  - tables-and-forms: Conservative for structured data extraction
  - mixed-content: Balanced for mixed document types
  - high-precision: Maximum accuracy over speed/cost
    """)


def example_creating_custom_config():
    """
    Example 6: Creating Custom Configurations
    
    If presets don't fit your exact needs, you can customize them further!
    """
    print("\n" + "="*70)
    print("Example 6: Customizing Presets")
    print("="*70)
    
    # Start with a preset and customize
    config = Config.for_cost_optimization()
    
    # Modify specific thresholds for your domain
    custom_config = Config(
        # Copy most settings from cost-optimization
        min_text_length=config.min_text_length,
        min_office_text_length=config.min_office_text_length,
        ocr_score_low_band_max=config.ocr_score_low_band_max,
        ocr_score_high_band_min=config.ocr_score_high_band_min,
        ocr_decision_threshold=config.ocr_decision_threshold,
        # But customize digital bias for your domain
        digital_bias_text_coverage_min=70.0,  # Higher threshold
        digital_bias_image_coverage_max=30.0,  # Lower image threshold
    )
    
    print("✅ Custom config created by starting with a preset and adjusting thresholds")
    print(f"   ocr_decision_threshold: {custom_config.ocr_decision_threshold}")
    print(f"   digital_bias_text_coverage_min: {custom_config.digital_bias_text_coverage_min}")
    print(f"   digital_bias_image_coverage_max: {custom_config.digital_bias_image_coverage_max}")


if __name__ == "__main__":
    print("\n" + "🚀 PreOCR Config Templates Examples")
    print("=" * 70)
    
    # Note: These examples use placeholder file paths
    # In real usage, replace with actual files
    
    try:
        example_cost_optimization()
    except FileNotFoundError:
        print("(File not found - example shows usage pattern)")
    
    example_scanned_documents.__doc__ and print(example_scanned_documents.__doc__)
    example_tables_and_forms.__doc__ and print(example_tables_and_forms.__doc__)
    example_high_precision.__doc__ and print(example_high_precision.__doc__)
    example_batch_processing()
    example_cli_usage()
    example_creating_custom_config()
    
    print("\n" + "="*70)
    print("📚 For more info, see documentation: https://preocr.io")
    print("="*70 + "\n")
