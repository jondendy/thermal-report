# FLIR Thermal Image Calibration Extension

Extension module for FLIR thermal image processing that adds reference object detection and calibration capabilities for building survey applications.

## 🎯 New Features

This extension adds the following capabilities to the base FLIR extraction code:

1. **Scale Calibration**
   - ArUco marker detection for spatial reference
   - Convert pixel measurements to real-world dimensions (mm, cm, inches)
   - Persistent calibration across multiple images

2. **Color Reference Patch Detection**
   - HSV-based color detection
   - Automatic patch localization
   - Temperature measurement at reference points

3. **Temperature Calibration**
   - Single-point offset correction
   - Two-point linear correction
   - Multi-point calibration support
   - Reference object-based correction

4. **Cross-Image Normalization**
   - Min-max normalization
   - Z-score standardization
   - Reference-based normalization
   - Consistent comparison across different conditions

5. **Visual Overlays**
   - Detection visualization
   - Calibration markers
   - Hot/cold spot identification
   - Comprehensive analysis reports

## 📦 Installation

### Prerequisites

All requirements from the base FLIR processor plus:

```bash
# Install OpenCV with ArUco support
pip install opencv-python opencv-contrib-python

# Verify ArUco module
python -c "import cv2; print(cv2.aruco.__version__)"
```

### Full Installation

```bash
# Base requirements
pip install numpy pillow flirimageextractor matplotlib

# Calibration extension requirements
pip install opencv-python opencv-contrib-python

# Optional: for advanced visualization
pip install scipy scikit-image
```

## 🚀 Quick Start

### 1. Scale Calibration with ArUco Marker

```python
from flir_calibration import ThermalCalibrator

# Initialize calibrator
calibrator = ThermalCalibrator()

# Process image with ArUco marker
import cv2
image = cv2.imread('thermal_with_marker.jpg')

# Detect marker and calibrate scale
corners, ids, annotated = calibrator.detect_aruco_markers(image)

# Now you can measure objects in mm
bbox = (100, 100, 200, 150)  # x, y, width, height in pixels
size = calibrator.measure_object_size(bbox, unit='mm')
print(f"Object size: {size['width']:.1f} x {size['height']:.1f} mm")
```

### 2. Temperature Calibration

```python
from flir_calibration import ThermalCalibrator
from flirimageextractor import FlirImageExtractor

# Extract temperature data
extractor = FlirImageExtractor()
extractor.process_image('thermal.jpg')
temp_data = extractor.get_thermal_np()

# Set reference point with known temperature
calibrator = ThermalCalibrator()
calibrator.set_manual_reference(
    name='reference_thermometer',
    center=(320, 240),  # pixel coordinates
    measured_temp=temp_data[240, 320],
    expected_temp=22.5  # known temperature in °C
)

# Calculate and apply correction
calibrator.calculate_temp_correction(
    calibrator.calibration_data['manual_references']
)
corrected_temp = calibrator.apply_temp_correction(temp_data)
```

### 3. Complete Building Survey Workflow

```python
from example_building_survey import BuildingSurveyProcessor

# Initialize processor
processor = BuildingSurveyProcessor()

# Calibrate from reference image
processor.calibrate_from_reference_image(
    'reference.jpg',
    reference_temp=22.0,
    reference_point=(320, 240)
)

# Process building images
results = processor.process_multiple_buildings([
    'building_01.jpg',
    'building_02.jpg',
    'building_03.jpg'
])
```

## 📖 Detailed Usage

### Generating ArUco Markers

```python
import cv2

# Create ArUco dictionary
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

# Generate marker
marker_id = 42
marker_size = 400  # pixels
marker_image = cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_size)

# Save for printing
cv2.imwrite('aruco_marker.png', marker_image)
```

**Important:** Print the marker at exactly the size you specify in the configuration (e.g., 50mm × 50mm).

### Configuring Reference Objects

```python
config = {
    'aruco_marker': {
        'enabled': True,
        'size_mm': 50,  # Physical size of printed marker
        'dict': 'DICT_6X6_250'
    },
    'color_patches': {
        'enabled': True,
        'patches': [
            {
                'name': 'blue_reference',
                'hsv_lower': [100, 100, 100],
                'hsv_upper': [130, 255, 255],
                'expected_temp': 20.0  # Known temperature
            }
        ]
    }
}

calibrator = ThermalCalibrator(config=config)
```

### Finding HSV Color Ranges

Use this helper to find HSV ranges for your reference patches:

