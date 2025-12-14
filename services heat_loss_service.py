"""
Heat loss service: orchestrates labeling and report generation workflow.
Step 1: Load and save hot spot labels
Step 2: Generate professional heat loss report
"""
from datetime import datetime
from pathlib import Path

import settings
from services.batch_io import (
    load_thermal_analysis, load_hotspot_labels, save_hotspot_labels,
    load_heat_loss_report, save_heat_loss_report
)
from heat_loss_reporter import HeatLossReporter


def get_thermal_analysis(batch_id, tenant_id=None):
    """
    Load thermal analysis data for UI (labeling interface).
    
    Args:
        batch_id (str): Batch ID
        tenant_id (str): Tenant ID
        
    Returns:
        dict: Thermal analysis data with detected hot spots per image
    """
    if tenant_id is None:
        tenant_id = settings.DEFAULT_TENANT
    
    return load_thermal_analysis(batch_id, tenant_id=tenant_id)


def get_existing_labels(batch_id, tenant_id=None):
    """
    Load existing hot spot labels (if any).
    
    Args:
        batch_id (str): Batch ID
        tenant_id (str): Tenant ID
        
    Returns:
        dict: Existing labels, or empty dict if none
    """
    if tenant_id is None:
        tenant_id = settings.DEFAULT_TENANT
    
    return load_hotspot_labels(batch_id, tenant_id=tenant_id)


def save_labels(batch_id, label_data, tenant_id=None):
    """
    Save hot spot labels submitted by operator.
    
    Args:
        batch_id (str): Batch ID
        label_data (dict): Label data structure
        tenant_id (str): Tenant ID
        
    Returns:
        dict: Saved label structure
    """
    if tenant_id is None:
        tenant_id = settings.DEFAULT_TENANT
    
    # Structure the data
    labels_structure = {
        'batch_id': batch_id,
        'tenant_id': tenant_id,
        'labeled_spots': label_data.get('labeled_spots', []),
        'timestamp': datetime.now().isoformat()
    }
    
    # Generate cross-references (spots visible in multiple images)
    cross_refs = {}
    for spot in labels_structure['labeled_spots']:
        spot_num = spot.get('spot_number')
        if spot_num:
            if spot_num not in cross_refs:
                cross_refs[spot_num] = []
            cross_refs[spot_num].append(spot.get('spot_id'))
    
    labels_structure['cross_references'] = cross_refs
    
    # Save
    save_hotspot_labels(batch_id, labels_structure, tenant_id=tenant_id)
    
    return labels_structure


def generate_report(batch_id, property_address='', inspector_name='', tenant_id=None):
    """
    Generate professional heat loss report from labeled hot spots.
    
    Args:
        batch_id (str): Batch ID
        property_address (str): Optional property address
        inspector_name (str): Optional inspector name
        tenant_id (str): Tenant ID
        
    Returns:
        dict: Generated report data
        
    Raises:
        FileNotFoundError: If required data files not found
        ValueError: If labels not yet created
    """
    if tenant_id is None:
        tenant_id = settings.DEFAULT_TENANT
    
    # Load existing labels
    labels = load_hotspot_labels(batch_id, tenant_id=tenant_id)
    if not labels or not labels.get('labeled_spots'):
        raise ValueError(
            f"No labels found for batch {batch_id}. "
            "Please label hot spots before generating report."
        )
    
    # Load thermal analysis
    analysis = load_thermal_analysis(batch_id, tenant_id=tenant_id)
    
    # Initialize reporter
    reporter = HeatLossReporter()
    
    # Generate report
    report_data = reporter.generate_report(
        batch_id=batch_id,
        analysis_data=analysis,
        labels=labels,
        property_address=property_address,
        inspector_name=inspector_name,
        org_name=settings.ORG_NAME,
        org_website=settings.ORG_WEBSITE,
        org_contact=settings.ORG_CONTACT
    )
    
    # Save report data
    save_heat_loss_report(batch_id, report_data, tenant_id=tenant_id)
    
    return report_data


def get_report(batch_id, tenant_id=None):
    """
    Load a generated heat loss report.
    
    Args:
        batch_id (str): Batch ID
        tenant_id (str): Tenant ID
        
    Returns:
        dict: Report data
    """
    if tenant_id is None:
        tenant_id = settings.DEFAULT_TENANT
    
    return load_heat_loss_report(batch_id, tenant_id=tenant_id)
