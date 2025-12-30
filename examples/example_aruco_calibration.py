#!/usr/bin/env python3
"""
Example 1: Scale Calibration Using ArUco Markers
Demonstrates how to use ArUco markers for spatial calibration
"""

import cv2
import numpy as np
from flir_calibration import ThermalCalibrator, process_with_calibration

def example_aruco_calibration():
    """
    Example: Use ArUco marker for scale calibration
    """
    print("=" * 70)
    print("EXAMPLE 1: SCALE CALIBRATION WITH ARUCO MARKERS")
    print("=" * 70)

    # Initialize calibrator
    config = {
        'aruco_marker': {
            'enabled': True,
            'size_mm': 50,  # Your ArUco marker is 50mm x 50mm
            'dict': 'DICT_6X6_250'
        }
    }

    calibrator = ThermalCalibrator(config=config)

    # Process image with ArUco marker visible
    image_path = "thermal_with_aruco.jpg"

    print(f"\nProcessing: {image_path}")
    results = process_with_calibration(image_path, calibrator, display=True)

    if results['aruco_detected']:
        print("\n✓ ArUco marker detected!")
        print(f"✓ Scale calibration: {calibrator.scale_pixels_per_unit:.2f} pixels/mm")

        # Now you can measure objects in the image
        # Example: measure a detected region
        example_bbox = (100, 100, 200, 150)  # x, y, w, h in pixels

        size_mm = calibrator.measure_object_size(example_bbox, unit='mm')
        size_cm = calibrator.measure_object_size(example_bbox, unit='cm')

        print(f"\nExample object measurement:")
        print(f"  {size_mm['width']:.1f} x {size_mm['height']:.1f} mm")
        print(f"  {size_cm['width']:.1f} x {size_cm['height']:.1f} cm")

        # Save calibration for later use
        calibrator.save_calibration('aruco_calibration.json')
        print("\n✓ Calibration saved to aruco_calibration.json")
    else:
        print("\n✗ No ArUco marker detected")
        print("  Make sure:")
        print("  - ArUco marker is visible in the image")
        print("  - Marker is from DICT_6X6_250 dictionary")
        print("  - Marker is not too small or distorted")


def generate_aruco_marker():
    """
    Generate an ArUco marker for printing
    """
    print("\n" + "=" * 70)
    print("GENERATING ARUCO MARKER FOR PRINTING")
    print("=" * 70)

    # Create ArUco dictionary
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

    # Generate marker with ID 42
    marker_id = 42
    marker_size = 400  # pixels (will be scaled for printing)

    marker_image = cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_size)

    # Save marker
    cv2.imwrite('aruco_marker_id42.png', marker_image)

    print(f"\n✓ ArUco marker (ID {marker_id}) saved to: aruco_marker_id42.png")
    print("\nTo use this marker:")
    print("1. Print it at exactly 50mm x 50mm size")
    print("2. Mount it on a flat surface")
    print("3. Include it in your thermal images")
    print("4. The calibrator will detect it automatically")


def example_using_saved_calibration():
    """
    Example: Load previously saved calibration
    """
    print("\n" + "=" * 70)
    print("USING SAVED CALIBRATION ON NEW IMAGES")
    print("=" * 70)

    # Create new calibrator
    calibrator = ThermalCalibrator()

    # Load previous calibration
    calibrator.load_calibration('aruco_calibration.json')

    print("\n✓ Calibration loaded")
    print(f"✓ Scale: {calibrator.scale_pixels_per_unit:.2f} pixels/mm")

    # Now process new images with this calibration
    # The ArUco marker doesn't need to be in every image
    new_images = ['thermal_001.jpg', 'thermal_002.jpg', 'thermal_003.jpg']

    for img_path in new_images:
        print(f"\nProcessing: {img_path}")
        # Process without needing ArUco in the image
        # Scale calibration is already loaded
        # You can still detect other features and measure objects


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("ARUCO MARKER CALIBRATION EXAMPLES")
    print("=" * 70)
    print("\nThis script demonstrates scale calibration using ArUco markers.")
    print("\nUncomment the function you want to run:")
    print("  1. generate_aruco_marker() - Generate marker for printing")
    print("  2. example_aruco_calibration() - Calibrate with marker")
    print("  3. example_using_saved_calibration() - Use saved calibration")

    # Uncomment to run:
    # generate_aruco_marker()
    # example_aruco_calibration()
    # example_using_saved_calibration()
