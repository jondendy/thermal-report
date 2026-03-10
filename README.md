# FLIR Thermal Image Processing for Building Surveys

Complete Python toolkit for processing FLIR radiometric JPG files for building survey applications.

## 📋 Overview

This toolkit provides three Python scripts for processing FLIR thermal images:

1. **flir_processor_complete.py** - Standalone processor using exiftool directly
2. **flir_processor_simple.py** - Easy-to-use processor using flirimageextractor library
3. **flir_batch_processor.py** - Advanced batch processor with comprehensive reporting

## 🔧 Installation

### Prerequisites

**Required:**
- Python 3.6 or higher
- ExifTool (for extracting FLIR metadata)

**Python packages:**
```bash
# Install required packages
pip install numpy pillow

# For the simple and batch processors:
pip install flirimageextractor

# For visualization (optional but recommended):
pip install matplotlib
```
## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description | Example |
|---|---|---|
| `ORGNAME` | Organisation name shown in report footer | `Acme Thermal` |
| `ORGWEBSITE` | Website URL in footer | `https://acmethermal.co.uk` |
| `ORGCONTACT` | Contact email/phone in footer | `info@acmethermal.co.uk` |
| `RECOMMENDATIONS_DOCUMENT_URL` | Google Drive link to append | `https://drive.google.com/...` |
| `REPORTS_FOLDER` | Where batch report dirs live | `.reports` |
| `UPLOAD_FOLDER` | Where raw images are stored | `.Images` |



### Installing ExifTool

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install libimage-exiftool-perl
```

**Windows:**
1. Download from https://exiftool.org/
2. Extract exiftool(-k).exe
3. Rename to exiftool.exe
4. Add to your PATH or specify path in scripts

**MacOS:**
```bash
brew install exiftool
```

### Verify Installation

```bash
# Check ExifTool
exiftool -ver

# Check Python packages
python -c "import numpy; import PIL; print('OK')"
```

## 🚀 Quick Start

### Option 1: Simple Processor (Recommended for beginners)

```python
from flir_processor_simple import SimpleFLIRProcessor

# Create processor
processor = SimpleFLIRProcessor()

# Process a single image
temp_data, stats = processor.process_single_image('thermal_image.jpg', display=True)

print(f"Temperature range: {stats['min']:.1f} - {stats['max']:.1f} °C")
print(f"Average: {stats['mean']:.1f} °C")

# Save temperature data as CSV
processor.save_temperature_array(temp_data, 'temperatures.csv')
```

### Option 2: Batch Processing

```python
from flir_processor_simple import SimpleFLIRProcessor

processor = SimpleFLIRProcessor()

# Process all images in a folder
results = processor.process_folder(
    folder_path='./thermal_images',
    pattern='*.jpg',
    save_csv='summary.csv'
)

# Access results
for filename, data in results.items():
    stats = data['statistics']
    print(f"{filename}: {stats['mean']:.1f}°C average")
```

### Option 3: Advanced Batch Processing

```bash
# Command line usage
python flir_batch_processor.py ./thermal_images --csv --visualize 10

# With all options
python flir_batch_processor.py ./thermal_images \
    --output ./results \
    --recursive \
    --csv \
    --json \
    --save-temps npy \
    --visualize 20
```

## 📖 Detailed Usage

### Processing a Single Image

```python
from flir_processor_simple import SimpleFLIRProcessor

processor = SimpleFLIRProcessor()

# Process image
temp_data, stats = processor.process_single_image('building_facade.jpg')

# Temperature data is a 2D numpy array in Celsius
print(f"Shape: {temp_data.shape}")
print(f"Min temp: {stats['min']:.2f} °C")
print(f"Max temp: {stats['max']:.2f} °C")
print(f"Mean temp: {stats['mean']:.2f} °C")
print(f"Median temp: {stats['median']:.2f} °C")
print(f"Std dev: {stats['std']:.2f} °C")

# Access individual pixel temperatures
temp_at_pixel = temp_data[100, 150]  # row 100, column 150
print(f"Temperature at pixel (100, 150): {temp_at_pixel:.2f} °C")

