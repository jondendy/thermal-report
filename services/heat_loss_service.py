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
from typing import Dict, Any, List, Optional

from settings import ORG_NAME, ORG_WEBSITE, ORG_CONTACT, RECOMMENDATIONS_DOCUMENT_URL
import services.batch_io as batchio
from services.heat_loss_reporter import HeatLossReporter
from settings import PDF_STORAGE_ADDRESS
from services import drive_client

logger = logging.getLogger(__name__)

def _extract_survey_date(batch_id: str, tenant_id=None) -> str:
    """Return earliest EXIF DateTimeOriginal from batch images, or today's date."""
    from security_utils import safe_batch_path
    from settings import BASE_REPORT_DIR, BASE_UPLOAD_PATH
    import subprocess, shutil

    candidates: list[str] = []
    for search_dir in [
        BASE_UPLOAD_PATH / batch_id,
        safe_batch_path(BASE_REPORT_DIR, batch_id, tenant_id),
    ]:
        if not search_dir.exists():
            continue
        for img in list(search_dir.glob("*.jpg")) + list(search_dir.glob("*.jpeg")):
            if shutil.which("exiftool"):
                try:
                    result = subprocess.run(
                        ["exiftool", "-DateTimeOriginal", "-s3", str(img)],
                        capture_output=True, text=True, timeout=5
                    )
                    raw = result.stdout.strip()
                    if raw:
                        candidates.append(raw[:10].replace(":", "-"))
                        continue
                except Exception:
                    pass
            try:
                from PIL import Image as PilImage
                with PilImage.open(str(img)) as pil_img:
                    exif = pil_img._getexif() or {}
                    raw = exif.get(36867, "")
                    if raw:
                        candidates.append(raw[:10].replace(":", "-"))
            except Exception:
                pass

    if candidates:
        return min(candidates)
    return datetime.now().strftime("%Y-%m-%d")

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
    for group_key, spot_group in grouped.items():
        finding = reporter.generate_finding_narrative(spot_group, group_key)
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


def _download_google_drive_pdf(url: str, output_path: Path) -> bool:
    """Download PDF from Google Drive link and save locally."""
    try:
        import requests

        if "drive.google.com" in url:
            if "/file/d/" in url:
                file_id = url.split("/file/d/")[1].split("/")[0]
            elif "id=" in url:
                file_id = url.split("id=")[1].split("&")[0]
            else:
                logger.warning(f"Could not extract file ID from URL: {url}")
                return False

            download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
            resp = requests.get(download_url, timeout=30, allow_redirects=True)
            resp.raise_for_status()
            output_path.write_bytes(resp.content)
            logger.info(f"Downloaded recommendations PDF: {output_path}")
            return True
        else:
            logger.warning(f"Not a Google Drive URL: {url}")
            return False

    except Exception as e:
        logger.error(f"Failed to download PDF from {url}: {e}")
        return False


def _merge_recommendations_pdf(report_pdf_path: Path, recommendations_url: str) -> bool:
    """Download recommendations PDF and append it to the report PDF."""
    try:
        from pypdf import PdfReader, PdfWriter

        temp_pdf = report_pdf_path.parent / "temp_recommendations.pdf"
        if not _download_google_drive_pdf(recommendations_url, temp_pdf):
            return False

        writer = PdfWriter()
        report_reader = PdfReader(str(report_pdf_path))
        for page in report_reader.pages:
            writer.add_page(page)

        rec_reader = PdfReader(str(temp_pdf))
        for page in rec_reader.pages:
            writer.add_page(page)

        with open(str(report_pdf_path), 'wb') as output_file:
            writer.write(output_file)

        temp_pdf.unlink()
        logger.info(f"Merged recommendations PDF into report: {report_pdf_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to merge recommendations PDF: {e}")
        return False


def _merge_additional_pdfs(pdf_path: Path, report_data: Dict[str, Any]) -> None:
    """Merge any selected additional PDFs (recommendations, tips) into the report."""
    from settings import RECOMMENDATIONS_DOCUMENT_URL, TIPS_DOCUMENT_URL

    if report_data.get("doc_mode") != "embed":
        return

    pdfs_to_merge = []

    if report_data.get("attach_recommendations", True):
        url = report_data.get("recommendations_document_url") or RECOMMENDATIONS_DOCUMENT_URL
        if url:
            pdfs_to_merge.append(("recommendations", url))

    if report_data.get("attach_tips"):
        if TIPS_DOCUMENT_URL:
            pdfs_to_merge.append(("tips", TIPS_DOCUMENT_URL))

    for name, url in pdfs_to_merge:
        _merge_recommendations_pdf(pdf_path, url)
        logger.info(f"Merged {name} PDF into report")


