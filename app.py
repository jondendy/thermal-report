#!/usr/bin/env python3
"""
Thermal Report Web Application
A Flask-based web tool for uploading FLIR thermal images in batches,
processing them, and viewing reports through a web interface.
"""
import os
import json
import shutil
import hashlib
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from flir_processor_simple import SimpleFLIRProcessor
from thermal_analyzer import ThermalAnalyzer

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200MB max upload
app.config['UPLOAD_FOLDER'] = 'Images'
app.config['REPORTS_FOLDER'] = 'reports'

# Allowed file extensions
ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}
BATCH_SIZE = 8  # Process 6-8 images per batch

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_directories():
    """Ensure required directories exist"""
    Path(app.config['UPLOAD_FOLDER']).mkdir(exist_ok=True)
    Path(app.config['REPORTS_FOLDER']).mkdir(exist_ok=True)
    Path(app.config['REPORTS_FOLDER']).joinpath('batches').mkdir(exist_ok=True)

def get_batch_id(files):
    """Generate unique batch ID from file names"""
    file_list = sorted([f.filename for f in files])
    hash_str = hashlib.md5(''.join(file_list).encode()).hexdigest()[:8]
    return f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hash_str}"

def process_batch(batch_id, image_files):
    """Process a batch of images and generate reports"""
    try:
        processor = SimpleFLIRProcessor()
        analyzer = ThermalAnalyzer(sensitivity='medium')  # Initialize thermal analyzer
        batch_dir = Path(app.config['REPORTS_FOLDER']) / 'batches' / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)
        image_batch_dir = Path(app.config['UPLOAD_FOLDER']) / 'batches' / batch_id
        image_batch_dir.mkdir(parents=True, exist_ok=True)
        
        results = {
            'batch_id': batch_id,
            'timestamp': datetime.now().isoformat(),
            'images': [],
            'summary': {}
        }
        
        # Save uploaded images and process them
        saved_images = []
        for file in image_files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = image_batch_dir / filename
                file.save(str(filepath))
                saved_images.append(str(filepath))
        
        # Process each image
        all_temps = []
        for image_path in saved_images:
            try:
                temp_data, stats = processor.process_single_image(image_path, display=False)
                
                # Detect hot spots using dual method (relative + absolute)
                hot_spots = analyzer.detect_hot_spots_dual_method(temp_data)
                
                # Generate HTML report with thermal analysis
                html_report = analyzer.generate_report(
                    Path(image_path).name,
                    hot_spots,
                    stats
                )
                
                # Save HTML report to batch directory
                report_filename = Path(image_path).stem + '_thermal_report.html'
                report_path = batch_dir / report_filename
                with open(report_path, 'w') as f:
                    f.write(html_report)
                
                # Create labeled image with hot spot annotations
                labeled_filename = Path(image_path).stem + '_labeled.jpg'
                labeled_path = batch_dir / labeled_filename
                try:
                    analyzer.label_hot_spots(image_path, hot_spots, str(labeled_path))
                except Exception as label_error:
                    print(f"Warning: Could not create labeled image: {label_error}")
                
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
                    'labeled_image': labeled_filename
                }
                results['images'].append(image_result)
                all_temps.append(stats)
                
                # Save temperature CSV
                csv_filename = Path(image_path).stem + '_temperatures.csv'
                csv_path = batch_dir / csv_filename
                processor.save_temperature_array(temp_data, str(csv_path))
                
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
                'avg_temperature': sum(temps) / len(temps),
                'min_temperature': min([t['min'] for t in all_temps]),
                'max_temperature': max([t['max'] for t in all_temps])
            }
        
        # Save results JSON
        results_file = batch_dir / 'results.json'
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

        # Save thermal analysis JSON for heat loss labeling interface
        thermal_analysis = {
            'batch_id': batch_id,
            'timestamp': datetime.now().isoformat(),
            'images': results['images']
        }
        thermal_analysis_file = batch_dir / 'thermal_analysis.json'
        with open(thermal_analysis_file, 'w') as f:
            json.dump(thermal_analysis, f, indent=2)
        
        return results
        
    except Exception as e:
        return {'error': str(e)}

