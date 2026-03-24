"""
Thermal Data Service - FLIR temperature extraction and management

Extracts per-pixel temperature data from FLIR thermal images.
Uses exiftool to extract raw thermal data and converts to temperature values.
"""

import json
import subprocess
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Dict
import logging

logger = logging.getLogger(__name__)

# Plausible building-survey Celsius range used for sanity checks.
# Values outside this range indicate a failed / incorrect extraction.
_PLAUSIBLE_MIN = -60.0
_PLAUSIBLE_MAX = 200.0


def _is_plausible(arr: np.ndarray) -> bool:
    """Return True only if the array median sits in a plausible building-survey range."""
    if arr is None or arr.size == 0:
        return False
    median = float(np.median(arr))
    return _PLAUSIBLE_MIN <= median <= _PLAUSIBLE_MAX


class ThermalDataExtractor:
    """
    Extracts and manages temperature data from FLIR thermal images.
    """

    def __init__(self, exiftool_path='exiftool'):
        self.exiftool_path = exiftool_path

    def extract_thermal_data(self, image_path: Path) -> Optional[np.ndarray]:
        """
        Extract raw thermal data from FLIR image and convert to temperatures.

        Returns:
            2D numpy array of temperature values in Celsius, or None if extraction
            fails OR if the result is outside a plausible building-survey range.
        """
        try:
            raw_thermal = self._extract_raw_thermal(image_path)
            if raw_thermal is None:
                logger.warning(f"Failed to extract raw thermal data from {image_path}")
                return None

            params = self._extract_calibration_params(image_path)
            if params is None:
                # No calibration params — we cannot trust any conversion, so
                # return None rather than produce garbage via a fallback.
                logger.warning(
                    f"No calibration params for {image_path} — "
                    "skipping thermal data extraction to avoid corrupt values."
                )
                return None

            temperatures = self._convert_to_temperature(raw_thermal, params)

            if not _is_plausible(temperatures):
                logger.warning(
                    f"Planck result for {image_path} has median "
                    f"{float(np.median(temperatures)):.1f}°C — outside plausible range, "
                    "discarding."
                )
                return None

            logger.info(
                f"Extracted thermal data: {temperatures.shape}, "
                f"range {temperatures.min():.1f}°C to {temperatures.max():.1f}°C"
            )
            return temperatures

        except Exception as e:
            logger.exception(f"Error extracting thermal data from {image_path}: {e}")
            return None

    def _extract_raw_thermal(self, image_path: Path) -> Optional[np.ndarray]:
        """
        Extract raw thermal image data using exiftool.
        """
        try:
            cmd = [self.exiftool_path, '-b', '-RawThermalImage', str(image_path)]
            result = subprocess.run(cmd, capture_output=True, check=True)

            if not result.stdout:
                return None

            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(result.stdout))
                return np.array(img)
            except Exception:
                return np.frombuffer(result.stdout, dtype=np.uint16)

        except subprocess.CalledProcessError as e:
            logger.error(f"Exiftool failed: {e}")
            return None
        except Exception as e:
            logger.exception(f"Error extracting raw thermal: {e}")
            return None

    def _extract_calibration_params(self, image_path: Path) -> Optional[Dict]:
        """
        Extract FLIR calibration parameters for temperature conversion.
        Returns None if any of the key Planck constants are missing from metadata.
        """
        try:
            cmd = [
                self.exiftool_path,
                '-json',
                '-Planck*',
                '-Atmospheric*',
                '-Emissivity',
                '-ObjectDistance',
                '-ReflectedApparentTemperature',
                str(image_path)
            ]
            result = subprocess.run(cmd, capture_output=True, check=True, text=True)

            if not result.stdout:
                return None

            metadata = json.loads(result.stdout)[0]

            # Require the critical Planck constants to actually be present in EXIF.
            # If they're missing, the image likely isn't a genuine FLIR radiometric JPEG.
            required = ['PlanckR1', 'PlanckR2', 'PlanckB']
            missing = [k for k in required if k not in metadata]
            if missing:
                logger.warning(
                    f"{image_path}: missing Planck constants {missing} — "
                    "cannot perform calibrated conversion."
                )
                return None

            params = {
                'R1': float(metadata['PlanckR1']),
                'R2': float(metadata['PlanckR2']),
                'B':  float(metadata['PlanckB']),
                'F':  float(metadata.get('PlanckF', 1)),
                'O':  float(metadata.get('PlanckO', -7340)),
                'emissivity':     float(metadata.get('Emissivity', 0.95)),
                'distance':       float(str(metadata.get('ObjectDistance', 1.0)).split()[0]),
                'reflected_temp': float(str(metadata.get('ReflectedApparentTemperature', 20.0)).split()[0]),
                'atm_temp':       float(str(metadata.get('AtmosphericTemperature', 20.0)).split()[0]),
                'atm_trans':      float(metadata.get('AtmosphericTransAlpha1', 0.006569)),
            }
            return params

        except Exception as e:
            logger.exception(f"Error extracting calibration params: {e}")
            return None

    def _convert_to_temperature(self, raw_data: np.ndarray, params: Dict) -> np.ndarray:
        """
        Convert raw thermal values to temperature in Celsius using the FLIR Planck equation.

        Guards against log(negative/zero) producing NaN or inf.
        """
        R1 = params['R1']
        R2 = params['R2']
        B  = params['B']
        F  = params['F']
        O  = params['O']

        raw = raw_data.astype(np.float32)

        # FLIR Planck formula: T(K) = B / ln(R1 / (R2*(raw+O)) + F)
        radiance = (raw + O) / R2

        # Avoid log(<=0)
        safe_radiance = np.where(radiance > 0, radiance, 1e-10)
        log_arg = R1 / safe_radiance + F
        log_arg = np.clip(log_arg, 1.0 + 1e-10, None)

        temp_kelvin  = B / np.log(log_arg)
        temp_celsius = temp_kelvin - 273.15

        return temp_celsius

    def get_temperature_at_point(
        self,
        temperatures: np.ndarray,
        x: int,
        y: int,
        visual_width: Optional[int] = None,
        visual_height: Optional[int] = None,
    ) -> Optional[float]:
        """
        Get temperature value at specific coordinates.
        """
        try:
            scaled_x, scaled_y = x, y
            thermal_height, thermal_width = temperatures.shape

            if visual_width is not None and visual_height is not None:
                scaled_x = int(x * thermal_width  / visual_width)
                scaled_y = int(y * thermal_height / visual_height)

            if 0 <= scaled_y < thermal_height and 0 <= scaled_x < thermal_width:
                return float(temperatures[scaled_y, scaled_x])

            logger.warning(
                f"Coordinates ({scaled_x}, {scaled_y}) out of bounds "
                f"({thermal_width}x{thermal_height})"
            )
            return None

        except Exception as e:
            logger.exception(f"Error getting temperature at ({x}, {y}): {e}")
            return None


