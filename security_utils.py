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
