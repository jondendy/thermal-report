#!/usr/bin/env python3
"""
Example 3: Complete Integration - Building Survey Application
Demonstrates full workflow with all calibration features
"""

import cv2
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from flir_calibration import ThermalCalibrator
from flirimageextractor import FlirImageExtractor


class BuildingSurveyProcessor:
    """
    Complete building survey thermal image processor with calibration
    """

    def __init__(self, calibration_file=None):
        """
        Initialize processor

        Args:
            calibration_file: Optional path to saved calibration
        """
        # Configure for building surveys
        config = {
            'aruco_marker': {
                'enabled': True,
                'size_mm': 100,  # 100mm ArUco marker
                'dict': 'DICT_6X6_250'
            },
            'color_patches': {
                'enabled': True,
                'patches': [
                    {
                        'name': 'ambient_reference',
                        'hsv_lower': [100, 80, 80],
                        'hsv_upper': [130, 255, 255],
                        'expected_temp': None  # Will be set during calibration
                    }
                ]
            },
            'normalization': {
                'method': 'reference_based',
                'reference_temp_low': 15.0,
                'reference_temp_high': 35.0
            }
        }

        self.calibrator = ThermalCalibrator(config=config)
        self.extractor = FlirImageExtractor()

        # Load calibration if provided
        if calibration_file and Path(calibration_file).exists():
            self.calibrator.load_calibration(calibration_file)
            print(f"✓ Loaded calibration from {calibration_file}")

    def calibrate_from_reference_image(self, reference_image_path, 
                                      reference_temp=None, 
                                      reference_point=None):
        """
        Perform initial calibration using a reference image

        Args:
            reference_image_path: Path to image with reference objects
            reference_temp: Known temperature at reference point
            reference_point: (x, y) coordinates of reference point
        """
        print("\n" + "=" * 70)
        print("PERFORMING CALIBRATION")
        print("=" * 70)

        # Process reference image
        self.extractor.process_image(reference_image_path)
        temp_data = self.extractor.get_thermal_np()
        rgb_image = self.extractor.get_rgb_np()

        # Detect ArUco for scale calibration
        corners, ids, marked_img = self.calibrator.detect_aruco_markers(rgb_image)

        if ids is not None:
            print(f"✓ Scale calibration: {self.calibrator.scale_pixels_per_unit:.2f} px/mm")

        # Set temperature reference
        if reference_point and reference_temp:
            x, y = reference_point
            measured = temp_data[y, x]

            self.calibrator.set_manual_reference(
                name='ambient_reference',
                center=reference_point,
                measured_temp=measured,
                expected_temp=reference_temp
            )

            # Calculate correction
            self.calibrator.calculate_temp_correction(
                self.calibrator.calibration_data['manual_references']
            )

            print(f"✓ Temperature calibration complete")
            print(f"  Reference: {measured:.2f}°C -> {reference_temp:.2f}°C")

        # Save calibration
        self.calibrator.save_calibration('building_survey_calibration.json')
        print("✓ Calibration saved")

    def process_building_image(self, image_path, save_results=True):
        """
        Process a building thermal image with full analysis

        Args:
            image_path: Path to thermal image
            save_results: Whether to save processed images

        Returns:
            dict: Analysis results
        """
        print(f"\nProcessing: {Path(image_path).name}")
        print("-" * 70)

        # Extract thermal data
        self.extractor.process_image(image_path)
        temp_data = self.extractor.get_thermal_np()
        rgb_image = self.extractor.get_rgb_np()

        # Apply temperature correction
        corrected_temp = self.calibrator.apply_temp_correction(temp_data)

        # Detect features
        corners, ids, _ = self.calibrator.detect_aruco_markers(rgb_image, draw=False)
        patches = self.calibrator.detect_color_patches(rgb_image, corrected_temp)

        # Analyze temperature distribution
        valid_temps = corrected_temp[np.isfinite(corrected_temp)]

        # Find hot spots (>95th percentile)
        threshold_hot = np.percentile(valid_temps, 95)
        hot_spots = corrected_temp > threshold_hot

        # Find cold spots (<5th percentile)
        threshold_cold = np.percentile(valid_temps, 5)
        cold_spots = corrected_temp < threshold_cold

        # Calculate statistics
        stats = {
            'filename': Path(image_path).name,
            'min_temp': float(np.min(valid_temps)),
            'max_temp': float(np.max(valid_temps)),
            'mean_temp': float(np.mean(valid_temps)),
            'median_temp': float(np.median(valid_temps)),
            'std_temp': float(np.std(valid_temps)),
            'hot_spot_area': float(np.sum(hot_spots)),
            'cold_spot_area': float(np.sum(cold_spots)),
            'hot_spot_threshold': float(threshold_hot),
            'cold_spot_threshold': float(threshold_cold)
        }

        print(f"  Temperature range: {stats['min_temp']:.1f} - {stats['max_temp']:.1f}°C")
        print(f"  Mean: {stats['mean_temp']:.1f}°C, Std: {stats['std_temp']:.1f}°C")
        print(f"  Hot spots (>{threshold_hot:.1f}°C): {stats['hot_spot_area']:.0f} pixels")
        print(f"  Cold spots (<{threshold_cold:.1f}°C): {stats['cold_spot_area']:.0f} pixels")

        # Create visualizations
        if save_results:
            self._save_analysis_images(
                Path(image_path).stem,
                rgb_image, corrected_temp, hot_spots, cold_spots,
                corners, ids, patches
            )

        return {
            'statistics': stats,
            'temperature_data': corrected_temp,
            'hot_spots': hot_spots,
            'cold_spots': cold_spots
        }

    def _save_analysis_images(self, base_name, rgb_image, temp_data, 
                             hot_spots, cold_spots, corners, ids, patches):
        """Save analysis visualization images"""

        output_dir = Path('building_analysis_output')
        output_dir.mkdir(exist_ok=True)

        # Create comprehensive visualization
        fig = plt.figure(figsize=(16, 12))

        # 1. Original RGB with detections
        ax1 = plt.subplot(2, 3, 1)
        overlay = self.calibrator.create_calibration_overlay(
            rgb_image, corners, ids, patches
        )
        ax1.imshow(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))
        ax1.set_title('Original Image with Detections', fontsize=12)
        ax1.axis('off')

        # 2. Temperature map
        ax2 = plt.subplot(2, 3, 2)
        im2 = ax2.imshow(temp_data, cmap='jet', interpolation='nearest')
        ax2.set_title('Temperature Distribution', fontsize=12)
        ax2.axis('off')
        plt.colorbar(im2, ax=ax2, fraction=0.046, label='Temperature (°C)')

        # 3. Hot spots
        ax3 = plt.subplot(2, 3, 3)
        hot_overlay = rgb_image.copy()
        hot_overlay[hot_spots] = [0, 0, 255]  # Red overlay for hot spots
        hot_overlay = cv2.addWeighted(rgb_image, 0.6, hot_overlay, 0.4, 0)
        ax3.imshow(cv2.cvtColor(hot_overlay, cv2.COLOR_BGR2RGB))
        ax3.set_title('Hot Spots (>95th percentile)', fontsize=12)
        ax3.axis('off')

        # 4. Cold spots
        ax4 = plt.subplot(2, 3, 4)
        cold_overlay = rgb_image.copy()
        cold_overlay[cold_spots] = [255, 0, 0]  # Blue overlay for cold spots
        cold_overlay = cv2.addWeighted(rgb_image, 0.6, cold_overlay, 0.4, 0)
        ax4.imshow(cv2.cvtColor(cold_overlay, cv2.COLOR_BGR2RGB))
        ax4.set_title('Cold Spots (<5th percentile)', fontsize=12)
        ax4.axis('off')

        # 5. Temperature histogram
        ax5 = plt.subplot(2, 3, 5)
        valid_temps = temp_data[np.isfinite(temp_data)].flatten()
        ax5.hist(valid_temps, bins=50, color='steelblue', alpha=0.7)
        ax5.axvline(np.mean(valid_temps), color='red', linestyle='--', 
                   label=f'Mean: {np.mean(valid_temps):.1f}°C')
        ax5.axvline(np.median(valid_temps), color='green', linestyle='--', 
                   label=f'Median: {np.median(valid_temps):.1f}°C')
        ax5.set_xlabel('Temperature (°C)', fontsize=11)
        ax5.set_ylabel('Frequency', fontsize=11)
        ax5.set_title('Temperature Distribution Histogram', fontsize=12)
        ax5.legend()
        ax5.grid(True, alpha=0.3)

        # 6. Statistics text
        ax6 = plt.subplot(2, 3, 6)
        ax6.axis('off')

        stats_text = f"""
        TEMPERATURE STATISTICS
        ----------------------
        Minimum:  {np.min(valid_temps):.2f} °C
        Maximum:  {np.max(valid_temps):.2f} °C
        Mean:     {np.mean(valid_temps):.2f} °C
        Median:   {np.median(valid_temps):.2f} °C
        Std Dev:  {np.std(valid_temps):.2f} °C
        Range:    {np.max(valid_temps) - np.min(valid_temps):.2f} °C

        ANOMALY DETECTION
        -----------------
        Hot spot threshold:  >{np.percentile(valid_temps, 95):.1f} °C
        Cold spot threshold: <{np.percentile(valid_temps, 5):.1f} °C

        Hot spot area:  {np.sum(hot_spots)} pixels
        Cold spot area: {np.sum(cold_spots)} pixels

        CALIBRATION STATUS
        ------------------
        Scale calibrated: {'Yes' if self.calibrator.scale_pixels_per_unit else 'No'}
        Temp calibrated:  {'Yes' if self.calibrator.temp_correction_params else 'No'}
        """

        ax6.text(0.1, 0.5, stats_text, fontsize=10, family='monospace',
                verticalalignment='center', transform=ax6.transAxes)

        plt.tight_layout()

        # Save figure
        output_file = output_dir / f'{base_name}_analysis.png'
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"  ✓ Analysis saved: {output_file}")

    def process_multiple_buildings(self, image_paths, generate_report=True):
        """
        Process multiple building images and generate comparison report

        Args:
            image_paths: List of image paths
            generate_report: Whether to generate comparison report

        Returns:
            list: Results for each image
        """
        print("\n" + "=" * 70)
        print("BATCH PROCESSING BUILDING SURVEY IMAGES")
        print("=" * 70)

        results = []

        for img_path in image_paths:
            try:
                result = self.process_building_image(img_path)
                results.append(result)
            except Exception as e:
                print(f"  ✗ Error: {e}")

        print(f"\n✓ Processed {len(results)}/{len(image_paths)} images")

        if generate_report and results:
            self._generate_comparison_report(results)

        return results

    def _generate_comparison_report(self, results):
        """Generate comparison report across multiple images"""

        print("\n" + "=" * 70)
        print("COMPARISON REPORT")
        print("=" * 70)

        # Extract statistics
        filenames = [r['statistics']['filename'] for r in results]
        means = [r['statistics']['mean_temp'] for r in results]
        maxs = [r['statistics']['max_temp'] for r in results]
        mins = [r['statistics']['min_temp'] for r in results]
        hot_areas = [r['statistics']['hot_spot_area'] for r in results]

        # Find extremes
        hottest_idx = np.argmax(maxs)
        coldest_idx = np.argmin(mins)
        most_uniform_idx = np.argmin([r['statistics']['std_temp'] for r in results])

        print(f"\nHottest building: {filenames[hottest_idx]}")
        print(f"  Max temperature: {maxs[hottest_idx]:.1f}°C")

        print(f"\nColdest building: {filenames[coldest_idx]}")
        print(f"  Min temperature: {mins[coldest_idx]:.1f}°C")

        print(f"\nMost uniform: {filenames[most_uniform_idx]}")
        print(f"  Std dev: {results[most_uniform_idx]['statistics']['std_temp']:.2f}°C")

        print(f"\nAverage across all buildings:")
        print(f"  Mean temperature: {np.mean(means):.1f}°C")
        print(f"  Temperature range: {np.min(mins):.1f} - {np.max(maxs):.1f}°C")