# Find hottest and coldest points
hot_spot = np.unravel_index(np.argmax(temp_data), temp_data.shape)
cold_spot = np.unravel_index(np.argmin(temp_data), temp_data.shape)
print(f"Hottest point: {hot_spot}, {temp_data[hot_spot]:.2f} °C")
print(f"Coldest point: {cold_spot}, {temp_data[cold_spot]:.2f} °C")
```

### Batch Processing with Error Handling

```python
from flir_processor_simple import SimpleFLIRProcessor

processor = SimpleFLIRProcessor()

image_list = ['image1.jpg', 'image2.jpg', 'image3.jpg']
results = []

for img_path in image_list:
    try:
        temp_data, stats = processor.process_single_image(img_path, display=False)
        results.append({
            'filename': img_path,
            'min': stats['min'],
            'max': stats['max'],
            'mean': stats['mean']
        })
        print(f"✓ {img_path}: Success")
    except FileNotFoundError:
        print(f"✗ {img_path}: File not found")
    except Exception as e:
        print(f"✗ {img_path}: Error - {e}")

# Save results
import csv
with open('results.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['filename', 'min', 'max', 'mean'])
    writer.writeheader()
    writer.writerows(results)
```

### Using the Complete Processor (Direct ExifTool)

```python
from flir_processor_complete import FlirImageProcessor

# Create processor
processor = FlirImageProcessor(exiftool_path='exiftool')

# Process single image
temp_data, metadata, stats = processor.process_image('thermal.jpg', display=True)

# Process entire folder
results = processor.process_folder('./images', output_csv='summary.csv')

# Save temperature array
import numpy as np
np.save('temperature_matrix.npy', temp_data)
```

### Advanced Batch Processing

```python
from flir_batch_processor import BatchThermalProcessor

# Create batch processor
processor = BatchThermalProcessor(output_dir='./results')

# Process directory
summary = processor.process_directory(
    directory='./thermal_images',
    recursive=True  # Include subdirectories
)

# Print comparison across all images
processor.print_comparison_report()

# Save outputs
processor.save_summary_csv('summary.csv')
processor.save_detailed_report('report.json')
processor.save_temperature_arrays(format='csv')
processor.export_visualizations(max_images=10)
```

## 📊 Output Formats

### Temperature Data

The temperature data is returned as a 2D NumPy array where each element represents the temperature in Celsius for that pixel.

```python
# Temperature data shape
print(temp_data.shape)  # e.g., (512, 640) - height x width

# Data type
print(temp_data.dtype)  # float64

# Access specific pixel
temp = temp_data[row, col]

# Get region average
region = temp_data[100:200, 150:250]
avg_temp = np.mean(region)
```

### Statistics Dictionary

```python
{
    'min': 15.3,      # Minimum temperature (°C)
    'max': 45.7,      # Maximum temperature (°C)
    'mean': 22.4,     # Mean temperature (°C)
    'median': 21.8,   # Median temperature (°C)
    'std': 5.2        # Standard deviation (°C)
}
```

### CSV Output

The CSV summary contains:
- filename
- min_temp, max_temp, mean_temp, median_temp, std_temp
- Additional statistics (percentiles, range, etc.)

### JSON Report

Detailed JSON report includes:
- Processing timestamp
- Individual image results
- Error log
- Metadata from FLIR files

## 🔍 Troubleshooting

### "ExifTool not found"

**Solution:** Install ExifTool (see Installation section above)

### "No thermal data extracted"

**Possible causes:**
1. File is not a FLIR radiometric JPG
2. Thermal data is not embedded in the image
3. Unsupported FLIR camera model

**Solution:** Verify file with ExifTool:
```bash
exiftool -a -G1 your_image.jpg | grep -i thermal
```

### "ModuleNotFoundError: flirimageextractor"

**Solution:**
```bash
pip install flirimageextractor
```

### Temperatures seem incorrect

**Possible causes:**
1. Incorrect emissivity setting
2. Non-standard calibration parameters
3. Atmospheric correction needed

**Solution:** Check metadata and adjust parameters in the complete processor

### "ImportError: No module named 'matplotlib'"

**Solution:** Install matplotlib for visualization:
```bash
pip install matplotlib
```

## 📝 Examples

### Example 1: Building Facade Survey

```python
from flir_processor_simple import SimpleFLIRProcessor
import numpy as np

processor = SimpleFLIRProcessor()

# Process facade image
temp_data, stats = processor.process_single_image('facade.jpg', display=True)

# Identify potential thermal bridges (areas >3°C above mean)
threshold = stats['mean'] + 3.0
hot_areas = temp_data > threshold
num_hotspots = np.sum(hot_areas)

print(f"Detected {num_hotspots} pixels above threshold")
print(f"Threshold: {threshold:.1f}°C")

# Calculate percentage of area with issues
percent_hot = (num_hotspots / temp_data.size) * 100
print(f"Hot area coverage: {percent_hot:.2f}%")
```

### Example 2: Comparing Multiple Buildings

```python
from flir_batch_processor import BatchThermalProcessor

processor = BatchThermalProcessor(output_dir='./building_comparison')

# Process all building images
processor.process_directory('./building_images')

# Get comparison report
comparison = processor.generate_comparison_report()

print(f"Analyzed {comparison['num_images']} buildings")
print(f"Temperature range: {comparison['overall_min']:.1f} - {comparison['overall_max']:.1f}°C")
print(f"Most efficient building: {comparison['coldest_image']}")
print(f"Least efficient building: {comparison['hottest_image']}")

# Save comprehensive report
processor.save_summary_csv()
processor.save_detailed_report()
```

### Example 3: Export for Further Analysis

```python
from flir_processor_simple import SimpleFLIRProcessor
import numpy as np

processor = SimpleFLIRProcessor()

# Process image
temp_data, stats = processor.process_single_image('thermal.jpg', display=False)

# Save in multiple formats
np.save('temp_array.npy', temp_data)  # NumPy binary format
np.savetxt('temp_data.csv', temp_data, delimiter=',', fmt='%.2f')  # CSV

# Save statistics
import json
with open('stats.json', 'w') as f:
    json.dump(stats, f, indent=2)

print("Data exported successfully")
```

## 🎯 Features

- ✅ Extract temperature matrix from FLIR radiometric JPG files
- ✅ Calculate comprehensive statistics (min, max, mean, median, std dev)
- ✅ Batch process multiple images
- ✅ Error handling for non-FLIR images
- ✅ Save results in CSV, JSON, NPY formats
- ✅ Generate thermal visualizations
- ✅ Compare multiple images
- ✅ Command-line interface
- ✅ Detailed logging
- ✅ Cross-platform (Windows, Linux, MacOS)

## 📚 Supported FLIR Cameras

These scripts have been tested with:
- FLIR ONE
- FLIR E-Series (E4, E5, E6, E8)
- FLIR T-Series
- DJI Zenmuse XT/XT2/H20T
- FLIR Tau 2
- FLIR Boson

Most FLIR cameras that save radiometric JPG files should work.

## 🤝 Contributing

Suggestions and improvements welcome! Common enhancements:
- Support for additional file formats (SEQ, FFF)
- Advanced analysis features
- GUI interface
- Real-time camera capture

## 📄 License

These scripts are provided for building survey and thermal analysis applications.

## 🔗 Related Resources

- [FLIR Systems](https://www.flir.com/)
- [ExifTool](https://exiftool.org/)
- [flirimageextractor on PyPI](https://pypi.org/project/flirimageextractor/)
- [flirpy library](https://pypi.org/project/flirpy/)

## ❓ Support

For issues or questions:
1. Check the Troubleshooting section
2. Verify your FLIR image contains thermal data: `exiftool -a image.jpg | grep -i thermal`
3. Test with the example images from your FLIR camera

## 📈 Version History

- v1.0 - Initial release with three processing options
- Complete processor using exiftool directly
- Simple processor using flirimageextractor library
- Advanced batch processor with comprehensive reporting
