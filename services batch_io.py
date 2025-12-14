"""
Batch I/O abstraction layer.
Handles all JSON read/write operations for batches.
Centralizes file structure knowledge in one place.
"""
import json
from pathlib import Path
from lib.security_utils import safe_batch_path, validate_batch_id, validate_tenant_id


def load_json(file_path):
    """
    Safely load JSON from file.
    
    Args:
        file_path (str or Path): Path to JSON file
        
    Returns:
        dict: Loaded JSON data
        
    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is invalid JSON
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'r') as f:
        return json.load(f)


def save_json(file_path, data):
    """
    Safely save JSON to file, creating parent directories as needed.
    
    Args:
        file_path (str or Path): Path to JSON file
        data (dict): Data to save
        
    Raises:
        IOError: If write fails
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)


def ensure_batch_dir(batch_id, tenant_id=None, reports_dir=None):
    """
    Ensure batch directory exists and is ready for use.
    
    Args:
        batch_id (str): Batch ID
        tenant_id (str): Tenant ID
        reports_dir (str): Base reports directory
        
    Returns:
        Path: Path to batch directory
    """
    batch_path = safe_batch_path(batch_id, tenant_id=tenant_id, reports_dir=reports_dir)
    batch_path.mkdir(parents=True, exist_ok=True)
    return batch_path


# ============================================================================
# Batch Data Access Functions (Higher-level API)
# ============================================================================

def load_batch_results(batch_id, tenant_id=None, reports_dir=None):
    """Load results.json for a batch."""
    batch_path = safe_batch_path(batch_id, tenant_id=tenant_id, reports_dir=reports_dir)
    results_file = batch_path / 'results.json'
    return load_json(results_file)


def save_batch_results(batch_id, results, tenant_id=None, reports_dir=None):
    """Save results.json for a batch."""
    batch_path = safe_batch_path(batch_id, tenant_id=tenant_id, reports_dir=reports_dir)
    results_file = batch_path / 'results.json'
    save_json(results_file, results)


def load_thermal_analysis(batch_id, tenant_id=None, reports_dir=None):
    """Load thermal_analysis.json (raw analyzer output)."""
    batch_path = safe_batch_path(batch_id, tenant_id=tenant_id, reports_dir=reports_dir)
    analysis_file = batch_path / 'thermal_analysis.json'
    return load_json(analysis_file)


def save_thermal_analysis(batch_id, analysis, tenant_id=None, reports_dir=None):
    """Save thermal_analysis.json."""
    batch_path = safe_batch_path(batch_id, tenant_id=tenant_id, reports_dir=reports_dir)
    analysis_file = batch_path / 'thermal_analysis.json'
    save_json(analysis_file, analysis)


def load_hotspot_labels(batch_id, tenant_id=None, reports_dir=None):
    """Load hotspot_labels.json (operator labels)."""
    batch_path = safe_batch_path(batch_id, tenant_id=tenant_id, reports_dir=reports_dir)
    labels_file = batch_path / 'hotspot_labels.json'
    
    if not labels_file.exists():
        return {}
    
    return load_json(labels_file)


def save_hotspot_labels(batch_id, labels, tenant_id=None, reports_dir=None):
    """Save hotspot_labels.json."""
    batch_path = safe_batch_path(batch_id, tenant_id=tenant_id, reports_dir=reports_dir)
    labels_file = batch_path / 'hotspot_labels.json'
    save_json(labels_file, labels)


def load_heat_loss_report(batch_id, tenant_id=None, reports_dir=None):
    """Load heat_loss_report.json (final report data)."""
    batch_path = safe_batch_path(batch_id, tenant_id=tenant_id, reports_dir=reports_dir)
    report_file = batch_path / 'heat_loss_report.json'
    return load_json(report_file)


def save_heat_loss_report(batch_id, report_data, tenant_id=None, reports_dir=None):
    """Save heat_loss_report.json."""
    batch_path = safe_batch_path(batch_id, tenant_id=tenant_id, reports_dir=reports_dir)
    report_file = batch_path / 'heat_loss_report.json'
    save_json(report_file, report_data)