def main():
    """
    Complete building survey workflow example
    """
    print("=" * 70)
    print("BUILDING SURVEY - COMPLETE WORKFLOW")
    print("=" * 70)

    # Initialize processor
    processor = BuildingSurveyProcessor()

    # Step 1: Calibrate using reference image
    print("\nStep 1: Calibration")
    print("-" * 70)

    # Calibrate with a reference image that has:
    # - ArUco marker for scale
    # - Known temperature reference point

    reference_image = "building_reference.jpg"
    reference_temp = 22.0  # Measured with calibrated thermometer
    reference_point = (320, 240)  # Center of reference object

    processor.calibrate_from_reference_image(
        reference_image,
        reference_temp=reference_temp,
        reference_point=reference_point
    )

    # Step 2: Process individual building images
    print("\nStep 2: Process Building Images")
    print("-" * 70)

    building_images = [
        "building_facade_01.jpg",
        "building_facade_02.jpg",
        "building_facade_03.jpg"
    ]

    results = processor.process_multiple_buildings(
        building_images,
        generate_report=True
    )

    # Step 3: Export calibration for future use
    print("\nStep 3: Export Results")
    print("-" * 70)

    # Generate calibration report
    calib_report = processor.calibrator.generate_calibration_report()

    print("\nCalibration report:")
    if calib_report['scale_calibration']:
        print(f"  Scale: {calib_report['scale_calibration']['pixels_per_mm']:.2f} px/mm")
    if calib_report['temperature_correction']:
        tc = calib_report['temperature_correction']
        print(f"  Temp correction: scale={tc.get('scale', 1):.4f}, "
              f"offset={tc.get('offset', 0):.2f}°C")

    print("\n✓ Building survey complete!")
    print("✓ Results saved to: building_analysis_output/")


if __name__ == '__main__':
    main()
