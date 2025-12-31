#!/usr/bin/env python3
"""
Security utilities for thermal-report application.

Provides strict validation for tenant IDs and batch IDs, plus safe path
construction under the reports directory to prevent directory traversal.
"""

import re
import logging
from pathlib import Path

from settings import BASE_REPORT_PATH, DEFAULT_TENANT, TENANT_MODE

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------

_BATCH_ID_PATTERN = re.compile(r"^[a-zA-Z0-9\-]+$")  # batchYYYYMMDDHHMMSShash
_TENANT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


def validate_tenant_id(tenant_id: str | None) -> str:
    """
    Validate tenant_id and return a safe value.

    In single-tenant mode, missing tenant_id is replaced with DEFAULT_TENANT.
    In multi-tenant mode, tenant_id must be provided and must match pattern.
    """
    if TENANT_MODE == "single":
        if not tenant_id:
            return DEFAULT_TENANT
    if not tenant_id:
        logger.warning("Missing tenant_id in multi-tenant mode")
        raise ValueError("Missing tenant ID")

    if not _TENANT_ID_PATTERN.match(tenant_id):
        logger.warning("Invalid tenant_id attempted: %s", tenant_id)
        raise ValueError(f"Invalid tenant ID: {tenant_id}")

    return tenant_id


def validate_batch_id(batch_id: str) -> bool:
    """
    Validate batch_id to prevent path traversal attacks.

    Returns True for valid IDs, False otherwise.
    """
    if not batch_id or len(batch_id) > 100:
        return False
    if ".." in batch_id or "/" in batch_id or "\\" in batch_id:
        return False
    return bool(_BATCH_ID_PATTERN.match(batch_id))


# ---------------------------------------------------------------------------
# Safe path builders
# ---------------------------------------------------------------------------

def safe_batch_path(batch_id: str, tenant_id: str | None = None) -> Path:
    """
    Safely construct batch path within BASE_REPORT_PATH/batches.

    Raises ValueError on invalid IDs or traversal attempts.
    """
    if not validate_batch_id(batch_id):
        logger.warning("Invalid batch_id attempted: %s", batch_id)
        raise ValueError(f"Invalid batch ID: {batch_id}")

    tenant_id = validate_tenant_id(tenant_id)
    reports_base = BASE_REPORT_PATH.resolve()
    batch_path = reports_base / "batches" / tenant_id / batch_id

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


def safe_upload_path(tenant_id: str | None = None) -> Path:
    """
    Return safe upload path for a tenant under BASE_REPORT_PATH/uploads.

    This ensures uploads and reports can be kept in a single tree if desired.
    """
    tenant_id = validate_tenant_id(tenant_id)
    uploads_base = BASE_REPORT_PATH.resolve() / "uploads" / tenant_id
    uploads_base.mkdir(parents=True, exist_ok=True)
    return uploads_base
