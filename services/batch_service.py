from __future__ import annotations
"""Batch service: orchestrates upload, processing, and batch management.
Separates batch logic from Flask routing.
"""

import hashlib
import settings
from datetime import datetime
from pathlib import Path
from typing import Iterable, Dict, Any, Tuple, List

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from settings import (
    BASE_UPLOAD_PATH,
    BATCH_SIZE_MAX,
    is_allowed_file,
    ALLOWED_EXTENSIONS,
)
from security_utils import safe_batch_path
from security_utils import validate_tenant_id
import services.batch_io as batchio
from services.flir_processor_simple import SimpleFLIRProcessor
from services.thermal_analyzer import ThermalAnalyzer
from services.thermal_data_service import ThermalDataExtractor, save_thermal_data


def get_batch_id(files: Iterable[FileStorage]) -> str:
    """
    Generate unique batch ID from uploaded files.
    Format: batch_YYYYMMDD_HHMMSS_hash
    
    Args:
        files: List of FileStorage objects
        
    Returns:
        str: Unique batch ID
    """
    file_list = sorted([f.filename or "" for f in files if f and f.filename])
    hash_str = hashlib.md5(''.join(file_list).encode()).hexdigest()[:8]
    return f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash_str}"


from settings import BASE_UPLOAD_PATH, BASE_REPORT_DIR
from security_utils import validate_tenant_id, safe_batch_path

def process_batch(
    batch_id: str,
    image_files: Iterable[FileStorage],
    tenant_id: str | None = None,
) -> Dict[str, Any]:
    """
    Process a batch of uploaded thermal images.
    
    - Extract temperature data using SimpleFLIRProcessor
    - Detect hot spots using ThermalAnalyzer with HIGH sensitivity
    - Generate labeled images and reports
    - Save results to batch directory
    
    Args:
        batch_id (str): Unique batch identifier
        image_files: List of FileStorage objects from upload
        tenant_id (str): Tenant ID (uses DEFAULT_TENANT if not provided)
        
    Returns:
        dict: Processing results with summary and per-image analysis
        
    Raises:
        ValueError: If batch_id or tenant_id invalid
    """
    # 1. Normalise tenant_id
    tenant_id = tenant_id or "NK"  # <- default when None/empty

    # 2. Validate tenant_id
    if not validate_tenant_id(tenant_id):
        raise ValueError(f"Invalid tenant_id: {tenant_id}")

    # 3. Build upload path (per‑tenant folder)
    upload_dir = BASE_UPLOAD_PATH / tenant_id / batch_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 4. Build report batch path
    batch_dir = safe_batch_path(BASE_REPORT_DIR, batch_id, tenant_id)
    batch_dir.mkdir(parents=True, exist_ok=True)
    
    processor = SimpleFLIRProcessor()
    # Use HIGH sensitivity to detect more hotspots for operator review
    analyzer = ThermalAnalyzer(sensitivity='high')
    
    results = {
        'batch_id': batch_id,
        'tenant_id': tenant_id,
        'timestamp': datetime.now().isoformat(),
        'images': [],
        'summary': {}
    }
    
    # Save uploaded images and process them
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

            # Extract thermal temperature data for coordinate lookups
            thermal_extractor = ThermalDataExtractor()
            thermal_data = thermal_extractor.extract_thermal_data(Path(image_path))
            
            # Save thermal data for later retrieval
            if thermal_data is not None:
                save_thermal_data(batch_dir, Path(image_path).name, thermal_data)
            
            # Detect hot spots - pass image_path so analyzer can get visual dimensions
            hot_spots = analyzer.detect_hot_spots(temp_data, image_path=image_path)
            
            # Generate HTML report for this image
            html_report = analyzer.generate_report(
                Path(image_path).name,
                hot_spots,
                stats
            )
            
            # Save HTML report
            report_filename = Path(image_path).stem + '_thermal_report.html'
            report_path = batch_dir / report_filename
            with open(report_path, 'w') as f:
                f.write(html_report)
            
            # Create labeled image with annotations
            labeled_filename = Path(image_path).stem + '_labeled.jpg'
            labeled_path = batch_dir / labeled_filename
            try:
                analyzer.label_hot_spots(image_path, hot_spots, str(labeled_path))
            except Exception as e:
                # Log but don't fail on labeled image generation
                pass
            
            # Save temperature CSV
            csv_filename = Path(image_path).stem + '_temperatures.csv'
            csv_path = batch_dir / csv_filename
            processor.save_temperature_array(temp_data, str(csv_path))
            
            # Record image result
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
    
    # Calculate batch summary
    if all_temps:
        results['summary'] = {
            'total_images': len(saved_images),
            'successful': len(all_temps),
            'failed': len(saved_images) - len(all_temps)
        }
    
    return results


def get_all_batches(tenant_id: str | None = None) -> List[Dict[str, Any]]:
    """
    Get list of all processed batches for a tenant.
    
    Args:
        tenant_id (str): Tenant ID (uses DEFAULT_TENANT if not provided)
        
    Returns:
        list: List of batch summaries, sorted by date (newest first)
    """
    tenant_id = validate_tenant_id(tenant_id)
    return batchio.list_batches(tenant_id)


def get_batch_summary(batch_id: str, tenant_id: str | None = None) -> Dict[str, Any]:
    """
    Get summary for a single batch.
    
    Args:
        batch_id (str): Batch ID
        tenant_id (str): Tenant ID
        
    Returns:
        dict: Batch summary from results.json
    """
    tenant_id = validate_tenant_id(tenant_id)
    data = batchio.load_batch_results(batch_id, tenant_id)
    if not data:
        raise FileNotFoundError(f"Batch {batch_id} not found")
    return data


def _allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
