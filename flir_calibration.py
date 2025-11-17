#!/usr/bin/env python3
"""
FLIR Thermal Image Calibration and Reference Object Detection
Extends the FLIR extraction scripts with:
- Reference color patch detection
- Scale calibration using ArUco markers or known objects
- Temperature calibration using reference objects
- Cross-image normalization
"""

import cv2
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json

# Assumes you have the FLIR processor from previous code
try:
    from flirimageextractor import FlirImageExtractor
    HAS_FLIR_EXTRACTOR = True
except ImportError:
    HAS_FLIR_EXTRACTOR = False
    print("Warning: flirimageextractor not found. Some features may be limited.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ThermalCalibrator:
    """
    Calibration system for thermal images with reference object detection
    """

    def __init__(self, config=None):
        """
        Initialize calibrator with optional configuration

        Args:
            config (dict): Configuration dictionary with reference object specs
        """
        self.config = config or self._default_config()
        self.calibration_data = {}
        self.scale_pixels_per_unit = None
        self.temp_correction_params = {}

        # Initialize ArUco detector
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
        self.aruco_params = cv2.aruco.DetectorParameters()

        logger.info("Thermal Calibrator initialized")

    def _default_config(self):
        """Default configuration for reference objects"""
        return {
            'aruco_marker': {
                'enabled': True,
                'size_mm': 50,  # Physical size in mm
                'dict': 'DICT_6X6_250'
            },
            'color_patches': {
                'enabled': True,
                'patches': [
                    {
                        'name': 'red',
                        'hsv_lower': [0, 100, 100],
                        'hsv_upper': [10, 255, 255],
                        'expected_temp': None  # Will be set manually
                    },
                    {
                        'name': 'blue',
                        'hsv_lower': [100, 100, 100],
                        'hsv_upper': [130, 255, 255],
                        'expected_temp': None
                    },
                    {
                        'name': 'green',
                        'hsv_lower': [40, 50, 50],
                        'hsv_upper': [80, 255, 255],
                        'expected_temp': None
                    }
                ]
            },
            'reference_temps': {
                'enabled': True,
                'objects': [
                    {
                        'name': 'ambient_reference',
                        'expected_temp': None,  # Set during calibration
                        'detection_method': 'manual'  # or 'color', 'marker'
                    }
                ]
            },
            'normalization': {
                'method': 'min_max',  # or 'z_score', 'reference_based'
                'reference_temp_low': 20.0,
                'reference_temp_high': 30.0
            }
        }

    def detect_aruco_markers(self, image, draw=True):
        """
        Detect ArUco markers in image for scale calibration

        Args:
            image: Input image (RGB or BGR)
            draw: Whether to draw detected markers

        Returns:
            tuple: (corners, ids, annotated_image)
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # Detect markers
        corners, ids, rejected = cv2.aruco.detectMarkers(
            gray, self.aruco_dict, parameters=self.aruco_params
        )

        result_image = image.copy()

        if ids is not None:
            logger.info(f"Detected {len(ids)} ArUco marker(s)")

            if draw:
                cv2.aruco.drawDetectedMarkers(result_image, corners, ids)

            # Calculate pixels per mm for each marker
            for i, (corner, marker_id) in enumerate(zip(corners, ids)):
                # Corner points are in order: top-left, top-right, bottom-right, bottom-left
                corner_points = corner[0]

                # Calculate width and height in pixels
                width_px = np.linalg.norm(corner_points[0] - corner_points[1])
                height_px = np.linalg.norm(corner_points[1] - corner_points[2])

                # Average size in pixels
                avg_size_px = (width_px + height_px) / 2

                # Calculate pixels per mm
                marker_size_mm = self.config['aruco_marker']['size_mm']
                pixels_per_mm = avg_size_px / marker_size_mm

                logger.info(f"Marker {marker_id[0]}: {pixels_per_mm:.2f} pixels/mm")

                # Store the first marker's calibration
                if self.scale_pixels_per_unit is None:
                    self.scale_pixels_per_unit = pixels_per_mm
                    self.calibration_data['scale_calibration'] = {
                        'pixels_per_mm': pixels_per_mm,
                        'marker_id': int(marker_id[0]),
                        'marker_size_mm': marker_size_mm
                    }
        else:
            logger.warning("No ArUco markers detected")

        return corners, ids, result_image

    def detect_color_patches(self, image, temp_data=None):
        """
        Detect colored reference patches in image

        Args:
            image: Input RGB/BGR image
            temp_data: Optional temperature data array

        Returns:
            dict: Detected patches with locations and temperatures
        """
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        detected_patches = []

        for patch_config in self.config['color_patches']['patches']:
            # Create mask for this color
            lower = np.array(patch_config['hsv_lower'])
            upper = np.array(patch_config['hsv_upper'])
            mask = cv2.inRange(hsv_image, lower, upper)

            # Apply morphological operations to clean up
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

            # Find contours
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if contours:
                # Get the largest contour
                largest_contour = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(largest_contour)

                # Filter by minimum area
                if area > 100:  # Minimum 100 pixels
                    # Get bounding box
                    x, y, w, h = cv2.boundingRect(largest_contour)

                    # Calculate center
                    center_x = x + w // 2
                    center_y = y + h // 2

                    # Get temperature if available
                    measured_temp = None
                    if temp_data is not None:
                        # Get average temperature in the patch region
                        roi = temp_data[y:y+h, x:x+w]
                        valid_temps = roi[np.isfinite(roi)]
                        if len(valid_temps) > 0:
                            measured_temp = float(np.mean(valid_temps))

                    patch_info = {
                        'name': patch_config['name'],
                        'bbox': (x, y, w, h),
                        'center': (center_x, center_y),
                        'area': area,
                        'measured_temp': measured_temp,
                        'expected_temp': patch_config['expected_temp']
                    }

                    detected_patches.append(patch_info)
                    logger.info(f"Detected {patch_config['name']} patch at ({center_x}, {center_y})")

        return detected_patches

    def detect_reference_object(self, image, temp_data, object_config):
        """
        Detect a reference object of known temperature

        Args:
            image: Input image
            temp_data: Temperature array
            object_config: Configuration for this object

        Returns:
            dict: Detection results
        """
        detection_method = object_config.get('detection_method', 'manual')

        if detection_method == 'manual':
            # Manual specification - will be set via set_manual_reference()
            return None
        elif detection_method == 'color':
            # Use color detection
            patches = self.detect_color_patches(image, temp_data)
            matching = [p for p in patches if p['name'] == object_config.get('color_name')]
            return matching[0] if matching else None
        else:
            logger.warning(f"Unknown detection method: {detection_method}")
            return None

    def set_manual_reference(self, name, center, measured_temp, expected_temp=None):
        """
        Manually specify a reference point

        Args:
            name: Reference name
            center: (x, y) coordinates
            measured_temp: Measured temperature at this point
            expected_temp: Expected/known temperature
        """
        if 'manual_references' not in self.calibration_data:
            self.calibration_data['manual_references'] = []

        self.calibration_data['manual_references'].append({
            'name': name,
            'center': center,
            'measured_temp': measured_temp,
            'expected_temp': expected_temp
        })

        logger.info(f"Manual reference '{name}' set at {center}: "
                   f"measured={measured_temp:.2f}°C, expected={expected_temp}°C")

    def calculate_temp_correction(self, reference_points):
        """
        Calculate temperature correction parameters based on reference points

        Args:
            reference_points: List of dicts with 'measured_temp' and 'expected_temp'

        Returns:
            dict: Correction parameters
        """
        # Extract measured and expected temperatures
        measured = np.array([p['measured_temp'] for p in reference_points 
                           if p['expected_temp'] is not None])
        expected = np.array([p['expected_temp'] for p in reference_points 
                           if p['expected_temp'] is not None])

        if len(measured) < 1:
            logger.warning("No reference points with expected temperatures")
            return {'method': 'none', 'offset': 0.0, 'scale': 1.0}

        if len(measured) == 1:
            # Single point: offset correction only
            offset = expected[0] - measured[0]
            correction = {
                'method': 'offset',
                'offset': float(offset),
                'scale': 1.0
            }
            logger.info(f"Single-point correction: offset = {offset:.2f}°C")
        else:
            # Multiple points: linear correction
            # T_corrected = scale * T_measured + offset
            coeffs = np.polyfit(measured, expected, 1)
            scale = coeffs[0]
            offset = coeffs[1]

            correction = {
                'method': 'linear',
                'scale': float(scale),
                'offset': float(offset)
            }

            # Calculate correction error
            corrected = scale * measured + offset
            rmse = np.sqrt(np.mean((corrected - expected) ** 2))

            logger.info(f"Linear correction: T_corrected = {scale:.4f} * T_measured + {offset:.2f}")
            logger.info(f"Correction RMSE: {rmse:.3f}°C")

            correction['rmse'] = float(rmse)

        self.temp_correction_params = correction
        return correction

    def apply_temp_correction(self, temp_data, correction_params=None):
        """
        Apply temperature correction to data

        Args:
            temp_data: Temperature array
            correction_params: Correction parameters (uses stored if None)

        Returns:
            numpy.ndarray: Corrected temperature data
        """
        if correction_params is None:
            correction_params = self.temp_correction_params

        if not correction_params or correction_params.get('method') == 'none':
            logger.info("No temperature correction applied")
            return temp_data.copy()

        corrected = temp_data.copy()
        scale = correction_params.get('scale', 1.0)
        offset = correction_params.get('offset', 0.0)

        # Apply correction
        corrected = scale * corrected + offset

        logger.info(f"Temperature correction applied: "
                   f"scale={scale:.4f}, offset={offset:.2f}°C")

        return corrected

    def normalize_temperatures(self, temp_data, method=None):
        """
        Normalize temperature data for cross-image comparison

        Args:
            temp_data: Temperature array
            method: Normalization method ('min_max', 'z_score', 'reference_based')

        Returns:
            numpy.ndarray: Normalized temperature data
        """
        if method is None:
            method = self.config['normalization']['method']

        valid_temps = temp_data[np.isfinite(temp_data)]

        if len(valid_temps) == 0:
            logger.warning("No valid temperatures for normalization")
            return temp_data

        normalized = temp_data.copy()

        if method == 'min_max':
            # Scale to [0, 1] range
            min_temp = np.min(valid_temps)
            max_temp = np.max(valid_temps)

            if max_temp > min_temp:
                normalized = (temp_data - min_temp) / (max_temp - min_temp)

            logger.info(f"Min-max normalization: [{min_temp:.2f}, {max_temp:.2f}] -> [0, 1]")

        elif method == 'z_score':
            # Standardize to mean=0, std=1
            mean_temp = np.mean(valid_temps)
            std_temp = np.std(valid_temps)

            if std_temp > 0:
                normalized = (temp_data - mean_temp) / std_temp

            logger.info(f"Z-score normalization: mean={mean_temp:.2f}, std={std_temp:.2f}")

        elif method == 'reference_based':
            # Normalize based on reference temperatures
            ref_low = self.config['normalization']['reference_temp_low']
            ref_high = self.config['normalization']['reference_temp_high']

            normalized = (temp_data - ref_low) / (ref_high - ref_low)

            logger.info(f"Reference-based normalization: "
                       f"[{ref_low}, {ref_high}] -> [0, 1]")

        return normalized

    def measure_object_size(self, bbox, unit='mm'):
        """
        Measure object size using scale calibration

        Args:
            bbox: Bounding box (x, y, w, h) in pixels
            unit: Unit to return ('mm', 'cm', 'in')

        Returns:
            dict: Width and height in specified unit
        """
        if self.scale_pixels_per_unit is None:
            logger.warning("No scale calibration available")
            return None

        x, y, w, h = bbox

        # Convert pixels to mm
        width_mm = w / self.scale_pixels_per_unit
        height_mm = h / self.scale_pixels_per_unit

        # Convert to requested unit
        if unit == 'cm':
            width = width_mm / 10
            height = height_mm / 10
        elif unit == 'in':
            width = width_mm / 25.4
            height = height_mm / 25.4
        else:  # mm
            width = width_mm
            height = height_mm

        return {
            'width': width,
            'height': height,
            'unit': unit
        }

    def create_calibration_overlay(self, image, corners=None, ids=None, patches=None):
        """
        Create visualization overlay showing detected reference objects

        Args:
            image: Input image
            corners: ArUco marker corners
            ids: ArUco marker IDs
            patches: Detected color patches

        Returns:
            numpy.ndarray: Annotated image
        """
        overlay = image.copy()

        # Draw ArUco markers
        if corners is not None and ids is not None:
            cv2.aruco.drawDetectedMarkers(overlay, corners, ids)

            # Add scale information
            if self.scale_pixels_per_unit:
                text = f"Scale: {self.scale_pixels_per_unit:.2f} px/mm"
                cv2.putText(overlay, text, (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Draw color patches
        if patches:
            for patch in patches:
                x, y, w, h = patch['bbox']
                color = (0, 255, 0) if patch['measured_temp'] else (0, 0, 255)

                # Draw rectangle
                cv2.rectangle(overlay, (x, y), (x + w, y + h), color, 2)

                # Draw label
                label = patch['name']
                if patch['measured_temp']:
                    label += f" {patch['measured_temp']:.1f}°C"

                cv2.putText(overlay, label, (x, y - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Draw manual references
        if 'manual_references' in self.calibration_data:
            for ref in self.calibration_data['manual_references']:
                cx, cy = ref['center']
                cv2.circle(overlay, (cx, cy), 5, (255, 0, 0), -1)

                label = f"{ref['name']}: {ref['measured_temp']:.1f}°C"
                cv2.putText(overlay, label, (cx + 10, cy),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        return overlay

    def generate_calibration_report(self):
        """
        Generate a calibration report

        Returns:
            dict: Comprehensive calibration report
        """
        report = {
            'scale_calibration': self.calibration_data.get('scale_calibration'),
            'temperature_correction': self.temp_correction_params,
            'manual_references': self.calibration_data.get('manual_references', []),
            'normalization_config': self.config['normalization']
        }

        return report

    def save_calibration(self, filepath):
        """Save calibration data to JSON file"""
        report = self.generate_calibration_report()
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        logger.info(f"Calibration saved to {filepath}")

    def load_calibration(self, filepath):
        """Load calibration data from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)

        if 'scale_calibration' in data:
            self.calibration_data['scale_calibration'] = data['scale_calibration']
            self.scale_pixels_per_unit = data['scale_calibration']['pixels_per_mm']

        if 'temperature_correction' in data:
            self.temp_correction_params = data['temperature_correction']

        if 'manual_references' in data:
            self.calibration_data['manual_references'] = data['manual_references']

        logger.info(f"Calibration loaded from {filepath}")


