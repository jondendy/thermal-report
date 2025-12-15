"""
Batch service: orchestrates upload, processing, and batch management.
Separates batch logic from Flask routing.
"""
import hashlib
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename

import settings
from lib.security_utils import safe_batch_path, safe_upload_path, validate_batch_id
from services.batch_io import (
    ensure_batch_dir, save_batch_results, save_thermal_analysis,
    load_batch_results
)
from flir_processor_simple import SimpleFLIRProcessor
from thermal_analyzer import ThermalAnalyzer


def get_batch_id(files):
    """
    Generate unique batch ID from uploaded files.
    Format: batch_YYYYMMDD_HHMMSS_hash
    
    Args:
        files: List of FileStorage objects
        
    Returns:
        str: Unique batch ID
    """
    file_list = sorted([f.filename for f in files])
    hash_str = hashlib.md5(''.join(file_list).encode()).hexdigest()[:8]
    return f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash_str}"


def process_batch(batch_id, image_files, tenant_id=None):
    """
    Process a batch of uploaded thermal images.
    
    - Extract temperature data using SimpleFLIRProcessor
    - Detect hot spots using ThermalAnalyzer
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
    if tenant_id is None:
        tenant_id = settings.DEFAULT_TENANT
    
    # Validate and create directories
    batch_dir = ensure_batch_dir(batch_id, tenant_id=tenant_id)
    upload_dir = safe_upload_path(tenant_id=tenant_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    processor = SimpleFLIRProcessor()
    analyzer = ThermalAnalyzer(sensitivity=settings.THERMAL_SENSITIVITY)
    
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
    
    # Process each image
    all_temps = []
    for image_path in saved_images:
        try:
            temp_data, stats = processor.process_single_image(image_path, display=False)
            
            # Detect hot spots
            hot_spots = analyzer.detect_hot_spots(temp_data)
            
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
        temps = [t['mean'] for t in all_temps]
        results['summary'] = {
            'total_images': len(all_temps),
            'successful_images': len(all_temps),
            'avg_temperature': sum(temps) / len(temps),
            'min_temperature': min([t['min'] for t in all_temps]),
            'max_temperature': max([t['max'] for t in all_temps])
        }
    
    # Save results
    save_batch_results(batch_id, results, tenant_id=tenant_id)
    
    # Save thermal analysis for UI
    thermal_analysis = {
        'batch_id': batch_id,
        'tenant_id': tenant_id,
        'timestamp': datetime.now().isoformat(),
        'images': results['images']
    }
    save_thermal_analysis(batch_id, thermal_analysis, tenant_id=tenant_id)
    
    return results


def get_all_batches(tenant_id=None):
    """
    Get list of all processed batches for a tenant.
    
    Args:
        tenant_id (str): Tenant ID (uses DEFAULT_TENANT if not provided)
        
    Returns:
        list: List of batch summaries, sorted by date (newest first)
    """
    if tenant_id is None:
        tenant_id = settings.DEFAULT_TENANT
    
    batches = []
    base_reports = Path(settings.BASE_REPORT_DIR)
    batches_dir = base_reports / 'batches' / tenant_id
    
    if batches_dir.exists():
        for batch_dir in sorted(batches_dir.iterdir(), reverse=True):
            if not batch_dir.is_dir():
                continue
            
            try:
                results = load_batch_results(batch_dir.name, tenant_id=tenant_id)
                batches.append({
                    'batch_id': batch_dir.name,
                    'timestamp': results.get('timestamp'),
                    'image_count': len(results.get('images', [])),
                    'summary': results.get('summary', {})
                })
            except Exception:
                # Skip batches with missing/invalid results.json
                continue
    
    return batches


def get_batch_summary(batch_id, tenant_id=None):
    """
    Get summary for a single batch.
    
    Args:
        batch_id (str): Batch ID
        tenant_id (str): Tenant ID
        
    Returns:
        dict: Batch summary from results.json
    """
    if tenant_id is None:
        tenant_id = settings.DEFAULT_TENANT
    
    return load_batch_results(batch_id, tenant_id=tenant_id)


def _allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in settings.ALLOWED_EXTENSIONS
