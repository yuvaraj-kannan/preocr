"""Command-line interface for PreOCR."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from .core.detector import needs_ocr
from .constants import Config
from .reporting import generate_html_report, ReportConfig
from .version import __version__


def format_json_serializable(obj: Any) -> Any:
    """Convert non-serializable objects to JSON-safe types."""
    if isinstance(obj, Path):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: format_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [format_json_serializable(item) for item in obj]
    return obj


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="preocr")
@click.pass_context
def main(ctx: click.Context) -> None:
    """PreOCR – Fast OCR detection for document processing pipelines.
    
    Determine if files need OCR before expensive processing.
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed decision breakdown and signals.",
)
@click.option(
    "--signals",
    is_flag=True,
    help="Include raw signals (text_length, image_coverage, etc.) in output.",
)
@click.option(
    "--page-level",
    is_flag=True,
    help="Analyze each page separately (for PDFs only).",
)
@click.option(
    "--layout-aware",
    is_flag=True,
    help="Use layout analysis for improved accuracy (slower).",
)
@click.option(
    "--config-preset",
    "-c",
    type=click.Choice([
        "default",
        "scanned-documents",
        "cost-optimization",
        "tables-and-forms",
        "mixed-content",
        "high-precision",
    ]),
    default="default",
    help="Config preset for specific use cases.",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json", "table", "text"]),
    default="table",
    help="Output format.",
)
def check(
    file_path: str,
    verbose: bool,
    signals: bool,
    page_level: bool,
    layout_aware: bool,
    config_preset: str,
    format: str,
) -> None:
    """Analyze a single file to determine if it needs OCR.
    
    Example:
        preocr check document.pdf --verbose
        preocr check document.pdf --format json
        preocr check document.pdf -c scanned-documents
        preocr check document.pdf --config-preset high-precision
    """
    try:
        # Load config preset
        if config_preset == "scanned-documents":
            config = Config.for_scanned_documents()
        elif config_preset == "cost-optimization":
            config = Config.for_cost_optimization()
        elif config_preset == "tables-and-forms":
            config = Config.for_tables_and_forms()
        elif config_preset == "mixed-content":
            config = Config.for_mixed_content()
        elif config_preset == "high-precision":
            config = Config.high_precision()
        else:
            config = None
        
        file_path_obj = Path(file_path)
        
        with click.progressbar(
            length=100,
            label=f"Analyzing {file_path_obj.name}",
            show_pos=True,
        ) as bar:
            result = needs_ocr(
                file_path_obj,
                page_level=page_level,
                layout_aware=layout_aware,
                config=config,
            )
            bar.update(100)

        if format == "json":
            output = format_json_serializable(result)
            if not signals:
                output.pop("signals", None)
            click.echo(json.dumps(output, indent=2))

        elif format == "text":
            click.echo(f"\n📄 File: {file_path_obj.name}")
            click.echo(f"📋 File Type: {result.get('file_type', 'unknown')}")
            click.echo("")
            
            needs = result.get("needs_ocr", False)
            icon = "❌ NEEDS OCR" if needs else "✅ DIGITAL"
            click.echo(f"{icon}")
            click.echo(f"Reason: {result.get('reason', 'unknown')}")
            click.echo(f"Confidence: {result.get('confidence', 0):.1%}")
            click.echo(f"Category: {result.get('category', 'unknown')}")
            
            if verbose:
                click.echo("\n📊 Decision Breakdown:")
                click.echo(f"  Reason Code: {result.get('reason_code', 'unknown')}")
                
            if signals and "signals" in result:
                sigs = result["signals"]
                click.echo("\n🔍 Signals:")
                click.echo(f"  Text length: {sigs.get('text_length', 0)} chars")
                text_cov = sigs.get('text_coverage')
                text_cov_str = f"{text_cov:.1f}%" if text_cov is not None and text_cov >= 0 else "N/A (not analyzed)"
                click.echo(f"  Text coverage: {text_cov_str}")
                img_cov = sigs.get('image_coverage')
                img_cov_str = f"{img_cov:.1f}%" if img_cov is not None and img_cov >= 0 else "N/A (not analyzed)"
                click.echo(f"  Image coverage: {img_cov_str}")
                layout_type = sigs.get('layout_type')
                if layout_type:
                    click.echo(f"  Layout type: {layout_type}")
                if sigs.get("font_count") is not None:
                    click.echo(f"  Fonts detected: {sigs.get('font_count')}")
                if text_cov is None and layout_aware:
                    click.echo(f"  ℹ️  Layout analysis skipped (early exit: {result.get('reason_code', 'N/A')})")
                
            if page_level and result.get("pages"):
                click.echo(f"\n📑 Page Analysis ({len(result['pages'])} pages):")
                for page in result["pages"][:5]:  # Show first 5 pages
                    icon = "❌" if page.get("needs_ocr") else "✅"
                    click.echo(
                        f"  Page {page.get('page_number', '?')}: {icon} "
                        f"(confidence: {page.get('confidence', 0):.1%})"
                    )
                if len(result["pages"]) > 5:
                    click.echo(f"  ... and {len(result['pages']) - 5} more pages")

        else:  # table format (default)
            click.echo("\n" + "─" * 70)
            click.echo(f"{'File':<40} {file_path_obj.name:<28} │")
            click.echo(f"{'File Type':<40} {result.get('file_type', 'unknown'):<28} │")
            needs_ocr_text = 'Yes' if result.get('needs_ocr') else 'No'
            click.echo(f"{'Needs OCR':<40} {needs_ocr_text:<28} │")
            conf_str = f"{result.get('confidence', 0):.1%}"
            click.echo(f"{'Confidence':<40} {conf_str:<28} │")
            click.echo(f"{'Category':<40} {result.get('category', 'unknown'):<28} │")
            reason_text = result.get('reason', '')[:27] if result.get('reason') else ''
            click.echo(f"{'Reason':<40} {reason_text:<28} │")
            click.echo("─" * 70 + "\n")
            
            if signals and "signals" in result:
                sigs = result["signals"]
                click.echo("Signal Details:")
                click.echo(f"  Text length: {sigs.get('text_length', 0)} chars")
                text_cov = sigs.get('text_coverage')
                text_cov_str = f"{text_cov:.1f}%" if text_cov is not None and text_cov >= 0 else "N/A"
                click.echo(f"  Text coverage: {text_cov_str}")
                img_cov = sigs.get('image_coverage')
                img_cov_str = f"{img_cov:.1f}%" if img_cov is not None and img_cov >= 0 else "N/A"
                click.echo(f"  Image coverage: {img_cov_str}")
                if text_cov is None and layout_aware:
                    click.echo(f"  ℹ️  Tip: Layout analysis was skipped (early exit: {result.get('reason_code', 'N/A')})")
                click.echo("")

    except FileNotFoundError:
        click.echo(f"❌ Error: File not found: {file_path}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        raise SystemExit(1)


@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--pattern",
    "-p",
    default="*.pdf",
    help="File pattern to match (e.g., '*.pdf', '*.docx').",
)
@click.option(
    "--recursive",
    "-r",
    is_flag=True,
    help="Recursively search subdirectories.",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["json", "csv", "table"]),
    default="table",
    help="Output format.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Save results to file (optional).",
)
@click.option(
    "--layout-aware",
    is_flag=True,
    help="Use layout analysis for improved accuracy (slower).",
)
@click.option(
    "--config-preset",
    "-c",
    type=click.Choice([
        "default",
        "scanned-documents",
        "cost-optimization",
        "tables-and-forms",
        "mixed-content",
        "high-precision",
    ]),
    default="default",
    help="Config preset for specific use cases.",
)
@click.option(
    "--limit",
    "-l",
    type=int,
    default=None,
    help="Limit number of files to analyze.",
)
@click.option(
    "--report",
    "--html-report",
    type=click.Path(),
    help="Generate HTML report at specified path.",
)
@click.option(
    "--report-theme",
    type=click.Choice(["light", "dark"]),
    default="light",
    help="HTML report theme.",
)
def batch_analyze(
    directory: str,
    pattern: str,
    recursive: bool,
    format: str,
    output: Optional[str],
    layout_aware: bool,
    config_preset: str,
    limit: Optional[int],
    report: Optional[str],
    report_theme: str,
) -> None:
    """Analyze multiple files in a directory.
    
    Example:
        preocr batch-analyze ./documents --pattern '*.pdf'
        preocr batch-analyze ./documents -r --format csv --output results.csv
        preocr batch-analyze ./documents -c cost-optimization --format csv --output results.csv
    """
    try:
        # Load config preset
        if config_preset == "scanned-documents":
            config = Config.for_scanned_documents()
        elif config_preset == "cost-optimization":
            config = Config.for_cost_optimization()
        elif config_preset == "tables-and-forms":
            config = Config.for_tables_and_forms()
        elif config_preset == "mixed-content":
            config = Config.for_mixed_content()
        elif config_preset == "high-precision":
            config = Config.high_precision()
        else:
            config = None
        
        dir_path = Path(directory)
        
        # Find files
        search_pattern = f"**/{pattern}" if recursive else pattern
        files = sorted(dir_path.glob(search_pattern))
        
        if not files:
            click.echo(f"⚠️  No files found matching '{pattern}' in {directory}", err=True)
            return
        
        if limit:
            files = files[:limit]
        
        results: List[Dict[str, Any]] = []
        
        with click.progressbar(
            files,
            label="Analyzing files",
            show_pos=True,
        ) as bar:
            for file_path in bar:
                try:
                    result = needs_ocr(file_path, layout_aware=layout_aware, config=config)
                    results.append({
                        "file": str(file_path.relative_to(dir_path)),
                        "needs_ocr": result.get("needs_ocr"),
                        "confidence": result.get("confidence"),
                        "file_type": result.get("file_type"),
                        "category": result.get("category"),
                        "reason_code": result.get("reason_code"),
                    })
                except Exception as e:
                    results.append({
                        "file": str(file_path.relative_to(dir_path)),
                        "needs_ocr": None,
                        "confidence": 0.0,
                        "file_type": "error",
                        "category": "error",
                        "reason_code": f"ERROR: {str(e)}",
                    })
        
        # Output results
        if format == "json":
            output_text = json.dumps(format_json_serializable(results), indent=2)
        
        elif format == "csv":
            import csv
            import io
            
            output_buffer = io.StringIO()
            writer = csv.DictWriter(
                output_buffer,
                fieldnames=["file", "needs_ocr", "confidence", "file_type", "category", "reason_code"],
            )
            writer.writeheader()
            writer.writerows(results)
            output_text = output_buffer.getvalue()
        
        else:  # table format
            # Calculate statistics
            total = len(results)
            needs_ocr_count = sum(1 for r in results if r["needs_ocr"])
            digital_count = total - needs_ocr_count
            avg_confidence = sum(r["confidence"] for r in results) / total if total > 0 else 0
            
            lines = [
                "\n" + "─" * 80,
                f"{'File':<50} {'Needs OCR':<15} {'Confidence':<15}",
                "─" * 80,
            ]
            
            for result in results[:50]:  # Show first 50
                needs = "❌ Yes" if result["needs_ocr"] else "✅ No"
                conf = f"{result['confidence']:.1%}" if result["confidence"] else "–"
                filename = result["file"]
                if len(filename) > 48:
                    filename = "..." + filename[-45:]
                lines.append(f"{filename:<50} {needs:<15} {conf:<15}")
            
            if len(results) > 50:
                lines.append(f"... and {len(results) - 50} more files")
            
            lines.extend([
                "─" * 80,
                f"Summary: {total} files analyzed",
                f"  Digital (no OCR needed): {digital_count} ({digital_count/total:.1%})",
                f"  Needs OCR: {needs_ocr_count} ({needs_ocr_count/total:.1%})",
                f"  Average confidence: {avg_confidence:.1%}",
                "",
            ])
            
            output_text = "\n".join(lines)
        
        # Display or save
        if output:
            output_path = Path(output)
            output_path.write_text(output_text)
            click.echo(f"✅ Results saved to: {output_path}")
        else:
            click.echo(output_text)
        
        # Generate HTML report if requested
        if report:
            with click.progressbar(
                length=100,
                label="Generating HTML report",
                show_pos=True,
            ) as bar:
                report_config = ReportConfig(
                    title=f"PreOCR Analysis - {Path(directory).name}",
                    include_signals=True,
                    include_confidence_details=True,
                    include_summary_charts=True,
                    theme=report_theme,
                )
                report_result = generate_html_report(results, report_config)
                bar.update(100)
            
            report_path = Path(report)
            report_path.write_text(report_result.html_content)
            click.echo(f"✅ HTML report saved to: {report_path}")
    
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        raise SystemExit(1)


