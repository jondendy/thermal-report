#!/usr/bin/env python3
"""
Heat Loss Service
Generates heat loss reports from labeled thermal data.
"""
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import json

import settings
from security_utils import safe_batch_path
from services import batch_io as batchio

logger = logging.getLogger(__name__)


def get_thermal_analysis(batch_id: str, tenant_id: Optional[str]) -> Dict[str, Any]:
    """Load thermal analysis results for a batch."""
    return batchio.load_thermal_analysis(batch_id, tenant_id)


def get_existing_labels(batch_id: str, tenant_id: Optional[str]) -> Dict[str, Any]:
    """Load existing labels for a batch."""
    try:
        return batchio.load_labels(batch_id, tenant_id)
    except FileNotFoundError:
        logger.debug(f"No existing labels found for batch {batch_id}")
        return {"spots": {}, "notes": []}


def save_labels(batch_id: str, data: Dict[str, Any], tenant_id: Optional[str]) -> None:
    """Save labels for a batch."""
    batchio.save_labels(batch_id, data, tenant_id)
    logger.info(f"Labels saved for batch {batch_id}")


def generate_report(
    batch_id: str,
    property_address: str = "",
    inspector_name: str = "",
    doc_mode: str = "link",
    tenant_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a heat loss report from labeled thermal data.
    
    Args:
        batch_id: Unique batch identifier
        property_address: Address of surveyed property
        inspector_name: Name of inspector
        doc_mode: How to handle attached documents ('link', 'embed', or 'none')
        tenant_id: Optional tenant identifier for multi-tenant setups
    
    Returns:
        Dictionary containing structured report data
    """
    analysis_data = get_thermal_analysis(batch_id, tenant_id)
    labels_data = get_existing_labels(batch_id, tenant_id)
    
    spots_by_location = labels_data.get("spots", {})
    notes = labels_data.get("notes", [])
    saved_links = labels_data.get("links", [])
    
    findings = _process_findings(analysis_data, spots_by_location)
    summary = _generate_summary(findings)
    
    now = datetime.now()
    report_data = {
        "batch_id": batch_id,
        "property_address": property_address or "Not specified",
        "inspector_name": inspector_name or "Not specified",
        "survey_date": now.strftime("%Y-%m-%d"),
        "survey_time": now.strftime("%H:%M"),
        "summary": summary,
        "findings": findings,
        "notes": notes,
        "links": saved_links,
        "doc_mode": doc_mode,
    }
    
    batchio.save_report(batch_id, report_data, tenant_id)
    logger.info(f"Heat loss report generated for batch {batch_id} with {len(findings)} findings")
    return report_data


def _process_findings(
    analysis_data: Dict[str, Any],
    spots_by_location: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Process thermal analysis data and user labels into structured findings.
    
    Args:
        analysis_data: Raw thermal analysis results
        spots_by_location: User-provided labels keyed by "filename:spot_id"
    
    Returns:
        List of finding dictionaries grouped by labeled spot type
    """
    findings_by_type = {}
    images_data = analysis_data.get("images", [])
    
    for image_info in images_data:
        filename = image_info.get("filename", "")
        hot_spots = image_info.get("hot_spots", [])
        
        for spot_idx, spot in enumerate(hot_spots):
            spot_id = f"{filename}:{spot_idx}"
            label_info = spots_by_location.get(spot_id, {})
            
            if not label_info:
                continue
            
            spot_type = label_info.get("type", "Other")
            severity = label_info.get("severity", "low").lower()
            description = label_info.get("description", "No description provided.")
            
            if spot_type not in findings_by_type:
                findings_by_type[spot_type] = {
                    "title": f"Heat Loss at {spot_type}",
                    "type": spot_type,
                    "severity": severity,
                    "description": description,
                    "spot_locations": [],
                    "temperatures": [],
                    "image_count": 0,
                    "recommendations": _get_recommendations_for_type(spot_type, severity),
                }
            
            finding = findings_by_type[spot_type]
            finding["spot_locations"].append((filename, (spot.get("x", 0), spot.get("y", 0))))
            finding["temperatures"].extend([
                spot.get("max_temp", 0),
                spot.get("avg_temp", 0),
                spot.get("min_temp", 0)
            ])
            finding["image_count"] += 1
            
            if _severity_rank(severity) > _severity_rank(finding["severity"]):
                finding["severity"] = severity
                finding["description"] = description
    
    for finding in findings_by_type.values():
        temps = finding["temperatures"]
        if temps:
            finding["max_temp"] = max(temps)
            finding["avg_temp"] = sum(temps) / len(temps)
            finding["min_temp"] = min(temps)
        else:
            finding["max_temp"] = finding["avg_temp"] = finding["min_temp"] = 0.0
        del finding["temperatures"]
    
    return sorted(findings_by_type.values(), key=lambda f: _severity_rank(f["severity"]), reverse=True)


def _severity_rank(severity: str) -> int:
    """Return numeric rank for severity level."""
    ranks = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    return ranks.get(severity.lower(), 0)


def _get_recommendations_for_type(spot_type: str, severity: str) -> str:
    """Generate recommendations based on spot type and severity."""
    recommendations = {
        "Wall": "Consider additional wall insulation. Check for gaps or missing insulation.",
        "Window": "Consider upgrading to double/triple glazing. Check seals and weatherstripping.",
        "Door": "Install or replace weatherstripping. Consider adding a draft excluder.",
        "Roof": "Add or upgrade loft insulation. Check for gaps around roof penetrations.",
        "Floor": "Consider underfloor insulation. Check for drafts around skirting boards.",
        "Vent": "Ensure proper sealing when not in use. Consider adjustable vents.",
        "Other": "Investigate the source of heat loss and take appropriate action.",
    }
    base_rec = recommendations.get(spot_type, recommendations["Other"])
    
    if severity in ["critical", "high"]:
        return f"⚠️ PRIORITY ACTION REQUIRED: {base_rec}"
    return base_rec


def _generate_summary(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate summary statistics from findings."""
    severity_breakdown = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    highest_severity = "low"
    
    for finding in findings:
        severity = finding.get("severity", "low").lower()
        severity_breakdown[severity] = severity_breakdown.get(severity, 0) + 1
        if _severity_rank(severity) > _severity_rank(highest_severity):
            highest_severity = severity
    
    return {
        "total_findings": len(findings),
        "highest_severity": highest_severity.capitalize(),
        "severity_breakdown": severity_breakdown,
    }


def get_report(batch_id: str, tenant_id: Optional[str]) -> Dict[str, Any]:
    """Load a previously generated report."""
    return batchio.load_report(batch_id, tenant_id)


def _render_report_html(batch_id: str, report_data: Dict[str, Any], tenant_id: Optional[str]) -> str:
    """
    Render report data as standalone HTML with embedded/linked images.
    
    This version is optimized for PDF generation:
    - Uses file:// URLs instead of base64 encoding to prevent PDF bloat
    - xhtml2pdf supports local file paths
    - Reduces PDF size from 65 pages to reasonable length
    
    Args:
        batch_id: Unique batch identifier
        report_data: Structured report data
        tenant_id: Optional tenant identifier
    
    Returns:
        Complete HTML string ready for PDF conversion
    """
    batch_dir = safe_batch_path(settings.BASE_REPORT_DIR, batch_id, tenant_id)
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Building Heat Loss Survey Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: white;
        }}
        .header {{
            border-bottom: 4px solid #2c3e50;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .header h1 {{
            color: #2c3e50;
            margin: 0;
            font-size: 2em;
        }}
        .property-info {{
            background: #ecf0f1;
            padding: 15px;
            border-left: 4px solid #3498db;
            margin-bottom: 20px;
        }}
        .summary-box {{
            background: #e8f4f8;
            border: 2px solid #3498db;
            padding: 15px;
            margin: 20px 0;
            border-radius: 5px;
        }}
        .severity-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 15px;
            font-weight: bold;
            font-size: 0.85em;
            margin: 3px;
        }}
        .severity-critical {{ background: #e74c3c; color: white; }}
        .severity-high {{ background: #e67e22; color: white; }}
        .severity-medium {{ background: #f39c12; color: white; }}
        .severity-low {{ background: #f1c40f; color: #333; }}
        .finding {{
            margin: 30px 0;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 5px;
            page-break-inside: avoid;
        }}
        .finding h3 {{
            color: #2c3e50;
            margin-top: 0;
        }}
        .finding-images {{
            margin: 15px 0;
        }}
        .finding-image {{
            margin: 10px 0;
            page-break-inside: avoid;
        }}
        .finding-image img {{
            max-width: 100%;
            height: auto;
            border: 2px solid #ddd;
            border-radius: 5px;
        }}
        .finding-image .caption {{
            background: #2c3e50;
            color: white;
            padding: 8px;
            text-align: center;
            font-size: 0.85em;
            margin-top: -3px;
        }}
        .temperature-stats {{
            background: #fff;
            padding: 10px;
            margin: 10px 0;
            border-left: 4px solid #3498db;
        }}
        .recommendations {{
            background: #d4edda;
            border: 2px solid #28a745;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
        }}
        .recommendations h4 {{
            color: #155724;
            margin-top: 0;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 15px;
            border-top: 2px solid #ecf0f1;
            text-align: center;
            color: #7f8c8d;
            font-size: 0.85em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Building Heat Loss Survey Report</h1>
        <div style="color: #7f8c8d; font-size: 1.1em; margin-top: 8px;">Thermal Imaging Analysis</div>
    </div>

    <div class="property-info">
        <h2 style="margin-top: 0; font-size: 1.3em;">Property Information</h2>
        <p><strong>Address:</strong> {report_data.get('property_address', 'Not specified')}</p>
        <p><strong>Survey Date:</strong> {report_data.get('survey_date', 'Not specified')}</p>
        <p><strong>Survey Time:</strong> {report_data.get('survey_time', 'Not specified')}</p>
        <p><strong>Inspector:</strong> {report_data.get('inspector_name', 'Not specified')}</p>
        <p><strong>Batch ID:</strong> {batch_id}</p>
    </div>

    <div class="summary-box">
        <h2 style="margin-top: 0; font-size: 1.3em;">Executive Summary</h2>
        <p><strong>Total Heat Loss Points:</strong> {report_data['summary']['total_findings']}</p>
        <p><strong>Highest Severity:</strong>
            <span class="severity-badge severity-{report_data['summary']['highest_severity'].lower()}">
                {report_data['summary']['highest_severity']}
            </span>
        </p>
        <p><strong>Severity Breakdown:</strong></p>
        <div>
'''
    
    severity_breakdown = report_data['summary']['severity_breakdown']
    for severity, count in severity_breakdown.items():
        if count > 0:
            html += f'            <span class="severity-badge severity-{severity}">{severity.capitalize()}: {count}</span>\n'
    
    html += '''        </div>
    </div>

    <h2 style="color: #2c3e50; margin-top: 40px; font-size: 1.5em;">Detailed Findings</h2>
'''
    
    for finding in report_data.get('findings', []):
        severity = finding.get('severity', 'low').lower()
        html += f'''
    <div class="finding">
        <h3>{finding.get('title', 'Heat Loss Point')}</h3>
        <div>
            <span class="severity-badge severity-{severity}">{severity.upper()} PRIORITY</span>
'''
        if finding.get('image_count', 0) > 1:
            html += f'            <span style="background: #95a5a6; color: white; padding: 4px 12px; border-radius: 15px; font-weight: bold; margin-left: 8px;">Visible in {finding["image_count"]} images</span>\n'
        
        html += f'''
        </div>
        <div class="temperature-stats">
            <strong>Temperature Analysis:</strong><br>
            Max: {finding.get('max_temp', 0):.1f}°C |
            Avg: {finding.get('avg_temp', 0):.1f}°C |
            Min: {finding.get('min_temp', 0):.1f}°C
        </div>
        <p>{finding.get('description', 'No description provided.')}</p>
        <div class="finding-images">
'''
        
        # Add images using file:// URLs (xhtml2pdf supports this)
        for image_name, location in finding.get('spot_locations', []):
            labeled_name = image_name.replace('.jpg', '_labeled.jpg')
            labeled_path = batch_dir / labeled_name
            
            if labeled_path.exists():
                # Use file:// URL for PDF generation (works with xhtml2pdf)
                file_url = labeled_path.as_uri()
                html += f'''
            <div class="finding-image">
                <img src="{file_url}" alt="Thermal image showing {finding.get('type', 'heat loss')}">
                <div class="caption">{image_name} - Location: ({location[0]}, {location[1]})</div>
            </div>
'''
        
        html += '        </div>\n'
        
        # Add recommendations
        recommendations = finding.get('recommendations', '')
        if recommendations:
            html += f'''
        <div class="recommendations">
            <h4 style="margin-top: 0;">🔧 Recommendations</h4>
            <p>{recommendations}</p>
        </div>
'''
        
        html += '    </div>\n'
    
    # Add notes if present
    notes = report_data.get('notes', [])
    if notes:
        html += '''
    <div style="margin: 40px 0;">
        <h2 style="color: #2c3e50; border-bottom: 3px solid #2c3e50; padding-bottom: 8px;">Additional Notes</h2>
'''
        for note_idx, note in enumerate(notes, 1):
            html += f'''
        <div style="margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; background: #fafafa;">
            <h3 style="margin-top: 0;">Note {note_idx}</h3>
            <p>{note.get('content', 'No content')}</p>
        </div>
'''
        html += '    </div>\n'
    
    # Add footer
    html += f'''
    <div class="footer">
        <p>Report generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        <p>Thermal Report System v{settings.APP_VERSION}</p>
    </div>
</body>
</html>
'''
    
    return html


def generate_pdf_from_report_data(
    batch_id: str,
    report_data: Dict[str, Any],
    tenant_id: Optional[str]
) -> Optional[str]:
    """
    Generate a PDF file from report data.
    
    Args:
        batch_id: Unique batch identifier
        report_data: Structured report data
        tenant_id: Optional tenant identifier
    
    Returns:
        Path to generated PDF file, or None if PDF generation unavailable
    """
    try:
        from xhtml2pdf import pisa
    except ImportError:
        logger.warning("xhtml2pdf not installed. Falling back to HTML export.")
        batch_dir = safe_batch_path(settings.BASE_REPORT_DIR, batch_id, tenant_id)
        html_path = batch_dir / f"thermal_report_{batch_id}.html"
        html_content = _render_report_html(batch_id, report_data, tenant_id)
        html_path.write_text(html_content, encoding='utf-8')
        return str(html_path)
    
    batch_dir = safe_batch_path(settings.BASE_REPORT_DIR, batch_id, tenant_id)
    pdf_filename = f"thermal_report_{batch_id}.pdf"
    pdf_path = batch_dir / pdf_filename
    
    html_content = _render_report_html(batch_id, report_data, tenant_id)
    
    try:
        with open(pdf_path, 'w+b') as pdf_file:
            pisa_status = pisa.CreatePDF(
                html_content,
                dest=pdf_file,
                encoding='utf-8'
            )
        
        if pisa_status.err:
            logger.error(f"PDF generation had errors for batch {batch_id}")
            return None
        
        logger.info(f"PDF generated successfully: {pdf_path}")
        return str(pdf_path)
    
    except Exception as e:
        logger.exception(f"Error generating PDF for batch {batch_id}: {e}")
        return None