def _apply_rec_overrides(
    recommendations: List[Dict[str, Any]],
    review: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Remove any advice lines the surveyor has disabled.
    A finding key looks like "Wall_1"; review[key]["disabled_rec_lines"] is a list
    of 0-based indices into that finding's recommendations.advice list.
    Recommendations with all lines removed are dropped entirely.
    """
    result = []
    for rec in recommendations:
        key = f"{rec.get('type', '')}_{rec.get('spot_number', '')}"
        disabled = review.get(key, {}).get("disabled_rec_lines", [])
        if not disabled:
            result.append(rec)
            continue
        filtered_advice = [
            line for idx, line in enumerate(rec.get("advice", []))
            if idx not in disabled
        ]
        if filtered_advice:
            updated = dict(rec)
            updated["advice"] = filtered_advice
            result.append(updated)
    return result


def generate_report(
    batch_id: str,
    property_address: str | None,
    inspector_name: str | None,
    doc_mode: str = "link",
    tenant_id: str | None = None,
    review_override: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate the full report data dict.

    review_override: if supplied (e.g. fresh from the POST body), it is used
    directly so we never read stale data from disk when generate_report is
    called immediately after save_review.
    """
    analysis = get_thermal_analysis(batch_id, tenant_id)
    labels = get_existing_labels(batch_id, tenant_id)
    findings = _combine_analysis_and_labels(analysis, labels)

    # Use caller-supplied review when available, otherwise fall back to disk
    review = review_override if review_override is not None else labels.get("review", {})

    # Apply surveyor review overrides (narrative, severity, note)
    for finding in findings:
        key = f"{finding['type']}_{finding['spot_number']}"
        if key in review:
            r = review[key]
            if r.get("narrative"):
                finding["description"] = r["narrative"]
            if r.get("severity"):
                finding["severity"] = r["severity"]
            if r.get("note"):
                finding["surveyor_note"] = r["note"]

    # Carry general surveyor notes through to the PDF
    general_notes = review.get("_global_notes", "")

    property_address = property_address or labels.get("property_address") or "Not specified"
    inspector_name = inspector_name or labels.get("surveyor_name") or "Not specified"

    reporter = HeatLossReporter(
        org_name=ORG_NAME,
        org_website=ORG_WEBSITE,
        org_contact=ORG_CONTACT,
    )

    summary = reporter.generate_executive_summary(findings)
    recommendations = reporter.generate_recommendations(findings)

    # Apply per-line recommendation toggles from review
    recommendations = _apply_rec_overrides(recommendations, review)

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
        "survey_date": _extract_survey_date(batch_id, tenant_id),
        "survey_time": datetime.now().strftime("%H:%M"),
        "general_notes": general_notes,
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
    from settings import BASE_REPORT_DIR, BASE_UPLOAD_PATH  # FIX: import BASE_UPLOAD_PATH
    from services.thermal_analyzer import ThermalAnalyzer

    try:
        batch_dir = safe_batch_path(BASE_REPORT_DIR, batch_id, tenant_id)
        labeled_spots = labels.get("labeled_spots", [])

        images_to_process: Dict[str, list] = {}
        for spot in labeled_spots:
            if not spot.get('spot_number'):
                continue
            img_name = spot.get('image_name')
            if img_name:
                images_to_process.setdefault(img_name, []).append(spot)

        analyzer = ThermalAnalyzer()
        for image_name, spots in images_to_process.items():
            # FIX: images are stored under BASE_UPLOAD_PATH/batch_id — check there first
            original_path = BASE_UPLOAD_PATH / batch_id / image_name
            if not original_path.exists():
                # fallback: might have been copied into the report batch dir
                original_path = batch_dir / image_name
            if not original_path.exists():
                logger.warning("Original image not found for labeling: %s", image_name)
                continue

            labeled_name = (
                image_name.replace(".jpg", "_labeled.jpg")
                          .replace(".jpeg", "_labeled.jpeg")
            )
            labeled_path = batch_dir / labeled_name

            try:
                analyzer.draw_manual_labels(str(original_path), spots, str(labeled_path))
                logger.info("Generated labeled image: %s", labeled_name)
            except Exception as e:
                logger.error("Failed to generate labeled image %s: %s", labeled_name, e)

    except Exception as e:
        logger.error("Failed to regenerate labeled images: %s", e, exc_info=True)


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
    from settings import PDF_STORAGE_ADDRESS
    from services import drive_client

    try:
        batch_dir = safe_batch_path(BASE_REPORT_DIR, batch_id, tenant_id)

        # Regenerate labeled images with manual annotations
        labels = get_existing_labels(batch_id, tenant_id)
        _regenerate_labeled_images_with_manual_spots(batch_id, labels, tenant_id)

        html_content = _render_report_html(report_data, batch_dir=str(batch_dir))

        # Scrub surrogate characters that FLIR EXIF data can introduce,
        # preventing UnicodeEncodeError when writing UTF-8 or feeding PDF engines.
        html_content = html_content.encode("utf-8", errors="replace").decode("utf-8")

        html_path = batch_dir / f"final_report_{batch_id}.html"
        html_path.write_text(html_content, encoding="utf-8")

        pdf_filename = f"thermal_report_{batch_id}.pdf"
        pdf_path = batch_dir / pdf_filename

        try:
            from weasyprint import HTML as WeasyHTML

            WeasyHTML(string=html_content, base_url=str(batch_dir)).write_pdf(str(pdf_path))
            _merge_additional_pdfs(pdf_path, report_data)
            try:
                drive_client.upload_file_to_folder(PDF_STORAGE_ADDRESS, str(pdf_path))
            except Exception as e:
                logger.warning(
                    "Drive upload failed for batch %s (non-fatal): %s",
                    batch_id,
                    e,
                )
            return str(pdf_path)
        except ImportError:
            logger.warning("weasyprint not installed")
        except Exception as e:
            logger.warning("weasyprint failed at runtime: %s", e)

        try:
            import pdfkit

            pdfkit.from_string(html_content, str(pdf_path))
            _merge_additional_pdfs(pdf_path, report_data)
            try:
                drive_client.upload_file_to_folder(PDF_STORAGE_ADDRESS, str(pdf_path))
            except Exception as e:
                logger.warning(
                    "Drive upload failed for batch %s (non-fatal): %s",
                    batch_id,
                    e,
                )
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
                    _merge_additional_pdfs(pdf_path, report_data)
                    try:
                        drive_client.upload_file_to_folder(PDF_STORAGE_ADDRESS, str(pdf_path))
                    except Exception as e:
                        logger.warning(
                            "Drive upload failed for batch %s (non-fatal): %s",
                            batch_id,
                            e,
                        )
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


def save_review(batch_id: str, review_data: dict, tenant_id=None) -> None:
    """Persist surveyor review edits into hotspotlabels.json under 'review' key."""
    labels = get_existing_labels(batch_id, tenant_id)
    labels["review"] = review_data.get("review", {})
    labels["property_address"] = review_data.get("property_address", labels.get("property_address", ""))
    labels["surveyor_name"] = review_data.get("inspector_name", labels.get("surveyor_name", ""))
    batchio.save_hotspot_labels(batch_id, labels, tenant_id)


def save_report(batch_id: str, report_data: Dict[str, Any], tenant_id: str | None = None) -> None:
    """Persist report data to disk."""
    batchio.save_heatloss_report(batch_id, report_data, tenant_id)


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
    generated_at = report_data.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M")
    general_notes = report_data.get("general_notes", "")

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
        .surveyor-notes {{ background: #f8f9fa; border-left: 4px solid #667eea; padding: 15px 20px; margin-bottom: 30px; border-radius: 4px; font-style: italic; color: #555; }}
        .finding {{ background: #f8f9fa; border-left: 4px solid #ffc107; padding: 15px; margin-bottom: 15px; border-radius: 4px; }}
        .finding h3 {{ margin-top: 0; color: #495057; }}
        .finding img {{ width: 100%; max-width: 600px; margin: 10px 0; border: 1px solid #dee2e6; border-radius: 4px; }}
        .surveyor-note {{ color: #555; font-style: italic; border-left: 3px solid #ffc107; padding-left: 8px; margin-top: 6px; }}
        .recommendation {{ background: #e7f3ff; border-left: 4px solid #2196F3; padding: 15px; margin-bottom: 15px; border-radius: 4px; }}
        /* FIX: replaced gap: (unsupported in IE/old Edge flexbox) with margin-right on children */
        .stats {{ display: -ms-flexbox; display: flex; margin-bottom: 20px; }}
        .stat-box {{ background: #fff; border: 1px solid #dee2e6; padding: 15px; border-radius: 4px; text-align: center; -ms-flex: 1; flex: 1; margin-right: 15px; }}
        .stat-box:last-child {{ margin-right: 0; }}
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
"""

    # Render general surveyor notes immediately after header if present
    if general_notes:
        html += f"""    <div class=\"surveyor-notes\">
        <strong>\U0001f4dd Surveyor Notes:</strong> {general_notes}
    </div>\n"""

    html += """    <div class=\"section\">
        <h2>Executive Summary</h2>
        <div class=\"stats\">
            <div class=\"stat-box\">
                <div class=\"stat-value\">{total}</div>
                <div class=\"stat-label\">Total Findings</div>
            </div>
            <div class=\"stat-box\">
                <div class=\"stat-value\">{critical}</div>
                <div class=\"stat-label\">Critical Issues</div>
            </div>
            <div class=\"stat-box\">
                <div class=\"stat-value\">{high}</div>
                <div class=\"stat-label\">High Priority</div>
            </div>
        </div>
    </div>
""".format(
        total=summary.get('total_findings', 0),
        critical=summary.get('critical_count', 0),
        high=summary.get('high_count', 0),
    )

    html += """    <div class=\"section\">
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
        surveyor_note = finding.get("surveyor_note", "")

        html += f"""        <div class=\"finding\">
            <h3>Finding {i}: {spot_label}</h3>
            <p><strong>Severity:</strong> {str(severity).upper()} | <strong>Type:</strong> {spot_type}</p>
            <p><strong>Temperature:</strong> Max {float(max_temp):.1f}\u00b0C / Avg {float(avg_temp):.1f}\u00b0C / Min {float(min_temp):.1f}\u00b0C</p>
            <p>{description}</p>
"""
        if surveyor_note:
            html += f'            <p class=\"surveyor-note\"><em>\U0001f4dd Surveyor note: {surveyor_note}</em></p>\n'

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
        <p>Report generated on {generated_at}</p>
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
