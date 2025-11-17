#!/usr/bin/env python3
"""
Example 2: Temperature Calibration Using Reference Objects
Demonstrates how to calibrate temperature readings using known references
"""

import numpy as np
from flir_calibration import ThermalCalibrator
from flirimageextractor import FlirImageExtractor

def example_single_point_calibration():
    """
    Example: Single point temperature calibration
    Use when you have one reference object of known temperature
    """
    print("=" * 70)
    print("EXAMPLE: SINGLE-POINT TEMPERATURE CALIBRATION")
    print("=" * 70)

    # Initialize
    calibrator = ThermalCalibrator()
    extractor = FlirImageExtractor()

    # Process image
    image_path = "thermal_with_reference.jpg"
    extractor.process_image(image_path)

    temp_data = extractor.get_thermal_np()
    rgb_image = extractor.get_rgb_np()

    print(f"\nImage processed: {temp_data.shape}")

    # Scenario: You have a reference object at a known temperature
    # For example, a calibrated thermometer showing 22.5°C

    # Method 1: Manually specify the reference point
    reference_center = (320, 240)  # Center of reference object in pixels
    x, y = reference_center

    # Get measured temperature at that point
    measured_temp = temp_data[y, x]
    expected_temp = 22.5  # Known temperature from calibrated thermometer

    print(f"\nReference point at {reference_center}:")
    print(f"  Measured: {measured_temp:.2f}°C")
    print(f"  Expected: {expected_temp:.2f}°C")
    print(f"  Difference: {measured_temp - expected_temp:.2f}°C")

    # Set manual reference
    calibrator.set_manual_reference(
        name='reference_thermometer',
        center=reference_center,
        measured_temp=measured_temp,
        expected_temp=expected_temp
    )

    # Calculate correction
    correction = calibrator.calculate_temp_correction(
        calibrator.calibration_data['manual_references']
    )

    print(f"\nCalculated correction:")
    print(f"  Method: {correction['method']}")
    print(f"  Offset: {correction['offset']:.2f}°C")

    # Apply correction
    corrected_temp = calibrator.apply_temp_correction(temp_data)

    # Verify correction at reference point
    corrected_ref_temp = corrected_temp[y, x]
    print(f"\nAfter correction:")
    print(f"  Reference point: {corrected_ref_temp:.2f}°C")
    print(f"  Error: {abs(corrected_ref_temp - expected_temp):.3f}°C")

    # Statistics
    print(f"\nOverall temperature adjustment:")
    print(f"  Original range: {np.min(temp_data):.1f} - {np.max(temp_data):.1f}°C")
    print(f"  Corrected range: {np.min(corrected_temp):.1f} - {np.max(corrected_temp):.1f}°C")

    return corrected_temp


def example_two_point_calibration():
    """
    Example: Two-point temperature calibration
    Use when you have two reference objects at different temperatures
    """
    print("\n" + "=" * 70)
    print("EXAMPLE: TWO-POINT TEMPERATURE CALIBRATION")
    print("=" * 70)

    # Initialize
    calibrator = ThermalCalibrator()
    extractor = FlirImageExtractor()

    # Process image with two reference objects
    image_path = "thermal_with_two_references.jpg"
    extractor.process_image(image_path)

    temp_data = extractor.get_thermal_np()

    # Scenario: You have two reference objects
    # - Ice water: 0°C
    # - Room temperature calibrated object: 23°C

    # Reference 1: Ice water
    ref1_center = (150, 200)
    x1, y1 = ref1_center
    measured_temp1 = temp_data[y1, x1]
    expected_temp1 = 0.0

    calibrator.set_manual_reference(
        name='ice_water',
        center=ref1_center,
        measured_temp=measured_temp1,
        expected_temp=expected_temp1
    )

    # Reference 2: Room temperature object
    ref2_center = (450, 200)
    x2, y2 = ref2_center
    measured_temp2 = temp_data[y2, x2]
    expected_temp2 = 23.0

    calibrator.set_manual_reference(
        name='room_temp_object',
        center=ref2_center,
        measured_temp=measured_temp2,
        expected_temp=expected_temp2
    )

    print(f"\nReference 1 (ice water):")
    print(f"  Measured: {measured_temp1:.2f}°C, Expected: {expected_temp1:.2f}°C")
    print(f"\nReference 2 (room temp):")
    print(f"  Measured: {measured_temp2:.2f}°C, Expected: {expected_temp2:.2f}°C")

    # Calculate linear correction
    correction = calibrator.calculate_temp_correction(
        calibrator.calibration_data['manual_references']
    )

    print(f"\nCalculated linear correction:")
    print(f"  T_corrected = {correction['scale']:.4f} * T_measured + {correction['offset']:.2f}")
    print(f"  RMSE: {correction.get('rmse', 0):.3f}°C")

    # Apply correction
    corrected_temp = calibrator.apply_temp_correction(temp_data)

    # Verify at both reference points
    corrected_temp1 = corrected_temp[y1, x1]
    corrected_temp2 = corrected_temp[y2, x2]

    print(f"\nVerification:")
    print(f"  Reference 1: {corrected_temp1:.2f}°C (expected {expected_temp1:.2f}°C)")
    print(f"  Reference 2: {corrected_temp2:.2f}°C (expected {expected_temp2:.2f}°C)")

    # Save calibration
    calibrator.save_calibration('two_point_calibration.json')
    print("\n✓ Calibration saved")

    return corrected_temp


