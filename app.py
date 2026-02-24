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
import re
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
    batches = batchservice.get_all_batches(None)
    return render_template("index.html", batches=batches, app_name=APP_NAME, app_version=APP_VERSION)


@app.route("/upload", methods=["POST"])
def upload() -> Any:
    files = request.files.getlist("files")
    if not files or len(files) == 0:
        return jsonify({"error": "No files uploaded"}), 400
    try:
        batch_id = batchservice.get_batch_id(files)
        results = batchservice.process_batch(batch_id, files, None)
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
    try:
        import services.drive_client as drive_client
        from settings import STORAGE_ADDRESS
        if not STORAGE_ADDRESS:
            return '<h1>Error</h1><p>STORAGE_ADDRESS not configured in .env file</p>', 500
        folders = drive_client.list_files_in_folder(STORAGE_ADDRESS)
        folder_list = [f for f in folders if f.get('mimeType') == 'application/vnd.google-apps.folder']
        return render_template('list_folders.html', folders=folder_list, parent_id=STORAGE_ADDRESS)
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.exception(f"Error listing folders: {str(e)}")
        return f'<h1>Error</h1><p>Failed to list folders: {str(e)}</p>', 500


@app.route("/select_images/<folder_id>", methods=["GET"])
def select_images(folder_id: str):
    try:
        import services.drive_client as drive_client
        folder_metadata = drive_client.get_folder_metadata(folder_id)
        folder_name = folder_metadata.get('name', 'Unknown Folder')
        service = drive_client.get_drive_service()
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(
            q=query, fields="files(id, name, thumbnailLink, mimeType)", orderBy="name"
        ).execute()
        files = results.get('files', [])
        image_mimes = ['image/jpeg', 'image/png', 'image/tiff']
        image_files = [f for f in files if f.get('mimeType') in image_mimes]
        if not image_files:
            return f'''<!DOCTYPE html><html><head><title>No Images Found</title>
            <style>body {{ font-family: Arial; margin: 40px; text-align: center; }} h1 {{ color: #d32f2f; }} a {{ color: #1976d2; }}</style>
            </head><body><h1>No Image Files Found</h1>
            <p>The folder "{folder_name}" does not contain any image files.</p>
            <p><a href="/">&larr; Return to Home</a></p></body></html>'''
        return render_template("select_images.html", folder_id=folder_id, folder_name=folder_name, images=image_files)
    except Exception as e:
        logger.exception(f"Error listing folder {folder_id}: {str(e)}")
        abort(500)


@app.route("/edit_spots/<batchid>", methods=["GET"])
def editspots(batchid: str) -> str:
    try:
        analysis_data = heatlossservice.get_thermal_analysis(batchid, None)
        existing_labels = heatlossservice.get_existing_labels(batchid, None)
        saved_links = existing_labels.get("links", [])
        if "images" not in analysis_data:
            if "results" in analysis_data and "images" in analysis_data["results"]:
                analysis_data = analysis_data["results"]
            elif "images_data" in analysis_data:
                analysis_data = {"images": analysis_data["images_data"]}
        return render_template(
            "edit_spots.html", batch_id=batchid, analysis_data=analysis_data,
            existing_labels=existing_labels, saved_links=saved_links, spot_types=SPOT_TYPES,
        )
    except FileNotFoundError:
        logger.error(f"Batch {batchid} not found")
        abort(404)
    except Exception as e:
        logger.exception(f"Error loading batch {batchid}: {str(e)}")
        abort(500)


@app.route("/save_labels/<batchid>", methods=["POST"])
def save_labels(batchid: str) -> Any:
    try:
        data = request.get_json()
        heatlossservice.save_labels(batchid, data, None)
        return jsonify({"success": True, "message": "Labels saved"})
    except Exception as e:
        logger.exception(f"Error saving labels for batch {batchid}: {str(e)}")
        return jsonify({"error": "Failed to save labels"}), 500


