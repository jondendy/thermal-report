"""
Heat loss service.

Connects stored thermal analysis and operator hotspot labels with the
HeatLossReporter to generate homeowner-friendly HTML reports.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, List, Optional

from settings import ORG_NAME, ORG_WEBSITE, ORG_CONTACT
import services.batch_io as batchio
from heat_loss_reporter import HeatLossReporter
from thermal_analyzer import ThermalAnalyzer


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
    Build a list of findings suitable for HeatLossReporter from raw analysis and labels.
    """
    analyzer = ThermalAnalyzer()  # sensitivity can be embedded in analysis if needed
    findings = analyzer.merge_labels_with_analysis(analysis, labels)
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
        "batchid": batch_id,
        "propertyaddress": property_address or "Not specified",
        "inspectorname": inspector_name or "Not specified",
        "surveydate": datetime.now().strftime("%Y-%m-%d"),
        "surveytime": datetime.now().strftime("%H:%M"),
        "summary": summary,
        "findings": findings,
        "recommendations": recommendations,
        "organisation": {
            "name": ORG_NAME,
            "website": ORG_WEBSITE,
            "contact": ORG_CONTACT,
        },
    }

    batchio.save_heatloss_report(batch_id, report_data, tenant_id)
    return report_data


def get_report(batch_id: str, tenant_id: str | None = None) -> Dict[str, Any]:
    report_data = batchio.load_heatloss_report(batch_id, tenant_id)
    if report_data is None:
        raise FileNotFoundError(f"No report found for batch {batch_id}")
    return report_data
