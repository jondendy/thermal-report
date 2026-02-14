"""
Batch IO utilities.

Single source of truth for how batch-related JSON data and analysis artifacts
are stored and loaded on disk.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from settings import BASE_REPORT_PATH
from security_utils import safe_batch_path


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Batch-level helpers
# ---------------------------------------------------------------------------

def ensure_batch_dir(batch_id: str, tenant_id: str | None = None) -> Path:
    from security_utils import safe_batch_path
    from settings import BASE_REPORT_DIR
    
    batch_dir = safe_batch_path(BASE_REPORT_DIR, batch_id, tenant_id)
    batch_dir.mkdir(parents=True, exist_ok=True)
    return batch_dir


def load_batch_results(batch_id: str, tenant_id: str | None = None) -> Optional[Dict[str, Any]]:
    batch_dir = ensure_batch_dir(batch_id, tenant_id)
    return _read_json(batch_dir / "batchresults.json")


def save_batch_results(batch_id: str, results: Dict[str, Any], tenant_id: str | None = None) -> None:
    batch_dir = ensure_batch_dir(batch_id, tenant_id)
    _write_json(batch_dir / "batchresults.json", results)


def load_thermal_analysis(batch_id: str, tenant_id: str | None = None) -> Optional[Dict[str, Any]]:
    batch_dir = ensure_batch_dir(batch_id, tenant_id)
    return _read_json(batch_dir / "thermalanalysis.json")


def save_thermal_analysis(batch_id: str, analysis: Dict[str, Any], tenant_id: str | None = None) -> None:
    batch_dir = ensure_batch_dir(batch_id, tenant_id)
    _write_json(batch_dir / "thermalanalysis.json", analysis)


def load_hotspot_labels(batch_id: str, tenant_id: str | None = None) -> Optional[Dict[str, Any]]:
    batch_dir = ensure_batch_dir(batch_id, tenant_id)
    return _read_json(batch_dir / "hotspotlabels.json")


def save_hotspot_labels(batch_id: str, labels: Dict[str, Any], tenant_id: str | None = None) -> None:
    batch_dir = ensure_batch_dir(batch_id, tenant_id)
    _write_json(batch_dir / "hotspotlabels.json", labels)


def load_heatloss_report(batch_id: str, tenant_id: str | None = None) -> Optional[Dict[str, Any]]:
    batch_dir = ensure_batch_dir(batch_id, tenant_id)
    return _read_json(batch_dir / "heatlossreportdata.json")


def save_heatloss_report(batch_id: str, report_data: Dict[str, Any], tenant_id: str | None = None) -> None:
    batch_dir = ensure_batch_dir(batch_id, tenant_id)
    _write_json(batch_dir / "heatlossreportdata.json", report_data)


def get_report_html_path(batch_id: str, tenant_id: str | None = None) -> Path:
    batch_dir = ensure_batch_dir(batch_id, tenant_id)
    return batch_dir / "heatlossreport.html"


# ---------------------------------------------------------------------------
# Index listing
# ---------------------------------------------------------------------------

def list_batches(tenant_id: str | None = None) -> list[Dict[str, Any]]:
    """
    Return a list of batch metadata for the index page.

    Each item contains:
      - batchid
      - timestamp (if present in batchresults.json)
      - imagecount
      - summary (optional: min/max/mean temps etc.)
    """
    from security_utils import validate_tenant_id  # avoid circular import

    tenant_id = validate_tenant_id(tenant_id)
    base = BASE_REPORT_PATH.resolve() / "batches" / tenant_id
    if not base.exists():
        return []

    items: list[Dict[str, Any]] = []
    for batch_dir in sorted(base.iterdir()):
        if not batch_dir.is_dir():
            continue
        batch_id = batch_dir.name
        meta = load_batch_results(batch_id, tenant_id)
        if not meta:
            continue
        summary = meta.get("summary") or {}
        timestamp = meta.get("timestamp")
        imagecount = meta.get("image_count", len(meta.get("images", [])))
        items.append(
            {
                "batchid": batch_id,
                "timestamp": timestamp,
                "imagecount": imagecount,
                "summary": summary,
            }
        )
    # Sort newest first by timestamp if available
    items.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    return items
