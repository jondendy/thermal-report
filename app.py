#!/usr/bin/env python3
"""
Flask entrypoint for the Thermal Report web tool.

Testbed goals (branch: testbed/main-flat-safe-pdf):
- Flat folders under settings.BASE_REPORT_DIR via security_utils.safe_batch_path
- tenant_id defaults to None (portable main)
- Add PDF generation + /download_pdf like folder-workflow branch
- Keep Drive/GCS routes optional (only used when configured)
"""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv()  # call this before `import settings`

import re
import shutil
from typing import Any
from pathlib import Path

from flask import Flask, render_template, request, jsonify, abort, url_for, send_file

import settings
from settings import APP_NAME, APP_VERSION, MAX_CONTENT_LENGTH, BATCH_SIZE_MAX

import services.batch_service as batchservice
import services.heat_loss_service as heatlossservice

from security_utils import validate_tenant_id, safe_batch_path
from services.logging_service import setup_logging

# Optional Drive ingest routes (guarded)
try:
    from ingest_drive import register_ingest_routes
except Exception:
    register_ingest_routes = None

logger = setup_logging(level="INFO")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["SECRET_KEY"] = "change-me-in-production"

SPOT_TYPES = ["Wall", "Window", "Door", "Roof", "Floor", "Vent", "Other"]

if register_ingest_routes:
    try:
        register_ingest_routes(app)
    except Exception:
        # Keep portable mode alive even if Drive deps are missing
        pass


def _get_tenant_id() -> str | None:
    """Tenant is optional in portable main; validate only if provided."""
    tenant_id = request.args.get("tenant") or request.headers.get("X-Tenant-ID") or None
    return validate_tenant_id(tenant_id)


@app.route("/", methods=["GET"])
def index() -> str:
    batches = batchservice.get_all_batches(None)
    return render_template(
        "index.html",
        app_name=APP_NAME,
        app_version=APP_VERSION,
        batches=batches,
        batch_size_max=BATCH_SIZE_MAX,
    )


@app.route("/upload", methods=["POST"])
def upload() -> Any:
    files = request.files.getlist("files")
    if not files or len(files) == 0:
        return jsonify({"error": "No files uploaded"}), 400
    try:
        batch_id = batchservice.get_batch_id(files)
        results = batchservice.process_batch(batch_id, files, None)
        summary = results.get("summary", {})
        return jsonify({"batchid": batch_id, "results": {"summary": summary}})
    except ValueError as e:
        logger.warning("Validation error during upload: %s", str(e))
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Error processing batch: %s", str(e))
        return jsonify({"error": f"Processing error: {e}"}), 500


# --- Optional Drive UI flows (keep mimeType fields) ---
@app.route("/list_folders")
def list_folders():
    try:
        import services.drive_client as drive_client
        from settings import STORAGE_ADDRESS
        if not STORAGE_ADDRESS:
            return "<h1>Error</h1><p>STORAGE_ADDRESS not configured</p>", 500
        folders = drive_client.list_files_in_folder(STORAGE_ADDRESS)
        folder_list = [f for f in folders if f.get("mimeType") == "application/vnd.google-apps.folder"]
        return render_template("list_folders.html", folders=folder_list, parent_id=STORAGE_ADDRESS)
    except Exception as e:
        logger.exception("Error listing folders: %s", str(e))
        return f"<h1>Error</h1><p>Failed to list folders: {str(e)}</p>", 500


@app.route("/select_images/<folder_id>", methods=["GET"])
def select_images(folder_id: str):
    try:
        import services.drive_client as drive_client
        folder_metadata = drive_client.get_folder_metadata(folder_id)
        folder_name = folder_metadata.get("name", "Unknown Folder")
        service = drive_client.get_drive_service()
        query = f"'{folder_id}' in parents and trashed = false"
        results = service.files().list(
            q=query,
            fields="files(id, name, thumbnailLink, mimeType)",
            orderBy="name",
        ).execute()
        files = results.get("files", [])
        image_mimes = ["image/jpeg", "image/png", "image/tiff"]
        image_files = [f for f in files if f.get("mimeType") in image_mimes]
        if not image_files:
            return (
                f"<!DOCTYPE html><html><head><title>No Images Found</title>"
                f"<style>body {{ font-family: Arial; margin: 40px; text-align: center; }} "
                f"h1 {{ color: #d32f2f; }} a {{ color: #1976d2; }}</style>"
                f"</head><body><h1>No Image Files Found</h1>"
                f"<p>The folder \"{folder_name}\" does not contain any image files.</p>"
                f"<p><a href=\"/\">&larr; Return to Home</a></p></body></html>",
                200,
            )
        return render_template("select_images.html", folder_id=folder_id, folder_name=folder_name, images=image_files)
    except Exception as e:
        logger.exception("Error listing folder %s: %s", folder_id, str(e))
        abort(500)


