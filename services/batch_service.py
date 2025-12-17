"""
Batch service.

Handles upload, validation and initial processing of image batches.
Connects the Flask layer to SimpleFLIRProcessor and ThermalAnalyzer.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable, Dict, Any, Tuple, List

from werkzeug.datastructures import FileStorage

from settings import (
    BASE_UPLOAD_PATH,
    BATCH_SIZE_MAX,
    THERMAL_SENSITIVITY,
    is_allowed_file,
)
from lib.security_utils import safe_batch_path, validate_tenant_id
import services.batch_io as batchio
from flir_processor_simple import SimpleFLIRProcessor
from thermal_analyzer import ThermalAnalyzer


def _generate_batch_id() -> str:
    """
    Generate a unique batch ID.

    Uses timestamp plus a short random suffix to remain readable.
    """
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"batch{ts}{suffix}"


def _save_uploads(files: Iterable[FileStorage], tenant_id: str, batch_id: str) -> List[Path]:
    """Save uploaded image files to a tenant-specific upload dir."""
    upload_base = BASE_UPLOAD_PATH / tenant_id / batch_id
    upload_base.mkdir(parents=True, exist_ok=True)

    saved_paths: List[Path] = []
    for f in files:
        filename = f.filename or ""
        if not filename:
            continue
        if not is_allowed_file(filename):
            # Skip silently; caller can decide to enforce at Flask layer
            continue
        safe_name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        dest = upload_base / safe_name
        f.save(str(dest))
        saved_paths.append(dest)

    return saved_paths


def process_batch(
    files: Iterable[FileStorage],
    tenant_id: str | None = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Process a new batch from uploaded files.

    Returns:
      (batch_id, batch_summary_dict)
    """
    tenant_id = validate_tenant_id(tenant_id)

    file_list = [f for f in files if (f.filename or "").strip()]
    if not file_list:
        raise ValueError("No files uploaded")
    if len(file_list) > BATCH_SIZE_MAX:
        raise ValueError(f"Too many files: max {BATCH_SIZE_MAX} per batch")

    batch_id = _generate_batch_id()
    saved_paths = _save_uploads(file_list, tenant_id, batch_id)

    if not saved_paths:
        raise ValueError("No valid JPEG files found in upload")

    # Ensure batch directory exists immediately
    batch_dir = safe_batch_path(batch_id, tenant_id)

    # Use SimpleFLIRProcessor for extraction
    processor = SimpleFLIRProcessor()
    analyzer = ThermalAnalyzer(sensitivity=THERMAL_SENSITIVITY)

    images_meta: List[Dict[str, Any]] = []
    global_min = None
    global_max = None
    temps_sum = 0.0
    temps_count = 0

        for image_path in saved_paths:
        tempdata, stats = processor.process_single_image(str(image_path), display=False)
        hotspots = analyzer.detect_hot_spots(tempdata, method='statistical')
        
        # Convert hotspots to dict format for JSON storage
        analysis = {
            "hotspots": [spot.to_dict() for spot in hotspots],
            "hotspot_count": len(hotspots),
            "method": "statistical",
        }

        # persist per-image analysis into batch_dir/analysis-images if needed
        analysis_dir = batch_dir / "analysis-images"
        analysis_dir.mkdir(parents=True, exist_ok=True)
        # analyzer could optionally save overlay images there; keep JSON in memory for now

        images_meta.append(
            {
                "filename": image_path.name,
                "path": str(image_path),
                "stats": stats,
                "analysis": analysis,
            }
        )

        # aggregate statistics
        img_min = stats.get("min")
        img_max = stats.get("max")
        img_mean = stats.get("mean")
        if img_min is not None:
            global_min = img_min if global_min is None else min(global_min, img_min)
        if img_max is not None:
            global_max = img_max if global_max is None else max(global_max, img_max)
        if img_mean is not None:
            temps_sum += float(img_mean)
            temps_count += 1

    avg_temp = temps_sum / temps_count if temps_count else None

    summary = {
        "batchid": batch_id,
        "timestamp": datetime.utcnow().isoformat(),
        "image_count": len(images_meta),
        "mintemperature": global_min,
        "maxtemperature": global_max,
        "avgtemperature": avg_temp,
    }

    batch_results = {
        "batchid": batch_id,
        "timestamp": summary["timestamp"],
        "image_count": summary["image_count"],
        "summary": summary,
        "images": images_meta,
    }

    # Save batch results and overall thermal analysis
    batchio.save_batch_results(batch_id, batch_results, tenant_id)

    # ThermalAnalyzer can also return batch-level findings
    # Simple batch-level summary (ThermalAnalyzer doesn't have generate_batch_analysis)
    batch_analysis = {
        "batch_id": batch_id,
        "timestamp": datetime.utcnow().isoformat(),
        "total_images": len(images_meta),
        "total_hotspots": sum(img.get("analysis", {}).get("hotspot_count", 0) for img in images_meta),
        "images": images_meta,
    }
    batchio.save_thermal_analysis(batch_id, batch_analysis, tenant_id)

    return batch_id, summary


def get_all_batches(tenant_id: str | None = None) -> list[Dict[str, Any]]:
    """Return list of batches for index page."""
    tenant_id = validate_tenant_id(tenant_id)
    return batchio.list_batches(tenant_id)


def get_batch_summary(batch_id: str, tenant_id: str | None = None) -> Dict[str, Any]:
    """Return full batchresults.json for a given batch."""
    tenant_id = validate_tenant_id(tenant_id)
    data = batchio.load_batch_results(batch_id, tenant_id)
    if not data:
        raise FileNotFoundError(f"Batch {batch_id} not found")
    return data
