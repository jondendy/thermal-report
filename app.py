#!/usr/bin/env python3
"""
Flask entrypoint for the Thermal Report web tool.
"""
from __future__ import annotations

import json
import shutil
from typing import Any

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    abort,
)

import settings
from settings import (
    APP_NAME,
    APP_VERSION,
    MAX_CONTENT_LENGTH,
    BATCH_SIZE_MAX,
)
# Use the correct underscore naming for imports
import services.batch_service as batchservice
import services.heat_loss_service as heatlossservice
import services.batch_io as batchio
from lib.security_utils import validate_tenant_id, safe_batch_path

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["SECRET_KEY"] = "change-me-in-production"


def _get_tenant_id() -> str:
    tenant_id = request.args.get("tenant") or None
    return validate_tenant_id(tenant_id)


@app.route("/", methods=["GET"])
def index() -> str:
    tenant_id = _get_tenant_id()
    batches = batchservice.get_all_batches(tenant_id)
    return render_template(
        "index.html",
        app_name=APP_NAME,
        app_version=APP_VERSION,
        batches=batches,
        batch_size_max=BATCH_SIZE_MAX,
    )


@app.route("/upload", methods=["POST"])
def upload() -> Any:
    tenant_id = _get_tenant_id()
    files = request.files.getlist("files")  # Expects 'files' form field

    if not files or len(files) == 0:
        return jsonify({"error": "No files uploaded"}), 400

    try:
        batch_id, summary = batchservice.process_batch(files, tenant_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Processing error: {e}"}), 500

    return jsonify({"batchid": batch_id, "results": {"summary": summary}})


@app.route("/editspots/<batch_id>", methods=["GET"])
def edit_spots(batch_id: str) -> str:
    tenant_id = _get_tenant_id()
    try:
        batch_summary = batchservice.get_batch_summary(batch_id, tenant_id)
        analysis = heatlossservice.get_thermal_analysis(batch_id, tenant_id)
        labels = heatlossservice.get_existing_labels(batch_id, tenant_id)
    except FileNotFoundError:
        abort(404)

    # Define spot types required by edit_spots.html template
    spot_types = ["Window", "Door", "Wall", "Ceiling", "Floor", "Vent", "Radiator", "Pipe", "Roof", "Other"]

    return render_template(
        "edit_spots.html",        # Matches your actual template name
        batch=batch_summary,
        analysis_data=analysis,   # Template expects 'analysis_data'
        existing_labels=labels,   # Template expects 'existing_labels' dict (handles tojson itself)
        spot_types=spot_types,    # Template expects 'spot_types'
    )


@app.route("/savelabels/<batch_id>", methods=["POST"])
def save_labels(batch_id: str) -> Any:
    tenant_id = _get_tenant_id()
    try:
        label_data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON body"}), 400

    try:
        heatlossservice.save_labels(batch_id, label_data, tenant_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"status": "ok"})


@app.route("/generateheatlossreport/<batch_id>", methods=["POST"])
def generate_heatloss_report(batch_id: str) -> Any:
    tenant_id = _get_tenant_id()

    if request.is_json:
        payload = request.get_json() or {}
        property_address = payload.get("propertyaddress") or payload.get("property_address")
        inspector_name = payload.get("inspectorname") or payload.get("inspector_name")
    else:
        property_address = request.form.get("propertyaddress")
        inspector_name = request.form.get("inspectorname")

    try:
        report_data = heatlossservice.generate_report(
            batch_id=batch_id,
            property_address=property_address,
            inspector_name=inspector_name,
            tenant_id=tenant_id,
        )
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Report generation error: {e}"}), 500

    # Save HTML report
    html_path = batchio.get_report_html_path(batch_id, tenant_id)
    # Use heat_loss_report.html to match your actual template name
    html = render_template("heat_loss_report.html", reportdata=report_data)
    html_path.write_text(html, encoding="utf-8")

    return jsonify({"status": "ok", "batchid": batch_id})


@app.route("/report/<batch_id>", methods=["GET"])
def view_report(batch_id: str) -> str:
    tenant_id = _get_tenant_id()
    try:
        report_data = heatlossservice.get_report(batch_id, tenant_id)
    except FileNotFoundError:
        abort(404)

    return render_template("heat_loss_report.html", reportdata=report_data)


@app.route("/delete/<batch_id>", methods=["POST"])
def delete_batch(batch_id: str) -> Any:
    tenant_id = _get_tenant_id()
    try:
        batch_path = safe_batch_path(batch_id, tenant_id)
        if batch_path.exists():
            shutil.rmtree(batch_path)
        return jsonify({"status": "deleted", "batchid": batch_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/info", methods=["GET"])
def info() -> str:
    return render_template(
        "info.html",
        app_name=APP_NAME,
        app_version=APP_VERSION,
        description=settings.APP_DESCRIPTION,
    )


# --- API Routes ---

@app.route("/api/batches", methods=["GET"])
def api_list_batches() -> Any:
    tenant_id = _get_tenant_id()
    batches = batchservice.get_all_batches(tenant_id)
    return jsonify(batches)


@app.route("/api/batch/<batch_id>", methods=["GET"])
def api_get_batch(batch_id: str) -> Any:
    tenant_id = _get_tenant_id()
    try:
        data = batchservice.get_batch_summary(batch_id, tenant_id)
    except FileNotFoundError:
        return jsonify({"error": "Batch not found"}), 404
    return jsonify(data)


@app.route("/api/batch/<batch_id>/analysis", methods=["GET"])
def api_get_analysis(batch_id: str) -> Any:
    tenant_id = _get_tenant_id()
    try:
        analysis = heatlossservice.get_thermal_analysis(batch_id, tenant_id)
    except FileNotFoundError:
        return jsonify({"error": "Analysis not found"}), 404
    return jsonify(analysis)


# --- Error Handlers ---

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error"}), 500
    return render_template("500.html"), 500


if __name__ == "__main__":
    app.run(debug=settings.FLASK_DEBUG, host="0.0.0.0", port=5000)