```python
import cv2
import numpy as np

def find_hsv_range(image_path, x, y, window=10):
    """Find HSV range around a point"""
    img = cv2.imread(image_path)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Get region around point
    roi = hsv[y-window:y+window, x-window:x+window]

    # Calculate ranges
    lower = np.min(roi.reshape(-1, 3), axis=0)
    upper = np.max(roi.reshape(-1, 3), axis=0)

    print(f"HSV range at ({x}, {y}):")
    print(f"  Lower: {lower}")
    print(f"  Upper: {upper}")

    return lower, upper

# Example: Find HSV range for blue patch at position (200, 150)
find_hsv_range('thermal_image.jpg', 200, 150)
```

### Single-Point vs Two-Point Calibration

**Single-Point (Offset Only):**
- Use when you have one reference temperature
- Corrects systematic offset
- `T_corrected = T_measured + offset`

```python
# One reference at 22°C
calibrator.set_manual_reference('ref1', (320, 240), 
                               measured_temp=21.5, expected_temp=22.0)
```

**Two-Point (Linear Correction):**
- Use when you have two reference temperatures
- Corrects both offset and gain
- `T_corrected = scale × T_measured + offset`

```python
# Reference 1: Ice water at 0°C
calibrator.set_manual_reference('ice', (150, 200), 
                               measured_temp=0.8, expected_temp=0.0)

# Reference 2: Room temp at 23°C
calibrator.set_manual_reference('room', (450, 200), 
                               measured_temp=22.3, expected_temp=23.0)
```

### Batch Processing with Saved Calibration

```python
# Step 1: Create and save calibration
calibrator = ThermalCalibrator()
# ... perform calibration ...
calibrator.save_calibration('my_calibration.json')

# Step 2: Load calibration for batch processing
calibrator_new = ThermalCalibrator()
calibrator_new.load_calibration('my_calibration.json')

# Step 3: Process multiple images with same calibration
for img_path in image_list:
    extractor.process_image(img_path)
    temp_data = extractor.get_thermal_np()
    corrected = calibrator_new.apply_temp_correction(temp_data)
    # ... analyze corrected data ...
```

### Measuring Object Dimensions

```python
# After scale calibration with ArUco marker
calibrator.detect_aruco_markers(image)

# Detect object (example: using color detection)
hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
mask = cv2.inRange(hsv, lower_color, upper_color)
contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# Get bounding box
x, y, w, h = cv2.boundingRect(contours[0])

# Measure in real units
size_mm = calibrator.measure_object_size((x, y, w, h), unit='mm')
size_cm = calibrator.measure_object_size((x, y, w, h), unit='cm')

print(f"Object dimensions:")
print(f"  {size_mm['width']:.1f} × {size_mm['height']:.1f} mm")
print(f"  {size_cm['width']:.2f} × {size_cm['height']:.2f} cm")
```

## 📊 Output Examples

### Calibration Report

```json
{
  "scale_calibration": {
    "pixels_per_mm": 29.52,
    "marker_id": 42,
    "marker_size_mm": 50
  },
  "temperature_correction": {
    "method": "linear",
    "scale": 0.9845,
    "offset": 0.73,
    "rmse": 0.15
  },
  "manual_references": [
    {
      "name": "reference_thermometer",
      "center": [320, 240],
      "measured_temp": 21.77,
      "expected_temp": 22.5
    }
  ]
}
```

### Temperature Statistics (Before/After Correction)

```
Original Temperature Data:
  Min:     18.3°C
  Max:     34.7°C
  Mean:    23.2°C

After Calibration:
  Min:     18.8°C
  Max:     35.0°C
  Mean:    23.6°C
  Correction: scale=0.9845, offset=0.73°C
```

## 🎨 Visualization Features

### Detection Overlay

Shows detected reference objects:
- ArUco markers with IDs
- Color patches with temperatures
- Manual reference points
- Scale information

### Analysis Images

Complete analysis visualization includes:
- Original image with detections
- Temperature distribution map
- Hot spot overlay (>95th percentile)
- Cold spot overlay (<5th percentile)
- Temperature histogram
- Statistical summary

## 🔧 Advanced Configuration

### Custom Color Patch Detection

```python
config = {
    'color_patches': {
        'enabled': True,
        'patches': [
            {
                'name': 'custom_patch',
                'hsv_lower': [H_min, S_min, V_min],
                'hsv_upper': [H_max, S_max, V_max],
                'expected_temp': 25.0,
                'min_area': 100  # Minimum area in pixels
            }
        ]
    }
}
```

