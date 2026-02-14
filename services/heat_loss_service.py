"""
Heat loss service.

Connects stored thermal analysis and operator hotspot labels with the
HeatLossReporter to generate homeowner-friendly HTML reports.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List, Optional

from settings import ORG_NAME, ORG_WEBSITE, ORG_CONTACT, RECOMMENDATIONS_DOCUMENT_URL
import services.batch_io as batchio
from services.heat_loss_reporter import HeatLossReporter


def get_thermal_analysis(batch_id: str, tenant_id: str | None = None) -> Dict[str, Any]:
    analysis = batchio.load_thermal_analysis(batch_id, tenant_id)
    if analysis is None:
        raise FileNotFoundError(f"No thermal analysis found for batch {batch_id}")
    return analysis


def get_existing_labels(batch_id: str, tenant_id: str | None = None) -> Dict[str, Any]:
    labels = batchio.load_hotspot_labels(batch_id, tenant_id)
    return labels or {"labeled_spots": []}


def save_labels(batch_id: str, label_data: Dict[str, Any], tenant_id: str | None = None) -> None:
    # Expect label_data like {"labeled_spots": [...]} from editspots.js form
    batchio.save_hotspot_labels(batch_id, label_data, tenant_id)


def _combine_analysis_and_labels(
    analysis: Dict[str, Any],
    labels: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Build a list of findings using HeatLossReporter from operator labels.
    
    The reporter groups spots by spot_number and generates professional
    finding narratives with recommendations.
    """
    reporter = HeatLossReporter(
        org_name=ORG_NAME,
        org_website=ORG_WEBSITE,
        org_contact=ORG_CONTACT,
    )
    
    labeled_spots = labels.get('labeled_spots', [])
    
    # Group spots by number
    grouped = reporter.group_by_spot_number(labeled_spots)
    
    # Generate findings for each spot number
    findings = []
    for spot_number, spot_group in grouped.items():
        finding = reporter.generate_finding_narrative(spot_group, spot_number)
        findings.append(finding)
    
    # Sort by severity and spot number
    severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    findings.sort(key=lambda f: (severity_order.get(f['severity'], 3), f['spot_number']))
    
    return findings


def generate_report(
    batch_id: str,
    property_address: str | None,
    inspector_name: str | None,
    doc_mode: str = 'link',
    tenant_id: str | None = None,
) -> Dict[str, Any]:
    """
    Generate full heat loss report data (not HTML) and persist it.
    
    Args:
        batch_id: Batch identifier
        property_address: Property address for report
        inspector_name: Inspector/surveyor name
        doc_mode: 'link' to include external URL, 'embed' to embed document
        tenant_id: Tenant identifier for multi-tenant setups
    """
    analysis = get_thermal_analysis(batch_id, tenant_id)
    labels = get_existing_labels(batch_id, tenant_id)
    findings = _combine_analysis_and_labels(analysis, labels)

    reporter = HeatLossReporter(
        org_name=ORG_NAME,
        org_website=ORG_WEBSITE,
        org_contact=ORG_CONTACT,
    )

    summary = reporter.generate_executive_summary(findings)
    recommendations = reporter.generate_recommendations(findings)

    # Only include recommendations_document_url if doc_mode is 'link'
    # If doc_mode is 'embed', the document content would be embedded (future feature)
    recommendations_url = RECOMMENDATIONS_DOCUMENT_URL if doc_mode == 'link' else None

    report_data = {
        "batch_id": batch_id,
        "property_address": property_address or "Not specified",
        "inspector_name": inspector_name or "Not specified",
        "survey_date": datetime.now().strftime("%Y-%m-%d"),
        "survey_time": datetime.now().strftime("%H:%M"),
        "summary": summary,
        "findings": findings,
        "recommendations": recommendations,
        "organisation": {
            "name": ORG_NAME,
            "website": ORG_WEBSITE,
            "contact": ORG_CONTACT,
        },
        "recommendations_document_url": recommendations_url,
        "doc_mode": doc_mode,
    }

    batchio.save_heatloss_report(batch_id, report_data, tenant_id)
    return report_data


