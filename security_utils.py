#!/usr/bin/env python3
"""Security utilities for thermal-report application"""

import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def validate_batch_id(batch_id: str) -> bool:
    """Validate batch_id to prevent path traversal attacks"""
    if not batch_id or len(batch_id) > 100:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', batch_id)) and '..' not in batch_id

def safe_batch_path(reports_dir: str, batch_id: str) -> Path:
    """Safely construct batch path with validation"""
    if not validate_batch_id(batch_id):
        logger.warning(f"Invalid batch_id attempted: {batch_id}")
        raise ValueError(f"Invalid batch_id: {batch_id}")
    
    reports_base = Path(reports_dir).resolve()
    batch_path = reports_base / 'batches' / batch_id
    
    try:
        batch_resolved = batch_path.resolve()
        if not str(batch_resolved).startswith(str(reports_base)):
            logger.warning(f"Path traversal attempt: {batch_id}")
            raise ValueError("Invalid batch path: potential directory traversal")
    except (OSError, RuntimeError) as e:
        logger.error(f"Path resolution error: {e}")
        raise ValueError("Invalid batch path")
    
    return batch_path


def validate_tenant_id(tenant_id: str | None) -> bool:
    """
    Validate tenant_id to prevent injection/traversal.
    Allows None (no tenant), alphanumeric, underscores, and hyphens.
    """
    if tenant_id is None:
        return True
    if len(tenant_id) > 50:
        return False
    # Only allow safe characters: a-z, A-Z, 0-9, _, -
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', tenant_id))

def safe_upload_path(upload_dir: str, filename: str) -> Path:
    """Safely construct upload path with validation"""
    if not filename or '..' in filename or filename.startswith('/'):
        raise ValueError(f"Invalid filename: {filename}")
    
    # Simple sanitization
    clean_filename = re.sub(r'[^a-zA-Z0-9_.-]', '', filename)
    if not clean_filename:
        raise ValueError("Filename became empty after sanitization")
        
    upload_base = Path(upload_dir).resolve()
    file_path = upload_base / clean_filename
    
    try:
        resolved_path = file_path.resolve()
        if not str(resolved_path).startswith(str(upload_base)):
            raise ValueError("Invalid upload path: traversal attempt")
    except (OSError, RuntimeError):
        raise ValueError("Invalid upload path")
        
    return file_path