def save_thermal_data(batch_path: Path, image_name: str, thermal_data: np.ndarray):
    """
    Save extracted thermal data to disk.
    Refuses to save if the data looks implausible (corrupt extraction).
    """
    try:
        if not _is_plausible(thermal_data):
            logger.warning(
                f"Refusing to save thermal data for {image_name}: "
                f"median {float(np.median(thermal_data)):.1f}°C is outside plausible range."
            )
            return

        thermal_dir = batch_path / 'thermal_data'
        thermal_dir.mkdir(exist_ok=True)

        thermal_file = thermal_dir / f"{Path(image_name).stem}_thermal.npz"
        np.savez_compressed(thermal_file, temperatures=thermal_data)
        logger.info(f"Saved thermal data for {image_name}")

    except Exception as e:
        logger.exception(f"Error saving thermal data for {image_name}: {e}")


def load_thermal_data(batch_path: Path, image_name: str) -> Optional[np.ndarray]:
    """
    Load previously extracted thermal data.

    Returns:
        2D array of temperature values, or None if not found or implausible.
    """
    try:
        thermal_file = batch_path / 'thermal_data' / f"{Path(image_name).stem}_thermal.npz"

        if not thermal_file.exists():
            logger.warning(f"Thermal data file not found: {thermal_file}")
            return None

        data = np.load(thermal_file)
        arr = data['temperatures']

        if not _is_plausible(arr):
            logger.warning(
                f"Loaded thermal data for {image_name} has median "
                f"{float(np.median(arr)):.1f}°C — discarding as implausible."
            )
            return None

        return arr

    except Exception as e:
        logger.exception(f"Error loading thermal data for {image_name}: {e}")
        return None
