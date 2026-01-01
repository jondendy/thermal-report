"""Heat loss service.

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
    tenant_id: str | None = None,
) -> Dict[str, Any]:
    """
    Generate full heat loss report data (not HTML) and persist it.
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
        "recommendations_document_url": RECOMMENDATIONS_DOCUMENT_URL,
    }

    batchio.save_heatloss_report(batch_id, report_data, tenant_id)
    return report_data


def get_report(batch_id: str, tenant_id: str | None = None) -> Dict[str, Any]:
    report_data = batchio.load_heatloss_report(batch_id, tenant_id)
    if report_data is None:
        raise FileNotFoundError(f"No report found for batch {batch_id}")
    return report_data