### Normalization Methods

```python
# Min-max normalization (0 to 1)
normalized = calibrator.normalize_temperatures(temp_data, method='min_max')

# Z-score standardization (mean=0, std=1)
normalized = calibrator.normalize_temperatures(temp_data, method='z_score')

# Reference-based (custom range)
calibrator.config['normalization']['reference_temp_low'] = 15.0
calibrator.config['normalization']['reference_temp_high'] = 35.0
normalized = calibrator.normalize_temperatures(temp_data, method='reference_based')
```

## 📝 Example Scripts

### 1. example_aruco_calibration.py
- Generate ArUco markers
- Calibrate scale from markers
- Save/load calibration
- Measure object dimensions

### 2. example_temp_calibration.py
- Single-point calibration
- Two-point calibration
- Color patch auto-calibration
- Batch processing with calibration

### 3. example_building_survey.py
- Complete building survey workflow
- Multiple image processing
- Comparison reports
- Hot/cold spot detection

## 🎯 Best Practices

### For Scale Calibration:
1. Print ArUco marker at exact size (use high-quality printer)
2. Mount marker on flat, rigid surface
3. Place marker in same plane as objects to measure
4. Ensure marker is clearly visible and not distorted
5. Use marker in first image, save calibration for subsequent images

### For Temperature Calibration:
1. Use certified reference thermometer
2. Allow thermal equilibrium (15-30 minutes)
3. Place references at different temperature ranges when possible
4. Verify calibration periodically
5. Document reference object specifications

### For Building Surveys:
1. Calibrate in similar environmental conditions
2. Use multiple reference points when possible
3. Process images in batches with same calibration
4. Document ambient temperature and humidity
5. Review hot/cold spot detections manually

## 🐛 Troubleshooting

### ArUco Marker Not Detected

**Possible causes:**
- Marker too small or too far
- Poor lighting or image quality
- Wrong dictionary specified
- Marker partially obscured

**Solutions:**
```python
# Adjust detection parameters
params = cv2.aruco.DetectorParameters()
params.adaptiveThreshWinSizeMin = 3
params.adaptiveThreshWinSizeMax = 23
calibrator.aruco_params = params
```

### Color Patch Not Detected

**Possible causes:**
- Incorrect HSV range
- Patch too small
- Poor color separation

**Solutions:**
```python
# Find correct HSV range
find_hsv_range('image.jpg', x, y)

# Adjust minimum area
config['color_patches']['patches'][0]['min_area'] = 50
```

### Large Temperature Correction Error

**Possible causes:**
- Non-linear camera response
- Emissivity mismatch
- Atmospheric interference

**Solutions:**
- Use two-point calibration
- Check camera emissivity settings
- Measure multiple reference points
- Verify reference temperatures

## 📚 API Reference

### ThermalCalibrator Class

**Methods:**
- `detect_aruco_markers(image)` - Detect ArUco markers
- `detect_color_patches(image, temp_data)` - Detect color patches
- `set_manual_reference(name, center, measured_temp, expected_temp)` - Set reference point
- `calculate_temp_correction(reference_points)` - Calculate correction parameters
- `apply_temp_correction(temp_data)` - Apply temperature correction
- `normalize_temperatures(temp_data, method)` - Normalize temperatures
- `measure_object_size(bbox, unit)` - Measure object dimensions
- `save_calibration(filepath)` - Save calibration data
- `load_calibration(filepath)` - Load calibration data

## 🔗 Integration with Base FLIR Code

This extension integrates seamlessly with the base FLIR extraction scripts:

```python
# Use with flir_processor_simple.py
from flir_processor_simple import SimpleFLIRProcessor
from flir_calibration import ThermalCalibrator

processor = SimpleFLIRProcessor()
calibrator = ThermalCalibrator()

# Process and calibrate
temp_data, stats = processor.process_single_image('image.jpg', display=False)
corrected = calibrator.apply_temp_correction(temp_data)
```

## 📄 License

Compatible with the base FLIR thermal image processing toolkit.

## 🤝 Support

For issues specific to calibration:
1. Verify ArUco marker is printed at correct size
2. Check HSV color ranges for your specific patches
3. Ensure reference temperatures are accurately measured
4. Review calibration report for anomalies

## 📈 Version History

- v1.0 - Initial release
  - ArUco marker detection
  - Color patch detection
  - Temperature calibration
  - Normalization methods
  - Visual overlays
