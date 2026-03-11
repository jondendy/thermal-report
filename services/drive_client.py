from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

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