def example_color_patch_calibration():
    """
    Example: Automatic detection and calibration using color patches
    """
    print("\n" + "=" * 70)
    print("EXAMPLE: COLOR PATCH AUTO-CALIBRATION")
    print("=" * 70)

    # Configure with color patches
    config = {
        'color_patches': {
            'enabled': True,
            'patches': [
                {
                    'name': 'blue_reference',
                    'hsv_lower': [100, 100, 100],
                    'hsv_upper': [130, 255, 255],
                    'expected_temp': 20.0  # Known temperature
                },
                {
                    'name': 'red_reference',
                    'hsv_lower': [0, 100, 100],
                    'hsv_upper': [10, 255, 255],
                    'expected_temp': 30.0  # Known temperature
                }
            ]
        }
    }

    calibrator = ThermalCalibrator(config=config)
    extractor = FlirImageExtractor()

    # Process image with colored reference patches
    image_path = "thermal_with_color_patches.jpg"
    extractor.process_image(image_path)

    temp_data = extractor.get_thermal_np()
    rgb_image = extractor.get_rgb_np()

    # Automatically detect color patches
    patches = calibrator.detect_color_patches(rgb_image, temp_data)

    print(f"\nDetected {len(patches)} color patch(es)")

    # Use detected patches as reference points
    reference_points = []
    for patch in patches:
        if patch['expected_temp'] is not None and patch['measured_temp'] is not None:
            reference_points.append({
                'name': patch['name'],
                'center': patch['center'],
                'measured_temp': patch['measured_temp'],
                'expected_temp': patch['expected_temp']
            })

            print(f"  {patch['name']}:")
            print(f"    Measured: {patch['measured_temp']:.2f}°C")
            print(f"    Expected: {patch['expected_temp']:.2f}°C")

    if reference_points:
        # Calculate correction
        correction = calibrator.calculate_temp_correction(reference_points)

        # Apply correction
        corrected_temp = calibrator.apply_temp_correction(temp_data)

        print(f"\n✓ Temperature calibration complete")

        return corrected_temp
    else:
        print("\n✗ No valid reference points found")
        return None


def example_batch_calibration():
    """
    Example: Apply same calibration to multiple images
    """
    print("\n" + "=" * 70)
    print("EXAMPLE: BATCH PROCESSING WITH CALIBRATION")
    print("=" * 70)

    # Create and calibrate on first image
    calibrator = ThermalCalibrator()
    extractor = FlirImageExtractor()

    # Calibration image with reference
    calib_image = "thermal_reference.jpg"
    extractor.process_image(calib_image)
    temp_data = extractor.get_thermal_np()

    # Set reference point (manual)
    calibrator.set_manual_reference(
        name='reference',
        center=(320, 240),
        measured_temp=temp_data[240, 320],
        expected_temp=22.0
    )

    # Calculate correction
    calibrator.calculate_temp_correction(
        calibrator.calibration_data['manual_references']
    )

    # Save calibration
    calibrator.save_calibration('batch_calibration.json')
    print("\n✓ Calibration created from reference image")

    # Now process multiple images with same calibration
    image_list = [
        'building_01.jpg',
        'building_02.jpg',
        'building_03.jpg'
    ]

    print(f"\nProcessing {len(image_list)} images with calibration...")

    results = []
    for img_path in image_list:
        try:
            extractor.process_image(img_path)
            temp_data = extractor.get_thermal_np()

            # Apply calibration
            corrected = calibrator.apply_temp_correction(temp_data)

            results.append({
                'filename': img_path,
                'min': np.min(corrected),
                'max': np.max(corrected),
                'mean': np.mean(corrected)
            })

            print(f"  ✓ {img_path}: {np.mean(corrected):.1f}°C avg")

        except Exception as e:
            print(f"  ✗ {img_path}: {e}")

    print(f"\n✓ Processed {len(results)}/{len(image_list)} images")

    return results


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("TEMPERATURE CALIBRATION EXAMPLES")
    print("=" * 70)
    print("\nThis script demonstrates temperature calibration methods.")
    print("\nUncomment the function you want to run:")
    print("  1. example_single_point_calibration()")
    print("  2. example_two_point_calibration()")
    print("  3. example_color_patch_calibration()")
    print("  4. example_batch_calibration()")

    # Uncomment to run:
    # example_single_point_calibration()
    # example_two_point_calibration()
    # example_color_patch_calibration()
    # example_batch_calibration()
