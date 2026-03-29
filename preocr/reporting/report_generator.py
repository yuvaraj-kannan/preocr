"""HTML report generation for PreOCR decision analysis."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ReportConfig:
    """Configuration for report generation."""
    title: str = "PreOCR Analysis Report"
    include_signals: bool = True
    include_confidence_details: bool = True
    include_summary_charts: bool = True
    theme: str = "light"  # "light" or "dark"


@dataclass
class DecisionReport:
    """Result of report generation."""
    html_content: str
    summary: Dict[str, Any]
    file_path: Optional[Path] = None


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _format_reason(reason: str) -> str:
    """Format reason text with line breaks."""
    return _escape_html(reason).replace("\n", "<br>")


def generate_html_report(
    results: List[Dict[str, Any]],
    config: Optional[ReportConfig] = None,
) -> DecisionReport:
    """
    Generate an HTML report from batch analysis results.
    
    Args:
        results: List of result dictionaries from needs_ocr()
        config: ReportConfig for customization
    
    Returns:
        DecisionReport with HTML content and summary statistics
    """
    if config is None:
        config = ReportConfig()
    
    # Calculate summary statistics
    total_files = len(results)
    ocr_needed = sum(1 for r in results if r.get("needs_ocr"))
    digital = total_files - ocr_needed
    avg_confidence = (
        sum(r.get("confidence", 0) for r in results) / total_files
        if total_files > 0
        else 0
    )
    
    # Group by file type
    file_types = {}
    for result in results:
        ft = result.get("file_type", "unknown")
        if ft not in file_types:
            file_types[ft] = {"total": 0, "ocr": 0}
        file_types[ft]["total"] += 1
        if result.get("needs_ocr"):
            file_types[ft]["ocr"] += 1
    
    # Group by category
    categories = {}
    for result in results:
        cat = result.get("category", "unknown")
        if cat not in categories:
            categories[cat] = {"total": 0, "ocr": 0}
        categories[cat]["total"] += 1
        if result.get("needs_ocr"):
            categories[cat]["ocr"] += 1
    
    summary = {
        "total_files": total_files,
        "digital_count": digital,
        "ocr_needed_count": ocr_needed,
        "digital_percentage": 100 * digital / total_files if total_files > 0 else 0,
        "ocr_percentage": 100 * ocr_needed / total_files if total_files > 0 else 0,
        "average_confidence": avg_confidence,
        "file_types": file_types,
        "categories": categories,
        "generated_at": datetime.now().isoformat(),
    }
    
    # Generate HTML
    html = _build_html(results, config, summary)
    
    return DecisionReport(html_content=html, summary=summary)


def _build_html(
    results: List[Dict[str, Any]],
    config: ReportConfig,
    summary: Dict[str, Any],
) -> str:
    """Build the complete HTML document."""
    theme_css = _get_theme_css(config.theme)
    
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='UTF-8'>",
        "  <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        f"  <title>{_escape_html(config.title)}</title>",
        "  <style>",
        theme_css,
        "  </style>",
        "</head>",
        "<body>",
        _build_header(config, summary),
        _build_summary_section(summary, config),
    ]
    
    if config.include_summary_charts:
        html_parts.append(_build_charts_section(summary))
    
    html_parts.extend([
        _build_results_section(results, config),
        _build_footer(),
        "</body>",
        "</html>",
    ])
    
    return "\n".join(html_parts)


def _get_theme_css(theme: str) -> str:
    """Get CSS for the specified theme."""
    if theme == "dark":
        return """
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    background-color: #1a1a1a;
    color: #e0e0e0;
    line-height: 1.6;
    padding: 20px;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
}

