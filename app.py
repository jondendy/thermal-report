#!/usr/bin/env python3
"""
Thermal Report Web Application
Thin Flask routing layer.

All business logic is delegated to services modules:
  - services.batch_service: Upload, processing, batch management
  - services.heat_loss_service: Labeling, report generation
  - services.batch_io: All JSON I/O

Configuration driven by settings.py and environment variables.
"""
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file

import settings
from lib.logging_config import setup_logging
from services.batch_service import process_batch, get_batch_id, get_all_batches, get_batch_summary
from services.heat_loss_service import (
    get_thermal_analysis, get_existing_labels, save_labels, generate_report, get_report
)

# ============================================================================
# Setup
# ============================================================================

# Configure logging
logger = setup_logging(
    level=settings.LOG_LEVEL,
    log_file=settings.LOG_FILE
)

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = settings.MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = settings.BASE_UPLOAD_DIR
app.config['REPORTS_FOLDER'] = settings.BASE_REPORT_DIR

# ============================================================================
# Routes – Batch Upload & Index
# ============================================================================

@app.route('/')
def index():
    """Main page: batch upload and report index."""
    batches = get_all_batches()
    return render_template('index.html', batches=batches)


@app.route('/upload', methods=['POST'])
def upload_files():
    """
    Handle file uploads and batch processing.
    
    Expected: multipart form data with 'files[]' containing 6-8 JPEG images
    Returns: JSON with batch_id and processing results
    """
    try:
        # Validate request
        if 'files[]' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
        
        files = request.files.getlist('files[]')
        
        # Filter valid files
        valid_files = [f for f in files if f and f.filename and _allowed_file(f.filename)]
        
        if not valid_files:
            return jsonify({'error': 'No valid FLIR images provided'}), 400
        
        if len(valid_files) > settings.BATCH_SIZE_MAX:
            return jsonify({'error': f'Maximum {settings.BATCH_SIZE_MAX} images per batch'}), 400
        
        # Generate batch ID and process
        batch_id = get_batch_id(valid_files)
        results = process_batch(batch_id, valid_files)
        
        return jsonify({
            'success': True,
            'batch_id': batch_id,
            'results': results
        }), 201
        
    except Exception as e:
        logger.exception(f"Upload error: {str(e)}")
        return jsonify({'error': 'An error occurred during upload. Please try again.'}), 500


@app.route('/info')
def info():
    """Information and instructions page."""
    return render_template('info.html')


# ============================================================================
# Routes – Heat Loss Workflow
# ============================================================================

@app.route('/edit_spots/<batch_id>')
def edit_spots(batch_id):
    try:
        tenant_id = request.headers.get('X-Tenant-ID', settings.DEFAULT_TENANT)
        
        # Load thermal analysis data
        analysis_data = heat_loss_service.load_batch_analysis(tenant_id, batch_id)
        
        # Load existing labels if they exist
        existing_labels = heat_loss_service.load_existing_labels(tenant_id, batch_id)
        
        # Get spot types
        spot_types = ["Window", "Door", "Wall", "Eaves", "Vent", "Roof", "Chimney", "Porch"]
        
        # Initialize empty saved_links and saved_documents if they don't exist
        saved_links = existing_labels.get('links', []) if existing_labels else []
        saved_documents = existing_labels.get('documents', []) if existing_labels else []
        
        return render_template(
            'edit_spots.html',
            batch_id=batch_id,
            analysis_data=analysis_data,
            existing_labels=existing_labels,
            spot_types=spot_types,
            saved_links=saved_links,
            saved_documents=saved_documents
        )
        
    except Exception as e:
        logger.error(f"Error loading edit_spots for batch {batch_id}: {e}", exc_info=True)
        return jsonify({"error": "An error occurred loading the labeling interface"}), 500

    
    except FileNotFoundError:
        return "Batch not found", 404
    except Exception as e:
        logger.exception(f"Error loading edit_spots for batch {batch_id}: {str(e)}")
        return "An error occurred loading the labeling interface", 500


@app.route('/save_labels/<batch_id>', methods=['POST'])
def save_labels_route(batch_id):
    """
    Save hot spot labels submitted by operator.
    
    Receives JSON with labeled_spots array:
    [
        {
            "spot_id": "img1_spot1",
            "spot_number": 1,
            "type": "Window",
            "image_name": "FLIR0001.jpg",
            "location": [x, y],
            "temperature": 15.2
        },
        ...
    ]
    """
    try:
        label_data = request.get_json()
        saved_labels = save_labels(batch_id, label_data)
        
        return jsonify({
            'success': True,
            'message': 'Labels saved successfully',
            'labels': saved_labels
        })
    
    except FileNotFoundError:
        return jsonify({'error': 'Batch not found'}), 404
    except Exception as e:
        logger.exception(f"Error saving labels for batch {batch_id}: {str(e)}")
        return jsonify({'error': 'Failed to save labels'}), 500