def get_all_batches():
    """Get list of all processed batches"""
    batches = []
    batches_dir = Path(app.config['REPORTS_FOLDER']) / 'batches'
    
    if batches_dir.exists():
        for batch_dir in sorted(batches_dir.iterdir(), reverse=True):
            results_file = batch_dir / 'results.json'
            if results_file.exists():
                with open(results_file, 'r') as f:
                    data = json.load(f)
                    batches.append({
                        'batch_id': batch_dir.name,
                        'timestamp': data.get('timestamp'),
                        'image_count': len(data.get('images', [])),
                        'summary': data.get('summary', {})
                    })
    
    return batches

@app.route('/')
def index():
    """Main page - batch upload and report index"""
    ensure_directories()
    batches = get_all_batches()
    return render_template('index.html', batches=batches)

@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file uploads and batch processing"""
    ensure_directories()
    
    # Check if files were provided
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files[]')
    
    # Filter valid files
    valid_files = [f for f in files if f and allowed_file(f.filename)]
    
    if not valid_files:
        return jsonify({'error': 'No valid FLIR images provided'}), 400
    
    if len(valid_files) > BATCH_SIZE:
        return jsonify({'error': f'Maximum {BATCH_SIZE} images per batch'}), 400
    
    try:
        batch_id = get_batch_id(valid_files)
        results = process_batch(batch_id, valid_files)
        
        if 'error' in results:
            return jsonify(results), 500
        
        return jsonify({
            'success': True,
            'batch_id': batch_id,
            'results': results
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/report/<batch_id>')
def view_report(batch_id):
    """View detailed report for a batch"""
    ensure_directories()
    
    results_file = Path(app.config['REPORTS_FOLDER']) / 'batches' / batch_id / 'results.json'
    
    if not results_file.exists():
        return "Batch not found", 404
    
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    return render_template('report.html', batch_id=batch_id, report=data)

@app.route('/api/batches')
def api_batches():
    """API endpoint to get all batches as JSON"""
    ensure_directories()
    batches = get_all_batches()
    return jsonify({'batches': batches})

@app.route('/api/report/<batch_id>')
def api_report(batch_id):
    """API endpoint to get batch report as JSON"""
    ensure_directories()
    
    results_file = Path(app.config['REPORTS_FOLDER']) / 'batches' / batch_id / 'results.json'
    
    if not results_file.exists():
        return jsonify({'error': 'Batch not found'}), 404
    
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    return jsonify(data)

@app.route('/download/<batch_id>/<filename>')
def download_file(batch_id, filename):
    """Download temperature CSV from batch"""
    file_path = Path(app.config['REPORTS_FOLDER']) / 'batches' / batch_id / secure_filename(filename)
    
    if not file_path.exists():
        return "File not found", 404
    
    return send_file(str(file_path), as_attachment=True)

@app.route('/delete/<batch_id>', methods=['POST'])
def delete_batch(batch_id):
    """Delete a batch and its associated files"""
    try:
        batch_dir = Path(app.config['REPORTS_FOLDER']) / 'batches' / batch_id
        if batch_dir.exists():
            shutil.rmtree(batch_dir)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/info')
def info():
    """Information and instructions page"""
    return render_template('info.html')

@app.route('/help')
def help_page():
    """Redirect /help to /info"""
    return redirect(url_for('info'))


# === HEAT LOSS REPORTING ROUTES ===

@app.route('/label_hotspots/<batch_id>')
def label_hotspots(batch_id):
    """
    Display hot spot labeling interface for operator to categorize and number hot spots.
    Step 1 of heat loss reporting workflow.
    """
    try:
        batch_path = Path(app.config['REPORTS_FOLDER']) / 'batches' / batch_id        if not batch_path.exists():
            return "Batch not found", 404
        
        # Load thermal analysis results (from thermal_analyzer.py)
        # This should have been saved during batch processing
        analysis_file = batch_path / 'thermal_analysis.json'
        if not analysis_file.exists():
            return "Thermal analysis not found. Please process batch first.", 404
        
        with open(analysis_file, 'r') as f:
            analysis_data = json.load(f)
        
        # Check if labels already exist
        labels_file = batch_path / 'hotspot_labels.json'
        existing_labels = {}
        if labels_file.exists():
            with open(labels_file, 'r') as f:
                existing_labels = json.load(f)
        
        return render_template('label_hotspots.html',
                             batch_id=batch_id,
                             analysis_data=analysis_data,
                             existing_labels=existing_labels,
                             spot_types=['Window', 'Door', 'Wall', 'Eaves', 'Vent', 'Roof', 'Chimney', 'Porch'])
    
    except Exception as e:
        return f"Error loading labeling interface: {str(e)}", 500


@app.route('/save_labels/<batch_id>', methods=['POST'])
def save_labels(batch_id):
    """
    Save hot spot labels submitted by operator.
    Receives JSON data with spot labels and numbers.
    """
    try:
        batch_path = Path(app.config['REPORTS_FOLDER']) / 'batches' / batch_id        if not batch_path.exists():
            return jsonify({'error': 'Batch not found'}), 404
        
        # Get label data from request
        label_data = request.get_json()
        
        # Structure the data
        labels_structure = {
            'batch_id': batch_id,
            'labeled_spots': label_data.get('labeled_spots', []),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Generate cross-references (spots with same number)
        cross_refs = {}
        for spot in labels_structure['labeled_spots']:
            spot_num = spot.get('spot_number')
            if spot_num:
                if spot_num not in cross_refs:
                    cross_refs[spot_num] = []
                cross_refs[spot_num].append(spot.get('spot_id'))
        
        labels_structure['cross_references'] = cross_refs
        
        # Save to file
        labels_file = batch_path / 'hotspot_labels.json'
        with open(labels_file, 'w') as f:
            json.dump(labels_structure, f, indent=2)
        
        return jsonify({'success': True, 'message': 'Labels saved successfully'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/generate_heat_loss_report/<batch_id>', methods=['POST'])
def generate_heat_loss_report(batch_id):
    """
    Generate professional heat loss report from labeled hot spots.
    Step 2 of heat loss reporting workflow.
    """
    try:
        from heat_loss_reporter import HeatLossReporter
        
        # Get optional parameters from form
        property_address = request.form.get('property_address', '')
        inspector_name = request.form.get('inspector_name', '')
        
        # Initialize reporter
        reporter = HeatLossReporter()
        
        # Generate report
        report_data_file = reporter.generate_html_report(
            batch_id=batch_id,
            property_address=property_address,
            inspector_name=inspector_name,
            reports_dir=app.config['REPORTS_FOLDER']
        )
        
        return jsonify({
            'success': True,
            'message': 'Heat loss report generated successfully',
            'report_url': f'/view_heat_loss_report/{batch_id}'
        })
    
    except FileNotFoundError as e:
        return jsonify({'error': f'Required data not found: {str(e)}'}), 404
    except Exception as e:
        return jsonify({'error': f'Report generation failed: {str(e)}'}), 500


@app.route('/view_heat_loss_report/<batch_id>')
def view_heat_loss_report(batch_id):
    """
    Display the generated heat loss report.
    """
    try:
        batch_path = Path(app.config['REPORTS_FOLDER']) / 'batches' / batch_id        report_data_file = batch_path / 'heat_loss_report_data.json'
        
        if not report_data_file.exists():
            return "Report not found. Please generate report first.", 404
        
        with open(report_data_file, 'r') as f:
            report_data = json.load(f)
        
        return render_template('heat_loss_report.html', report_data=report_data)
    
    except Exception as e:
        return f"Error loading report: {str(e)}", 500


if __name__ == '__main__':
    ensure_directories()
    app.run(debug=True, host='0.0.0.0', port=5000)