@app.route('/generate_heat_loss_report/<batch_id>', methods=['POST'])
def generate_heat_loss_report_route(batch_id):
    try:
        property_address = request.form.get('property_address', '')
        inspector_name = request.form.get('inspector_name', '')
        doc_mode = request.form.get('doc_mode', 'link')
        folder_id = request.form.get('folder_id')
        report_data = heatlossservice.generate_report(
            batch_id, property_address=property_address,
            inspector_name=inspector_name, doc_mode=doc_mode, tenant_id=None
        )
        pdf_path = None
        try:
            pdf_path = heatlossservice.generate_pdf_from_report_data(batch_id, report_data, None)
            if pdf_path and folder_id:
                import services.drive_client as drive_client
                drive_client.upload_file_to_folder(pdf_path, folder_id)
                logger.info(f"Uploaded PDF to Drive folder {folder_id}")
        except Exception as e:
            logger.warning(f"PDF generation/upload failed (non-fatal): {e}")
        return jsonify({
            'success': True, 'message': 'Heat loss report generated successfully',
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
    try:
        report_data = heatlossservice.get_report(batch_id, None)
        return render_template("heat_loss_report.html", batch_id=batch_id, report_data=report_data)
    except FileNotFoundError:
        logger.error(f"Report for batch {batch_id} not found")
        abort(404)
    except Exception as e:
        logger.exception(f"Error loading report for batch {batch_id}: {str(e)}")
        abort(500)


@app.route("/download_pdf/<batch_id>", methods=["GET"])
def download_pdf(batch_id: str) -> Any:
    try:
        batch_dir = safe_batch_path(settings.BASE_REPORT_DIR, batch_id, None)
        pdf_filename = f"thermal_report_{batch_id}.pdf"
        pdf_path = batch_dir / pdf_filename
        if pdf_path.exists():
            return send_file(str(pdf_path), as_attachment=True, download_name=pdf_filename, mimetype='application/pdf')
        report_data = heatlossservice.get_report(batch_id, None)
        result_path = heatlossservice.generate_pdf_from_report_data(batch_id, report_data, None)
        if not result_path:
            return jsonify({"error": "PDF generation failed. Check server logs.", "hint": "pip install xhtml2pdf"}), 500
        result_file = Path(result_path)
        if not result_file.exists():
            return jsonify({"error": "Generated file not found"}), 500
        if result_file.suffix == '.pdf':
            return send_file(str(result_file), as_attachment=True, download_name=pdf_filename, mimetype='application/pdf')
        else:
            return send_file(str(result_file), as_attachment=True,
                download_name=f"thermal_report_{batch_id}.html", mimetype='text/html')
    except FileNotFoundError:
        abort(404)
    except Exception as e:
        logger.exception(f"Error downloading PDF for batch {batch_id}: {str(e)}")
        abort(500)


@app.route("/api/fetch_shared_notes", methods=["POST"])
def api_fetch_shared_notes() -> Any:
    """
    Fetch the shared recommendations HTML from Google Drive and return it.
    The file ID is taken from RECOMMENDATIONS_DOCUMENT_URL in settings.
    """
    try:
        from settings import RECOMMENDATIONS_DOCUMENT_URL
        if not RECOMMENDATIONS_DOCUMENT_URL:
            return jsonify({"error": "No shared notes URL configured"}), 400

        # Extract Google Drive file ID from URL
        file_id = _extract_drive_file_id(RECOMMENDATIONS_DOCUMENT_URL)
        if not file_id:
            return jsonify({"error": "Could not extract file ID from URL"}), 400

        # Try fetching via Drive API first (uses service account credentials)
        html_content = None
        try:
            import services.drive_client as drive_client
            service = drive_client.get_drive_service()
            # Export as HTML if it's a Google Doc, otherwise download raw
            file_meta = service.files().get(fileId=file_id, fields='mimeType,name').execute()
            mime = file_meta.get('mimeType', '')

            if 'google-apps' in mime:
                # It's a Google Doc/Sheet/etc — export as HTML
                resp = service.files().export(fileId=file_id, mimeType='text/html').execute()
                html_content = resp.decode('utf-8') if isinstance(resp, bytes) else resp
            else:
                # It's an uploaded file (HTML, PDF, etc) — download raw
                import io
                from googleapiclient.http import MediaIoBaseDownload
                req = service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, req)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                html_content = fh.getvalue().decode('utf-8', errors='replace')

        except Exception as e:
            logger.warning(f"Drive API fetch failed, trying direct HTTP: {e}")
            # Fallback: direct HTTP fetch
            html_content = _fetch_drive_html_direct(file_id)

        if not html_content:
            return jsonify({"error": "Failed to fetch shared notes content"}), 500

        # Strip outer HTML wrappers
        html_content = re.sub(r'<!DOCTYPE[^>]*>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</?html[^>]*>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<head[^>]*>.*?</head>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
        html_content = re.sub(r'</?body[^>]*>', '', html_content, flags=re.IGNORECASE)

        return jsonify({"success": True, "html": html_content.strip()})

    except Exception as e:
        logger.exception(f"Error fetching shared notes: {e}")
        return jsonify({"error": str(e)}), 500


def _extract_drive_file_id(url: str) -> str | None:
    """Extract Google Drive file ID from various URL formats."""
    patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)',         # drive.google.com/file/d/ID/...
        r'/document/d/([a-zA-Z0-9_-]+)',      # docs.google.com/document/d/ID/...
        r'/spreadsheets/d/([a-zA-Z0-9_-]+)',  # docs.google.com/spreadsheets/d/ID/...
        r'[?&]id=([a-zA-Z0-9_-]+)',           # drive.google.com/open?id=ID
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _fetch_drive_html_direct(file_id: str) -> str | None:
    """Fetch Google Drive file content via direct export URL (no API key needed for public files)."""
    import requests
    # Try Google Docs export URL first
    export_url = f"https://docs.google.com/document/d/{file_id}/export?format=html"
    try:
        resp = requests.get(export_url, timeout=15, allow_redirects=True)
        if resp.status_code == 200 and '<' in resp.text[:100]:
            return resp.text
    except Exception:
        pass

    # Try Drive direct download
    direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        resp = requests.get(direct_url, timeout=15, allow_redirects=True)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass

    return None


@app.route("/delete/<batch_id>", methods=["DELETE"])
def delete_batch(batch_id: str) -> Any:
    try:
        batch_path = safe_batch_path(settings.BASE_REPORT_DIR, batch_id, None)
        if batch_path.exists():
            shutil.rmtree(batch_path)
            logger.info(f"Deleted batch {batch_id}")
        return jsonify({"success": True, "message": "Batch deleted"})
    except Exception as e:
        logger.exception(f"Error deleting batch {batch_id}: {str(e)}")
        return jsonify({"error": "Failed to delete batch"}), 500


@app.route("/api/batches", methods=["GET"])
def api_list_batches() -> Any:
    try:
        batches = batchservice.get_all_batches(None)
        return jsonify({"success": True, "batches": batches})
    except Exception as e:
        logger.exception(f"Error listing batches: {str(e)}")
        return jsonify({"error": "Failed to list batches"}), 500


@app.route("/api/batch/<batch_id>", methods=["GET"])
def api_batch_info(batch_id: str) -> Any:
    try:
        summary = batchservice.get_batch_summary(batch_id, None)
        return jsonify({"success": True, "batch": summary})
    except FileNotFoundError:
        return jsonify({"error": "Batch not found"}), 404
    except Exception as e:
        logger.exception(f"Error getting batch info: {str(e)}")
        return jsonify({"error": "Failed to get batch info"}), 500


@app.route("/api/batch/<batch_id>/analysis", methods=["GET"])
def api_thermal_analysis(batch_id: str) -> Any:
    try:
        analysis = heatlossservice.get_thermal_analysis(batch_id, None)
        return jsonify({"success": True, "analysis": analysis})
    except FileNotFoundError:
        return jsonify({"error": "Analysis not found"}), 404
    except Exception as e:
        logger.exception(f"Error getting thermal analysis: {str(e)}")
        return jsonify({"error": "Failed to get analysis"}), 500


@app.route("/info", methods=["GET"])
def info() -> str:
    return render_template("info.html", app_name=APP_NAME, app_version=APP_VERSION)


@app.route("/download/<batch_id>/<filename>", methods=["GET"])
def download_file(batch_id: str, filename: str) -> Any:
    try:
        batch_path = (settings.BASE_REPORT_PATH / batch_id).resolve()
        file_path = (batch_path / filename).resolve()
        if not str(file_path).startswith(str(batch_path)):
            abort(403)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            abort(404)
        return send_file(file_path, as_attachment=False)
    except Exception as e:
        logger.exception(f"Error downloading file: {str(e)}")
        abort(500)


@app.errorhandler(404)
def not_found(error) -> tuple:
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(error) -> tuple:
    logger.exception(f"Server error: {str(error)}")
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=False, host="0.0.0.0", port=port)
