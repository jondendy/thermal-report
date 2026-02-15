"""
Configuration module for thermal-report application.

All settings are driven by environment variables with sensible defaults.
This module is intentionally dependency-free so it can be imported early.
"""

from dotenv import load_dotenv
load_dotenv()  # Load .env file before reading environment variables

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Environment / runtime mode
# ---------------------------------------------------------------------------

FLASK_ENV = os.getenv("FLASK_ENV", "production")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Paths and storage
# ---------------------------------------------------------------------------
REPORTS_DIR = os.getenv('REPORTS_DIR', 'reports')
# or if you use UPLOAD_FOLDER as the base:
# REPORTS_DIR = UPLOAD_FOLDER

# Base directories for uploads and reports
BASE_UPLOAD_DIR = os.getenv("UPLOAD_FOLDER", ".Images")
BASE_REPORT_DIR = os.getenv("REPORTS_FOLDER", ".reports")

BASE_UPLOAD_PATH = Path(BASE_UPLOAD_DIR)
BASE_REPORT_PATH = Path(BASE_REPORT_DIR)

# Ensure directories exist at import time so the app can assume they are present
BASE_UPLOAD_PATH.mkdir(parents=True, exist_ok=True)
BASE_REPORT_PATH.mkdir(parents=True, exist_ok=True)

# Storage abstraction (currently only "local" implemented, but env-ready)
STORAGE_TYPE = os.getenv("STORAGETYPE", "local")  # local, googledrive, s3
STORAGE_ADDRESS = os.getenv("STORAGEADDRESS", "")  # URL or base path for cloud
STORAGE_ACCESS_KEY = os.getenv("STORAGEACCESSKEY", "")  # API key / service JSON

# ---------------------------------------------------------------------------
# Multi-tenant setup (single-tenant by default)
# ---------------------------------------------------------------------------

TENANT_MODE = os.getenv("TENANTMODE", "single")  # "single" or "multi"
DEFAULT_TENANT = os.getenv("DEFAULTTENANT", "default")

# ---------------------------------------------------------------------------
# Processing limits and behavior
# ---------------------------------------------------------------------------

# Max images per batch (UI already enforces 8)
BATCH_SIZE_MAX = int(os.getenv("BATCHSIZEMAX", "8"))

# Sensitivity used by ThermalAnalyzer / heat loss logic (low, medium, high)
THERMAL_SENSITIVITY = os.getenv("THERMALSENSITIVITY", "medium")

# Allowed upload extensions and max content length
ALLOWED_EXTENSIONS = {"jpg", "jpeg"}
MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200 MB

# Upload timeout (for large batches)
UPLOAD_TIMEOUT_SECONDS = int(os.getenv("UPLOADTIMEOUTSECONDS", "300"))

# ---------------------------------------------------------------------------
# Organisation / reporting metadata
# ---------------------------------------------------------------------------

ORG_NAME = os.getenv("ORGNAME", "Your Survey Organisation")
ORG_WEBSITE = os.getenv("ORGWEBSITE", "https://example.com")
ORG_CONTACT = os.getenv("ORGCONTACT", "contact@example.com")

# External recommendations document URL (e.g., Google Drive shareable link)
# Set this to the public link to your recommendations PDF/document
RECOMMENDATIONS_DOCUMENT_URL = os.getenv(
    "RECOMMENDATIONS_DOCUMENT_URL",
    ""  # Leave empty to hide the link in reports
)

# Suffix appended to generated report filenames
REPORT_FILENAME_SUFFIX = os.getenv("REPORTFILENAMESUFFIX", "thermal-survey-report")

# ---------------------------------------------------------------------------
# Application identity
# ---------------------------------------------------------------------------

APP_NAME = "Thermal Report"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "Professional FLIR thermal image analysis for building heat loss surveys"

# ---------------------------------------------------------------------------
# Logging configuration (used by lib.loggingconfig)
# ---------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOGLEVEL", "ERROR")
LOG_FILE = os.getenv("LOGFILE", "thermal-report-errors.log")


def is_allowed_file(filename: str) -> bool:
    """Return True if the filename has an allowed extension."""
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext in ALLOWED_EXTENSIONS