def generate_pdf_from_report_data(
    batch_id: str, 
    report_data: Dict[str, Any], 
    tenant_id: str | None = None
) -> str | None:
    """
    Generate a professional PDF from report data using weasyprint.
    
    Args:
        batch_id: Batch identifier
        report_data: The complete report data dictionary from generate_report()
        tenant_id: Tenant identifier
        
    Returns:
        Path to generated PDF file, or None if generation failed
    """
    import logging
    from pathlib import Path
    from security_utils import safe_batch_path
    from settings import BASE_REPORT_DIR
    
    logger = logging.getLogger(__name__)
    
    try:
        # Get batch directory
        batch_dir = safe_batch_path(BASE_REPORT_DIR, batch_id, tenant_id)
        
        # Create HTML from report data
        html_content = _render_report_html(report_data)
        
        # Save HTML temporarily
        html_path = batch_dir / f"final_report_{batch_id}.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Generate PDF filename
        pdf_filename = f"thermal_report_{batch_id}.pdf"
        pdf_path = batch_dir / pdf_filename
        
        # Try to use weasyprint for PDF generation
        try:
            from weasyprint import HTML
            HTML(string=html_content, base_url=str(batch_dir)).write_pdf(str(pdf_path))
            logger.info(f"Generated PDF report at {pdf_path} using weasyprint")
            
        except ImportError:
            # Fallback: if weasyprint not available, try pdfkit
            logger.warning("weasyprint not available, trying pdfkit...")
            try:
                import pdfkit
                pdfkit.from_string(html_content, str(pdf_path))
                logger.info(f"Generated PDF report at {pdf_path} using pdfkit")
                
            except ImportError:
                # If no PDF libraries available, just save HTML
                logger.error("No PDF library available (weasyprint or pdfkit). Saved HTML only.")
                return str(html_path)  # Return HTML path as fallback
        
        return str(pdf_path)
        
    except Exception as e:
        logger.error(f"Failed to generate PDF: {e}", exc_info=True)
        return None


def _render_report_html(report_data: Dict[str, Any]) -> str:
    """
    Render professional HTML from report data.
    
    Creates a standalone HTML document with embedded CSS for PDF generation.
    """
    from datetime import datetime
    
    # Extract data
    property_address = report_data.get('property_address', 'Not specified')
    inspector_name = report_data.get('inspector_name', 'Not specified')
    survey_date = report_data.get('survey_date', datetime.now().strftime('%Y-%m-%d'))
    summary = report_data.get('summary', {})
    findings = report_data.get('findings', [])
    recommendations = report_data.get('recommendations', [])
    org = report_data.get('organisation', {})
    
    # Build HTML with embedded CSS
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Thermal Survey Report - {property_address}</title>
    <style>
        @page {{
            size: A4;
            margin: 2cm;
        }}
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            margin-bottom: 30px;
            border-radius: 8px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 28px;
        }}
        .header p {{
            margin: 5px 0;
            opacity: 0.9;
        }}
        .section {{
            margin-bottom: 30px;
            page-break-inside: avoid;
        }}
        .section h2 {{
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 15px;
        }}
        .finding {{
            background: #f8f9fa;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 4px;
        }}
        .finding h3 {{
            margin-top: 0;
            color: #495057;
        }}
        .recommendation {{
            background: #e7f3ff;
            border-left: 4px solid #2196F3;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 4px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-box {{
            background: #fff;
            border: 1px solid #dee2e6;
            padding: 15px;
            border-radius: 4px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            font-size: 12px;
            color: #6c757d;
            text-transform: uppercase;
        }}
        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #dee2e6;
            text-align: center;
            color: #6c757d;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Thermal Survey Report</h1>
        <p><strong>Property:</strong> {property_address}</p>
        <p><strong>Inspector:</strong> {inspector_name}</p>
        <p><strong>Survey Date:</strong> {survey_date}</p>
    </div>
    
    <div class="section">
        <h2>Executive Summary</h2>
        <div class="stats">
            <div class="stat-box">
                <div class="stat-value">{summary.get('total_findings', 0)}</div>
                <div class="stat-label">Total Findings</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{summary.get('critical_count', 0)}</div>
                <div class="stat-label">Critical Issues</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{summary.get('moderate_count', 0)}</div>
                <div class="stat-label">Moderate Issues</div>
            </div>
        </div>
        <p>{summary.get('overview', 'No summary available.')}</p>
    </div>
    
    <div class="section">
        <h2>Detailed Findings</h2>
"""
    
    # Add findings
    for i, finding in enumerate(findings, 1):
        spot_label = finding.get('label', f'Spot {i}')
        description = finding.get('narrative', finding.get('description', 'No description available'))
        severity = finding.get('severity', 'Unknown')
        
        html += f"""
        <div class="finding">
            <h3>Finding {i}: {spot_label}</h3>
            <p><strong>Severity:</strong> {severity}</p>
            <p>{description}</p>
        </div>
"""
    
    html += """
    </div>
    
    <div class="section">
        <h2>Recommendations</h2>
"""
    
    # Add recommendations
    for i, rec in enumerate(recommendations, 1):
        rec_title = rec.get('title', f'Recommendation {i}')
        rec_desc = rec.get('description', 'No description available')
        
        html += f"""
        <div class="recommendation">
            <h3>{rec_title}</h3>
            <p>{rec_desc}</p>
        </div>
"""
    
    html += f"""
    </div>
    
    <div class="footer">
        <p><strong>{org.get('name', 'Thermal Survey Services')}</strong></p>
        <p>{org.get('website', '')} | {org.get('contact', '')}</p>
        <p>Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
    </div>
</body>
</html>
"""
    
    return html


def get_report(batch_id: str, tenant_id: str | None = None) -> Dict[str, Any]:
    report_data = batchio.load_heatloss_report(batch_id, tenant_id)
    if report_data is None:
        raise FileNotFoundError(f"No report found for batch {batch_id}")
    return report_data
