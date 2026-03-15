"""Batch service: orchestrates upload, processing, and batch management.

Testbed goals (flat layout + tenant optional):
- Batch artifacts live in settings.BASE_REPORT_DIR/{batch_id}
- Uploads live in settings.BASE_UPLOAD_PATH/{batch_id}
- tenant_id is optional and defaults to None (validated only if present)

This keeps the "services" style while retaining safe path protections.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Iterable, Dict, Any, List

import numpy as np
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

import settings
from settings import (
    BASE_UPLOAD_PATH,
    ALLOWED_EXTENSIONS,
)

from security_utils import safe_batch_path, validate_tenant_id
import services.batch_io as batchio
from services.flir_processor_simple import SimpleFLIRProcessor
from services.thermal_analyzer import ThermalAnalyzer
from services.thermal_data_service import ThermalDataExtractor, save_thermal_data

# Plausible Celsius range for a building survey.
_TEMP_MIN = -60.0
_TEMP_MAX = 200.0


def _temp_data_is_plausible(temp_data: np.ndarray) -> bool:
    """True if the temperature array median is within a plausible building-survey range."""
    if temp_data is None or temp_data.size == 0:
        return False
    median = float(np.median(temp_data[np.isfinite(temp_data)]))
    return _TEMP_MIN <= median <= _TEMP_MAX


def get_batch_id(files: Iterable[FileStorage]) -> str:
    file_list = sorted([f.filename or "" for f in files if f and f.filename])
    hash_str = hashlib.md5("".join(file_list).encode()).hexdigest()[:8]
    return f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash_str}"


def process_batch(
    batch_id: str,
    image_files: Iterable[FileStorage],
    tenant_id: str | None = None,
) -> Dict[str, Any]:
    """Process a batch of uploaded thermal images."""

    tenant_id = validate_tenant_id(tenant_id)

    batch_dir = safe_batch_path(settings.BASE_REPORT_DIR, batch_id, tenant_id)
    upload_dir = (BASE_UPLOAD_PATH / batch_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    processor = SimpleFLIRProcessor()
    analyzer = ThermalAnalyzer(sensitivity="high")

    results: Dict[str, Any] = {
        "batch_id": batch_id,
        "tenant_id": tenant_id,
        "timestamp": datetime.now().isoformat(),
        "images": [],
        "summary": {},
    }

    saved_images: list[str] = []
    for file in image_files:
        if file and file.filename and _allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = upload_dir / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            file.save(str(filepath))
            saved_images.append(str(filepath))

    if not saved_images:
        raise ValueError("No valid JPEG files found in upload")

    all_temps = []
    for image_path in saved_images:
        try:
            # ── Primary extraction via flirimageextractor ──────────────────────
            temp_data, stats = processor.process_single_image(image_path, display=False)

            # Sanity-check: flirimageextractor sometimes returns raw ADC counts
            # instead of Celsius when it can't parse the FLIR metadata.
            # If the result is implausible, fall through to the Planck extractor.
            if not _temp_data_is_plausible(temp_data):
                import logging
                logging.getLogger(__name__).warning(
                    f"{Path(image_path).name}: flirimageextractor returned implausible "
                    f"median {float(np.median(temp_data)):.1f} — trying ThermalDataExtractor."
                )
                temp_data = None
                stats = None

            # ── Secondary extraction via our own Planck code ───────────────────
            thermal_extractor = ThermalDataExtractor()
            thermal_data = thermal_extractor.extract_thermal_data(Path(image_path))

            # Prefer the primary result; use Planck grid as fallback for temp_data
            if temp_data is None and thermal_data is not None:
                temp_data = thermal_data
                valid = temp_data[np.isfinite(temp_data)]
                stats = {
                    "min":    float(np.min(valid)),
                    "max":    float(np.max(valid)),
                    "mean":   float(np.mean(valid)),
                    "median": float(np.median(valid)),
                    "std":    float(np.std(valid)),
                }

            if temp_data is None:
                raise ValueError(
                    f"Could not extract plausible temperature data from {Path(image_path).name}. "
                    "Check that exiftool is installed and the file is a genuine FLIR radiometric JPEG."
                )

            # Save the Planck grid (.npz) for per-pixel API queries
            if thermal_data is not None:
                save_thermal_data(batch_dir, Path(image_path).name, thermal_data)
            else:
                # Use temp_data from flirimageextractor as the grid
                save_thermal_data(batch_dir, Path(image_path).name, temp_data)

            hot_spots = analyzer.detect_hot_spots(temp_data, image_path=image_path)

            html_report = analyzer.generate_report(Path(image_path).name, hot_spots, stats)
            report_filename = Path(image_path).stem + "_thermal_report.html"
            report_path = batch_dir / report_filename
            report_path.write_text(html_report, encoding="utf-8")

            labeled_filename = Path(image_path).stem + "_labeled.jpg"
            labeled_path = batch_dir / labeled_filename
            try:
                analyzer.label_hot_spots(image_path, hot_spots, str(labeled_path))
            except Exception:
                pass

            csv_filename = Path(image_path).stem + "_temperatures.csv"
            csv_path = batch_dir / csv_filename
            processor.save_temperature_array(temp_data, str(csv_path))

            image_result = {
                "filename": Path(image_path).name,
                "stats": {
                    "min":    float(stats["min"]),
                    "max":    float(stats["max"]),
                    "mean":   float(stats["mean"]),
                    "median": float(stats["median"]),
                    "std":    float(stats["std"]),
                },
                "shape": list(temp_data.shape),
                "hot_spots": [spot.to_dict() for spot in hot_spots],
                "hot_spot_count": len(hot_spots),
                "thermal_report": report_filename,
                "labeled_image": labeled_filename,
                "temperatures_csv": csv_filename,
            }
            results["images"].append(image_result)
            all_temps.append(stats)

        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(
                "Error processing %s: %s", Path(image_path).name, e
            )
            results["images"].append({"filename": Path(image_path).name, "error": str(e)})

    if all_temps:
        temps = [t["mean"] for t in all_temps]
        results["summary"] = {
            "total_images":      len(all_temps),
            "successful_images": len(all_temps),
            "avg_temperature":   sum(temps) / len(temps),
            "min_temperature":   min(t["min"] for t in all_temps),
            "max_temperature":   max(t["max"] for t in all_temps),
        }

    batchio.save_batch_results(batch_id, results, tenant_id=tenant_id)

    thermal_analysis = {
        "batch_id": batch_id,
        "tenant_id": tenant_id,
        "timestamp": datetime.now().isoformat(),
        "images": [
            {
                "filename":     img["filename"],
                "hot_spots":    img.get("hot_spots", []),
                "labeled_image": img.get("labeled_image", ""),
            }
            for img in results["images"]
            if "error" not in img
        ],
    }
    batchio.save_thermal_analysis(batch_id, thermal_analysis, tenant_id=tenant_id)

    return results


def get_all_batches(tenant_id: str | None = None) -> List[Dict[str, Any]]:
    validate_tenant_id(tenant_id)
    return batchio.list_batches(tenant_id)


def get_batch_summary(batch_id: str, tenant_id: str | None = None) -> Dict[str, Any]:
    validate_tenant_id(tenant_id)
    data = batchio.load_batch_results(batch_id, tenant_id)
    if not data:
        raise FileNotFoundError(f"Batch {batch_id} not found")
    return data


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
