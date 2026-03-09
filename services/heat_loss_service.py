"""
Heat loss service.

Connects stored thermal analysis and operator hotspot labels with the
HeatLossReporter to generate homeowner-friendly HTML reports.

Testbed enhancements:
- Includes links + attached files saved from edit_spots
- Optionally embeds shared recommendations HTML
- Can render standalone HTML and compile PDF (weasyprint/pdfkit/xhtml2pdf)
"""

from __future__ import annotations

import logging
import re
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from settings import ORG_NAME, ORG_WEBSITE, ORG_CONTACT, RECOMMENDATIONS_DOCUMENT_URL
import services.batch_io as batchio
from services.heat_loss_reporter import HeatLossReporter

logger = logging.getLogger(__name__)


def get_thermal_analysis(batch_id: str, tenant_id: str | None = None) -> Dict[str, Any]:
    analysis = batchio.load_thermal_analysis(batch_id, tenant_id)
    if analysis is None:
        raise FileNotFoundError(f"No thermal analysis found for batch {batch_id}")
    return analysis


def get_existing_labels(batch_id: str, tenant_id: str | None = None) -> Dict[str, Any]:
    labels = batchio.load_hotspot_labels(batch_id, tenant_id)
    return labels or {"labeled_spots": []}


def save_labels(batch_id: str, label_data: Dict[str, Any], tenant_id: str | None = None) -> None:
    batchio.save_hotspot_labels(batch_id, label_data, tenant_id)


def _combine_analysis_and_labels(
    analysis: Dict[str, Any],
    labels: Dict[str, Any],
) -> List[Dict[str, Any]]:
    reporter = HeatLossReporter(
        org_name=ORG_NAME,
        org_website=ORG_WEBSITE,
        org_contact=ORG_CONTACT,
    )
    labeled_spots = labels.get("labeled_spots", [])
    grouped = reporter.group_by_spot_number(labeled_spots)
    findings = []
    for spot_number, spot_group in grouped.items():
        finding = reporter.generate_finding_narrative(spot_group, spot_number)
        findings.append(finding)
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: (severity_order.get(f.get("severity"), 3), f.get("spot_number", 0)))
    return findings