@app.route("/edit_spots/<batchid>", methods=["GET"])
def editspots(batchid: str) -> str:
    try:
        recommendations_url=getattr(settings, "RECOMMENDATIONS_DOCUMENT_URL", "") or "",
        analysis_data = heatlossservice.get_thermal_analysis(batchid, None)
        existing_labels = heatlossservice.get_existing_labels(batchid, None)
        saved_links = existing_labels.get("links", [])

        # Compatibility shim: some historical analyses nest images
        if "images" not in analysis_data:
            if "results" in analysis_data and "images" in analysis_data["results"]:
                analysis_data = analysis_data["results"]
            elif "images_data" in analysis_data:
                analysis_data = {"images": analysis_data["images_data"]}

        current_sensitivity = analysis_data.get("sensitivity", "medium")

        return render_template(
            "edit_spots.html",
            batch_id=batchid,
            analysis_data=analysis_data,
            existing_labels=existing_labels,
            saved_links=saved_links,
            spot_types=SPOT_TYPES,
            current_sensitivity=current_sensitivity,
        )
    except FileNotFoundError:
        abort(404)
    except Exception as e:
        logger.exception("Error loading batch %s: %s", batchid, str(e))
        abort(500)


@app.route("/api/reprocess_batch/<batch_id>", methods=["POST"])
def api_reprocess_batch(batch_id: str) -> Any:
    """Re-run thermal analysis on existing batch with new sensitivity settings."""
    try:
        data = request.get_json() or {}
        new_sensitivity = data.get("sensitivity", "medium")
        if new_sensitivity not in ["low", "medium", "high"]:
            return jsonify({"error": "Invalid sensitivity. Use: low, medium, or high"}), 400

        upload_dir = settings.BASE_UPLOAD_PATH / batch_id
        if not upload_dir.exists():
            return jsonify({"error": "Batch images not found"}), 404

        image_files = list(upload_dir.glob("*.jpg")) + list(upload_dir.glob("*.jpeg"))
        if not image_files:
            return jsonify({"error": "No images in batch directory"}), 404

        from services.flir_processor_simple import SimpleFLIRProcessor
        from services.thermal_analyzer import ThermalAnalyzer

        processor = SimpleFLIRProcessor()
        analyzer = ThermalAnalyzer(sensitivity=new_sensitivity)

        batch_dir = safe_batch_path(settings.BASE_REPORT_DIR, batch_id, None)
        max_spots = settings.MAX_HOTSPOTS_PER_IMAGE

        results = {
            "batch_id": batch_id,
            "sensitivity": new_sensitivity,
            "max_spots_per_image": max_spots,
            "images": [],
        }

        for image_path in image_files:
            temp_data, stats = processor.process_single_image(str(image_path), display=False)
            hot_spots = analyzer.detect_hot_spots(temp_data, image_path=str(image_path))[:max_spots]

            labeled_filename = image_path.stem + "_labeled.jpg"
            labeled_path = batch_dir / labeled_filename
            try:
                analyzer.label_hot_spots(str(image_path), hot_spots, str(labeled_path))
            except Exception:
                pass

            image_result = {
                "filename": image_path.name,
                "stats": {
                    "min": float(stats["min"]),
                    "max": float(stats["max"]),
                    "mean": float(stats["mean"]),
                    "median": float(stats["median"]),
                    "std": float(stats["std"]),
                },
                "hot_spots": [spot.to_dict() for spot in hot_spots],
                "hot_spot_count": len(hot_spots),
                "labeled_image": labeled_filename,
            }
            results["images"].append(image_result)

        import services.batch_io as batchio
        batchio.save_thermal_analysis(batch_id, results, None)

        total_spots = sum(img["hot_spot_count"] for img in results["images"])
        return jsonify(
            {
                "success": True,
                "sensitivity": new_sensitivity,
                "total_spots": total_spots,
                "image_count": len(results["images"]),
                "message": f"Reprocessed with {new_sensitivity} sensitivity: {total_spots} spots detected",
            }
        )

    except Exception as e:
        logger.exception("Error reprocessing batch %s: %s", batch_id, str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/save_labels/<batchid>", methods=["POST"])
def save_labels(batchid: str) -> Any:
    try:
        data = request.get_json()
        heatlossservice.save_labels(batchid, data, None)
        return jsonify({"success": True, "message": "Labels saved"})
    except Exception as e:
        logger.exception("Error saving labels for batch %s: %s", batchid, str(e))
        return jsonify({"error": "Failed to save labels"}), 500


@app.route("/api/fetch_shared_notes", methods=["POST"])
def api_fetch_shared_notes() -> Any:
    """Fetch shared recommendations HTML from RECOMMENDATIONS_DOCUMENT_URL and return inner HTML."""
    try:
        from settings import RECOMMENDATIONS_DOCUMENT_URL
        if not RECOMMENDATIONS_DOCUMENT_URL:
            return jsonify({"error": "No shared notes URL configured"}), 400

        file_id = _extract_drive_file_id(RECOMMENDATIONS_DOCUMENT_URL)
        if not file_id:
            return jsonify({"error": "Could not extract file ID from URL"}), 400

        html_content = None
        try:
            import services.drive_client as drive_client
            service = drive_client.get_drive_service()
            file_meta = service.files().get(fileId=file_id, fields="mimeType,name").execute()
            mime = file_meta.get("mimeType", "")

            if "google-apps" in mime:
                resp = service.files().export(fileId=file_id, mimeType="text/html").execute()
                html_content = resp.decode("utf-8") if isinstance(resp, (bytes, bytearray)) else resp
            else:
                import io
                from googleapiclient.http import MediaIoBaseDownload
                req = service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, req)
                done = False
                while not done:
                    _, done = downloader.next_chunk()
                html_content = fh.getvalue().decode("utf-8", errors="replace")

        except Exception as e:
            logger.warning("Drive API fetch failed, trying direct HTTP: %s", e)
            html_content = _fetch_drive_html_direct(file_id)

        if not html_content:
            return jsonify({"error": "Failed to fetch shared notes content"}), 500

        # Strip wrappers
        html_content = re.sub(r"<!DOCTYPE[^>]*>", "", html_content, flags=re.IGNORECASE)
        html_content = re.sub(r"</?html[^>]*>", "", html_content, flags=re.IGNORECASE)
        html_content = re.sub(r"<head[^>]*>.*?</head>", "", html_content, flags=re.IGNORECASE | re.DOTALL)
        html_content = re.sub(r"</?body[^>]*>", "", html_content, flags=re.IGNORECASE)

        return jsonify({"success": True, "html": html_content.strip()})

    except Exception as e:
        logger.exception("Error fetching shared notes: %s", e)
        return jsonify({"error": str(e)}), 500


