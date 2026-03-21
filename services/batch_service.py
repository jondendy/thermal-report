"""Batch service: orchestrates upload, processing, and batch management.
Separates batch logic from Flask routing.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from typing import Iterable, Dict, Any, List

import numpy as np
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from settings import (
    BASE_UPLOAD_PATH,
    BATCH_SIZE_MAX,
    is_allowed_file,
    ALLOWED_EXTENSIONS,
)
from utils.security_utils import safe_batch_path, validate_tenant_id
import services.batch_io as batchio
from services.thermal_analyzer import ThermalAnalyzer
from services.thermal_data_service import ThermalDataExtractor, save_thermal_data


def get_batch_id(files: Iterable[FileStorage]) -> str:
    file_list = sorted([f.filename or "" for f in files if f and f.filename])
    hash_str = hashlib.md5(''.join(file_list).encode()).hexdigest()[:8]
    return f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash_str}"


def _compute_stats(temp_data: np.ndarray) -> Dict[str, float]:
    valid = temp_data[np.isfinite(temp_data)]
    if len(valid) == 0:
        return {'min': 0.0, 'max': 0.0, 'mean': 0.0, 'median': 0.0, 'std': 0.0}
    return {
        'min': float(np.min(valid)),
        'max': float(np.max(valid)),
        'mean': float(np.mean(valid)),
        'median': float(np.median(valid)),
        'std': float(np.std(valid)),
    }


def process_batch(
    batch_id: str,
    image_files: Iterable[FileStorage],
    tenant_id: str | None = None,
) -> Dict[str, Any]:
    tenant_id = validate_tenant_id(tenant_id)

    batch_dir = safe_batch_path(batch_id, tenant_id)
    batch_dir.mkdir(parents=True, exist_ok=True)

    upload_dir = BASE_UPLOAD_PATH / tenant_id / batch_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    extractor = ThermalDataExtractor()
    analyzer = ThermalAnalyzer(sensitivity='high')

    results = {
        'batch_id': batch_id,
        'tenant_id': tenant_id,
        'timestamp': datetime.now().isoformat(),
        'images': [],
        'summary': {}
    }

    saved_images = []
    for file in image_files:
        if file and file.filename and _allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = upload_dir / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            file.save(str(filepath))
            saved_images.append(filepath)

    if not saved_images:
        raise ValueError("No valid JPEG files found in upload")

    all_stats = []
    for image_path in saved_images:
        try:
            temp_data = extractor.extract_thermal_data(image_path)
            if temp_data is None:
                raise ValueError("Could not extract thermal data from image")

            stats = _compute_stats(temp_data)
            save_thermal_data(batch_dir, image_path.name, temp_data)

            hot_spots = analyzer.detect_hot_spots(temp_data, image_path=str(image_path))

            html_report = analyzer.generate_report(image_path.name, hot_spots, stats)
            report_filename = image_path.stem + '_thermal_report.html'
            (batch_dir / report_filename).write_text(html_report)

            labeled_filename = image_path.stem + '_labeled.jpg'
            try:
                analyzer.label_hot_spots(str(image_path), hot_spots, str(batch_dir / labeled_filename))
            except Exception:
                pass

            csv_filename = image_path.stem + '_temperatures.csv'
            np.savetxt(str(batch_dir / csv_filename), temp_data, delimiter=',', fmt='%.2f')

            results['images'].append({
                'filename': image_path.name,
                'stats': stats,
                'shape': list(temp_data.shape),
                'hot_spots': [s.to_dict() for s in hot_spots],
                'hot_spot_count': len(hot_spots),
                'thermal_report': report_filename,
                'labeled_image': labeled_filename,
                'temperatures_csv': csv_filename,
            })
            all_stats.append(stats)

        except Exception as e:
            results['images'].append({
                'filename': image_path.name,
                'error': str(e)
            })

    if all_stats:
        results['summary'] = {
            'total_images': len(all_stats),
            'successful_images': len(all_stats),
            'avg_temperature': sum(s['mean'] for s in all_stats) / len(all_stats),
            'min_temperature': min(s['min'] for s in all_stats),
            'max_temperature': max(s['max'] for s in all_stats),
        }

    batchio.save_batch_results(batch_id, results, tenant_id=tenant_id)

    thermal_analysis = {
        'batch_id': batch_id,
        'tenant_id': tenant_id,
        'timestamp': datetime.now().isoformat(),
        'images': [
            {
                'filename': img['filename'],
                'hot_spots': img.get('hot_spots', []),
                'labeled_image': img.get('labeled_image', ''),
            }
            for img in results['images']
            if 'error' not in img
        ]
    }
    batchio.save_thermal_analysis(batch_id, thermal_analysis, tenant_id=tenant_id)

    return results


def get_all_batches(tenant_id: str | None = None) -> List[Dict[str, Any]]:
    tenant_id = validate_tenant_id(tenant_id)
    return batchio.list_batches(tenant_id)


def get_batch_summary(batch_id: str, tenant_id: str | None = None) -> Dict[str, Any]:
    tenant_id = validate_tenant_id(tenant_id)
    data = batchio.load_batch_results(batch_id, tenant_id)
    if not data:
        raise FileNotFoundError(f"Batch {batch_id} not found")
    return data


def _allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def reprocess_batch(batch_id: str, sensitivity: str = 'medium', tenant_id: str | None = None) -> dict:
    tenant_id = validate_tenant_id(tenant_id)
    batch_dir = safe_batch_path(batch_id, tenant_id)
    upload_dir = BASE_UPLOAD_PATH / tenant_id / batch_id

    if not upload_dir.exists():
        raise FileNotFoundError(f"Batch images not found for {batch_id}")

    saved_images = sorted(upload_dir.glob("*.jpg"))
    if not saved_images:
        raise FileNotFoundError(f"No images found in batch directory for {batch_id}")

    extractor = ThermalDataExtractor()
    analyzer = ThermalAnalyzer(sensitivity=sensitivity)

    results = {
        'batch_id': batch_id,
        'tenant_id': tenant_id,
        'timestamp': datetime.now().isoformat(),
        'images': [],
        'summary': {}
    }

    all_stats = []
    for image_path in saved_images:
        try:
            temp_data = extractor.extract_thermal_data(image_path)
            if temp_data is None:
                raise ValueError("Could not extract thermal data from image")

            stats = _compute_stats(temp_data)
            hot_spots = analyzer.detect_hot_spots(temp_data, image_path=str(image_path))

            html_report = analyzer.generate_report(image_path.name, hot_spots, stats)
            report_filename = image_path.stem + '_thermal_report.html'
            batch_dir.mkdir(parents=True, exist_ok=True)
            (batch_dir / report_filename).write_text(html_report)

            labeled_filename = image_path.stem + '_labeled.jpg'
            try:
                analyzer.label_hot_spots(str(image_path), hot_spots, str(batch_dir / labeled_filename))
            except Exception:
                pass

            csv_filename = image_path.stem + '_temperatures.csv'
            np.savetxt(str(batch_dir / csv_filename), temp_data, delimiter=',', fmt='%.2f')

            results['images'].append({
                'filename': image_path.name,
                'stats': stats,
                'shape': list(temp_data.shape),
                'hot_spots': [s.to_dict() for s in hot_spots],
                'hot_spot_count': len(hot_spots),
                'thermal_report': report_filename,
                'labeled_image': labeled_filename,
                'temperatures_csv': csv_filename,
            })
            all_stats.append(stats)

        except Exception as e:
            results['images'].append({
                'filename': image_path.name,
                'error': str(e)
            })

    if all_stats:
        results['summary'] = {
            'total_images': len(all_stats),
            'successful_images': len(all_stats),
            'avg_temperature': sum(s['mean'] for s in all_stats) / len(all_stats),
            'min_temperature': min(s['min'] for s in all_stats),
            'max_temperature': max(s['max'] for s in all_stats),
        }

    batchio.save_batch_results(batch_id, results, tenant_id=tenant_id)

    thermal_analysis = {
        'batch_id': batch_id,
        'tenant_id': tenant_id,
        'timestamp': datetime.now().isoformat(),
        'images': [
            {
                'filename': img['filename'],
                'hot_spots': img.get('hot_spots', []),
                'labeled_image': img.get('labeled_image', ''),
            }
            for img in results['images']
            if 'error' not in img
        ]
    }
    batchio.save_thermal_analysis(batch_id, thermal_analysis, tenant_id=tenant_id)

    return results
