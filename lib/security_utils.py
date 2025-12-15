"""
Security utilities for path validation and batch access control.
Tenant-aware: supports both single and multi-tenant modes.
"""
import re
from pathlib import Path
import settings


def validate_tenant_id(tenant_id):
    """
    Validate tenant ID format.
    
    Args:
        tenant_id (str): Tenant identifier
        
    Returns:
        bool: True if valid format
        
    Raises:
        ValueError: If invalid format
    """
    if not tenant_id or not isinstance(tenant_id, str):
        raise ValueError(f"Invalid tenant_id: {tenant_id}")
    
    # Allow alphanumeric, hyphen, underscore
    if not re.match(r'^[a-zA-Z0-9_-]+$', tenant_id):
        raise ValueError(f"Invalid tenant_id format: {tenant_id}. Use alphanumeric, hyphen, underscore only.")
    
    return True


def validate_batch_id(batch_id):
    """
    Validate batch ID format.
    Expected format: batch_YYYYMMDD_HHMMSS_xxxxx
    
    Args:
        batch_id (str): Batch identifier
        
    Returns:
        bool: True if valid format
        
    Raises:
        ValueError: If invalid format
    """
    if not batch_id or not isinstance(batch_id, str):
        raise ValueError(f"Invalid batch_id: {batch_id}")
    
    # batch_YYYYMMDD_HHMMSS_hash
    if not re.match(r'^batch_\d{8}_\d{6}_[a-f0-9]+$', batch_id):
        raise ValueError(f"Invalid batch_id format: {batch_id}")
    
    return True


def safe_batch_path(batch_id, tenant_id=None, reports_dir=None):
    """
    Construct a safe, validated path to a batch directory.
    Prevents path traversal attacks.
    
    Args:
        batch_id (str): Batch identifier
        tenant_id (str): Tenant ID (uses DEFAULT_TENANT if not provided)
        reports_dir (str): Base reports directory (uses BASE_REPORT_DIR from settings if not provided)
        
    Returns:
        Path: Safe path object to batch directory
        
    Raises:
        ValueError: If batch_id or tenant_id invalid
    """
    # Validate inputs
    validate_batch_id(batch_id)
    
    if tenant_id is None:
        tenant_id = settings.DEFAULT_TENANT
    
    validate_tenant_id(tenant_id)
    
    if reports_dir is None:
        reports_dir = settings.BASE_REPORT_DIR
    
    # Construct path: reports_dir / batches / tenant_id / batch_id
    base = Path(reports_dir).resolve()
    batch_path = base / 'batches' / tenant_id / batch_id
    
    # Ensure the resolved path is still within base (path traversal check)
    try:
        batch_path.relative_to(base)
    except ValueError:
        raise ValueError(f"Path traversal attempt detected: {batch_path}")
    
    return batch_path


def safe_upload_path(tenant_id=None, upload_dir=None):
    """
    Construct a safe path to upload directory for a tenant.
    
    Args:
        tenant_id (str): Tenant ID (uses DEFAULT_TENANT if not provided)
        upload_dir (str): Base upload directory (uses BASE_UPLOAD_DIR from settings if not provided)
        
    Returns:
        Path: Safe path to tenant upload directory
        
    Raises:
        ValueError: If tenant_id invalid
    """
    if tenant_id is None:
        tenant_id = settings.DEFAULT_TENANT
    
    validate_tenant_id(tenant_id)
    
    if upload_dir is None:
        upload_dir = settings.BASE_UPLOAD_DIR
    
    base = Path(upload_dir).resolve()
    tenant_path = base / 'batches' / tenant_id
    
    # Path traversal check
    try:
        tenant_path.relative_to(base)
    except ValueError:
        raise ValueError(f"Path traversal attempt detected: {tenant_path}")
    
    return tenant_path
