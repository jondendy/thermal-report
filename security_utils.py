#!/usr/bin/env python3
"""Security utilities for thermal-report application.

This testbed version aligns with the folder-workflow behavior:
- Flat batch folders (no tenant subfolders by default)
- Uses BASE_REPORT_DIR as the canonical base (via `safe_batch_path` calls)
- tenant_id is optional (None by default) and does not affect paths

Still enforces strict batch_id validation and path traversal protections.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Allow common batch id styles: batch_YYYYMMDD_HHMMSS_hash, UUID-ish, etc.
_BATCH_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-_]+$")
_TENANT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


def validate_tenant_id(tenant_id: str | None) -> str | None:
    """Validate tenant_id format when provided.

    In this flat-folder testbed, tenant_id is optional and defaults to None.
    """
    if tenant_id is None or tenant_id == "":
        return None

    if len(tenant_id) > 50:
        raise ValueError(f"Tenant ID too long: {tenant_id}")

    if not _TENANT_ID_PATTERN.match(tenant_id):
        logger.warning("Invalid tenant_id attempted: %s", tenant_id)
        raise ValueError(f"Invalid tenant ID: {tenant_id}")

    return tenant_id


def validate_batch_id(batch_id: str) -> bool:
    """Validate batch_id to prevent path traversal attacks."""
    if not batch_id or len(batch_id) > 100:
        return False
    if ".." in batch_id or "/" in batch_id or "\\" in batch_id:
        return False
    return bool(_BATCH_ID_PATTERN.match(batch_id))


def safe_batch_path(reports_dir: str | Path, batch_id: str, tenant_id: str | None = None) -> Path:
    """Safely construct a flat batch path within reports_dir/batch_id.

    Raises ValueError on invalid IDs or traversal attempts.
    Creates the directory (parents=True) if needed.

    Note: tenant_id is accepted for forward-compatibility but does not change
    the resulting path in this flat-folder workflow.
    """
    # Validate IDs
    validate_tenant_id(tenant_id)

    if not validate_batch_id(batch_id):
        logger.warning("Invalid batch_id attempted: %s", batch_id)
        raise ValueError(f"Invalid batch ID: {batch_id}")

    reports_base = Path(reports_dir).resolve()
    batch_path = (reports_base / batch_id)

    try:
        batch_resolved = batch_path.resolve()
        if not str(batch_resolved).startswith(str(reports_base)):
            logger.warning("Path traversal attempt for batch_id=%s", batch_id)
            raise ValueError("Invalid batch path: potential directory traversal")
    except (OSError, RuntimeError) as e:
        logger.error("Path resolution error: %s", e)
        raise ValueError("Invalid batch path") from e

    batch_path.mkdir(parents=True, exist_ok=True)
    return batch_path


def safe_upload_path(upload_dir: str | Path, filename: str, tenant_id: str | None = None) -> Path:
    """Safely construct upload path with validation."""
    validate_tenant_id(tenant_id)

    if not filename or ".." in filename or filename.startswith("/") or filename.startswith("\\"):
        raise ValueError(f"Invalid filename: {filename}")

    # Simple sanitization
    clean_filename = re.sub(r"[^a-zA-Z0-9_.-]", "", filename)
    if not clean_filename:
        raise ValueError("Filename became empty after sanitization")

    upload_base = Path(upload_dir).resolve()
    file_path = upload_base / clean_filename

    try:
        resolved_path = file_path.resolve()
        if not str(resolved_path).startswith(str(upload_base)):
            raise ValueError("Invalid upload path: traversal attempt")
    except (OSError, RuntimeError) as e:
        raise ValueError("Invalid upload path") from e

    return file_path
