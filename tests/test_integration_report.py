"""
High-level integration checks for thermal-report.

These tests do NOT try to be exhaustive; they focus on the issues
we've seen in manual runs:

1. Address and surveyor metadata appear in the final report.
2. The report uses _labeled images (with hotspots) rather than raw images.
3. get_temperature_at_point returns reasonable values for a known pixel.
4. Automatic hotspot coordinates are not all clumped near (0, 0).
5. Appendix link is propagated into the report.

The tests emit a summary text report to the repo root:
    test_integration_report.txt
"""

import io
import json
import re
from pathlib import Path
from typing import Dict, Any, Tuple, List, Optional

import numpy as np
import pytest

from app import app  # adjust if your Flask app is exposed differently
from services.thermal_data_service import ThermalDataExtractor


# Paths and configuration
REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_IMAGE = REPO_ROOT / "upload" / "FLIR1468.jpg"
REPORTS_ROOT = REPO_ROOT / "reports" / "batches"

# Where we write the human-readable summary
SUMMARY_PATH = REPO_ROOT / "test_integration_report.txt"


@pytest.fixture(scope="session")
def flask_client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def _write_summary(lines: List[str]) -> None:
    SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")


def _extract_batch_id_from_upload_response(resp_data: Dict[str, Any]) -> str:
    """
    Helper: extract the batch_id returned by /upload (JSON or HTML).
    Adjust this if your /upload endpoint returns differently.
    """
    # If JSON:
    if isinstance(resp_data, dict) and "batch_id" in resp_data:
        return resp_data["batch_id"]

    # Fallback: try regex from HTML
    text = str(resp_data)
    m = re.search(r"batch[_-]\d{8}[_-]\d{6}[_-][0-9a-fA-F]+", text)
    if not m:
        raise AssertionError("Could not find batch ID in upload response")
    return m.group(0)


def _get_report_text(client, batch_id: str) -> str:
    """
    Fetch the rendered HTML report text, which is what wkhtmltopdf (or similar)
    will convert into the PDF. We use /view_heat_loss_report/<batch_id>.
    """
    resp = client.get(f"/view_heat_loss_report/{batch_id}")
    assert resp.status_code == 200, f"view_heat_loss_report failed: {resp.status_code}"
    return resp.get_data(as_text=True)


def _find_hotspot_coordinates_from_csv(batch_path: Path, image_stem: str) -> List[Tuple[int, int]]:
    """
    Example helper to load hotspot CSV (if you write one) and return coordinates.
    Adjust to match your actual format. For now, this just returns an empty list
    if no hotspot CSV is present.
    """
    csv_path = batch_path / f"{image_stem}_temperatures.csv"
    if not csv_path.exists():
        return []

    # You might have (x,y,temp) or similar; adapt as needed.
    # Here we do nothing specific, just placeholder.
    # Example:
    # import csv
    # coords = []
    # with csv_path.open(newline="") as f:
    #     reader = csv.DictReader(f)
    #     for row in reader:
    #         coords.append((int(row["x"]), int(row["y"])))
    # return coords
    return []


