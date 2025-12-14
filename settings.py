"""
Configuration module for thermal-report application.
All settings are driven by environment variables with sensible defaults.
"""
import os
from pathlib import Path

# ============================================================================
# Flask & Environment
# ============================================================================

FLASK_ENV = os.getenv('FLASK_ENV', 'production')
FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

# ============================================================================
# Paths & Storage
# ============================================================================

BASE_UPLOAD_DIR = os.getenv('UPLOAD_FOLDER', 'Images')
BASE_REPORT_DIR = os.getenv('REPORTS_FOLDER', 'reports')

# Create directories if they don't exist
Path(BASE_UPLOAD_DIR).mkdir(exist_ok=True)
Path(BASE_REPORT_DIR).mkdir(exist_ok=True)

# ============================================================================
# Tenancy (Single-tenant now, multi-tenant ready)
# ============================================================================

TENANT_MODE = os.getenv('TENANT_MODE', 'single')  # 'single' or 'multi'
DEFAULT_TENANT = os.getenv('DEFAULT_TENANT', 'default')

# ============================================================================
# Processing Parameters
# ============================================================================

BATCH_SIZE_MAX = int(os.getenv('BATCH_SIZE_MAX', '8'))
THERMAL_SENSITIVITY = os.getenv('THERMAL_SENSITIVITY', 'medium')  # low, medium, high

ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}
MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200MB max upload

# ============================================================================
# Logging
# ============================================================================

LOG_LEVEL = os.getenv('LOG_LEVEL', 'ERROR')
LOG_FILE = os.getenv('LOG_FILE', 'thermal_report_errors.log')

# ============================================================================
# Survey Organisation Details (for reports)
# ============================================================================

ORG_NAME = os.getenv('ORG_NAME', 'Your Survey Organisation')
ORG_WEBSITE = os.getenv('ORG_WEBSITE', 'https://example.com')
ORG_CONTACT = os.getenv('ORG_CONTACT', 'contact@example.com')

# Used at end of generated reports
REPORT_FILENAME_SUFFIX = os.getenv('REPORT_FILENAME_SUFFIX', 'thermal_survey_report')

# ============================================================================
# Storage Backend Configuration (for future cloud integration)
# ============================================================================

# Type of storage: 'local', 'google_drive', 's3' (currently only 'local' implemented)
STORAGE_TYPE = os.getenv('STORAGE_TYPE', 'local')

# For Google Drive integration (or other cloud storage)
STORAGE_ADDRESS = os.getenv('STORAGE_ADDRESS', '')  # Folder URL or base path
STORAGE_ACCESS_KEY = os.getenv('STORAGE_ACCESS_KEY', '')  # API key / service account JSON path

# ============================================================================
# Application Metadata
# ============================================================================

APP_NAME = 'Thermal Report'
APP_VERSION = '2.0.0'
APP_DESCRIPTION = 'Professional FLIR thermal image analysis for building heat loss surveys'

# ============================================================================
# File Upload Configuration
# ============================================================================

UPLOAD_TIMEOUT_SECONDS = int(os.getenv('UPLOAD_TIMEOUT_SECONDS', '300'))  # 5 minutes
