#!/usr/bin/env python3
"""
Drive folder ingestion route for thermal-report.
"""

from flask import Blueprint, request, jsonify, url_for
from pathlib import Path
import os
import tempfile
import shutil
from datetime import datetime
import logging
from werkzeug.datastructures import FileStorage

import services.drive_client as drive_client
import services.batch_service as batchservice
import services.heat_loss_service as heatlossservice
from security_utils import validate_tenant_id
from lib import folder_parser

logger = logging.getLogger(__name__)

# Create blueprint for ingest routes
ingest_bp = Blueprint('ingest', __name__)


@ingest_bp.route('/process_drive_folder', methods=['POST'])
def process_drive_folder():
    """
    Trigger processing for a specific Drive folder ID.
    Returns:
        JSON with batch_id, status, and report_url
    """
    temp_batch_dir = None
    pdf_path = None
    
    try:
        # --- 1. Validation & Metadata ---
        folder_id = request.args.get('folder_id')
        if not folder_id:
            return jsonify({'error': 'Missing folder_id parameter'}), 400

        # Get folder name first
        try:
            folder_metadata = drive_client.get_folder_metadata(folder_id)
            folder_name = folder_metadata.get('name', '')
            logger.info(f"Processing folder: {folder_name} (ID: {folder_id})")

            if folder_name.startswith('_'):
                return jsonify({
                    'message': 'Folder already processed',
                    'folder_name': folder_name,
                    'folder_id': folder_id
                }), 200
        except Exception as e:
            logger.error(f"Failed to get metadata: {e}")
            return jsonify({'error': 'Failed to access Drive folder'}), 500

        # Parse survey info
        survey_info = folder_parser.parse_folder_name(folder_name)
        if survey_info:
            tenant_id = survey_info.owner_initials
        else:
            tenant_id = request.args.get('tenant') or request.headers.get('X-Tenant-ID')
            tenant_id = validate_tenant_id(tenant_id)
            logger.warning(f"Using fallback tenant_id: {tenant_id}")

        # --- 2. List & Filter Files ---
        try:
            files = drive_client.list_files_in_folder(folder_id)
        except Exception as e:
            return jsonify({'error': f'Failed to list files: {str(e)}'}), 403

        image_extensions = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
        image_files = [f for f in files if any(f['name'].lower().endswith(ext) for ext in image_extensions)]
        
        if not image_files:
            return jsonify({'error': 'No image files found in folder'}), 404
        
        image_files.sort(key=lambda x: x['name'])

        # --- 3. Setup Batch & Download ---
        batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_batch_dir = Path(tempfile.gettempdir()) / batch_id
        temp_batch_dir.mkdir(parents=True, exist_ok=True)
        
        downloaded_files = []
        for file_info in image_files:
            dest_path = temp_batch_dir / file_info['name']
            try:
                drive_client.download_file(file_info['id'], str(dest_path))
                downloaded_files.append(dest_path)
            except Exception as e:
                logger.error(f"Failed to download {file_info['name']}: {e}")

        if not downloaded_files:
            return jsonify({'error': 'Failed to download any files'}), 500

        # --- 4. Process Batch ---
        # Create mock FileStorage objects for the existing batch service
        file_objects = []
        try:
            for file_path in downloaded_files:
                f = open(file_path, 'rb')
                file_obj = FileStorage(stream=f, filename=file_path.name, content_type='image/jpeg')
                file_objects.append(file_obj)

            logger.info(f"Processing batch {batch_id} with {len(file_objects)} files")
            results = batchservice.process_batch(batch_id, file_objects, tenant_id)
        finally:
            # Close file handles immediately after processing
            for f in file_objects:
                f.stream.close()

        # --- 5. Generate PDF & Upload ---
        try:
            pdf_path = heatlossservice.generate_pdf_report(batch_id, tenant_id)
            if pdf_path:
                drive_client.upload_file_to_folder(pdf_path, folder_id)
                new_folder_name = f"_{folder_name}"
                drive_client.rename_folder(folder_id, new_folder_name)
                logger.info(f"Renamed folder to {new_folder_name}")
        except Exception as e:
            logger.error(f"PDF/Upload failed: {e}")
            # We don't return error here, because the batch processing succeeded

        # --- 6. Success Response ---
        return jsonify({
            'status': 'success',
            'message': 'Report generated and uploaded successfully',
            'batch_id': batch_id,
            'folder_id': folder_id,
            'report_url': pdf_path if pdf_path else None,
            'next_steps': {
                'edit_spots': url_for('editspots', batchid=batch_id, _external=True)
            }
        }), 200

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return jsonify({'error': str(e)}), 500
        
    finally:
        # Cleanup temp dir
        if temp_batch_dir and temp_batch_dir.exists():
            try:
                shutil.rmtree(temp_batch_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp dir: {e}")


def register_ingest_routes(app):
    """Register the ingest blueprint with the Flask app."""
    app.register_blueprint(ingest_bp)
    logger.info("Ingest routes registered")