@app.route('/generate_heat_loss_report/<batch_id>', methods=['POST'])
def generate_heat_loss_report_route(batch_id):
    """
    Generate professional heat loss report from labeled hot spots.
    
    Step 2: Creates final HTML report with energy-saving recommendations
    
    Optional form parameters:
    - property_address: Property address for report
    - inspector_name: Inspector name for report
    """
    try:
        property_address = request.form.get('property_address', '')
        inspector_name = request.form.get('inspector_name', '')
        
        report_data = generate_report(
            batch_id,
            property_address=property_address,
            inspector_name=inspector_name
        )
        
        return jsonify({
            'success': True,
            'message': 'Heat loss report generated successfully',
            'report_url': url_for('view_heat_loss_report', batch_id=batch_id)
        })
    
    except FileNotFoundError as e:
        logger.error(f"Missing data for batch {batch_id}: {str(e)}")
        return jsonify({'error': 'Required data not found. Please ensure hotspots are labeled.'}), 404
    except ValueError as e:
        logger.error(f"Validation error for batch {batch_id}: {str(e)}")
        return jsonify({'error': 'Invalid input data.'}), 400
    except Exception as e:
        logger.exception(f"Error generating heat loss report for batch {batch_id}: {str(e)}")
        return jsonify({'error': 'Report generation failed'}), 500


@app.route('/view_heat_loss_report/<batch_id>')
def view_heat_loss_report(batch_id):
    """
    Display the final professional heat loss report.
    
    This is the homeowner-facing report with energy-saving recommendations
    and cross-image analysis of heat loss points.
    """
    try:
        report_data = get_report(batch_id)
        return render_template('heat_loss_report.html', report_data=report_data)
    
    except FileNotFoundError:
        return "Report not found. Please generate the report first.", 404
    except Exception as e:
        logger.exception(f"Error loading heat loss report for batch {batch_id}: {str(e)}")
        return "An error occurred loading the report", 500


# ============================================================================
# Routes – API Endpoints (for integration)
# ============================================================================

@app.route('/api/batches')
def api_batches():
    """Get all batches as JSON (for programmatic access)."""
    try:
        batches = get_all_batches()
        return jsonify({'batches': batches})
    except Exception as e:
        logger.exception(f"Error fetching batches: {str(e)}")
        return jsonify({'error': 'Failed to fetch batches'}), 500


@app.route('/api/batch/<batch_id>')
def api_batch(batch_id):
    """Get batch summary as JSON."""
    try:
        summary = get_batch_summary(batch_id)
        return jsonify(summary)
    except FileNotFoundError:
        return jsonify({'error': 'Batch not found'}), 404
    except Exception as e:
        logger.exception(f"Error fetching batch {batch_id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch batch'}), 500


@app.route('/api/batch/<batch_id>/analysis')
def api_batch_analysis(batch_id):
    """Get thermal analysis data as JSON."""
    try:
        analysis = get_thermal_analysis(batch_id)
        return jsonify(analysis)
    except FileNotFoundError:
        return jsonify({'error': 'Batch not found'}), 404
    except Exception as e:
        logger.exception(f"Error fetching analysis for batch {batch_id}: {str(e)}")
        return jsonify({'error': 'Failed to fetch analysis'}), 500


# ============================================================================
# Routes – Admin / Maintenance
# ============================================================================

@app.route('/delete/<batch_id>', methods=['POST'])
def delete_batch(batch_id):
    """Delete a batch and its associated files."""
    try:
        from lib.security_utils import safe_batch_path
        import shutil
        
        batch_dir = safe_batch_path(batch_id)
        if batch_dir.exists():
            shutil.rmtree(batch_dir)
        
        return jsonify({'success': True})
    
    except ValueError as e:
        logger.error(f"Invalid batch_id: {str(e)}")
        return jsonify({'error': 'Invalid batch ID'}), 400
    except Exception as e:
        logger.exception(f"Error deleting batch {batch_id}: {str(e)}")
        return jsonify({'error': 'Failed to delete batch'}), 500


# ============================================================================
# Helpers
# ============================================================================

def _allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in settings.ALLOWED_EXTENSIONS


# ============================================================================
# Error Handlers
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return render_template('info.html'), 404


@app.errorhandler(500)
def server_error(error):
    """Handle 500 errors."""
    logger.exception(f"Server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    Path(settings.BASE_UPLOAD_DIR).mkdir(exist_ok=True)
    Path(settings.BASE_REPORT_DIR).mkdir(exist_ok=True)
    
    debug_mode = settings.FLASK_DEBUG
    logger.info(f"Starting thermal-report app (debug={debug_mode})")
    
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