def test_integration_end_to_end(flask_client):
    """
    Single end-to-end style test that:

    - Uploads one sample image with metadata (address, inspector, appendix_url).
    - Triggers processing and report generation.
    - Inspects the generated HTML report to confirm:
        * Address and inspector appear.
        * Appendix link appears.
        * _labeled images are referenced.
    - Exercises ThermalDataExtractor.get_temperature_at_point with a synthetic
      temperature array.
    - Checks that auto hotspots (if any) are not all at (0, 0).
    """

    summary: List[str] = []
    summary.append("Thermal-report integration test summary")
    summary.append("======================================")
    summary.append("")

    # --- Sanity check: sample image exists ---
    assert SAMPLE_IMAGE.exists(), f"Sample image not found: {SAMPLE_IMAGE}"
    summary.append(f"[OK] Sample image exists: {SAMPLE_IMAGE}")

    # --- Step 1: upload image with metadata ---
    address = "123 Test Street"
    inspector = "Test Surveyor Dendy"
    appendix_url = "https://drive.google.com/file/d/1QJAXrvwvP32By_6j8Uf8a-hU5c_B7VZJ/view?usp=drive_link"

    data = {
        "address": address,
        "inspector": inspector,
        "appendix_url": appendix_url,
    }

    with SAMPLE_IMAGE.open("rb") as f:
        upload_data = {
            "batch_name": "default",
            "files[]": (io.BytesIO(f.read()), SAMPLE_IMAGE.name),        }

        resp = flask_client.post(
            "/upload",
            data={**data, **upload_data},
            content_type="multipart/form-data",
        )

    assert resp.status_code in (200, 201), f"Upload failed: {resp.status_code}"
    summary.append(f"[OK] Upload route returned {resp.status_code}")

    # Try to parse JSON, else fallback to plain text
    try:
        resp_json = resp.get_json() or {}
    except Exception:
        resp_json = {}

    batch_id = _extract_batch_id_from_upload_response(resp_json or resp.get_data(as_text=True))
    summary.append(f"[OK] Derived batch_id from upload response: {batch_id}")

    # --- Step 2: trigger report generation ---
    resp_gen = flask_client.post(f"/generate_heat_loss_report/{batch_id}")
    assert resp_gen.status_code == 200, f"Report generation failed: {resp_gen.status_code}"
    summary.append("[OK] generate_heat_loss_report returned 200")

    # --- Step 3: fetch report HTML ---
    report_html = _get_report_text(flask_client, batch_id)
    summary.append("[OK] view_heat_loss_report returned HTML")

    # --- Step 4: validate address & surveyor presence ---
    addr_present = address in report_html
    inspector_present = inspector in report_html

    if addr_present:
        summary.append(f"[OK] Address '{address}' appears in the report.")
    else:
        summary.append(f"[ISSUE] Address '{address}' does NOT appear in the report.")

    if inspector_present:
        summary.append(f"[OK] Inspector/Surveyor '{inspector}' appears in the report.")
    else:
        summary.append(f"[ISSUE] Inspector/Surveyor '{inspector}' does NOT appear in the report.")

    # --- Step 5: validate appendix link presence ---
    appendix_present = appendix_url in report_html
    if appendix_present:
        summary.append(f"[OK] Appendix URL '{appendix_url}' appears in the report.")
    else:
        summary.append(f"[ISSUE] Appendix URL '{appendix_url}' does NOT appear in the report.")

    # --- Step 6: validate labeled images in report ---
    # We expect at least one reference to *_labeled.jpg in the report HTML.
    labeled_refs = re.findall(r"FLIR\d+_labeled\.jpg", report_html)
    if labeled_refs:
        unique_refs = sorted(set(labeled_refs))
        summary.append(f"[OK] Report references labeled images: {', '.join(unique_refs)}")
    else:
        summary.append("[ISSUE] Report does not reference any *_labeled.jpg images; "
                       "it may be using raw/unlabeled images.")

    # --- Step 7: synthetic test for get_temperature_at_point ---
    extractor = ThermalDataExtractor(exiftool_path="exiftool")  # path not used for synthetic
    # Create a simple synthetic 4x3 thermal array with known values
    temperatures = np.arange(12, dtype=np.float32).reshape(3, 4)  # shape (3,4)
    visual_width, visual_height = 400, 300  # pretend canvas size

    # Pick a visual coordinate that should map near the center
    x_visual = 200
    y_visual = 150
    temp_value = extractor.get_temperature_at_point(
        temperatures,
        x_visual,
        y_visual,
        visual_width=visual_width,
        visual_height=visual_height,
    )

    if temp_value is None:
        summary.append("[ISSUE] get_temperature_at_point returned None for a valid synthetic "
                       "coordinate; coordinate scaling or bounds logic may be incorrect.")
    else:
        summary.append(f"[OK] get_temperature_at_point returned {temp_value:.2f} "
                       "for synthetic test array.")

    # --- Step 8: check auto hotspot clustering (if detectable via data files) ---
    # We look under the reports directory for this batch and image.
    report_batch_dir = REPORTS_ROOT / "default" / batch_id
    image_stem = SAMPLE_IMAGE.stem  # e.g. "FLIR1468"
    hotspot_coords = _find_hotspot_coordinates_from_csv(report_batch_dir, image_stem)

    if hotspot_coords:
        # Count how many are at or very near (0,0)
        near_origin = [
            (x, y) for x, y in hotspot_coords if abs(x) <= 2 and abs(y) <= 2
        ]
        if len(near_origin) == len(hotspot_coords):
            summary.append("[ISSUE] All auto hotspot coordinates are near (0,0); "
                           "there may be a coordinate mapping bug causing clustering.")
        else:
            summary.append("[OK] Auto hotspot coordinates are not all clumped at (0,0).")
    else:
        summary.append("[WARN] Could not load hotspot coordinates from CSV. "
                       "Auto-hotspot clustering not checked by tests; inspect the CSV "
                       "format and update _find_hotspot_coordinates_from_csv.")

    # --- Final: write summary file and assert no critical issues if you want ---
    _write_summary(summary)

    # Optionally, fail the test if any [ISSUE] lines exist.
    issues = [line for line in summary if line.startswith("[ISSUE]")]
    if issues:
        pytest.fail(
            "One or more integration issues detected. See "
            f"{SUMMARY_PATH} for details:\n" + "\n".join(issues)
        )

