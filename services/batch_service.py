from __future__ import annotations
"""Batch service: orchestrates upload, processing, and batch management."""

import hashlib
import settings
from datetime import datetime
from pathlib import Path
from typing import Iterable, Dict, Any, List

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from settings import (
    BASE_UPLOAD_PATH,
    BASE_REPORT_DIR,
    BATCH_SIZE_MAX,
    is_allowed_file,
    ALLOWED_EXTENSIONS,
    THERMAL_SENSITIVITY,
    MAX_HOTSPOTS_PER_IMAGE,
)
from security_utils import safe_batch_path, validate_tenant_id
import services.batch_io as batchio
from services.flir_processor_simple import SimpleFLIRProcessor
from services.thermal_analyzer import ThermalAnalyzer
from services.thermal_data_service import ThermalDataExtractor, save_thermal_data


def get_batch_id(files: Iterable[FileStorage]) -> str:
    """Generate unique batch ID from uploaded files."""
    file_list = sorted([f.filename or "" for f in files if f and f.filename])
    hash_str = hashlib.md5(''.join(file_list).encode()).hexdigest()[:8]
    return f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash_str}"


def process_batch(
    batch_id: str,
    image_files: Iterable[FileStorage],
    tenant_id: str | None = None,
    sensitivity: str | None = None,
    max_spots: int | None = None,
) -> Dict[str, Any]:
    """
    Process a batch of uploaded thermal images.
    
    Args:
        batch_id: Unique batch identifier
        image_files: List of FileStorage objects from upload
        tenant_id: Tenant ID (deprecated - pass None)
        sensitivity: Detection sensitivity (low/medium/high), uses THERMAL_SENSITIVITY if None
        max_spots: Max hotspots per image, uses MAX_HOTSPOTS_PER_IMAGE if None
        
    Returns:
        dict: Processing results with summary and per-image analysis
    """
    if tenant_id and not validate_tenant_id(tenant_id):
        raise ValueError(f"Invalid tenant_id: {tenant_id}")

    upload_dir = BASE_UPLOAD_PATH / batch_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    batch_dir = safe_batch_path(BASE_REPORT_DIR, batch_id, tenant_id)
    batch_dir.mkdir(parents=True, exist_ok=True)
    
    processor = SimpleFLIRProcessor()
    
    # Use provided sensitivity or default from settings
    sens = sensitivity or THERMAL_SENSITIVITY
    max_spots_val = max_spots if max_spots is not None else MAX_HOTSPOTS_PER_IMAGE
    
    analyzer = ThermalAnalyzer(sensitivity=sens)
    
    results = {
        'batch_id': batch_id,
        'tenant_id': tenant_id,
        'timestamp': datetime.now().isoformat(),
        'sensitivity': sens,
        'max_spots_per_image': max_spots_val,
        'images': [],
        'summary': {}
    }
    
    # Save uploaded images
    saved_images = []
    for file in image_files:
        if file and file.filename and _allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = upload_dir / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            file.save(str(filepath))
            saved_images.append(str(filepath))
    
    if not saved_images:
        raise ValueError("No valid JPEG files found in upload")
    
    # Process each image
    all_temps = []
    for image_path in saved_images:
        try:
            temp_data, stats = processor.process_single_image(image_path, display=False)

            thermal_extractor = ThermalDataExtractor()
            thermal_data = thermal_extractor.extract_thermal_data(Path(image_path))
            
            if thermal_data is not None:
                save_thermal_data(batch_dir, Path(image_path).name, thermal_data)
            
            # Detect hot spots with max_spots cap
            hot_spots = analyzer.detect_hot_spots(
                temp_data, 
                image_path=image_path,
                max_spots=max_spots_val
            )
            
            html_report = analyzer.generate_report(
                Path(image_path).name, hot_spots, stats
            )
            
            report_filename = Path(image_path).stem + '_thermal_report.html'
            report_path = batch_dir / report_filename
            with open(report_path, 'w') as f:
                f.write(html_report)
            
            labeled_filename = Path(image_path).stem + '_labeled.jpg'
            labeled_path = batch_dir / labeled_filename
            try:
                analyzer.label_hot_spots(image_path, hot_spots, str(labeled_path))
            except Exception:
                pass
            
            csv_filename = Path(image_path).stem + '_temperatures.csv'
            csv_path = batch_dir / csv_filename
            processor.save_temperature_array(temp_data, str(csv_path))
            
            image_result = {
                'filename': Path(image_path).name,
                'stats': {
                    'min': float(stats['min']),
                    'max': float(stats['max']),
                    'mean': float(stats['mean']),
                    'median': float(stats['median']),
                    'std': float(stats['std'])
                },
                'shape': temp_data.shape,
                'hot_spots': [spot.to_dict() for spot in hot_spots],
                'hot_spot_count': len(hot_spots),
                'thermal_report': report_filename,
                'labeled_image': labeled_filename,
                'temperatures_csv': csv_filename
            }
            results['images'].append(image_result)
            all_temps.append(stats)
            
        except Exception as e:
            results['images'].append({
                'filename': Path(image_path).name,
                'error': str(e)
            })
    
    if all_temps:
        results['summary'] = {
            'total_images': len(saved_images),
            'successful': len(all_temps),
            'failed': len(saved_images) - len(all_temps)
        }

    batchio.save_thermal_analysis(batch_id, results, tenant_id)
    return results


def get_all_batches(tenant_id: str | None = None) -> List[Dict[str, Any]]:
    """Get list of all processed batches."""
    return batchio.list_batches(None)


def get_batch_summary(batch_id: str, tenant_id: str | None = None) -> Dict[str, Any]:
    """Get summary for a single batch."""
    data = batchio.load_batch_results(batch_id, tenant_id)
    if not data:
        raise FileNotFoundError(f"Batch {batch_id} not found")
    return data


def _allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
