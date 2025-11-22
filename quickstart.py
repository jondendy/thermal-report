#!/usr/bin/env python3
"""
FLIR Thermal Image Processor - Quick Start Example
This script demonstrates basic usage with example code you can modify
"""

import os
import sys

print("=" * 70)
print("FLIR THERMAL IMAGE PROCESSOR - QUICK START")
print("=" * 70)

# Check if required libraries are installed
try:
    import numpy as np
    print("✓ NumPy installed")
except ImportError:
    print("✗ NumPy not found. Install with: pip install numpy")
    sys.exit(1)

try:
    from flirimageextractor import FlirImageExtractor
    print("✓ flirimageextractor installed")
except ImportError:
    print("✗ flirimageextractor not found. Install with: pip install flirimageextractor")
    print("  Also install ExifTool (see README.md)")
    sys.exit(1)

try:
    import matplotlib.pyplot as plt
    print("✓ Matplotlib installed (for visualization)")
    HAS_MATPLOTLIB = True
except ImportError:
    print("⚠ Matplotlib not found (visualization disabled)")
    print("  Install with: pip install matplotlib")
    HAS_MATPLOTLIB = False

print("\n" + "=" * 70)
print("EXAMPLE 1: Process a Single Image")
print("=" * 70)

# Example code for processing a single image
example_single = """
from flirimageextractor import FlirImageExtractor
import numpy as np

# Create extractor
extractor = FlirImageExtractor()

# Process your FLIR image (replace with your file path)
image_path = "your_thermal_image.jpg"
extractor.process_image(image_path)

# Get temperature data as numpy array (in Celsius)
temp_data = extractor.get_thermal_np()

# Calculate statistics
min_temp = np.min(temp_data)
max_temp = np.max(temp_data)
mean_temp = np.mean(temp_data)
median_temp = np.median(temp_data)

print(f"Temperature Statistics:")
print(f"  Min:    {min_temp:.2f} °C")
print(f"  Max:    {max_temp:.2f} °C")
print(f"  Mean:   {mean_temp:.2f} °C")
print(f"  Median: {median_temp:.2f} °C")

# Get visual image too
rgb_data = extractor.get_rgb_np()
print(f"\nImage shape: {temp_data.shape}")
"""

print(example_single)

print("=" * 70)
print("EXAMPLE 2: Process Multiple Images in a Folder")
print("=" * 70)

example_batch = """
from flirimageextractor import FlirImageExtractor
import numpy as np
from pathlib import Path

extractor = FlirImageExtractor()
folder = Path("./thermal_images")  # Your folder path

results = []
for img_file in folder.glob("*.jpg"):
    try:
        extractor.process_image(str(img_file))
        temp_data = extractor.get_thermal_np()

        results.append({
            'filename': img_file.name,
            'min': float(np.min(temp_data)),
            'max': float(np.max(temp_data)),
            'mean': float(np.mean(temp_data))
        })
        print(f"✓ Processed: {img_file.name}")

    except Exception as e:
        print(f"✗ Failed {img_file.name}: {e}")

# Save results to CSV
import csv
with open('results.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['filename', 'min', 'max', 'mean'])
    writer.writeheader()
    writer.writerows(results)

print(f"\nProcessed {len(results)} images. Results saved to results.csv")
"""

print(example_batch)

print("=" * 70)
print("EXAMPLE 3: Display Thermal Image with Visualization")
print("=" * 70)

if HAS_MATPLOTLIB:
    example_viz = """
from flirimageextractor import FlirImageExtractor
import matplotlib.pyplot as plt

extractor = FlirImageExtractor()
extractor.process_image("thermal_image.jpg")

# Get data
temp_data = extractor.get_thermal_np()
rgb_data = extractor.get_rgb_np()

# Create visualization
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Visual image
axes[0].imshow(rgb_data)
axes[0].set_title('Visual Image')
axes[0].axis('off')

# Thermal image
im = axes[1].imshow(temp_data, cmap='jet', interpolation='nearest')
axes[1].set_title('Thermal Image')
axes[1].axis('off')
plt.colorbar(im, ax=axes[1], label='Temperature (°C)')

plt.tight_layout()
plt.show()
"""
    print(example_viz)
else:
    print("(Requires matplotlib - install with: pip install matplotlib)")

print("=" * 70)
print("NEXT STEPS")
print("=" * 70)
print("""
1. Replace 'your_thermal_image.jpg' with your actual FLIR image path
2. Run the examples above in a Python script or interactive session
3. For more advanced features, see:
   - flir_processor_simple.py (easy-to-use wrapper)
   - flir_batch_processor.py (comprehensive batch processing)
4. Check README.md for detailed documentation

Quick Commands:
  # Process single image
  python -c "from flir_processor_simple import SimpleFLIRProcessor; \
            p = SimpleFLIRProcessor(); \
            p.process_single_image('your_image.jpg', display=True)"

  # Batch process folder
  python flir_batch_processor.py ./your_folder --csv --visualize 5
""")

print("=" * 70)
print("TESTING YOUR SETUP")
print("=" * 70)

print("""
To test if everything works, you need a FLIR thermal image.

If you have a FLIR image, run:
  python flir_processor_simple.py

Then uncomment one of the example functions at the bottom of the file.

If you don't have FLIR images, you can:
1. Download sample images from FLIR's website
2. Use images from a FLIR thermal camera or FLIR ONE
3. Obtain sample thermal images from building survey databases
""")

print("\n" + "=" * 70)
print("Setup check complete! You're ready to process FLIR thermal images.")
print("=" * 70)
