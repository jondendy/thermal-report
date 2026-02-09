from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import os

SCOPES = ["https://www.googleapis.com/auth/drive"]

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'),
        scopes=SCOPES,
    )
    return build("drive", "v3", credentials=creds)

def list_files_in_folder(folder_id):

def get_folder_metadata(folder_id):
    service = get_drive_service()
    folder = service.files().get(fileId=folder_id, fields='id, name').execute()
    return folder

def upload_file_to_folder(file_path, folder_id):
    """Upload a file to a specific Google Drive folder."""
    from googleapiclient.http import MediaFileUpload
    import os

    service = get_drive_service()
    file_name = os.path.basename(file_path)

    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')

def rename_folder(folder_id, new_name):
    """Rename a Google Drive folder."""
    service = get_drive_service()
    file_metadata = {'name': new_name}
    updated_file = service.files().update(fileId=folder_id, body=file_metadata, fields='id, name').execute()
    return updated_file
    service = get_drive_service()
    q = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(q=q, fields="files(id, name)").execute()
    return results.get("files", [])

def download_file(file_id, dest_path):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    with open(dest_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        _, done = downloader.next_chunk()
