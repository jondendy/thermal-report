from __future__ import annotations

import json
import logging
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from settings import STORAGE_ADDRESS, PDF_STORAGE_ADDRESS

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]

_SECRET_NAME = "projects/sc-thermal-project/secrets/drive-token/versions/latest"
_TOKEN_FILE = Path("token.json")


def _load_creds_from_secret_manager() -> Credentials | None:
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        payload = client.access_secret_version(name=_SECRET_NAME).payload.data.decode("utf-8")
        creds = Credentials.from_authorized_user_info(json.loads(payload), SCOPES)
        logger.info("Loaded Drive credentials from Secret Manager")
        return creds
    except Exception as e:
        logger.warning("Could not load credentials from Secret Manager: %s", e)
        return None


def _load_creds_from_file() -> Credentials | None:
    if not _TOKEN_FILE.exists():
        logger.warning("token.json not found at %s", _TOKEN_FILE.resolve())
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), SCOPES)
        logger.info("Loaded Drive credentials from token.json")
        return creds
    except Exception as e:
        logger.warning("Could not load credentials from token.json: %s", e)
        return None


def get_drive_credentials() -> Credentials:
    """
    Load OAuth2 user credentials.
    1. GCP Secret Manager (production)
    2. Local token.json (development fallback)
    Refreshes token if expired.
    """
    creds = _load_creds_from_secret_manager() or _load_creds_from_file()

    if creds is None:
        raise RuntimeError(
            "No Drive credentials available. "
            "Ensure 'drive-token' secret exists in Secret Manager, "
            "or place a valid token.json in the app root directory."
        )

    if creds.expired and creds.refresh_token:
        logger.info("Refreshing expired Drive token")
        creds.refresh(Request())

    return creds


def get_drive_service():
    """Return an authorised Google Drive API v3 service."""
    return build("drive", "v3", credentials=get_drive_credentials())


def list_files_in_folder(folder_id: str) -> list:
    service = get_drive_service()
    q = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(
        q=q, fields="files(id, name, mimeType)",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    return results.get("files", [])


def get_folder_metadata(folder_id: str) -> dict:
    service = get_drive_service()
    return service.files().get(
        fileId=folder_id, fields="id, name, mimeType",
        supportsAllDrives=True,
    ).execute()


def download_file(file_id: str, dest_path: str) -> None:
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def upload_file_to_folder(folder_id: str, local_path: str, mime_type: str | None = None) -> str:
    service = get_drive_service()
    path = Path(local_path)
    if not mime_type:
        mime_type = "application/pdf"
    file_metadata = {"name": path.name, "parents": [folder_id]}
    media = MediaFileUpload(str(path), mimetype=mime_type, resumable=False)
    created = service.files().create(
        body=file_metadata, media_body=media, fields="id",
        supportsAllDrives=True,
    ).execute()
    return created.get("id")
