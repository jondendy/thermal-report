#!/usr/bin/env python3
"""
Flir thermal data extractor bridge.

Called by server/thermal.ts as a subprocess:
  python3 flir_extract.py <image_path>

Outputs a single JSON object to stdout:
  {
    "width":  <int>,
    "height": <int>,
    "min":    <float>,   # degrees C
    "max":    <float>,
    "mean":   <float>,
    "median": <float>,
    "std":    <float>,
    "data":   "<base64-encoded little-endian float32 array, row-major>"
  }

Errors are written to stderr and exit code is non-zero.
"""

import sys
import json
import base64
import struct
import os

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: flir_extract.py <image_path>"}), file=sys.stderr)
        sys.exit(1)

    image_path = sys.argv[1]

    if not os.path.exists(image_path):
        print(json.dumps({"error": f"File not found: {image_path}"}), file=sys.stderr)
        sys.exit(1)

    try:
        import numpy as np
        from flirimageextractor import FlirImageExtractor
    except ImportError as e:
        print(json.dumps({"error": f"Import error: {e}. Ensure flirimageextractor and numpy are installed."}), file=sys.stderr)
        sys.exit(1)

    try:
        extractor = FlirImageExtractor()
        extractor.process_image(image_path)

        # Raw temperature array in degrees C — no HUD, no annotations
        temp_data = extractor.get_thermal_np()

        # Remove NaN / Inf before stats
        valid = temp_data[np.isfinite(temp_data)]
        if valid.size == 0:
            raise ValueError("No valid temperature data found in image")

        height, width = temp_data.shape

        stats = {
            "width":  int(width),
            "height": int(height),
            "min":    float(np.min(valid)),
            "max":    float(np.max(valid)),
            "mean":   float(np.mean(valid)),
            "median": float(np.median(valid)),
            "std":    float(np.std(valid)),
        }

        # Normalise to 0-1 range (same contract as the old RGB-luminance approach)
        # so detectHotspots() and the .bin cache format are unchanged.
        t_min = stats["min"]
        t_max = stats["max"]
        t_range = t_max - t_min if t_max != t_min else 1.0

        flat = temp_data.flatten().astype(np.float32)
        normalised = ((flat - t_min) / t_range).astype(np.float32)

        # Base64-encode as little-endian float32
        encoded = base64.b64encode(normalised.tobytes()).decode("ascii")

        result = {**stats, "data": encoded}
        print(json.dumps(result))

    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
