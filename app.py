#!/usr/bin/env python3
"""
Flask entrypoint for the Thermal Report web tool.
Canonical routes that match edit_spots.html, index.html, and JS expectations.
"""
from __future__ import annotations

import json
import shutil
from typing import Any
from flask import Flask, render_template, request, jsonify, abort, url_for
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
    files = request.files.getlist("files")

    if not files or len(files) == 0:
        return jsonify({"error": "No files uploaded"}), 400

    try:
        batch_id, summary = batchservice.process_batch(files, tenant_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Processing error: {e}"}), 500

    return jsonify({"batchid": batch_id, "results": {"summary": summary}})


@app.route("/editspots/<batchid>", methods=["GET"])
def editspots(batchid: str) -> str:
    """Display thermal hotspot editing interface."""
    tenant_id = _get_tenant_id()
    try:
        # Load analysis data for the UI
        analysisdata = heatlossservice.get_thermal_analysis(batchid, tenant_id)
        
        # Load existing labels if they exist
        existinglabels = heatlossservice.get_existing_labels(batchid, tenant_id)
        
        # Spot types for the dropdown
        spottypes = ["Window", "Door", "Wall", "Eaves", "Vent", "Roof", "Chimney", "Porch"]
        
        # Initialize empty savedlinks and saveddocuments if they don't exist
        savedlinks = existinglabels.get("links", []) if existinglabels else []
        saveddocuments = existinglabels.get("documents", []) if existinglabels else []
        
        return render_template(
            "editspots.html",
            batchid=batchid,
            analysisdata=analysisdata,
            existinglabels=existinglabels,
            spottypes=spottypes,
            savedlinks=savedlinks,
            saveddocuments=saveddocuments,
        )
    except Exception as e:
        return jsonify({"error": f"An error occurred loading the labeling interface: {e}"}), 500


@app.route("/savelabels/<batchid>", methods=["POST"])
def savelabels(batchid: str) -> Any:
    """Save hot spot labels submitted by operator."""
    tenant_id = _get_tenant_id()
    try:
        labeldata = request.get_json(force=True)
        savedlabels = heatlossservice.save_labels(batchid, labeldata, tenant_id)
        return jsonify({
            "success": True,
            "message": "Labels saved successfully",
            "labels": savedlabels,
        })
    except FileNotFoundError:
        return jsonify({"error": "Batch not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Failed to save labels: {e}"}), 500


@app.route("/generateheatlossreport/<batchid>", methods=["POST"])
def generateheatlossreport(batchid: str) -> Any:
    """Generate professional heat loss report from labeled hot spots."""
    tenant_id = _get_tenant_id()
    
    # Get form parameters for report metadata
    if request.is_json:
        payload = request.get_json() or {}
        propertyaddress = payload.get("propertyaddress")
        inspectorname = payload.get("inspectorname")
    else:
        propertyaddress = request.form.get("propertyaddress")
        inspectorname = request.form.get("inspectorname")
    
    try:
        reportdata = heatlossservice.generate_report(
            batchid,
            propertyaddress=propertyaddress,
            inspectorname=inspectorname,
            tenant_id=tenant_id,
        )
        
        # Return success with URL to view the report
        return jsonify({
            "success": True,
            "message": "Heat loss report generated successfully",
            "reporturl": url_for("viewheatlossreport", batchid=batchid),
        })
    except FileNotFoundError as e:
        return jsonify({
            "error": "Required data not found. Please ensure hotspots are labeled.",
        }), 404
    except ValueError as e:
        return jsonify({"error": f"Invalid input data: {e}"}), 400
    except Exception as e:
        return jsonify({"error": f"Report generation failed: {e}"}), 500


@app.route("/viewheatlossreport/<batchid>", methods=["GET"])
def viewheatlossreport(batchid: str) -> str:
    """Display the final professional heat loss report."""
    tenant_id = _get_tenant_id()
    try:
        reportdata = heatlossservice.get_report(batchid, tenant_id)
        return render_template("heatlossreport.html", reportdata=reportdata)
    except FileNotFoundError:
        return "Report not found. Please generate the report first.", 404
    except Exception as e:
        return f"An error occurred loading the report: {e}", 500


@app.route("/delete/<batchid>", methods=["POST"])
def deletebatch(batchid: str) -> Any:
    """Delete a batch and its associated files."""
    tenant_id = _get_tenant_id()
    try:
        batchdir = safe_batch_path(batchid, tenant_id)
        if batchdir.exists():
            shutil.rmtree(batchdir)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": f"Invalid batch ID: {e}"}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to delete batch: {e}"}), 500


@app.route("/info", methods=["GET"])
def info() -> str:
    return render_template(
        "info.html",
        app_name=APP_NAME,
        app_version=APP_VERSION,
    )


# --- API Routes ---

@app.route("/api/batches", methods=["GET"])
def api_list_batches() -> Any:
    tenant_id = _get_tenant_id()
    batches = batchservice.get_all_batches(tenant_id)
    return jsonify(batches)


@app.route("/api/batch/<batchid>", methods=["GET"])
def api_get_batch(batchid: str) -> Any:
    tenant_id = _get_tenant_id()
    try:
        data = batchservice.get_batch_summary(batchid, tenant_id)
    except FileNotFoundError:
        return jsonify({"error": "Batch not found"}), 404
    return jsonify(data)


@app.route("/api/batch/<batchid>/analysis", methods=["GET"])
def api_get_analysis(batchid: str) -> Any:
    tenant_id = _get_tenant_id()
    try:
        analysis = heatlossservice.get_thermal_analysis(batchid, tenant_id)
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