header {
    background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
    padding: 30px;
    border-radius: 8px;
    margin-bottom: 30px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

h1 {
    color: #3498db;
    font-size: 2.5em;
    margin-bottom: 10px;
}

.timestamp {
    color: #95a5a6;
    font-size: 0.9em;
}

.summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.summary-card {
    background-color: #262626;
    padding: 20px;
    border-radius: 8px;
    border-left: 4px solid #3498db;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

.summary-card.digital {
    border-left-color: #2ecc71;
}

.summary-card.ocr {
    border-left-color: #e74c3c;
}

.summary-card h3 {
    color: #3498db;
    font-size: 0.9em;
    text-transform: uppercase;
    margin-bottom: 10px;
}

.summary-card .value {
    font-size: 2.5em;
    font-weight: bold;
    color: #ecf0f1;
}

.summary-card .percentage {
    color: #95a5a6;
    font-size: 1em;
    margin-top: 5px;
}

.charts-section {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.chart-container {
    background-color: #262626;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

.chart-container h3 {
    color: #3498db;
    margin-bottom: 15px;
}

.results-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 30px;
    background-color: #262626;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
}

.results-table thead {
    background-color: #34495e;
}

.results-table th {
    padding: 12px;
    text-align: left;
    color: #3498db;
    font-weight: 600;
}

.results-table td {
    padding: 12px;
    border-bottom: 1px solid #34495e;
}

.results-table tbody tr:hover {
    background-color: #323232;
}

.status-digital {
    color: #2ecc71;
    font-weight: 600;
}

.status-ocr {
    color: #e74c3c;
    font-weight: 600;
}

.confidence-high {
    color: #2ecc71;
}

.confidence-medium {
    color: #f39c12;
}

.confidence-low {
    color: #e74c3c;
}

.reason {
    font-size: 0.9em;
    color: #95a5a6;
    max-width: 400px;
}

.signals {
    font-size: 0.85em;
    color: #95a5a6;
    margin-top: 10px;
    padding: 10px;
    background-color: #1a1a1a;
    border-radius: 4px;
}

.signals-header {
    color: #3498db;
    margin-bottom: 5px;
    font-weight: 600;
}

.detail-row {
    margin-top: 20px;
    padding: 15px;
    background-color: #262626;
    border-radius: 8px;
    border-left: 4px solid #3498db;
}

.detail-row.digital {
    border-left-color: #2ecc71;
}

.detail-row.ocr {
    border-left-color: #e74c3c;
}

footer {
    text-align: center;
    padding: 20px;
    color: #7f8c8d;
    border-top: 1px solid #34495e;
    margin-top: 40px;
}

.progress-bar {
    width: 100%;
    height: 30px;
    background-color: #34495e;
    border-radius: 15px;
    overflow: hidden;
    margin: 10px 0;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #2ecc71 0%, #27ae60 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 600;
    font-size: 0.9em;
}

.progress-fill.ocr {
    background: linear-gradient(90deg, #e74c3c 0%, #c0392b 100%);
}

@media (max-width: 768px) {
    h1 {
        font-size: 1.8em;
    }
    
    .summary-grid {
        grid-template-columns: 1fr;
    }
    
    .charts-section {
        grid-template-columns: 1fr;
    }
    
    .results-table {
        font-size: 0.9em;
    }
}
"""
    else:  # light theme
        return """
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
    background-color: #f5f7fa;
    color: #333;
    line-height: 1.6;
    padding: 20px;
}

.container {
    max-width: 1200px;
    margin: 0 auto;
}

header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 30px;
    border-radius: 8px;
    margin-bottom: 30px;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
    color: white;
}

h1 {
    font-size: 2.5em;
    margin-bottom: 10px;
}

.timestamp {
    color: rgba(255, 255, 255, 0.8);
    font-size: 0.9em;
}

.summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.summary-card {
    background-color: white;
    padding: 20px;
    border-radius: 8px;
    border-left: 4px solid #667eea;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.summary-card.digital {
    border-left-color: #10b981;
}

.summary-card.ocr {
    border-left-color: #ef4444;
}

.summary-card h3 {
    color: #667eea;
    font-size: 0.9em;
    text-transform: uppercase;
    margin-bottom: 10px;
}

.summary-card .value {
    font-size: 2.5em;
    font-weight: bold;
    color: #1f2937;
}

.summary-card .percentage {
    color: #6b7280;
    font-size: 1em;
    margin-top: 5px;
}

.charts-section {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}

.chart-container {
    background-color: white;
    padding: 20px;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.chart-container h3 {
    color: #667eea;
    margin-bottom: 15px;
}

.results-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 30px;
    background-color: white;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.results-table thead {
    background-color: #f3f4f6;
}

.results-table th {
    padding: 12px;
    text-align: left;
    color: #667eea;
    font-weight: 600;
}

.results-table td {
    padding: 12px;
    border-bottom: 1px solid #e5e7eb;
}

.results-table tbody tr:hover {
    background-color: #f9fafb;
}

.status-digital {
    color: #10b981;
    font-weight: 600;
}

.status-ocr {
    color: #ef4444;
    font-weight: 600;
}

.confidence-high {
    color: #10b981;
}

.confidence-medium {
    color: #f59e0b;
}

.confidence-low {
    color: #ef4444;
}

.reason {
    font-size: 0.9em;
    color: #6b7280;
    max-width: 400px;
}

.signals {
    font-size: 0.85em;
    color: #6b7280;
    margin-top: 10px;
    padding: 10px;
    background-color: #f9fafb;
    border-radius: 4px;
}

.signals-header {
    color: #667eea;
    margin-bottom: 5px;
    font-weight: 600;
}

.detail-row {
    margin-top: 20px;
    padding: 15px;
    background-color: white;
    border-radius: 8px;
    border-left: 4px solid #667eea;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.detail-row.digital {
    border-left-color: #10b981;
}

.detail-row.ocr {
    border-left-color: #ef4444;
}

footer {
    text-align: center;
    padding: 20px;
    color: #9ca3af;
    border-top: 1px solid #e5e7eb;
    margin-top: 40px;
}

.progress-bar {
    width: 100%;
    height: 30px;
    background-color: #e5e7eb;
    border-radius: 15px;
    overflow: hidden;
    margin: 10px 0;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #10b981 0%, #059669 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 600;
    font-size: 0.9em;
}

.progress-fill.ocr {
    background: linear-gradient(90deg, #ef4444 0%, #dc2626 100%);
}

@media (max-width: 768px) {
    h1 {
        font-size: 1.8em;
    }
    
    .summary-grid {
        grid-template-columns: 1fr;
    }
    
    .charts-section {
        grid-template-columns: 1fr;
    }
    
    .results-table {
        font-size: 0.9em;
    }
}
"""


def _build_header(config: ReportConfig, summary: Dict[str, Any]) -> str:
    """Build the header section."""
    timestamp = summary["generated_at"]
    dt = datetime.fromisoformat(timestamp)
    formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
    
    return f"""
    <div class="container">
      <header>
        <h1>📊 {_escape_html(config.title)}</h1>
        <p class="timestamp">Generated on {formatted_time}</p>
      </header>
    </div>
"""


def _build_summary_section(summary: Dict[str, Any], config: ReportConfig) -> str:
    """Build the summary statistics section."""
    total = summary["total_files"]
    digital = summary["digital_count"]
    ocr = summary["ocr_needed_count"]
    avg_conf = summary["average_confidence"]
    digital_pct = summary["digital_percentage"]
    ocr_pct = summary["ocr_percentage"]
    
    conf_class = (
        "confidence-high"
        if avg_conf >= 0.8
        else "confidence-medium" if avg_conf >= 0.6 else "confidence-low"
    )
    
    return f"""
    <div class="container">
      <div class="summary-grid">
        <div class="summary-card">
          <h3>📁 Total Files</h3>
          <div class="value">{total}</div>
        </div>
        
        <div class="summary-card digital">
          <h3>✅ Digital (Skip OCR)</h3>
          <div class="value">{digital}</div>
          <div class="percentage">{digital_pct:.1f}%</div>
        </div>
        
        <div class="summary-card ocr">
          <h3>❌ Needs OCR</h3>
          <div class="value">{ocr}</div>
          <div class="percentage">{ocr_pct:.1f}%</div>
        </div>
        
        <div class="summary-card">
          <h3>📈 Avg Confidence</h3>
          <div class="value {conf_class}">{avg_conf:.1%}</div>
        </div>
      </div>
      
      <div class="progress-bar">
        <div class="progress-fill" style="width: {digital_pct}%">
          Digital: {digital_pct:.0f}%
        </div>
      </div>
      <div class="progress-bar">
        <div class="progress-fill ocr" style="width: {ocr_pct}%">
          Needs OCR: {ocr_pct:.0f}%
        </div>
      </div>
    </div>
"""


def _build_charts_section(summary: Dict[str, Any]) -> str:
    """Build charts and breakdown sections."""
    file_types = summary["file_types"]
    categories = summary["categories"]
    
    # File type breakdown
    ft_html = []
    for ft, counts in sorted(file_types.items()):
        pct = 100 * counts["ocr"] / counts["total"] if counts["total"] > 0 else 0
        ft_html.append(f"""
        <tr>
          <td>{_escape_html(ft)}</td>
          <td>{counts['total']}</td>
          <td><span class="status-digital">{counts['total'] - counts['ocr']}</span></td>
          <td><span class="status-ocr">{counts['ocr']}</span></td>
          <td>{pct:.1f}%</td>
        </tr>
        """)
    
    # Category breakdown
    cat_html = []
    for cat, counts in sorted(categories.items()):
        pct = 100 * counts["ocr"] / counts["total"] if counts["total"] > 0 else 0
        cat_html.append(f"""
        <tr>
          <td>{_escape_html(cat)}</td>
          <td>{counts['total']}</td>
          <td><span class="status-digital">{counts['total'] - counts['ocr']}</span></td>
          <td><span class="status-ocr">{counts['ocr']}</span></td>
          <td>{pct:.1f}%</td>
        </tr>
        """)
    
    return f"""
    <div class="container">
      <div class="charts-section">
        <div class="chart-container">
          <h3>Breakdown by File Type</h3>
          <table class="results-table">
            <thead>
              <tr>
                <th>File Type</th>
                <th>Total</th>
                <th>Digital</th>
                <th>OCR Needed</th>
                <th>OCR %</th>
              </tr>
            </thead>
            <tbody>
              {''.join(ft_html)}
            </tbody>
          </table>
        </div>
        
        <div class="chart-container">
          <h3>Breakdown by Category</h3>
          <table class="results-table">
            <thead>
              <tr>
                <th>Category</th>
                <th>Total</th>
                <th>Digital</th>
                <th>OCR Needed</th>
                <th>OCR %</th>
              </tr>
            </thead>
            <tbody>
              {''.join(cat_html)}
            </tbody>
          </table>
        </div>
      </div>
    </div>
"""


def _build_results_section(
    results: List[Dict[str, Any]],
    config: ReportConfig,
) -> str:
    """Build the detailed results section."""
    rows = []
    
    for result in results:
        needs_ocr = result.get("needs_ocr", False)
        status = "❌ Needs OCR" if needs_ocr else "✅ Digital"
        status_class = "status-ocr" if needs_ocr else "status-digital"
        detail_class = "detail-row ocr" if needs_ocr else "detail-row digital"
        
        confidence = result.get("confidence", 0)
        conf_class = (
            "confidence-high"
            if confidence >= 0.8
            else "confidence-medium" if confidence >= 0.6 else "confidence-low"
        )
        
        file_name = Path(result.get("file", "")).name
        reason = result.get("reason", "No reason provided")
        reason_code = result.get("reason_code", "UNKNOWN")
        file_type = result.get("file_type", "unknown")
        category = result.get("category", "unknown")
        
        signals_html = ""
        if config.include_signals and "signals" in result:
            sigs = result["signals"]
            signal_lines = []
            if "text_length" in sigs:
                signal_lines.append(f"Text: {sigs['text_length']} chars")
            if "text_coverage" in sigs and sigs["text_coverage"]:
                signal_lines.append(f"Text coverage: {sigs['text_coverage']:.1f}%")
            if "image_coverage" in sigs and sigs["image_coverage"]:
                signal_lines.append(f"Image coverage: {sigs['image_coverage']:.1f}%")
            
            if signal_lines:
                signals_html = f"""
                <div class="signals">
                  <div class="signals-header">Signals:</div>
                  {' • '.join(signal_lines)}
                </div>
                """
        
        rows.append(f"""
        <tr>
          <td><strong>{_escape_html(file_name)}</strong></td>
          <td><span class="{status_class}">{status}</span></td>
          <td>{_escape_html(file_type)}</td>
          <td><span class="{conf_class}">{confidence:.1%}</span></td>
          <td class="reason">{_format_reason(reason)}{signals_html}</td>
        </tr>
        """)
    
    return f"""
    <div class="container">
      <h2 style="margin: 40px 0 20px 0; color: #667eea;">📋 Detailed Results</h2>
      <table class="results-table">
        <thead>
          <tr>
            <th>File</th>
            <th>Decision</th>
            <th>Type</th>
            <th>Confidence</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows)}
        </tbody>
      </table>
    </div>
"""


def _build_footer() -> str:
    """Build the footer section."""
    return """
    <footer>
      <p>Generated by PreOCR • <a href="https://preocr.io" style="color: #667eea;">preocr.io</a></p>
    </footer>
"""
