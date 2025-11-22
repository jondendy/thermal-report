#!/usr/bin/env python3
"""
FLIR Thermal Image Processor for Building Surveys
Extracts temperature data from FLIR radiometric JPG files
Author: Generated for Building Survey Application
Date: November 2025
"""

import subprocess
import json
import numpy as np
import os
import sys
from pathlib import Path
from PIL import Image
import io
import struct
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FlirImageProcessor:
    """
    Process FLIR radiometric JPG files to extract temperature data
    """

    def __init__(self, exiftool_path='exiftool'):
        """
        Initialize the FLIR image processor

        Args:
            exiftool_path (str): Path to exiftool executable (default: 'exiftool')
        """
        self.exiftool_path = exiftool_path
        self._check_exiftool()

    def _check_exiftool(self):
        """Check if exiftool is available"""
        try:
            subprocess.run([self.exiftool_path, '-ver'], 
                         capture_output=True, check=True)
            logger.info("ExifTool found and working")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.error("ExifTool not found. Please install it:")
            logger.error("Ubuntu/Debian: sudo apt install libimage-exiftool-perl")
            logger.error("Windows: Download from https://exiftool.org/")
            logger.error("MacOS: brew install exiftool")
            raise RuntimeError("ExifTool is required but not found")

    def extract_metadata(self, image_path):
        """
        Extract FLIR metadata from image using exiftool

        Args:
            image_path (str): Path to FLIR image file

        Returns:
            dict: Metadata dictionary
        """
        try:
            # Run exiftool to get JSON metadata
            result = subprocess.run(
                [self.exiftool_path, '-j', '-b', str(image_path)],
                capture_output=True,
                text=True,
                check=True
            )

            metadata = json.loads(result.stdout)[0]
            logger.info(f"Successfully extracted metadata from {Path(image_path).name}")
            return metadata

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to extract metadata: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse metadata JSON: {e}")
            raise

    def extract_raw_thermal_data(self, image_path):
        """
        Extract raw thermal data from FLIR image

        Args:
            image_path (str): Path to FLIR image file

        Returns:
            numpy.ndarray: Raw thermal data as 16-bit unsigned integers
        """
        try:
            # Extract raw thermal image data
            result = subprocess.run(
                [self.exiftool_path, '-b', '-RawThermalImage', str(image_path)],
                capture_output=True,
                check=True
            )

            raw_data = result.stdout

            # Try to load as PNG first (common for newer FLIR cameras)
            try:
                img = Image.open(io.BytesIO(raw_data))
                thermal_np = np.array(img)
                logger.info(f"Loaded thermal data as PNG: shape {thermal_np.shape}")
                return thermal_np
            except:
                # If PNG fails, try to interpret as raw binary data
                # This requires knowing the image dimensions
                metadata = self.extract_metadata(image_path)

                # Try different metadata field names for dimensions
                width = None
                height = None

                for w_field in ['RawThermalImageWidth', 'ImageWidth', 'ExifImageWidth']:
                    if w_field in metadata:
                        width = int(metadata[w_field])
                        break

                for h_field in ['RawThermalImageHeight', 'ImageHeight', 'ExifImageHeight']:
                    if h_field in metadata:
                        height = int(metadata[h_field])
                        break

                if width and height:
                    # Assume 16-bit little-endian unsigned integers
                    thermal_np = np.frombuffer(raw_data, dtype=np.uint16)
                    thermal_np = thermal_np.reshape((height, width))
                    logger.info(f"Loaded thermal data as raw binary: shape {thermal_np.shape}")
                    return thermal_np
                else:
                    raise ValueError("Could not determine thermal image dimensions")

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to extract raw thermal data: {e}")
            raise
        except Exception as e:
            logger.error(f"Error processing raw thermal data: {e}")
            raise

    def raw_to_temperature(self, raw_data, metadata):
        """
        Convert raw thermal data to temperature values in Celsius
        Uses Planck's law and FLIR calibration parameters

        Args:
            raw_data (numpy.ndarray): Raw thermal sensor values
            metadata (dict): Image metadata containing calibration parameters

        Returns:
            numpy.ndarray: Temperature values in Celsius
        """
        # Extract calibration parameters from metadata
        # These field names may vary by camera model

        # Planck constants
        try:
            R1 = float(metadata.get('PlanckR1', 21546.0))
            R2 = float(metadata.get('PlanckR2', 0.012545258))
            B = float(metadata.get('PlanckB', 1501.0))
            F = float(metadata.get('PlanckF', 1.0))
            O = float(metadata.get('PlanckO', -7340.0))

            # Atmospheric and object parameters
            emissivity = float(metadata.get('Emissivity', 0.95))
            obj_dist = float(metadata.get('ObjectDistance', 1.0))
            refl_temp = float(metadata.get('ReflectedApparentTemperature', 20.0))
            atm_temp = float(metadata.get('AtmosphericTemperature', 20.0))
            ir_window_temp = float(metadata.get('IRWindowTemperature', 20.0))
            ir_window_trans = float(metadata.get('IRWindowTransmission', 1.0))
            rel_humidity = float(metadata.get('RelativeHumidity', 50.0))

            # Atmospheric transmission parameters
            try:
                alpha1 = float(metadata.get('AtmosphericTransAlpha1', 0.006569))
                alpha2 = float(metadata.get('AtmosphericTransAlpha2', 0.012620))
                beta1 = float(metadata.get('AtmosphericTransBeta1', -0.002276))
                beta2 = float(metadata.get('AtmosphericTransBeta2', -0.006670))
                X = float(metadata.get('AtmosphericTransX', 1.9))
            except:
                # Default values if atmospheric parameters not available
                alpha1 = 0.006569
                alpha2 = 0.012620
                beta1 = -0.002276
                beta2 = -0.006670
                X = 1.9

            logger.info("Using calibration parameters:")
            logger.info(f"  R1={R1}, R2={R2}, B={B}, F={F}, O={O}")
            logger.info(f"  Emissivity={emissivity}, Distance={obj_dist}m")

        except Exception as e:
            logger.warning(f"Error reading calibration parameters: {e}")
            logger.warning("Using default parameters - results may be inaccurate")
            R1, R2, B, F, O = 21546.0, 0.012545258, 1501.0, 1.0, -7340.0
            emissivity = 0.95
            obj_dist = 1.0
            refl_temp = 20.0
            atm_temp = 20.0
            ir_window_temp = 20.0
            ir_window_trans = 1.0
            rel_humidity = 50.0
            alpha1, alpha2, beta1, beta2, X = 0.006569, 0.012620, -0.002276, -0.006670, 1.9

        # Convert raw values to radiance
        # FLIR uses: Signal = R1/(R2*(exp(B/T)-F)) - O
        # Solving for T: T = B / ln(R1/(R2*(Signal+O)) + F)

        raw_data = raw_data.astype(np.float64)

        # Calculate atmospheric transmission
        h2o = rel_humidity
        tau = X * np.exp(-np.sqrt(obj_dist) * (alpha1 + beta1 * np.sqrt(h2o))) + \
              (1 - X) * np.exp(-np.sqrt(obj_dist) * (alpha2 + beta2 * np.sqrt(h2o)))

        # Pseudo radiance of reflected temperature
        refl_temp_K = refl_temp + 273.15
        r1 = ((1 - emissivity) / emissivity) * (R1 / (R2 * (np.exp(B / refl_temp_K) - F)) - O)

        # Pseudo radiance of atmospheric temperature
        atm_temp_K = atm_temp + 273.15
        r2 = ((1 - tau) / (emissivity * tau)) * (R1 / (R2 * (np.exp(B / atm_temp_K) - F)) - O)

        # Pseudo radiance of window
        ir_window_temp_K = ir_window_temp + 273.15
        r3 = ((1 - ir_window_trans) / (emissivity * tau * ir_window_trans)) * \
             (R1 / (R2 * (np.exp(B / ir_window_temp_K) - F)) - O)

        # Correct raw signal
        raw_obj = (raw_data - O - r1 - r2 - r3) / (emissivity * tau * ir_window_trans)

        # Convert to temperature
        # Handle potential mathematical errors
        with np.errstate(divide='ignore', invalid='ignore'):
            temp_K = B / np.log(R1 / (R2 * (raw_obj + O)) + F)
            temp_C = temp_K - 273.15

        # Replace invalid values with NaN
        temp_C[~np.isfinite(temp_C)] = np.nan

        logger.info(f"Temperature conversion complete")

        return temp_C

    def get_temperature_statistics(self, temp_data):
        """
        Calculate temperature statistics

        Args:
            temp_data (numpy.ndarray): Temperature data in Celsius

        Returns:
            dict: Statistics dictionary
        """
        valid_temps = temp_data[np.isfinite(temp_data)]

        if len(valid_temps) == 0:
            logger.warning("No valid temperature data found")
            return {
                'min': np.nan,
                'max': np.nan,
                'mean': np.nan,
                'median': np.nan,
                'std': np.nan
            }

        stats = {
            'min': float(np.min(valid_temps)),
            'max': float(np.max(valid_temps)),
            'mean': float(np.mean(valid_temps)),
            'median': float(np.median(valid_temps)),
            'std': float(np.std(valid_temps))
        }

        return stats

    def process_image(self, image_path, display=False):
        """
        Process a single FLIR image and extract temperature data

        Args:
            image_path (str): Path to FLIR image
            display (bool): Whether to display visualization

        Returns:
            tuple: (temperature_data, metadata, statistics)
        """
        logger.info(f"\nProcessing image: {image_path}")
        logger.info("=" * 60)

        # Check if file exists
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Extract metadata
        metadata = self.extract_metadata(image_path)

        # Extract raw thermal data
        raw_data = self.extract_raw_thermal_data(image_path)

        # Convert to temperature
        temp_data = self.raw_to_temperature(raw_data, metadata)

        # Calculate statistics
        stats = self.get_temperature_statistics(temp_data)

        # Display statistics
        logger.info("\nTemperature Statistics:")
        logger.info(f"  Minimum:  {stats['min']:.2f} °C")
        logger.info(f"  Maximum:  {stats['max']:.2f} °C")
        logger.info(f"  Mean:     {stats['mean']:.2f} °C")
        logger.info(f"  Median:   {stats['median']:.2f} °C")
        logger.info(f"  Std Dev:  {stats['std']:.2f} °C")

        # Optional visualization
        if display:
            try:
                import matplotlib.pyplot as plt

                fig, axes = plt.subplots(1, 2, figsize=(12, 5))

                # Display visual image
                visual_img = Image.open(image_path)
                axes[0].imshow(visual_img)
                axes[0].set_title('Visual Image')
                axes[0].axis('off')

                # Display thermal image
                im = axes[1].imshow(temp_data, cmap='jet', interpolation='nearest')
                axes[1].set_title(f'Thermal Image\n{stats["min"]:.1f}°C to {stats["max"]:.1f}°C')
                axes[1].axis('off')
                plt.colorbar(im, ax=axes[1], label='Temperature (°C)')

                plt.tight_layout()
                plt.show()

            except ImportError:
                logger.warning("Matplotlib not available for visualization")

        return temp_data, metadata, stats

    def process_folder(self, folder_path, output_csv=None):
        """
        Process all FLIR images in a folder

        Args:
            folder_path (str): Path to folder containing FLIR images
            output_csv (str): Optional path to save results as CSV

        Returns:
            dict: Dictionary mapping filenames to (temp_data, metadata, stats)
        """
        folder = Path(folder_path)

        if not folder.exists():
            raise FileNotFoundError(f"Folder not found: {folder_path}")

        # Find all image files
        image_extensions = ['.jpg', '.jpeg', '.JPG', '.JPEG']
        image_files = []
        for ext in image_extensions:
            image_files.extend(folder.glob(f'*{ext}'))

        if not image_files:
            logger.warning(f"No image files found in {folder_path}")
            return {}

        logger.info(f"\nFound {len(image_files)} images to process")
        logger.info("=" * 60)

        results = {}
        summary_data = []

        for img_file in sorted(image_files):
            try:
                temp_data, metadata, stats = self.process_image(str(img_file), display=False)
                results[img_file.name] = (temp_data, metadata, stats)

                summary_data.append({
                    'filename': img_file.name,
                    'min_temp': stats['min'],
                    'max_temp': stats['max'],
                    'mean_temp': stats['mean'],
                    'median_temp': stats['median'],
                    'std_temp': stats['std']
                })

            except Exception as e:
                logger.error(f"Failed to process {img_file.name}: {e}")
                continue

        # Save summary to CSV if requested
        if output_csv and summary_data:
            import csv
            with open(output_csv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=summary_data[0].keys())
                writer.writeheader()
                writer.writerows(summary_data)
            logger.info(f"\nSummary saved to {output_csv}")

        logger.info(f"\nProcessed {len(results)} images successfully")

        return results