@main.command("generate-report")
@click.argument("results_file", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    required=True,
    help="Output HTML report path.",
)
@click.option(
    "--title",
    "-t",
    default="PreOCR Analysis Report",
    help="Report title.",
)
@click.option(
    "--theme",
    type=click.Choice(["light", "dark"]),
    default="light",
    help="HTML report theme.",
)
def generate_report(
    results_file: str,
    output: str,
    title: str,
    theme: str,
) -> None:
    """Generate an HTML report from analysis results.
    
    Takes a JSON or CSV file from batch-analyze and creates an HTML report.
    
    Example:
        preocr generate-report results.json --output report.html
        preocr generate-report results.csv -o report.html --theme dark
    """
    try:
        results_path = Path(results_file)
        output_path = Path(output)
        
        # Load results
        with click.progressbar(
            length=100,
            label="Loading results",
            show_pos=True,
        ) as bar:
            if results_path.suffix.lower() == ".json":
                results = json.loads(results_path.read_text())
            elif results_path.suffix.lower() == ".csv":
                import csv
                reader = csv.DictReader(results_path.open())
                results = []
                for row in reader:
                    # Convert string boolean to actual boolean
                    row["needs_ocr"] = row.get("needs_ocr", "").lower() in ("true", "1", "yes")
                    # Convert confidence to float
                    try:
                        row["confidence"] = float(row.get("confidence", 0))
                    except (ValueError, TypeError):
                        row["confidence"] = 0.0
                    results.append(row)
            else:
                click.echo(
                    "❌ Unsupported file format. Please use JSON or CSV.",
                    err=True,
                )
                raise SystemExit(1)
            bar.update(100)
        
        # Generate report
        with click.progressbar(
            length=100,
            label="Generating HTML report",
            show_pos=True,
        ) as bar:
            report_config = ReportConfig(
                title=title,
                include_signals=True,
                include_confidence_details=True,
                include_summary_charts=True,
                theme=theme,
            )
            report_result = generate_html_report(results, report_config)
            bar.update(100)
        
        # Save report
        output_path.write_text(report_result.html_content)
        click.echo(f"✅ HTML report saved to: {output_path}")
        
        # Print summary
        summary = report_result.summary
        click.echo(f"\n📊 Report Summary:")
        click.echo(f"  Total files: {summary['total_files']}")
        click.echo(f"  Digital: {summary['digital_count']} ({summary['digital_percentage']:.1f}%)")
        click.echo(f"  Needs OCR: {summary['ocr_needed_count']} ({summary['ocr_percentage']:.1f}%)")
        click.echo(f"  Avg confidence: {summary['average_confidence']:.1%}")
    
    except FileNotFoundError:
        click.echo(f"❌ File not found: {results_file}", err=True)
        raise SystemExit(1)
    except json.JSONDecodeError:
        click.echo(f"❌ Invalid JSON file: {results_file}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
