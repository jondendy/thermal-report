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
        # Loa
