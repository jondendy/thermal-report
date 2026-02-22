#!/usr/bin/env python3
"""
from __future__ import annotations
Flask entrypoint for the Thermal Report web tool.
Canonical routes that match edit_spots.html, index.html, and JS expectations.
"""
from dotenv import load_dotenv
load_dotenv()  # call this before `import settings`
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


import json
import shutil
import logging
from typing import Any
from flask import Flask, render_template, request, jsonify, abort, url_for, send_file
from pathlib import Path

import settings
from settings import (
    APP_NAME,
    APP_VERSION,
    MAX_CONTENT_LENGTH,
    BATCH_SIZE_MAX,
)

import services.batch_service as batchservice
import services.heat_loss_service as heatlossservice
import services.batch_io as batchio
from security_utils import validate_tenant_id, safe_batch_path
from logging_config import setup_logging
from ingest_drive import register_ingest_routes

# Initialize logger
logger = setup_logging(level='INFO')

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["SECRET_KEY"] = "change-me-in-production"

# Spot types for thermal annotations
SPOT_TYPES = ["Wall", "Window", "Door", "Roof", "Floor", "Vent", "Other"]

# Register ingest routes blueprint
register_ingest_routes(app)


def _get_tenant_id() -> str:
    """Get tenant ID from request headers or query params."""
    tenant_id = request.args.get("tenant") or request.headers.get('X-Tenant-ID') or None
    return validate_tenant_id(tenant_id)


@app.route("/", methods=["GET"])
def index() -> str:
    """Display batch list and upload interface."""
    tenant_id = None  # No longer using tenant subdirectories
    batches = batchservice.get_all_batches(None)  # Pass None instead of tenant_id
    
    return render_template(
        "index.html", 
        batches=batches,
        app_name=APP_NAME,
        app_version=APP_VERSION
    )