def _extract_drive_file_id(url: str) -> str | None:
    patterns = [
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"/document/d/([a-zA-Z0-9_-]+)",
        r"/spreadsheets/d/([a-zA-Z0-9_-]+)",
        r"[?&]id=([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


def _fetch_drive_html_direct(file_id: str) -> str | None:
    import requests

    export_url = f"https://docs.google.com/document/d/{file_id}/export?format=html"
    try:
        resp = requests.get(export_url, timeout=15, allow_redirects=True)
        if resp.status_code == 200 and "<" in resp.text[:100]:
            return resp.text
    except Exception:
        pass

    direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    try:
        resp = requests.get(direct_url, timeout=15, allow_redirects=True)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass

    return None


@app.route("/generate_heat_loss_report/<batch_id>", methods=["POST"])
def generate_heat_loss_report_route(batch_id: str):
    try:
        property_address = request.form.get("property_address", "")
        inspector_name = request.form.get("inspector_name", "")
        doc_mode = request.form.get("doc_mode", "link")
        folder_id = request.form.get("folder_id")

        report_data = heatlossservice.generate_report(
            batch_id,
            property_address=property_address,
            inspector_name=inspector_name,
            doc_mode=doc_mode,
            tenant_id=None,
        )

        pdf_path = None
        try:
            pdf_path = heatlossservice.generate_pdf_from_report_data(batch_id, report_data, None)
            if pdf_path and folder_id:
                import services.drive_client as drive_client
                drive_client.upload_file_to_folder(pdf_path, folder_id)
        except Exception as e:
            logger.warning("PDF generation/upload failed (non-fatal): %s", e)

        return jsonify(
            {
                "success": True,
                "message": "Heat loss report generated successfully",
                "report_url": url_for("view_heat_loss_report", batch_id=batch_id),
                "pdf_generated": pdf_path is not None,
            }
        )

    except FileNotFoundError:
        return jsonify({"error": "Required data not found. Please ensure hotspots are labeled."}), 404
    except ValueError:
        return jsonify({"error": "Invalid input data."}), 400
    except Exception as e:
        logger.exception("Error generating heat loss report for batch %s: %s", batch_id, str(e))
        return jsonify({"error": "Report generation failed"}), 500


@app.route("/view_heat_loss_report/<batch_id>", methods=["GET"])
def view_heat_loss_report(batch_id: str) -> str:
    try:
        report_data = heatlossservice.get_report(batch_id, None)
        return render_template("heat_loss_report.html", batch_id=batch_id, report_data=report_data)
    except FileNotFoundError:
        abort(404)
    except Exception as e:
        logger.exception("Error loading report for batch %s: %s", batch_id, str(e))
        abort(500)


@app.route("/download_pdf/<batch_id>", methods=["GET"])
def download_pdf(batch_id: str) -> Any:
    try:
        batch_dir = safe_batch_path(settings.BASE_REPORT_DIR, batch_id, None)
        pdf_filename = f"thermal_report_{batch_id}.pdf"
        pdf_path = batch_dir / pdf_filename

        if pdf_path.exists():
            return send_file(str(pdf_path), as_attachment=True, download_name=pdf_filename, mimetype="application/pdf")

        report_data = heatlossservice.get_report(batch_id, None)
        result_path = heatlossservice.generate_pdf_from_report_data(batch_id, report_data, None)
        if not result_path:
            return jsonify({"error": "PDF generation failed. Check server logs."}), 500

        result_file = Path(result_path)
        if not result_file.exists():
            return jsonify({"error": "Generated file not found"}), 500

        if result_file.suffix == ".pdf":
            return send_file(str(result_file), as_attachment=True, download_name=pdf_filename, mimetype="application/pdf")

        return send_file(
            str(result_file),
            as_attachment=True,
            download_name=f"thermal_report_{batch_id}.html",
            mimetype="text/html",
        )

    except FileNotFoundError:
        abort(404)
    except Exception as e:
        logger.exception("Error downloading PDF for batch %s: %s", batch_id, str(e))
        abort(500)


@app.route("/download/<batch_id>/<filename>", methods=["GET"])
def download_file(batch_id: str, filename: str) -> Any:
    try:
        # Use the canonical safe_batch_path(BASE_REPORT_DIR, ...) base
        batch_dir = safe_batch_path(settings.BASE_REPORT_DIR, batch_id, None)
        file_path = (batch_dir / filename).resolve()

        # Verify within batch
        if not str(file_path).startswith(str(batch_dir.resolve())):
            abort(403)
        if not file_path.exists():
            abort(404)

        return send_file(file_path, as_attachment=False)
    except Exception as e:
        logger.exception("Error downloading file: %s", str(e))
        abort(500)


@app.route("/delete/<batch_id>", methods=["DELETE"])
def delete_batch(batch_id: str) -> Any:
    try:
        batch_path = safe_batch_path(settings.BASE_REPORT_DIR, batch_id, None)
        if batch_path.exists():
            shutil.rmtree(batch_path)
        return jsonify({"success": True, "message": "Batch deleted"})
    except Exception as e:
        logger.exception("Error deleting batch %s: %s", batch_id, str(e))
        return jsonify({"error": "Failed to delete batch"}), 500


@app.route("/api/batches", methods=["GET"])
def api_list_batches() -> Any:
    try:
        batches = batchservice.get_all_batches(None)
        return jsonify({"success": True, "batches": batches})
    except Exception as e:
        logger.exception("Error listing batches: %s", str(e))
        return jsonify({"error": "Failed to list batches"}), 500


@app.route("/api/batch/<batch_id>", methods=["GET"])
def api_batch_info(batch_id: str) -> Any:
    try:
        summary = batchservice.get_batch_summary(batch_id, None)
        return jsonify({"success": True, "batch": summary})
    except FileNotFoundError:
        return jsonify({"error": "Batch not found"}), 404
    except Exception as e:
        logger.exception("Error getting batch info: %s", str(e))
        return jsonify({"error": "Failed to get batch info"}), 500


@app.route("/api/batch/<batch_id>/analysis", methods=["GET"])
def api_thermal_analysis(batch_id: str) -> Any:
    try:
        analysis = heatlossservice.get_thermal_analysis(batch_id, None)
        return jsonify({"success": True, "analysis": analysis})
    except FileNotFoundError:
        return jsonify({"error": "Analysis not found"}), 404
    except Exception as e:
        logger.exception("Error getting thermal analysis: %s", str(e))
        return jsonify({"error": "Failed to get analysis"}), 500


@app.route("/info", methods=["GET"])
def info() -> str:
    return render_template("info.html", app_name=APP_NAME, app_version=APP_VERSION)


@app.errorhandler(404)
def not_found(error) -> tuple:
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(error) -> tuple:
    logger.exception("Server error: %s", str(error))
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=False, host="0.0.0.0", port=port)
