#!/usr/bin/env python3
"""
Advanced Batch Processor for FLIR Thermal Images
Handles multiple images with statistics, reports, and error handling
"""

import numpy as np
import os
import csv
import json
from pathlib import Path
from datetime import datetime
import logging

try:
    from flirimageextractor import FlirImageExtractor
except ImportError:
    print("ERROR: Please install flirimageextractor")
    print("Run: pip install flirimageextractor")
    exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('flir_batch_processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BatchThermalProcessor:
    """
    Advanced batch processor for FLIR thermal images
    """

    def __init__(self, output_dir='./processed_thermal'):
        """
        Initialize batch processor

        Args:
            output_dir (str): Directory for output files
        """
        self.extractor = FlirImageExtractor()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        self.results = []
        self.errors = []

        logger.info(f"Batch processor initialized. Output: {self.output_dir}")

    def process_image_safe(self, image_path):
        """
        Safely process a single image with error handling

        Args:
            image_path (str or Path): Path to image

        Returns:
            dict or None: Processing results or None if failed
        """
        image_path = Path(image_path)

        try:
            logger.info(f"Processing: {image_path.name}")

            # Check if file is a FLIR thermal image
            self.extractor.process_image(str(image_path))

            # Get temperature data
            temp_data = self.extractor.get_thermal_np()

            if temp_data is None or temp_data.size == 0:
                raise ValueError("No thermal data extracted")

            # Calculate statistics
            valid_temps = temp_data[np.isfinite(temp_data)]

            if len(valid_temps) == 0:
                raise ValueError("No valid temperature values")

            result = {
                'filename': image_path.name,
                'filepath': str(image_path.absolute()),
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'shape': temp_data.shape,
                'pixels': temp_data.size,
                'valid_pixels': len(valid_temps),
                'min_temp': float(np.min(valid_temps)),
                'max_temp': float(np.max(valid_temps)),
                'mean_temp': float(np.mean(valid_temps)),
                'median_temp': float(np.median(valid_temps)),
                'std_temp': float(np.std(valid_temps)),
                'percentile_5': float(np.percentile(valid_temps, 5)),
                'percentile_95': float(np.percentile(valid_temps, 95)),
                'temp_range': float(np.max(valid_temps) - np.min(valid_temps)),
                'temperature_data': temp_data
            }

            self.results.append(result)
            logger.info(f"  ✓ Success: {result['mean_temp']:.1f}°C avg, "
                       f"{result['min_temp']:.1f}-{result['max_temp']:.1f}°C range")

            return result

        except Exception as e:
            error_info = {
                'filename': image_path.name,
                'filepath': str(image_path.absolute()),
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
            self.errors.append(error_info)
            logger.error(f"  ✗ Failed: {e}")
            return None

    def process_directory(self, directory, patterns=None, recursive=False):
        """
        Process all FLIR images in a directory

        Args:
            directory (str or Path): Directory path
            patterns (list): List of file patterns (default: ['*.jpg', '*.jpeg'])
            recursive (bool): Search subdirectories

        Returns:
            dict: Processing summary
        """
        directory = Path(directory)

        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        if patterns is None:
            patterns = ['*.jpg', '*.jpeg', '*.JPG', '*.JPEG']

        # Find all matching files
        image_files = []
        for pattern in patterns:
            if recursive:
                image_files.extend(directory.rglob(pattern))
            else:
                image_files.extend(directory.glob(pattern))

        # Remove duplicates
        image_files = list(set(image_files))

        logger.info(f"\nFound {len(image_files)} images in {directory}")
        logger.info("=" * 70)

        # Process each image
        for i, img_file in enumerate(sorted(image_files), 1):
            logger.info(f"[{i}/{len(image_files)}] ", extra={'end': ''})
            self.process_image_safe(img_file)

        # Generate summary
        summary = {
            'total_images': len(image_files),
            'successful': len(self.results),
            'failed': len(self.errors),
            'success_rate': len(self.results) / len(image_files) * 100 if image_files else 0
        }

        logger.info(f"\n{'=' * 70}")
        logger.info(f"Processing complete:")
        logger.info(f"  Total: {summary['total_images']}")
        logger.info(f"  Success: {summary['successful']}")
        logger.info(f"  Failed: {summary['failed']}")
        logger.info(f"  Success rate: {summary['success_rate']:.1f}%")

        return summary

    def save_summary_csv(self, filename='thermal_summary.csv'):
        """
        Save processing results to CSV

        Args:
            filename (str): Output CSV filename
        """
        if not self.results:
            logger.warning("No results to save")
            return

        output_path = self.output_dir / filename

        # Fields to include in CSV
        fields = [
            'filename', 'min_temp', 'max_temp', 'mean_temp', 
            'median_temp', 'std_temp', 'temp_range',
            'percentile_5', 'percentile_95', 'valid_pixels'
        ]

        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(self.results)

        logger.info(f"Summary saved to: {output_path}")

    def save_detailed_report(self, filename='thermal_report.json'):
        """
        Save detailed report as JSON

        Args:
            filename (str): Output JSON filename
        """
        output_path = self.output_dir / filename

        report = {
            'processing_date': datetime.now().isoformat(),
            'summary': {
                'total_processed': len(self.results),
                'total_errors': len(self.errors)
            },
            'results': [
                {k: v for k, v in r.items() if k != 'temperature_data'}
                for r in self.results
            ],
            'errors': self.errors
        }

        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Detailed report saved to: {output_path}")

    def save_temperature_arrays(self, format='npy'):
        """
        Save all temperature arrays to files

        Args:
            format (str): 'npy' or 'csv'
        """
        temp_dir = self.output_dir / 'temperature_data'
        temp_dir.mkdir(exist_ok=True)

        for result in self.results:
            base_name = Path(result['filename']).stem

            if format == 'npy':
                output_file = temp_dir / f"{base_name}_temps.npy"
                np.save(output_file, result['temperature_data'])
            elif format == 'csv':
                output_file = temp_dir / f"{base_name}_temps.csv"
                np.savetxt(output_file, result['temperature_data'], 
                          delimiter=',', fmt='%.2f')

        logger.info(f"Temperature arrays saved to: {temp_dir}")

    def generate_comparison_report(self):
        """
        Generate a comparison report across all images

        Returns:
            dict: Comparison statistics
        """
        if not self.results:
            logger.warning("No results to compare")
            return {}

        all_means = [r['mean_temp'] for r in self.results]
        all_mins = [r['min_temp'] for r in self.results]
        all_maxs = [r['max_temp'] for r in self.results]

        comparison = {
            'num_images': len(self.results),
            'overall_min': min(all_mins),
            'overall_max': max(all_maxs),
            'average_mean': np.mean(all_means),
            'median_mean': np.median(all_means),
            'std_of_means': np.std(all_means),
            'hottest_image': self.results[np.argmax(all_maxs)]['filename'],
            'coldest_image': self.results[np.argmin(all_mins)]['filename'],
            'most_uniform': self.results[np.argmin([r['std_temp'] for r in self.results])]['filename'],
            'least_uniform': self.results[np.argmax([r['std_temp'] for r in self.results])]['filename']
        }

        return comparison

    def print_comparison_report(self):
        """Print comparison report to console"""
        comp = self.generate_comparison_report()

        if not comp:
            return

        print("\n" + "=" * 70)
        print("THERMAL IMAGE COMPARISON REPORT")
        print("=" * 70)
        print(f"Total images analyzed: {comp['num_images']}")
        print(f"\nTemperature Overview:")
        print(f"  Overall range: {comp['overall_min']:.1f}°C to {comp['overall_max']:.1f}°C")
        print(f"  Average mean: {comp['average_mean']:.1f}°C")
        print(f"  Median mean: {comp['median_mean']:.1f}°C")
        print(f"  Std dev of means: {comp['std_of_means']:.1f}°C")
        print(f"\nExtreme Images:")
        print(f"  Hottest: {comp['hottest_image']}")
        print(f"  Coldest: {comp['coldest_image']}")
        print(f"\nUniformity:")
        print(f"  Most uniform: {comp['most_uniform']}")
        print(f"  Least uniform: {comp['least_uniform']}")
        print("=" * 70)

    def export_visualizations(self, max_images=None):
        """
        Export thermal visualizations for all images

        Args:
            max_images (int): Maximum number to export (None = all)
        """
        try:
            import matplotlib.pyplot as plt
            from matplotlib import cm
        except ImportError:
            logger.error("Matplotlib required for visualizations")
            return

        viz_dir = self.output_dir / 'visualizations'
        viz_dir.mkdir(exist_ok=True)

        images_to_process = self.results[:max_images] if max_images else self.results

        for result in images_to_process:
            try:
                temp_data = result['temperature_data']
                base_name = Path(result['filename']).stem

                fig, ax = plt.subplots(figsize=(10, 8))
                im = ax.imshow(temp_data, cmap='jet', interpolation='nearest')
                ax.set_title(f"{result['filename']}\n"
                           f"{result['min_temp']:.1f}°C - {result['max_temp']:.1f}°C "
                           f"(Avg: {result['mean_temp']:.1f}°C)", 
                           fontsize=12)
                ax.axis('off')
                cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
                cbar.set_label('Temperature (°C)', fontsize=11)

                output_file = viz_dir / f"{base_name}_thermal.png"
                plt.savefig(output_file, dpi=150, bbox_inches='tight')
                plt.close()

            except Exception as e:
                logger.error(f"Failed to create visualization for {result['filename']}: {e}")

        logger.info(f"Visualizations saved to: {viz_dir}")


def main():
    """
    Main function for batch processing
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Batch process FLIR thermal images with comprehensive reporting'
    )
    parser.add_argument('directory', help='Directory containing FLIR images')
    parser.add_argument('-o', '--output', default='./processed_thermal',
                       help='Output directory (default: ./processed_thermal)')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Search subdirectories recursively')
    parser.add_argument('--csv', action='store_true',
                       help='Generate CSV summary')
    parser.add_argument('--json', action='store_true',
                       help='Generate JSON report')
    parser.add_argument('--save-temps', choices=['npy', 'csv'],
                       help='Save temperature arrays as NPY or CSV')
    parser.add_argument('--visualize', type=int, metavar='N',
                       help='Generate visualizations (max N images)')

    args = parser.parse_args()

    # Create processor
    processor = BatchThermalProcessor(output_dir=args.output)

    # Process directory
    summary = processor.process_directory(args.directory, recursive=args.recursive)

    # Print comparison report
    processor.print_comparison_report()

    # Save outputs
    if args.csv or not (args.json or args.save_temps or args.visualize):
        processor.save_summary_csv()

    if args.json:
        processor.save_detailed_report()

    if args.save_temps:
        processor.save_temperature_arrays(format=args.save_temps)

    if args.visualize is not None:
        processor.export_visualizations(max_images=args.visualize)


if __name__ == '__main__':
    main()
