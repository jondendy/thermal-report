"""Batch IO utilities.

Single source of truth for how batch-related JSON data and analysis artifacts
are stored and loaded on disk.

Testbed layout (flat folders):
  settings.BASE_REPORT_DIR/
    {batch_id}/
      batchresults.json
      thermalanalysis.json
      hotspotlabels.json
      heatlossreportdata.json
      final_report_{batch_id}.html
      thermal_report_{batch_id}.pdf

Tenant support is intentionally optional in this branch; tenant_id is accepted
for forward-compatibility but does not affect paths unless a future branch
reintroduces multi-tenant directory layouts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import settings
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
    """Ensure the batch directory exists and return its Path (flat layout)."""
    return safe_batch_path(settings.BASE_REPORT_DIR, batch_id, tenant_id)


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
    """Return a list of batch metadata for the index page.

    Scans settings.BASE_REPORT_DIR for batch directories (flat layout).
    """
    # tenant_id is ignored for now (flat layout), but validate if provided.
    from security_utils import validate_tenant_id

    validate_tenant_id(tenant_id)

    base = Path(settings.BASE_REPORT_DIR).resolve()
    if not base.exists():
        return []

    items: list[Dict[str, Any]] = []
    for batch_dir in sorted(base.iterdir()):
        if not batch_dir.is_dir():
            continue

        batch_id = batch_dir.name
        # Skip directories that don't look like batch IDs
        # (avoids issues if someone drops random folders in .reports)
        try:
            safe_batch_path(settings.BASE_REPORT_DIR, batch_id, None)
        except Exception:
            continue

        meta = _read_json(batch_dir / "batchresults.json")
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

    items.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    return items
