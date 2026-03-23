from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io, os, json

SCOPES = ["https://www.googleapis.com/auth/drive"]

def get_drive_service():
    creds_raw = os.environ.get("GOOGLE_DRIVE_CREDENTIALS")
    if creds_raw:
        info = json.loads(creds_raw)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = service_account.Credentials.from_service_account_file(
            "service-account.json", scopes=SCOPES
        )
    return build("drive", "v3", credentials=creds)

def list_folders(parent_id):
    service = get_drive_service()
    q = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=q, fields="files(id, name)", orderBy="name", supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
    return results.get("files", [])

def list_files_in_folder(folder_id):
    service = get_drive_service()
    q = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(
        q=q,
        fields="files(id, name, mimeType, thumbnailLink, imageMediaMetadata, size)",
        orderBy="name"
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    return results.get("files", [])

def get_folder_metadata(folder_id: str) -> dict:
    service = get_drive_service()
    return service.files().get(fileId=folder_id, fields="id, name, mimeType").execute()

def download_file(file_id, dest_path):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