def _fetch_recommendations_html(url: str) -> str | None:
    if not url:
        return None
    try:
        import requests

        resp = requests.get(url, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text
        html = re.sub(r"<!DOCTYPE[^>]*>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"</?html[^>]*>", "", html, flags=re.IGNORECASE)
        html = re.sub(r"<head[^>]*>.*?</head>", "", html, flags=re.IGNORECASE | re.DOTALL)
        html = re.sub(r"</?body[^>]*>", "", html, flags=re.IGNORECASE)
        return html.strip()
    except Exception as e:
        logger.warning("Failed to fetch recommendations document from %s: %s", url, e)
        return None


def generate_report(
    batch_id: str,
    property_address: str | None,
    inspector_name: str | None,
    doc_mode: str = "link",
    tenant_id: str | None = None,
) -> Dict[str, Any]:
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

    attached_files = labels.get("attached_files", [])
    links = labels.get("links", [])

    recommendations_html = None
    recommendations_url = RECOMMENDATIONS_DOCUMENT_URL or None
    if recommendations_url:
        recommendations_html = _fetch_recommendations_html(recommendations_url)

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
        "recommendations_html": recommendations_html,
        "doc_mode": doc_mode,
        "attached_files": attached_files,
        "links": links,
    }

    batchio.save_heatloss_report(batch_id, report_data, tenant_id)
    return report_data



def _regenerate_labeled_images_with_manual_spots(batch_id: str, labels: Dict[str, Any], tenant_id: str | None = None) -> None:
    """Regenerate labeled images with manual spot annotations before PDF generation."""
    from security_utils import safe_batch_path
    from settings import BASE_REPORT_DIR
    from services.thermal_analyzer import ThermalAnalyzer
    
    try:
        batch_dir = safe_batch_path(BASE_REPORT_DIR, batch_id, tenant_id)
        labeled_spots = labels.get("labeled_spots", [])
        
        # Group spots by image
        images_to_process = {}
        for spot in labeled_spots:
            if not spot.get('spot_number'):  # Skip unlabeled spots
                continue
            img_name = spot.get('image_name')
            if img_name:
                if img_name not in images_to_process:
                    images_to_process[img_name] = []
                images_to_process[img_name].append(spot)
        
        # Generate labeled images
        analyzer = ThermalAnalyzer()
        for image_name, spots in images_to_process.items():
            # Try batch_dir first, then .Images folder
            original_path = batch_dir / image_name
            if not original_path.exists():
                # Check .Images folder (where Google Drive images are stored)
                images_dir = batch_dir.parent.parent / ".Images" / batch_id / image_name
                if images_dir.exists():
                    original_path = images_dir
            if not original_path.exists():
                logger.warning(f"Original image not found: {original_path}")
                continue
            
            labeled_name = image_name.replace(".jpg", "_labeled.jpg").replace(".jpeg", "_labeled.jpeg")
            labeled_path = batch_dir / labeled_name
            
            try:
                analyzer.draw_manual_labels(str(original_path), spots, str(labeled_path))
                logger.info(f"Generated labeled image: {labeled_name}")
            except Exception as e:
                logger.error(f"Failed to generate labeled image {labeled_name}: {e}")
                
    except Exception as e:
        logger.error(f"Failed to regenerate labeled images: {e}", exc_info=True)

def generate_pdf_from_report_data(
    batch_id: str,
    report_data: Dict[str, Any],
    tenant_id: str | None = None,
) -> str | None:
    """Generate PDF from report data.

    Tries weasyprint -> pdfkit -> xhtml2pdf -> falls back to HTML.
    Returns path to generated file (.pdf or .html fallback), or None on failure.
    """
    from security_utils import safe_batch_path
    from settings import BASE_REPORT_DIR

    try:
        batch_dir = safe_batch_path(BASE_REPORT_DIR, batch_id, tenant_id)
        
        # Regenerate labeled images with manual annotations
        labels = get_existing_labels(batch_id, tenant_id)
        _regenerate_labeled_images_with_manual_spots(batch_id, labels, tenant_id)
        
        html_content = _render_report_html(report_data, batch_dir=str(batch_dir))

        html_path = batch_dir / f"final_report_{batch_id}.html"
        html_path.write_text(html_content, encoding="utf-8")

        pdf_filename = f"thermal_report_{batch_id}.pdf"
        pdf_path = batch_dir / pdf_filename

        try:
            from weasyprint import HTML as WeasyHTML

            WeasyHTML(string=html_content, base_url=str(batch_dir)).write_pdf(str(pdf_path))
            return str(pdf_path)
        except ImportError:
            logger.warning("weasyprint not installed")
        except Exception as e:
            logger.warning("weasyprint failed at runtime: %s", e)

        try:
            import pdfkit

            pdfkit.from_string(html_content, str(pdf_path))
            return str(pdf_path)
        except ImportError:
            logger.warning("pdfkit not installed")
        except Exception as e:
            logger.warning("pdfkit failed at runtime: %s", e)

        try:
            from xhtml2pdf import pisa

            with open(str(pdf_path), "wb") as pdf_file:
                result = pisa.CreatePDF(html_content, dest=pdf_file)
                if not result.err:
                    return str(pdf_path)
                logger.warning("xhtml2pdf reported errors: %s", result.err)
        except ImportError:
            logger.warning("xhtml2pdf not installed")
        except Exception as e:
            logger.warning("xhtml2pdf failed: %s", e)

        return str(html_path)

    except Exception as e:
        logger.error("Failed to generate PDF: %s", e, exc_info=True)
        return None


def _render_report_html(report_data: Dict[str, Any], batch_dir: str | None = None) -> str:
    """Render standalone HTML for PDF generation.

    Embeds labeled images as base64, appends recommendations content,
    and appends attached HTML notes.
    """
    property_address = report_data.get("property_address", "Not specified")
    inspector_name = report_data.get("inspector_name", "Not specified")
    survey_date = report_data.get("survey_date", datetime.now().strftime("%Y-%m-%d"))
    summary = report_data.get("summary", {})
    findings = report_data.get("findings", [])
    recommendations = report_data.get("recommendations", [])
    org = report_data.get("organisation", {})
    attached_files = report_data.get("attached_files", [])
    links = report_data.get("links", [])
    recommendations_html = report_data.get("recommendations_html", "")
    rec_url = report_data.get("recommendations_document_url", "")

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset=\"UTF-8\">
    <title>Thermal Survey Report - {property_address}</title>
    <style>
        @page {{ size: A4; margin: 2cm; }}
        body {{ font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; margin-bottom: 30px; border-radius: 8px; }}
        .header h1 {{ margin: 0 0 10px 0; font-size: 28px; }}
        .header p {{ margin: 5px 0; opacity: 0.9; }}
        .section {{ margin-bottom: 30px; page-break-inside: avoid; }}
        .section h2 {{ color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 10px; margin-bottom: 15px; }}
        .finding {{ background: #f8f9fa; border-left: 4px solid #ffc107; padding: 15px; margin-bottom: 15px; border-radius: 4px; }}
        .finding h3 {{ margin-top: 0; color: #495057; }}
        .finding img {{ width: 100%; max-width: 600px; margin: 10px 0; border: 1px solid #dee2e6; border-radius: 4px; }}
        .recommendation {{ background: #e7f3ff; border-left: 4px solid #2196F3; padding: 15px; margin-bottom: 15px; border-radius: 4px; }}
        .stats {{ display: flex; gap: 15px; margin-bottom: 20px; }}
        .stat-box {{ background: #fff; border: 1px solid #dee2e6; padding: 15px; border-radius: 4px; text-align: center; flex: 1; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #667eea; }}
        .stat-label {{ font-size: 12px; color: #6c757d; text-transform: uppercase; }}
        .links-section {{ background: #f0f7ff; border: 1px solid #b3d4fc; padding: 20px; margin: 30px 0; border-radius: 8px; }}
        .links-section a {{ color: #1565c0; text-decoration: none; }}
        .links-section a:hover {{ text-decoration: underline; }}
        .embedded-doc {{ page-break-before: always; margin-top: 40px; padding: 25px; border: 2px solid #667eea; border-radius: 8px; background: #fefefe; }}
        .embedded-doc h2 {{ color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 10px; margin-top: 0; }}
        .attached-notes {{ page-break-before: always; margin-top: 40px; }}
        .attached-notes h2 {{ color: #667eea; border-bottom: 2px solid #667eea; padding-bottom: 10px; margin-bottom: 20px; }}
        .note-page {{ margin-bottom: 30px; padding: 20px; border: 1px solid #dee2e6; border-radius: 8px; background: #fafafa; page-break-inside: avoid; }}
        .note-page h3 {{ color: #495057; margin-top: 0; padding-bottom: 8px; border-bottom: 1px solid #eee; }}
        .footer {{ margin-top: 50px; padding-top: 20px; border-top: 1px solid #dee2e6; text-align: center; color: #6c757d; font-size: 12px; }}
    </style>
</head>
<body>
    <div class=\"header\">
        <h1>Thermal Survey Report</h1>
        <p><strong>Property:</strong> {property_address}</p>
        <p><strong>Inspector:</strong> {inspector_name}</p>
        <p><strong>Survey Date:</strong> {survey_date}</p>
    </div>

    <div class=\"section\">
        <h2>Executive Summary</h2>
        <div class=\"stats\">
            <div class=\"stat-box\">
                <div class=\"stat-value\">{summary.get('total_findings', 0)}</div>
                <div class=\"stat-label\">Total Findings</div>
            </div>
            <div class=\"stat-box\">
                <div class=\"stat-value\">{summary.get('critical_count', 0)}</div>
                <div class=\"stat-label\">Critical Issues</div>
            </div>
            <div class=\"stat-box\">
                <div class=\"stat-value\">{summary.get('high_count', 0)}</div>
                <div class=\"stat-label\">High Priority</div>
            </div>
        </div>
    </div>

    <div class=\"section\">
        <h2>Detailed Findings</h2>
"""

    for i, finding in enumerate(findings, 1):
        spot_label = finding.get("title", f"Spot {i}")
        description = finding.get("description", "No description available")
        severity = finding.get("severity", "Unknown")
        spot_type = finding.get("type", "")
        max_temp = finding.get("max_temp", 0)
        min_temp = finding.get("min_temp", 0)
        avg_temp = finding.get("avg_temp", 0)

        html += f"""        <div class=\"finding\">
            <h3>Finding {i}: {spot_label}</h3>
            <p><strong>Severity:</strong> {str(severity).upper()} | <strong>Type:</strong> {spot_type}</p>
            <p><strong>Temperature:</strong> Max {float(max_temp):.1f}°C / Avg {float(avg_temp):.1f}°C / Min {float(min_temp):.1f}°C</p>
            <p>{description}</p>
"""

        spot_locations = finding.get("spot_locations", [])
        if batch_dir and spot_locations:
            for image_name, _location in spot_locations:
                if image_name:
                    labeled_name = (
                        str(image_name)
                        .replace(".jpg", "_labeled.jpg")
                        .replace(".jpeg", "_labeled.jpeg")
                    )
                    labeled_path = Path(batch_dir) / labeled_name
                    if labeled_path.exists():
                        img_data = base64.b64encode(labeled_path.read_bytes()).decode("utf-8")
                        html += f"            <img src=\"data:image/jpeg;base64,{img_data}\" alt=\"{labeled_name}\">\n"

        html += "        </div>\n"

    html += """    </div>

    <div class=\"section\">
        <h2>Recommendations</h2>
"""

    for i, rec in enumerate(recommendations, 1):
        rec_type = rec.get("type", f"Item {i}")
        spot_num = rec.get("spot_number", "")
        advice_list = rec.get("advice", [])
        savings = rec.get("savings", "")
        priority = rec.get("priority", "medium")
        advice_items = "".join(f"<li>{a}</li>" for a in advice_list)
        html += f"""        <div class=\"recommendation\">
            <h3>{rec_type} #{spot_num} ({str(priority).upper()} priority)</h3>
            <ul>{advice_items}</ul>
            <p><strong>Estimated savings:</strong> {savings}</p>
        </div>
"""

    html += "    </div>\n"

    valid_links = [l for l in links if l.get("title") and l.get("url")]
    if valid_links:
        html += "    <div class=\"links-section\">\n        <h2>Documents &amp; Links</h2>\n        <ul>\n"
        for link in valid_links:
            html += f"            <li><a href=\"{link['url']}\">{link['title']}</a></li>\n"
        html += "        </ul>\n    </div>\n"

    if recommendations_html:
        html += f"""    <div class=\"embedded-doc\">
        <h2>Recommendations &amp; Resources</h2>
        {recommendations_html}
    </div>
"""
    elif rec_url:
        html += f"""    <div class=\"links-section\" style=\"text-align:center;\">
        <h2>Additional Resources</h2>
        <p>For detailed improvement guidance, visit our recommendations document:</p>
        <p><a href=\"{rec_url}\" style=\"font-weight:bold; font-size:16px;\">{rec_url}</a></p>
    </div>
"""

    html_notes = [
        f
        for f in attached_files
        if f.get("data") and str(f.get("name", "")).lower().endswith((".html", ".htm"))
    ]
    if html_notes:
        html += "    <div class=\"attached-notes\">\n        <h2>Attached Notes</h2>\n"
        for note in html_notes:
            note_name = note.get("name", "Untitled")
            note_data = note.get("data", "")
            note_html = ""
            if "," in note_data:
                try:
                    encoded = note_data.split(",", 1)[1]
                    note_html = base64.b64decode(encoded).decode("utf-8", errors="replace")
                except Exception:
                    note_html = "<p><em>Could not decode attached note.</em></p>"
            else:
                note_html = note_data

            note_html = re.sub(r"<!DOCTYPE[^>]*>", "", note_html, flags=re.IGNORECASE)
            note_html = re.sub(r"</?html[^>]*>", "", note_html, flags=re.IGNORECASE)
            note_html = re.sub(r"<head[^>]*>.*?</head>", "", note_html, flags=re.IGNORECASE | re.DOTALL)
            note_html = re.sub(r"</?body[^>]*>", "", note_html, flags=re.IGNORECASE)

            html += f"        <div class=\"note-page\">\n            <h3>{note_name}</h3>\n            {note_html}\n        </div>\n"

        html += "    </div>\n"

    other_files = [
        f for f in attached_files if f.get("name") and not str(f.get("name", "")).lower().endswith((".html", ".htm"))
    ]
    if other_files:
        html += "    <div class=\"section\">\n        <h2>Other Attachments</h2>\n        <ul>\n"
        for af in other_files:
            size_kb = float(af.get("size", 0)) / 1024
            html += f"            <li>{af.get('name')} ({size_kb:.1f} KB)</li>\n"
        html += "        </ul>\n    </div>\n"

    html += f"""    <div class=\"footer\">
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