def main():
    """
    Main function with example usage
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Process FLIR thermal images for building surveys',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process a single image
  python flir_processor.py -i thermal_image.jpg -d

  # Process all images in a folder
  python flir_processor.py -f ./thermal_images/ -o summary.csv

  # Process single image and save temperature data
  python flir_processor.py -i image.jpg --save-temp temps.npy
        """
    )

    parser.add_argument('-i', '--image', help='Single FLIR image to process')
    parser.add_argument('-f', '--folder', help='Folder containing FLIR images')
    parser.add_argument('-d', '--display', action='store_true', 
                       help='Display visualization (requires matplotlib)')
    parser.add_argument('-o', '--output', help='Output CSV file for batch results')
    parser.add_argument('--save-temp', help='Save temperature array to numpy file')
    parser.add_argument('--exiftool', default='exiftool', 
                       help='Path to exiftool executable')

    args = parser.parse_args()

    if not args.image and not args.folder:
        parser.print_help()
        sys.exit(1)

    # Create processor
    processor = FlirImageProcessor(exiftool_path=args.exiftool)

    # Process single image
    if args.image:
        temp_data, metadata, stats = processor.process_image(args.image, display=args.display)

        if args.save_temp:
            np.save(args.save_temp, temp_data)
            logger.info(f"Temperature data saved to {args.save_temp}")

    # Process folder
    if args.folder:
        results = processor.process_folder(args.folder, output_csv=args.output)


if __name__ == '__main__':
    main()