def process_with_calibration(image_path, calibrator, display=True):
    """
    Process a FLIR image with calibration

    Args:
        image_path: Path to FLIR image
        calibrator: ThermalCalibrator instance
        display: Whether to display results

    Returns:
        dict: Processing results
    """
    if not HAS_FLIR_EXTRACTOR:
        logger.error("flirimageextractor required")
        return None

    # Extract thermal data
    extractor = FlirImageExtractor()
    extractor.process_image(image_path)

    temp_data = extractor.get_thermal_np()
    rgb_image = extractor.get_rgb_np()

    # Detect ArUco markers for scale calibration
    corners, ids, marked_image = calibrator.detect_aruco_markers(rgb_image)

    # Detect color patches
    patches = calibrator.detect_color_patches(rgb_image, temp_data)

    # Apply temperature correction if available
    corrected_temp = calibrator.apply_temp_correction(temp_data)

    # Create visualization
    overlay = calibrator.create_calibration_overlay(rgb_image, corners, ids, patches)

    # Display if requested
    if display:
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(2, 2, figsize=(14, 12))

        # Original RGB
        axes[0, 0].imshow(cv2.cvtColor(rgb_image, cv2.COLOR_BGR2RGB))
        axes[0, 0].set_title('Original Image')
        axes[0, 0].axis('off')

        # Detection overlay
        axes[0, 1].imshow(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
        axes[0, 1].set_title('Detected References')
        axes[0, 1].axis('off')

        # Temperature (uncorrected)
        im1 = axes[1, 0].imshow(temp_data, cmap='jet')
        axes[1, 0].set_title('Temperature (Uncorrected)')
        axes[1, 0].axis('off')
        plt.colorbar(im1, ax=axes[1, 0], fraction=0.046)

        # Temperature (corrected)
        im2 = axes[1, 1].imshow(corrected_temp, cmap='jet')
        axes[1, 1].set_title('Temperature (Corrected)')
        axes[1, 1].axis('off')
        plt.colorbar(im2, ax=axes[1, 1], fraction=0.046)

        plt.tight_layout()
        plt.show()

    results = {
        'temperature_data': corrected_temp,
        'rgb_image': rgb_image,
        'aruco_detected': ids is not None and len(ids) > 0,
        'patches_detected': len(patches),
        'patches': patches,
        'scale_calibrated': calibrator.scale_pixels_per_unit is not None
    }

    return results


if __name__ == '__main__':
    # Example usage
    print("Thermal Image Calibration System")
    print("=" * 60)
    print("\nThis module extends FLIR thermal image processing with:")
    print("  - ArUco marker detection for scale calibration")
    print("  - Color patch detection for reference points")
    print("  - Temperature correction using reference objects")
    print("  - Cross-image normalization")
    print("\nSee example scripts for usage demonstrations.")
