# Thermal Report – Refactored Architecture

## Overview

The refactored thermal-report application uses a **clean separation of concerns**:

- **`app.py`** – Thin Flask routing layer only
- **`services/`** – Business logic (orchestration, I/O, workflows)
- **`lib/`** – Shared utilities (security, logging, storage abstractions)
- **`settings.py`** – Configuration via environment variables

This structure makes the codebase easier to understand, test, extend, and deploy to multiple organisations.

## Directory Structure

```
thermal-report/
├── app.py                    # Flask routes (thin)
├── settings.py               # Configuration (env-driven)
├── requirements.txt          # Python dependencies
├── Dockerfile                # Single canonical Docker config
├── .env.example              # Config template
│
├── services/                 # Business logic layer
│   ├── batch_service.py      # Upload, processing, batch management
│   ├── heat_loss_service.py  # Labeling, report generation
│   └── batch_io.py           # JSON I/O abstraction
│
├── lib/                      # Shared utilities
│   ├── security_utils.py     # Path validation, tenant-aware
│   ├── logging_config.py     # Centralized logging setup
│   └── storage.py            # (Future) Cloud storage backends
│
├── templates/
│   ├── index.html            # Upload & batch index
│   ├── edit_spots.html       # CANONICAL labeling interface
│   ├── heat_loss_report.html # Final homeowner report
│   └── info.html             # Help/info
│
├── static/
│   ├── css/
│   └── js/
│
├── tests/
│   ├── test_security_utils.py
│   ├── test_batch_service.py
│   └── test_heat_loss_service.py
│
├── docs/
│   ├── ARCHITECTURE.md       # This file
│   ├── DEPLOYMENT.md         # Deployment guide
│   ├── API.md                # API endpoint reference
│   └── ...
│
└── [Core FLIR processing files]
    ├── flir_processor_simple.py
    ├── thermal_analyzer.py
    ├── heat_loss_reporter.py
    └── energy_recommendations.json
```

## Key Principles

### 1. Single Responsibility

Each module has **one clear job**:

| Module | Responsibility |
|--------|-----------------|
| `app.py` | HTTP routing and request handling |
| `batch_service.py` | Upload orchestration and batch processing |
| `heat_loss_service.py` | Labeling workflow and report generation |
| `batch_io.py` | All JSON file read/write operations |
| `security_utils.py` | Path validation and tenant context |
| `logging_config.py` | Centralized logging setup |

### 2. Tenant-Aware Design

All paths and data are structured with **tenant context from day one**, even though single-tenant is used now:

```python
batch_path = safe_batch_path(batch_id, tenant_id='org-a')
# → reports/batches/org-a/batch_20251214_154632_xxxxx/
```

This means **zero refactoring** needed when adding multi-tenant support later.

### 3. Configuration via Environment

All settings come from environment variables (`.env` file or container env):

```bash
ORG_NAME="Survey Team A"
ORG_WEBSITE="https://surveyteama.com"
STORAGE_TYPE="google_drive"
STORAGE_ADDRESS="https://drive.google.com/drive/folders/XXXXX"
```

Makes it trivial to deploy the same Docker image with different configs per organisation.

### 4. Data Access Abstraction

All JSON I/O goes through `batch_io.py`:

```python
# GOOD
results = batch_io.load_batch_results(batch_id)

# BAD (don't do this)
with open(f'reports/batches/{batch_id}/results.json') as f:
    results = json.load(f)
```

This allows swapping storage backends (S3, Google Drive) without touching business logic.

---

## Data Flow

### Batch Processing Workflow

```
1. User uploads 6-8 FLIR images
        ↓
2. app.py:/upload → batch_service.process_batch()
        ↓
3. batch_service:
   - SimpleFLIRProcessor extracts temps
   - ThermalAnalyzer detects hot spots
   - Saves: results.json, thermal_analysis.json
        ↓
4. User navigates to /edit_spots/<batch_id>
        ↓
5. app.py:/edit_spots → heat_loss_service.get_thermal_analysis()
   - Loads thermal_analysis.json for UI
   - Shows images with detected hot spots
        ↓
6. Operator labels spots (types, numbers)
        ↓
7. app.py:/save_labels → heat_loss_service.save_labels()
   - Saves hotspot_labels.json
   - Generates cross-references
        ↓
8. Operator clicks "Generate Report"
        ↓
9. app.py:/generate_heat_loss_report → heat_loss_service.generate_report()
   - HeatLossReporter combines:
     * Thermal analysis data
     * Operator labels
     * Energy recommendations
   - Saves heat_loss_report.json
        ↓
10. app.py:/view_heat_loss_report → renders homeowner-facing report
```

### JSON Files per Batch

Each batch produces 4 JSON files (in `reports/batches/<tenant_id>/<batch_id>/`):

| File | Purpose | Created By |
|------|---------|-----------|
| `results.json` | Processing summary (all images, temps, stats) | `batch_service` |
| `thermal_analysis.json` | Raw analyzer output (hot spots per image) | `batch_service` |
| `hotspot_labels.json` | Operator labels (types, numbers, cross-refs) | `heat_loss_service` |
| `heat_loss_report.json` | Final report data (recommendations, cross-image analysis) | `heat_loss_service` |

---

## Services Layer API

### `batch_service`

```python
# Upload and process images
results = batch_service.process_batch(
    batch_id='batch_20251214_154632_a1b2c3d4',
    image_files=[...],
    tenant_id='org-a'
)

# List all batches for a tenant
batches = batch_service.get_all_batches(tenant_id='org-a')

# Get summary of single batch
summary = batch_service.get_batch_summary(batch_id, tenant_id='org-a')
```

