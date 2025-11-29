# Thermal Report Testing Guide

Comprehensive testing documentation for the thermal-report project.

## Table of Contents

- [Quick Start](#quick-start)
- [Automated Testing](#automated-testing)
- [Manual Testing](#manual-testing)
- [Docker Testing](#docker-testing)
- [GitHub Codespaces Testing](#github-codespaces-testing)
- [GCP VM Testing](#gcp-vm-testing)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- **Python 3.6+**
- **ExifTool** (system package)
- **Git** (for cloning repository)

### Installation

```bash
# Clone the repository
git clone https://github.com/jondendy/thermal-report.git
cd thermal-report

# Install Python dependencies
pip install -r requirements.txt

# Install ExifTool (system package)
# Debian/Ubuntu/WSL2:
sudo apt update && sudo apt install libimage-exiftool-perl

# macOS:
brew install exiftool

# Windows:
# Download from https://exiftool.org/
```

### Run Automated Tests

```bash
python run_tests.py
```

This will run all tests and provide a detailed report.

---

## Automated Testing

The `run_tests.py` script performs comprehensive automated testing.

### What It Tests

1. **Python Dependencies** - Verifies all required packages are installed
2. **ExifTool Availability** - Checks system ExifTool installation
3. **Sample Image Processing** - Tests FLIR image extraction and processing
4. **File Export Operations** - Validates CSV and NPY export functionality

### Running Tests

```bash
# Run all tests
python run_tests.py

# Expected output:
############################################################
#  THERMAL REPORT - AUTOMATED TEST SUITE
############################################################

============================================================
TEST 1: Checking Python Dependencies
============================================================
✓ NumPy is installed
✓ Pillow is installed
✓ FlirImageExtractor is installed
✓ Matplotlib is installed

✓ All Python dependencies are installed

============================================================
TEST 2: Checking ExifTool
============================================================
✓ ExifTool is installed (version 12.40)

============================================================
TEST 3: Processing Sample FLIR Image
============================================================
✓ Test image FLIR0648.jpg found
✓ SimpleFLIRProcessor imported successfully
✓ Processor initialized

Processing image (this may take a moment)...

✓ Image processed successfully!
  - Image shape: 480 x 640 pixels
  - Temperature range: 15.2°C to 28.7°C
  - Mean temperature: 21.5°C
  - Median temperature: 21.3°C
  - Standard deviation: 2.1°C

============================================================
TEST 4: File Export Operations
============================================================
✓ CSV export successful: test_output.csv
✓ NPY export successful: test_output.npy

✓ All file operations successful

############################################################
#  TEST SUMMARY
############################################################
✓ PASSED: Python Dependencies
✓ PASSED: ExifTool
✓ PASSED: Sample Image Processing
✓ PASSED: File Export Operations

============================================================
RESULTS: 4/4 tests passed (100%)
============================================================

🎉 All tests passed! Your environment is ready.
```

### Test Failures

If tests fail, the script will provide specific error messages and suggestions for fixes.

---

## Manual Testing

### Test 1: Environment Verification

```bash
# Check Python version
python --version
# Expected: Python 3.6.0 or higher

# Check ExifTool
exiftool -ver
# Expected: Version number (e.g., 12.40)

# Check pip packages
pip list | grep -E "numpy|Pillow|flirimageextractor|matplotlib"
```

### Test 2: Single Image Processing

```bash
# Process the test image
python test1.py
```

**Expected Output:**
- Temperature visualization displayed
- Statistics printed to console
- CSV file generated

### Test 3: Batch Processing

```bash
# Create test directory with images
mkdir -p test_images
cp FLIR0648.jpg test_images/

# Run batch processor
python flir_batch_processor.py ./test_images --csv
```

**Expected Output:**
- All images processed
- Summary CSV generated
- Statistics displayed for each image

### Test 4: Advanced Batch Processing

```bash
# Full featured test
python flir_batch_processor.py ./test_images \
  --output ./reports \
  --csv \
  --json \
  --visualize 5
```

**Expected Output:**
- CSV summary in `./reports`
- JSON output in `./reports`
- Top 5 visualizations generated

---

## Docker Testing

### Build Docker Image

```bash
# From repository root
docker build -t thermal-report:latest .
```

### Run Container Interactively

```bash
# Mount your Images folder
docker run -it --rm \
  -v $(pwd)/Images:/app/Images \
  -v $(pwd)/reports:/app/reports \
  thermal-report:latest

# Inside container:
python run_tests.py
python flir_batch_processor.py ./Images --output ./reports --csv
```

### Run Tests in Container

```bash
# Run automated tests
docker run --rm thermal-report:latest python run_tests.py

# Process images
docker run --rm \
  -v $(pwd)/Images:/app/Images \
  -v $(pwd)/reports:/app/reports \
  thermal-report:latest \
  python flir_batch_processor.py /app/Images --output /app/reports --csv
```

### Docker Compose (Optional)

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  thermal-report:
    build: .
    volumes:
      - ./Images:/app/Images
      - ./reports:/app/reports
    command: python flir_batch_processor.py /app/Images --output /app/reports --csv
```

Run:
```bash
docker-compose up
```

---

## GitHub Codespaces Testing

### Launch Codespace

1. Go to https://github.com/jondendy/thermal-report
2. Click the green **Code** button
3. Select **Codespaces** tab
4. Click **Create codespace on testing-improvements**

### In Codespace

The development container is pre-configured with all dependencies.

```bash
# Verify environment
python run_tests.py

# Upload FLIR images to Images/ folder using file explorer

# Process images
python flir_batch_processor.py ./Images --csv

# Download reports from reports/ folder
```

### Codespace Benefits

- ✓ No local setup required
- ✓ Consistent environment
- ✓ Works on any device with browser
- ✓ Pre-installed dependencies

---

## GCP VM Testing

### Setup on Google Cloud VM

```bash
# SSH into your VM
gcloud compute ssh YOUR-VM-NAME --zone=YOUR-ZONE

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install -y python3 python3-pip libimage-exiftool-perl

# Clone repository
git clone https://github.com/jondendy/thermal-report.git
cd thermal-report

# Switch to testing branch
git checkout testing-improvements

# Install Python packages
pip3 install -r requirements.txt

# Run tests
python3 run_tests.py
```

### Docker on GCP VM

```bash
# Install Docker (if not already installed)
sudo apt install -y docker.io
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

# Log out and back in for group changes

# Build and run
cd thermal-report
docker build -t thermal-report:latest .
docker run --rm thermal-report:latest python run_tests.py
```

### Processing Large Batches on GCP VM

```bash
# Upload images via SCP
scp -r /local/path/to/images/ YOUR-VM:~/thermal-report/Images/

# Or use gsutil for Cloud Storage
gsutil -m cp -r gs://your-bucket/images/* ~/thermal-report/Images/

# Process on VM
cd ~/thermal-report
python3 flir_batch_processor.py ./Images --output ./reports --csv --json

# Download results
scp -r YOUR-VM:~/thermal-report/reports/ /local/path/

# Or upload to Cloud Storage
gsutil -m cp -r ~/thermal-report/reports/* gs://your-bucket/reports/
```

---

## Troubleshooting

### Common Issues

#### Issue: "ModuleNotFoundError: No module named 'numpy'"

**Solution:**
```bash
pip install -r requirements.txt
```

#### Issue: "ExifTool not found"

**Solution:**
```bash
# Debian/Ubuntu
sudo apt install libimage-exiftool-perl

# macOS
brew install exiftool

# Windows
# Download from https://exiftool.org/ and add to PATH
```

#### Issue: "FLIR0648.jpg not found"

**Solution:**
Make sure you're running tests from the repository root directory:
```bash
cd /path/to/thermal-report
python run_tests.py
```

#### Issue: "No thermal data in image"

**Solution:**
- Verify the image is a genuine FLIR thermal image
- Check with: `exiftool -a -G1 your_image.jpg | grep -i thermal`
- Ensure the image hasn't been re-encoded or compressed

#### Issue: Docker build fails

**Solution:**
```bash
# Clean Docker cache
docker system prune -a

# Rebuild
docker build --no-cache -t thermal-report:latest .
```

#### Issue: Permission denied in Docker

**Solution:**
```bash
# Run with correct user
docker run --rm --user $(id -u):$(id -g) \
  -v $(pwd)/Images:/app/Images \
  thermal-report:latest python run_tests.py
```

#### Issue: Slow processing on large images

**Solution:**
- Processing speed depends on image size and CPU
- Consider batch processing in Docker with resource limits:
```bash
docker run --rm --cpus="2" --memory="2g" \
  -v $(pwd)/Images:/app/Images \
  thermal-report:latest \
  python flir_batch_processor.py /app/Images
```

### Getting Help

- **GitHub Issues**: https://github.com/jondendy/thermal-report/issues
- **Documentation**: Check README.md and code comments
- **Test Output**: Run `python run_tests.py` for diagnostic info

---

## Testing Checklist

Use this checklist to verify your setup:

### Environment Setup
- [ ] Python 3.6+ installed
- [ ] All pip packages installed (`pip install -r requirements.txt`)
- [ ] ExifTool installed and accessible
- [ ] Repository cloned
- [ ] On correct branch (`git checkout testing-improvements`)

### Basic Functionality
- [ ] `python run_tests.py` passes all tests
- [ ] `python quickstart.py` runs without errors
- [ ] `python test1.py` processes sample image
- [ ] CSV export works
- [ ] NPY export works

### Batch Processing
- [ ] Single folder processing works
- [ ] Multiple images processed correctly
- [ ] Summary CSV generated
- [ ] JSON output generated (if requested)

### Docker
- [ ] Dockerfile builds successfully
- [ ] Container runs tests successfully
- [ ] Volume mounting works
- [ ] Can process images in container

### Advanced
- [ ] Codespaces environment works
- [ ] GCP VM setup complete
- [ ] Large batch processing tested
- [ ] Output files downloadable

---

## Next Steps

Once all tests pass:

1. **Place your FLIR images** in `./Images` folder
2. **Run batch processor**: `python flir_batch_processor.py ./Images --csv`
3. **Check results** in `./reports` folder
4. **Review visualizations** (if generated)
5. **Integrate into your workflow**

## Performance Benchmarks

### Typical Processing Times

- **Single 640x480 FLIR image**: ~1-2 seconds
- **Batch of 100 images**: ~2-3 minutes
- **1000+ images**: Consider Docker on GCP VM with multiple cores

### Optimization Tips

- Use SSD storage for faster I/O
- Process in batches on multi-core systems
- Use Docker with resource limits for consistent performance
- Upload large batches to GCP Cloud Storage for VM processing
