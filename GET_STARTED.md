# Getting Started with Refactored thermal-report

## Quick Start (5 minutes)

### 1. Prepare Your Test Images

Your 6 FLIR test images should be in `test_images/` folder:
```
test_images/
├── FLIR1470.jpg
├── FLIR1478.jpg
├── FLIR1462.jpg
├── FLIR1474.jpg
├── FLIR1466.jpg
└── FLIR1468.jpg
```

**Verify they're committed:**
```bash
git log --all --full-history -- test_images/FLIR*.jpg
```

---

### 2. Set Up Configuration

```bash
# Copy template
cp .env.example .env

# Edit with YOUR organisation details
nano .env
```

Minimal required changes:
```bash
ORG_NAME=Your Survey Team
ORG_WEBSITE=https://yourwebsite.com
ORG_CONTACT=your-email@example.com
```

---

### 3. Install Dependencies

```bash
# Create/activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install
pip install -r requirements.txt
```

---

### 4. Run Tests

```bash
# Security validation tests (should all pass)
pytest tests/test_security_utils.py -v

# Output should show:
# ✓ 4 tests in TestTenantIdValidation
# ✓ 4 tests in TestBatchIdValidation
# ✓ 3 tests in TestSafeBatchPath
# ✓ 2 tests in TestSafeUploadPath
# ✓ Total: 13 passed
```

---

### 5. Run Application

```bash
# Start Flask dev server
python app.py

# Output:
# * Running on http://0.0.0.0:5000
# Open browser to http://localhost:5000
```

---

## Testing Workflow

### Test 1: Upload & Process Batch

1. Open browser to `http://localhost:5000`
2. Click "Choose Files"
3. Select **all 6 test images** (FLIR1470–FLIR1468)
4. Click "Upload and Process"
5. Wait for processing (30–60 seconds)

**Expected result:**
- Batch is created with ID like `batch_20251214_154632_xxxxx`
- Batch appears in index with timestamp and 6 images
- Click batch ID to view results

**Check files were created:**
```bash
ls -la reports/batches/default/batch_20251214_154632_xxxxx/
# Should contain:
# - results.json
# - thermal_analysis.json
# - 6 × _labeled.jpg files
# - 6 × _thermal_report.html files
# - 6 × _temperatures.csv files
```

---

### Test 2: Label Hot Spots

1. From batch list, click batch ID
2. You should see batch summary (or click "Edit Spots" if link available)
3. Navigate to `/edit_spots/batch_20251214_154632_xxxxx`
4. You should see:
   - All 6 images in a grid
   - Detected hot spots highlighted on each
   - Dropdown for spot type (Window, Door, Wall, etc.)
   - Number field for cross-image identification

5. Label at least 3 hot spots:
   - Click first image's hottest area
   - Select type from dropdown
   - Enter number (e.g., 1)
   - Repeat for another image with same number (if visible in multiple)

6. Click "Save Labels"

**Expected result:**
- Labels saved to `hotspot_labels.json`
- JSON contains `labeled_spots` array and `cross_references`

**Check file:**
```bash
cat reports/batches/default/batch_20251214_154632_xxxxx/hotspot_labels.json
# Should show:
{
  "batch_id": "batch_20251214_154632_xxxxx",
  "tenant_id": "default",
  "labeled_spots": [...],
  "cross_references": {...}
}
```

---

### Test 3: Generate Heat Loss Report

1. On edit_spots page, click "Generate Report" button
2. Optionally enter:
   - Property Address
   - Inspector Name
3. Click "Generate"

**Expected result:**
- Report generated (takes 5–10 seconds)
- Button changes to "View Report"
- Click to see professional heat loss report

**Check files:**
```bash
cat reports/batches/default/batch_20251214_154632_xxxxx/heat_loss_report.json
# Should contain professional analysis with:
# - Org name and contact details
# - Property address and inspector (if provided)
# - Cross-image analysis of hot spots
# - Energy-saving recommendations per spot type
```

---

## Validating Data Contracts

### JSON Files Per Batch

After complete workflow, verify all JSON files exist and are valid:

```bash
BATCH_ID="batch_20251214_154632_xxxxx"
BATCH_DIR="reports/batches/default/$BATCH_ID"

# Verify all files present
for file in results.json thermal_analysis.json hotspot_labels.json heat_loss_report.json; do
    if [ -f "$BATCH_DIR/$file" ]; then
        echo "✓ $file exists"
        python -m json.tool "$BATCH_DIR/$file" > /dev/null && echo "  ✓ Valid JSON"
    else
        echo "✗ $file missing"
    fi
done
```

### Verify Data Shapes

Check that JSON has expected structure:

**results.json:**
```python
import json
with open('reports/batches/default/.../results.json') as f:
    data = json.load(f)
    
assert 'batch_id' in data
assert 'timestamp' in data
assert 'images' in data
assert len(data['images']) == 6  # 6 images processed
assert 'summary' in data
print("✓ results.json structure valid")
```

**thermal_analysis.json:**
```python
with open('reports/batches/default/.../thermal_analysis.json') as f:
    data = json.load(f)
    
assert 'images' in data
for img in data['images']:
    assert 'filename' in img
    assert 'hot_spots' in img
    assert 'stats' in img
print("✓ thermal_analysis.json structure valid")
```

