#!/usr/bin/env python3
"""
Flask entrypoint for the Thermal Report web tool.

Provides:
  - Home page with batch upload and batch list
  - Edit spots (label hotspots) page
  - Report generation and viewing
  - JSON API endpoints for integration
"""

from __future__ import annotations

import json
from typing import Any, Dict

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    send_file,
    abort,
)

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

from lib.security_utils import validate_tenant_id

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
app.config["SECRET_KEY"] = "change-me-in-production"


# ---------------------------------------------------------------------------
# Helper: tenant extraction
# ---------------------------------------------------------------------------

def _get_tenant_id() -> str:
    # In multi-tenant deployments, extract from headers or auth.
    # For now, read from query or default.
    tenant_id = request.args.get("tenant") or None
    return validate_tenant_id(tenant_id)


# ---------------------------------------------------------------------------
# Web routes
# ---------------------------------------------------------------------------

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
    files = request.files.getlist("files")
    
    # ADD THIS DEBUG OUTPUT
    print(f"DEBUG: Received {len(files)} files")
    for f in files:
        print(f"  - {f.filename} ({f.content_type})")
    
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

    return render_template(
        "editspots.html",
        batch=batch_summary,
        analysis=analysis,
        labels=json.dumps(labels),
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

    # Optionally render HTML immediately using template
    html_path = batchio.get_report_html_path(batch_id, tenant_id)
    html = render_template("heatlossreport.html", reportdata=report_data)
    html_path.write_text(html, encoding="utf-8")

    return jsonify({"status": "ok", "batchid": batch_id})


@app.route("/report/<batch_id>", methods=["GET"])
def view_report(batch_id: str) -> str:
    tenant_id = _get_tenant_id()
    try:
        report_data = heatlossservice.get_report(batch_id, tenant_id)
    except FileNotFoundError:
        abort(404)

    return render_template("heatlossreport.html", reportdata=report_data)


@app.route("/info", methods=["GET"])
def info() -> str:
    return render_template(
        "info.html",
        app_name=APP_NAME,
        app_version=APP_VERSION,
        description=settings.APP_DESCRIPTION,
    )


# ---------------------------------------------------------------------------
# JSON API routes
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(error):  # type: ignore[override]
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):  # type: ignore[override]
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error"}), 500
    return render_template("500.html"), 500


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=settings.FLASK_DEBUG, host="0.0.0.0", port=5000)