### `heat_loss_service`

```python
# Get thermal analysis for labeling UI
analysis = heat_loss_service.get_thermal_analysis(batch_id, tenant_id='org-a')

# Load existing labels (if any)
labels = heat_loss_service.get_existing_labels(batch_id, tenant_id='org-a')

# Save operator labels
heat_loss_service.save_labels(batch_id, label_data, tenant_id='org-a')

# Generate report
report = heat_loss_service.generate_report(
    batch_id,
    property_address='123 Main St',
    inspector_name='John Doe',
    tenant_id='org-a'
)

# Load generated report
report_data = heat_loss_service.get_report(batch_id, tenant_id='org-a')
```

### `batch_io`

```python
# Load/save any JSON file safely
data = batch_io.load_json(file_path)
batch_io.save_json(file_path, data)

# Higher-level API (recommended)
results = batch_io.load_batch_results(batch_id, tenant_id='org-a')
labels = batch_io.load_hotspot_labels(batch_id, tenant_id='org-a')
```

---

## Security Model

### Path Validation

All paths go through `safe_batch_path()` which:
1. Validates batch ID format (prevents injection)
2. Validates tenant ID format (prevents traversal)
3. Constructs safe path: `reports/batches/<tenant_id>/<batch_id>/`
4. Verifies resolved path stays within base directory (path traversal prevention)

```python
from lib.security_utils import safe_batch_path

# Safe – validated inputs
path = safe_batch_path('batch_20251214_154632_a1b2c3d4', tenant_id='org-a')

# Raises ValueError – invalid format
path = safe_batch_path('../../etc/passwd', tenant_id='org-a')
```

### Tenant Isolation

Even in single-tenant mode, all paths are tenant-aware:

```
reports/batches/default/batch_20251214_154632_xxxxx/
```

When switching to multi-tenant, just parse tenant ID from request (e.g., via JWT or headers) and pass to all service functions.

---

## Configuration

### Environment Variables

See `.env.example` for all available settings:

```bash
# Flask
FLASK_ENV=production
FLASK_DEBUG=false

# Paths
UPLOAD_FOLDER=Images
REPORTS_FOLDER=reports

# Tenancy
TENANT_MODE=single
DEFAULT_TENANT=default

# Processing
BATCH_SIZE_MAX=8
THERMAL_SENSITIVITY=medium

# Survey Organisation (in reports)
ORG_NAME=Your Organisation
ORG_WEBSITE=https://yourorg.com
ORG_CONTACT=contact@yourorg.com

# Storage (future cloud integration)
STORAGE_TYPE=local
STORAGE_ADDRESS=
STORAGE_ACCESS_KEY=
```

Load config:
```python
import settings
print(settings.ORG_NAME)
```

---

## Testing Strategy

### Security Tests (`tests/test_security_utils.py`)

- Tenant ID validation (alphanumeric, hyphens, underscores only)
- Batch ID validation (format: batch_YYYYMMDD_HHMMSS_hash)
- Path traversal prevention
- Invalid input rejection

Run:
```bash
pytest tests/test_security_utils.py -v
```

### Data Flow Tests (Planned)

- Batch upload → results.json creation
- Thermal analysis → hot spot detection
- Label saving → hotspot_labels.json
- Report generation → heat_loss_report.json

---

## Extending the Architecture

### Adding a New Feature

Example: "Allow users to edit detected hot spots before labeling"

1. **Add service function** in `heat_loss_service.py`:
   ```python
   def update_hot_spots(batch_id, spot_updates, tenant_id=None):
       # Load current analysis
       # Apply updates
       # Save modified analysis
   ```

2. **Add Flask route** in `app.py`:
   ```python
   @app.route('/update_spots/<batch_id>', methods=['POST'])
   def update_spots(batch_id):
       updates = request.get_json()
       result = heat_loss_service.update_hot_spots(batch_id, updates)
       return jsonify({'success': True})
   ```

3. **Update template** `edit_spots.html` to expose UI for editing

4. **Add tests** in `tests/test_heat_loss_service.py`

### Adding Cloud Storage

1. Create `lib/storage/google_drive.py` implementing storage interface
2. Instantiate correct backend in `app.py`:
   ```python
   if settings.STORAGE_TYPE == 'google_drive':
       storage = GoogleDriveStorage(settings.STORAGE_ACCESS_KEY)
   else:
       storage = LocalFileStorage()
   ```
3. Pass to service functions instead of direct file I/O

---

## Deployment

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment (or use .env file)
export FLASK_ENV=development
export FLASK_DEBUG=true

# Run
python app.py
```

### Docker

```bash
# Build
docker build -t thermal-report .

# Run with custom config
docker run -p 5000:5000 \
  -e ORG_NAME="Survey Team A" \
  -e STORAGE_TYPE=google_drive \
  -e STORAGE_ADDRESS="https://drive.google.com/..." \
  -v $(pwd)/Images:/app/Images \
  -v $(pwd)/reports:/app/reports \
  thermal-report
```

See `docs/DEPLOYMENT.md` for multi-organisation setup.

---

## Summary

The refactored architecture is:

✅ **Clean** – Clear separation of concerns  
✅ **Secure** – Tenant-aware, path validation, no traversal attacks  
✅ **Testable** – Services are independent, easy to mock  
✅ **Extensible** – New features don't require touching routing or core logic  
✅ **Multi-tenant ready** – Zero refactoring needed when scaling to multiple orgs  
✅ **Cloud-ready** – Storage abstraction allows swapping backends  
✅ **Configurable** – Environment-driven, no hardcoded paths or settings  

