from __future__ import annotations
from google.oauth2 import service_account
from googleapiclient.discovery import build
import io
from pathlib import Path
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from settings import STORAGE_ADDRESS, STORAGE_ACCESS_KEY, PDF_STORAGE_ADDRESS

SCOPES = ["https://www.googleapis.com/auth/drive"]

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        "service-account.json",
        scopes=SCOPES,
    )
    return build("drive", "v3", credentials=creds)

def list_files_in_folder(folder_id):
    service = get_drive_service()
    q = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(q=q, fields="files(id, name, mimeType)").execute()
    return results.get("files", [])

def get_folder_metadata(folder_id: str) -> dict:
    """Return basic metadata (name, mimeType, id) for a Drive folder."""
    service = get_drive_service()
    meta = service.files().get(
        fileId=folder_id,
        fields="id, name, mimeType",
    ).execute()
    return meta

def download_file(file_id, dest_path):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

def getdriveservice():
    """Return an authorized Drive API service instance."""
    creds = service_account.Credentials.from_service_account_file(
        STORAGE_ACCESS_KEY,
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds)

def upload_file_to_folder(folder_id: str, local_path: str, mime_type: str | None = None) -> str:
    """
    Upload a local file to a Google Drive folder and return the new file ID.
    """
    service = getdriveservice()

    path = Path(local_path)
    if not mime_type:
        # fall back to a generic PDF type if not provided
        mime_type = "application/pdf"

    file_metadata = {
        "name": path.name,
        "parents": [folder_id],
    }
    media = MediaFileUpload(str(path), mimetype=mime_type, resumable=False)

    created = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id",
    ).execute()

    return created.get("id")
