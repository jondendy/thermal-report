import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import googleapiclient.http

SCOPES = ["https://www.googleapis.com/auth/drive"]

def get_drive_service():
    # Use environment variable, fallback to default path
    key_path = os.environ.get('STORAGE_ACCESS_KEY') or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if not key_path:
        raise ValueError("STORAGE_ACCESS_KEY or GOOGLE_APPLICATION_CREDENTIALS not set in environment")
    
    creds = service_account.Credentials.from_service_account_file(
        key_path,
        scopes=SCOPES,
    )
    return build("drive", "v3", credentials=creds)

def list_files_in_folder(folder_id):
    service = get_drive_service()
    q = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(q=q, fields="files(id, name)").execute()
    return results.get("files", [])

def download_file(file_id, dest_path):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as fh:
        downloader = googleapiclient.http.MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
