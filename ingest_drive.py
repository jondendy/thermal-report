#!/usr/bin/env python3
"""
Drive folder ingestion route for thermal-report.

This module adds a /process_drive_folder route that:
1. Accepts a Google Drive folder_id parameter
2. Downloads images from the Drive folder to /tmp/<batch-id>
3. Processes them using existing batch processing logic
4. Returns a link to the generated report

Usage:
  GET/POST /process_drive_folder?folder_id=YOUR_FOLDER_ID
"""

from flask import Blueprint, request, jsonify, url_for
from pathlib import Path
import os
import tempfile
import shutil
from datetime import datetime
import logging

import services.drive_client as drive_client
import services.batch_service as batchservice
import services.heat_loss_service as heatlossservice
from security_utils import validate_tenant_id
from lib import folder_parser

logger = logging.getLogger(__name__)

# Create blueprint for ingest routes
ingest_bp = Blueprint('ingest', __name__)


@ingest_bp.route('/process_drive_folder', methods=['GET', 'POST'])
def process_drive_folder():
    """
    Process images from a Google Drive folder.
    
    Query parameters:
      - folder_id: Google Drive folder ID (required)
      - tenant: Tenant ID (optional, for multi-tenancy)
    
    Returns:
      JSON with batch_id, status, and report_url
    """
    try:
        # Get folder_id from query params
        folder_id = request.args.get('folder_id')
        if not folder_id:
            return jsonify({
                'error': 'Missing folder_id parameter',
                'usage': '/process_drive_folder?folder_id=YOUR_FOLDER_ID'
            }), 400
        
        # Get tenant ID

        # Parse folder name to extract survey information
        survey_info = folder_parser.parse_folder_name(folder_name)
        
        # Extract tenant_id from folder name (owner initials)
        if survey_info:
            tenant_id = survey_info.owner_initials
            logger.info(f"Extracted tenant_id '{tenant_id}' from folder name '{folder_name}'")
            logger.info(f"Survey details: Address={survey_info.address}, Ref={survey_info.reference_number}, Surveyors={survey_info.surveyor1_initials}/{survey_info.surveyor2_initials}")
        else:
            # Fallback to request parameter if folder name doesn't match expected format
            tenant_id = request.args.get('tenant') or request.headers.get('X-Tenant-ID')
            tenant_id = validate_tenant_id(tenant_id)
            logger.warning(f"Could not parse folder name '{folder_name}', using tenant from request: {tenant_id}")
            
            try:
                folder_metadata = drive_client.get_folder_metadata(folder_id)
                folder_name = folder_metadata.get('name', '')

                if folder_name.startswith('_'):
                    logger.info(f"Skipping already processed folder: {folder_name}")
                    return jsonify({
                        'message': 'Folder already processed',
                        'folder_name': folder_name,
                        'folder_id': folder_id
                    }), 200
            except Exception as e:
                logger.warning(f"Could not get folder metadata: {e}")
                # Continue processing if we can't get metadata
        tenant_id = request.args.get('tenant') or request.headers.get('X-Tenant-ID')
        tenant_id = validate_tenant_id(tenant_id)
        
        logger.info(f"Processing Drive folder: {folder_id}")
        
        # 1. List files in the Drive folder
        try:
            files = drive_client.list_files_in_folder(folder_id)
        except Exception as e:
            logger.error(f"Failed to list files from Drive folder {folder_id}: {e}")
            return jsonify({
                'error': 'Failed to access Drive folder',
                'details': str(e),
                'hint': 'Ensure the folder is shared with your service account'
            }), 403
        
        if not files:
            return jsonify({
                'error': 'No files found in folder',
                'folder_id': folder_id
            }), 404
        
        # Filter for image files only
        image_extensions = {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}
        image_files = [
            f for f in files 
            if any(f['name'].lower().endswith(ext) for ext in image_extensions)
        ]
        
        if not image_files:
            return jsonify({
                'error': 'No image files found in folder',
                'folder_id': folder_id,
                'total_files': len(files)
            }), 404
        
        # Sort files by name (assumption: first is thermal, second is visible)
        image_files.sort(key=lambda x: x['name'])
        
        logger.info(f"Found {len(image_files)} images in Drive folder")
        
        # 2. Generate batch ID based on current timestamp
        batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 3. Create temporary directory for this batch
        temp_batch_dir = Path(tempfile.gettempdir()) / batch_id
        temp_batch_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 4. Download images from Drive to temp directory
            logger.info(f"Downloading {len(image_files)} images to {temp_batch_dir}")
            downloaded_files = []
            
            for file_info in image_files:
                file_id = file_info['id']
                file_name = file_info['name']
                dest_path = temp_batch_dir / file_name
                
                try:
                    drive_client.download_file(file_id, str(dest_path))
                    downloaded_files.append(dest_path)
                    logger.debug(f"Downloaded: {file_name}")
                except Exception as e:
                    logger.error(f"Failed to download {file_name}: {e}")
                    # Continue with other files
            
            if not downloaded_files:
                raise Exception("Failed to download any files")
            
            logger.info(f"Successfully downloaded {len(downloaded_files)} files")
            
            # 5. Convert Path objects to file-like objects for batch processing
            # The existing batch processing expects werkzeug FileStorage objects
            # We'll create a workaround by creating mock FileStorage objects
            from werkzeug.datastructures import FileStorage
            
            file_objects = []
            for file_path in downloaded_files:
                with open(file_path, 'rb') as f:
                    file_obj = FileStorage(
                        stream=f,
                        filename=file_path.name,
                        content_type='image/jpeg'
                    )
                    # Read the file content into memory
                    file_obj.stream = open(file_path, 'rb')
                    file_objects.append(file_obj)

        except Exception as e:
            logger.error(f"Failed to process files from Drive: {e}")
            return jsonify({'error': str(e)}), 500

        # 7. Generate PDF report and upload to Drive
        try:
            # Generate PDF report
            pdf_path = heatlossservice.generate_pdf_report(batch_id, tenant_id)

            if pdf_path:
                # Upload PDF to the Drive folder
                drive_client.upload_file_to_folder(pdf_path, folder_id)
                logger.info(f"Uploaded PDF report to Drive folder {folder_id}")

                # Rename folder with underscore prefix to mark as processed
                new_folder_name = f"_{folder_name}"
                drive_client.rename_folder(folder_id, new_folder_name)
                logger.info(f"Renamed folder to {new_folder_name}")
        except Exception as e:
            logger.error(f"Failed to upload PDF or rename folder: {e}")
            # Continue even if PDF upload fails
            
            # 6. Process batch using existing service
            logger.info(f"Processing batch {batch_id} with {len(file_objects)} files")
            results = batchservice.process_batch(batch_id, file_objects, tenant_id)
            
            # Close file streams
            for f in file_objects:
                if hasattr(f.stream, 'close'):
                    f.stream.close()
            
            summary = results.get('summary', {})
            
            # 7. Return success response with links
            return jsonify({
                'success': True,
                'batch_id': batch_id,
                'folder_id': folder_id,
                'files_processed': len(downloaded_files),
                'summary': summary,
                'next_steps': {
                    'edit_spots': url_for('editspots', batchid=batch_id, _external=True),
                    'api_analysis': url_for('api_thermal_analysis', batch_id=batch_id, _external=True)
                },
                'message': 'Batch processed successfully. Visit edit_spots to label hotspots and generate report.'
            })
            
        finally:
            # Clean up temporary directory
            try:
                if temp_batch_dir.exists():
                    shutil.rmtree(temp_batch_dir)
                    logger.debug(f"Cleaned up temp directory: {temp_batch_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory {temp_batch_dir}: {e}")
    
    except Exception as e:
        logger.exception(f"Error processing Drive folder: {str(e)}")
        return jsonify({
            'error': 'Failed to process Drive folder',
            'details': str(e)
        }), 500


def register_ingest_routes(app):
    """
    Register the ingest blueprint with the Flask app.
    
    Usage in app.py:
        from ingest_drive import register_ingest_routes
        register_ingest_routes(app)
    """
    app.register_blueprint(ingest_bp)
    logger.info("Ingest routes registered")
