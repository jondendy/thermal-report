"""
Configuration module for thermal-report application.

All settings are driven by environment variables with sensible defaults.
This module is intentionally dependency-free so it can be imported early.
"""

from dotenv import load_dotenv
from pathlib import Path

# Get the directory where this settings.py file is located
SETTINGS_DIR = Path(__file__).resolve().parent
# Load .env from the same directory as settings.py
load_dotenv(SETTINGS_DIR / '.env')

import os

# ---------------------------------------------------------------------------
# Environment / runtime mode
# ---------------------------------------------------------------------------

FLASK_ENV = os.getenv("FLASK_ENV", "production")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Paths and storage
# ---------------------------------------------------------------------------
REPORTS_DIR = os.getenv('REPORTS_DIR', 'reports')

BASE_UPLOAD_DIR = os.getenv("UPLOAD_FOLDER", ".Images")
BASE_REPORT_DIR = os.getenv("REPORTS_FOLDER", ".reports")

BASE_UPLOAD_PATH = Path(BASE_UPLOAD_DIR)
BASE_REPORT_PATH = Path(BASE_REPORT_DIR)

BASE_UPLOAD_PATH.mkdir(parents=True, exist_ok=True)
BASE_REPORT_PATH.mkdir(parents=True, exist_ok=True)

STORAGE_TYPE = os.getenv("STORAGETYPE", "local")
STORAGE_ADDRESS = os.getenv("STORAGEADDRESS", "")
STORAGE_ACCESS_KEY = os.getenv("STORAGEACCESSKEY", "")

# ---------------------------------------------------------------------------
# Multi-tenant setup (single-tenant by default)
# ---------------------------------------------------------------------------

TENANT_MODE = os.getenv("TENANTMODE", "single")
DEFAULT_TENANT = os.getenv("DEFAULTTENANT", "default")

# ---------------------------------------------------------------------------
# Processing limits and behavior
# ---------------------------------------------------------------------------

BATCH_SIZE_MAX = int(os.getenv("BATCHSIZEMAX", "8"))

# Sensitivity used by ThermalAnalyzer (low=3σ, medium=2σ, high=1.5σ)
THERMAL_SENSITIVITY = os.getenv("THERMALSENSITIVITY", "medium")

# Maximum hotspots to detect per image (keeps hottest N)
MAX_HOTSPOTS_PER_IMAGE = int(os.getenv("MAX_HOTSPOTS_PER_IMAGE", "20"))

ALLOWED_EXTENSIONS = {"jpg", "jpeg"}
MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200 MB

UPLOAD_TIMEOUT_SECONDS = int(os.getenv("UPLOADTIMEOUTSECONDS", "300"))

# ---------------------------------------------------------------------------
# Organisation / reporting metadata
# ---------------------------------------------------------------------------

ORG_NAME = os.getenv("ORGNAME", "Your Survey Organisation")
ORG_WEBSITE = os.getenv("ORGWEBSITE", "https://example.com")
ORG_CONTACT = os.getenv("ORGCONTACT", "contact@example.com")

RECOMMENDATIONS_DOCUMENT_URL = os.getenv("RECOMMENDATIONS_DOCUMENT_URL", "")

REPORT_FILENAME_SUFFIX = os.getenv("REPORTFILENAMESUFFIX", "thermal-survey-report")

# ---------------------------------------------------------------------------
# Application identity
# ---------------------------------------------------------------------------

APP_NAME = "Thermal Report"
APP_VERSION = "2.0.0"
APP_DESCRIPTION = "Professional FLIR thermal image analysis for building heat loss surveys"

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------

LOG_LEVEL = os.getenv("LOGLEVEL", "ERROR")
LOG_FILE = os.getenv("LOGFILE", "thermal-report-errors.log")


def is_allowed_file(filename: str) -> bool:
    """Return True if the filename has an allowed extension."""
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext in ALLOWED_EXTENSIONS