@app.route("/upload", methods=["POST"])
def upload() -> Any:
    """Process uploaded thermal images and create batch."""
    tenant_id = _get_tenant_id()
    files = request.files.getlist("files")

    if not files or len(files) == 0:
        return jsonify({"error": "No files uploaded"}), 400

    try:
        # Generate batch_id from files
        batch_id = batchservice.get_batch_id(files)
        # Process batch with correct argument order: batch_id, files, tenant_id
        results = batchservice.process_batch(batch_id, files, tenant_id)
        summary = results.get('summary', {})
    except ValueError as e:
        logger.warning(f"Validation error during upload: {str(e)}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception(f"Error processing batch: {str(e)}")
        return jsonify({"error": f"Processing error: {e}"}), 500

    return jsonify({"batchid": batch_id, "results": {"summary": summary}})

@app.route("/list_folders")
def list_folders():
    """List all folders in the STORAGE_ADDRESS folder."""
    try:
        import services.drive_client as drive_client
        from settings import STORAGE_ADDRESS
        
        if not STORAGE_ADDRESS:
            return '<h1>Error</h1><p>STORAGE_ADDRESS not configured in .env file</p>', 500
        
        # List all folders in the parent folder
        folders = drive_client.list_files_in_folder(STORAGE_ADDRESS)
        
        # Filter to only show folders (mimeType = 'application/vnd.google-apps.folder')
        folder_list = [f for f in folders if f.get('mimeType') == 'application/vnd.google-apps.folder']
        
        return render_template('list_folders.html', folders=folder_list, parent_id=STORAGE_ADDRESS)
    except Exception as e:
        print(f"ERROR in list_folders: {e}")
        print(f"Type: {type(e)}")
        import traceback
        traceback.print_exc()
        logger.exception(f"Error listing folders: {str(e)}")
        return f'<h1>Error</h1><p>Failed to list folders: {str(e)}</p>', 500


@app.route("/select_images/<folder_id>", methods=["GET"])
def select_images(folder_id: str):
    """Display Google Drive folder contents for image selection."""
    try:
        import services.drive_client as drive_client
        
        # Get folder metadata
        folder_metadata = drive_client.get_folder_metadata(folder_id)
        folder_name = folder_metadata.get('name', 'Unknown Folder')
        
        # List files with thumbnailLink field
        service = drive_client.get_drive_service()
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(
            q=query,
            fields="files(id, name, thumbnailLink, mimeType)",
            orderBy="name"
        ).execute()
        
        files = results.get('files', [])
        
        # Filter to image files only
        image_mimes = ['image/jpeg', 'image/png', 'image/tiff']
        image_files = [f for f in files if f.get('mimeType') in image_mimes]
        
        if not image_files:
            return f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>No Images Found</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; text-align: center; }}
                    h1 {{ color: #d32f2f; }}
                    a {{ color: #1976d2; text-decoration: none; }}
                </style>
            </head>
            <body>
                <h1>No Image Files Found</h1>
                <p>The folder "{folder_name}" does not contain any image files (JPEG, PNG, or TIFF).</p>
                <p><a href="/">← Return to Home</a></p>
            </body>
            </html>
        '''
        
        return render_template(
            "select_images.html",
            folder_id=folder_id,
            folder_name=folder_name,
            images=image_files
        )
    
    except Exception as e:
        logger.exception(f"Error listing folder {folder_id}: {str(e)}")
        abort(500)
@app.route("/edit_spots/<batchid>", methods=["GET"])
def editspots(batchid: str) -> str:
    """Display thermal hotspot editing interface."""
    try:
        # Load thermal analysis and existing labels (no tenant_id needed)
        analysis_data = heatlossservice.get_thermal_analysis(batchid, None)
        # If analysis_data is nested, unwrap it for the template
        if "images" not in analysis_data and "results" in analysis_data:
            analysis_data = analysis_data["results"]

        existing_labels = heatlossservice.get_existing_labels(batchid, None)

        saved_links = existing_labels.get("links", [])

        return render_template(
            "edit_spots.html",
            batch_id=batchid,
            analysis_data=analysis_data,
            existing_labels=existing_labels,
            saved_links=saved_links,
            spot_types=SPOT_TYPES,
        )
    except FileNotFoundError:
        logger.error(f"Batch {batchid} not found")
        abort(404)
    except Exception as e:
        logger.exception(f"Error loading batch {batchid}: {str(e)}")
        abort(500)


@app.route("/save_labels/<batchid>", methods=["POST"])
def save_labels(batchid: str) -> Any:
    """Save operator hotspot labels and document links."""
    tenant_id = _get_tenant_id()
    try:
        data = request.get_json()
        heatlossservice.save_labels(batchid, data, tenant_id)
        return jsonify({"success": True, "message": "Labels saved"})
    except Exception as e:
        logger.exception(f"Error saving labels for batch {batchid}: {str(e)}")
        return jsonify({"error": "Failed to save labels"}), 500


@app.route('/generate_heat_loss_report/<batch_id>', methods=['POST'])
def generate_heat_loss_report_route(batch_id):
    """
    Generate professional heat loss report from labeled hot spots.
    Now also generates PDF and uploads to Drive if folder_id is provided.
    """
    try:
        tenant_id = request.headers.get('X-Tenant-ID', settings.DEFAULT_TENANT)
        property_address = request.form.get('property_address', '')
        inspector_name = request.form.get('inspector_name', '')
        doc_mode = request.form.get('doc_mode', 'link')
        folder_id = request.form.get('folder_id')  # Optional: Drive folder ID
        
        # Generate report data (HTML structure)
        report_data = heatlossservice.generate_report(
            batch_id,
            property_address=property_address,
            inspector_name=inspector_name,
            doc_mode=doc_mode,
            tenant_id=tenant_id
        )
        
        # NEW: Generate PDF from the report data
        pdf_path = None
        try:
            pdf_path = heatlossservice.generate_pdf_from_report_data(
                batch_id, 
                report_data, 
                tenant_id
            )
            
            # Upload to Drive if folder_id provided
            if pdf_path and folder_id:
                import services.drive_client as drive_client
                drive_client.upload_file_to_folder(pdf_path, folder_id)
                logger.info(f"Uploaded PDF to Drive folder {folder_id}")
                
        except Exception as e:
            logger.warning(f"PDF generation/upload failed (non-fatal): {e}")
            # Continue even if PDF fails
        
        return jsonify({
            'success': True,
            'message': 'Heat loss report generated successfully',
            'report_url': url_for('view_heat_loss_report', batch_id=batch_id),
            'pdf_generated': pdf_path is not None
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


@app.route("/view_heat_loss_report/<batch_id>", methods=["GET"])
def view_heat_loss_report(batch_id: str) -> str:
    """Display professional heat loss report."""
    tenant_id = _get_tenant_id()
    try:
        report_data = heatlossservice.get_report(batch_id, tenant_id)
        return render_template(
            "heat_loss_report.html",
            batch_id=batch_id,
            report_data=report_data,
        )
    except FileNotFoundError:
        logger.error(f"Report for batch {batch_id} not found")
        abort(404)
    except Exception as e:
        logger.exception(f"Error loading report for batch {batch_id}: {str(e)}")
        abort(500)


@app.route("/delete/<batch_id>", methods=["DELETE"])
def delete_batch(batch_id: str) -> Any:
    """Delete batch and all associated files."""
    tenant_id = _get_tenant_id()
    try:
        batch_path = safe_batch_path(settings.REPORTS_DIR, batch_id, tenant_id)
        if batch_path.exists():
            shutil.rmtree(batch_path)
            logger.info(f"Deleted batch {batch_id}")
        return jsonify({"success": True, "message": "Batch deleted"})
    except Exception as e:
        logger.exception(f"Error deleting batch {batch_id}: {str(e)}")
        return jsonify({"error": "Failed to delete batch"}), 500


@app.route("/api/batches", methods=["GET"])
def api_list_batches() -> Any:
    """List all batches as JSON."""
    tenant_id = _get_tenant_id()
    try:
        batches = batchservice.get_all_batches(tenant_id)
        return jsonify({"success": True, "batches": batches})
    except Exception as e:
        logger.exception(f"Error listing batches: {str(e)}")
        return jsonify({"error": "Failed to list batches"}), 500


@app.route("/api/batch/<batch_id>", methods=["GET"])
def api_batch_info(batch_id: str) -> Any:
    """Get batch summary as JSON."""
    tenant_id = _get_tenant_id()
    try:
        summary = batchservice.get_batch_summary(batch_id, tenant_id)
        return jsonify({"success": True, "batch": summary})
    except FileNotFoundError:
        return jsonify({"error": "Batch not found"}), 404
    except Exception as e:
        logger.exception(f"Error getting batch info: {str(e)}")
        return jsonify({"error": "Failed to get batch info"}), 500


@app.route("/api/batch/<batch_id>/analysis", methods=["GET"])
def api_thermal_analysis(batch_id: str) -> Any:
    """Get thermal analysis data as JSON."""
    tenant_id = _get_tenant_id()
    try:
        analysis = heatlossservice.get_thermal_analysis(batch_id, tenant_id)
        return jsonify({"success": True, "analysis": analysis})
    except FileNotFoundError:
        return jsonify({"error": "Analysis not found"}), 404
    except Exception as e:
        logger.exception(f"Error getting thermal analysis: {str(e)}")
        return jsonify({"error": "Failed to get analysis"}), 500


@app.route("/info", methods=["GET"])
def info() -> str:
    """Display help and information page."""
    return render_template(
        "info.html",
        app_name=APP_NAME,
        app_version=APP_VERSION,
    )


@app.route("/download/<batch_id>/<filename>", methods=["GET"])
def download_file(batch_id: str, filename: str) -> Any:
    """Download a file from batch storage."""
    tenant_id = _get_tenant_id()
    try:
        batch_path = safe_batch_path(settings.REPORTS_DIR, batch_id, tenant_id)
        file_path = batch_path / filename
        
        # Verify file is within batch directory (security check)
        if not str(file_path.resolve()).startswith(str(batch_path.resolve())):
            abort(403)
        
        if not file_path.exists():
            abort(404)
        
        return send_file(file_path, as_attachment=True)
    except Exception as e:
        logger.exception(f"Error downloading file: {str(e)}")
        abort(500)


@app.errorhandler(404)
def not_found(error) -> tuple:
    """Handle 404 errors."""
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(error) -> tuple:
    """Handle 500 errors."""
    logger.exception(f"Server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=False, host="0.0.0.0", port=port)