**hotspot_labels.json:**
```python
with open('reports/batches/default/.../hotspot_labels.json') as f:
    data = json.load(f)
    
assert 'labeled_spots' in data
assert 'cross_references' in data
for spot in data['labeled_spots']:
    assert 'spot_id' in spot
    assert 'type' in spot
    assert spot['type'] in ['Window', 'Door', 'Wall', 'Eaves', 'Vent', 'Roof', 'Chimney', 'Porch']
    assert 'spot_number' in spot
print("✓ hotspot_labels.json structure valid")
```

**heat_loss_report.json:**
```python
with open('reports/batches/default/.../heat_loss_report.json') as f:
    data = json.load(f)
    
assert 'batch_id' in data
assert 'property_address' in data  # May be empty string
assert 'inspector_name' in data  # May be empty string
assert 'org_name' in data
assert 'findings' in data
assert len(data['findings']) > 0
print("✓ heat_loss_report.json structure valid")
```

---

## Debugging

### View Logs

```bash
# Real-time logs
tail -f thermal_report_errors.log

# All errors
cat thermal_report_errors.log
```

### Check Python Imports

Make sure all imports resolve:

```bash
python -c "from services.batch_service import process_batch; print('✓ batch_service imports OK')"
python -c "from services.heat_loss_service import generate_report; print('✓ heat_loss_service imports OK')"
python -c "from lib.security_utils import safe_batch_path; print('✓ security_utils imports OK')"
```

### Validate Security Functions

```bash
python << 'EOF'
from lib.security_utils import validate_batch_id, validate_tenant_id

# Valid IDs should work
try:
    validate_batch_id('batch_20251214_154632_a1b2c3d4')
    print("✓ Valid batch_id accepted")
except ValueError:
    print("✗ Valid batch_id rejected")

try:
    validate_tenant_id('org-1')
    print("✓ Valid tenant_id accepted")
except ValueError:
    print("✗ Valid tenant_id rejected")

# Invalid IDs should fail
try:
    validate_batch_id('../../etc/passwd')
    print("✗ Path traversal accepted (BAD)")
except ValueError:
    print("✓ Path traversal rejected (GOOD)")

try:
    validate_tenant_id('org@1')
    print("✗ Invalid tenant_id accepted (BAD)")
except ValueError:
    print("✓ Invalid tenant_id rejected (GOOD)")
EOF
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'settings'"

**Solution:** Make sure you're running from repo root:
```bash
pwd  # Should be /path/to/thermal-report
python app.py
```

### "Module has no attribute X"

**Solution:** Clear Python cache:
```bash
find . -type d -name __pycache__ -exec rm -rf {} +
find . -name "*.pyc" -delete
```

### Imports failing but file exists

**Solution:** Create `__init__.py` in missing directories:
```bash
touch lib/__init__.py
touch services/__init__.py
touch tests/__init__.py
```

### Flask not finding templates

**Solution:** Ensure `templates/` directory exists and templates are there:
```bash
ls templates/index.html
ls templates/edit_spots.html
ls templates/heat_loss_report.html
```

---

## Committing to GitHub

Once tests pass locally:

```bash
# Create branch
git checkout -b refactor/clean-architecture

# Add all new files
git add settings.py .env.example app.py lib/ services/ tests/ docs/ARCHITECTURE.md REFACTOR_SUMMARY.md

# Commit with detailed message
git commit -m "Refactor: Clean architecture with services layer

- Thin Flask app.py (routes only)
- services/batch_service.py (upload, processing, batch mgmt)
- services/heat_loss_service.py (labeling, report generation)
- services/batch_io.py (JSON I/O abstraction)
- lib/security_utils.py (tenant-aware path validation)
- lib/logging_config.py (centralized logging)
- settings.py (env-driven configuration)
- Full tenant-context design (zero refactoring for multi-tenant)
- Security unit tests
- Comprehensive architecture documentation

This refactor:
✓ Improves code clarity and maintainability
✓ Enables testing of business logic separately
✓ Supports cloud storage backends (abstraction ready)
✓ Multi-tenant ready (no code changes needed later)
✓ Configuration-driven (env vars, not hardcoded)
✓ Eliminates code duplication and over-complication
"

# Push
git push origin refactor/clean-architecture

# Create PR on GitHub
# Paste REFACTOR_SUMMARY.md content as PR description
```

---

## Next: Real-World Testing

Once this refactor branch is merged, the next phase is:

1. **Integration tests** with real FLIR batches (your 6 test images)
2. **Deployment testing** (Docker locally, then to GCP)
3. **Multi-tenant setup** (dummy second org for testing)
4. **Google Drive backend** (if you want cloud storage)

Each step is isolated and testable thanks to the clean architecture.

---

## Support

If you hit issues:

1. Check logs: `tail -f thermal_report_errors.log`
2. Run security tests: `pytest tests/test_security_utils.py -v`
3. Verify imports: `python -c "import app; print('OK')"`
4. Review ARCHITECTURE.md for design questions

Good luck! 🚀
