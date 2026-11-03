"""
Google Drive Storage Provider.
Menggunakan Service Account untuk akses server-side tanpa OAuth user.
"""
import json
import io
import datetime
from typing import Optional

import streamlit as st

from .base import StorageProvider, FileInfo

SCOPES = ['https://www.googleapis.com/auth/drive']
IMAGE_MIMETYPES = (
    'image/jpeg', 'image/png', 'image/gif',
    'image/webp', 'image/bmp', 'image/tiff'
)
MIME_MAP = {
    'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
    'png': 'image/png', 'gif': 'image/gif',
    'webp': 'image/webp', 'bmp': 'image/bmp',
    'tiff': 'image/tiff', 'tif': 'image/tiff',
}


def _build_service(credentials_json: str):
    """Build Google Drive service dari credentials JSON string."""
    from googleapiclient.discovery import build
    from google.oauth2 import service_account
    creds_dict = json.loads(credentials_json)
    credentials = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=SCOPES
    )
    return build('drive', 'v3', credentials=credentials, cache_discovery=False)


class GoogleDriveStorage(StorageProvider):
    """
    Storage provider menggunakan Google Drive via Service Account.

    Setup:
    1. Buat project di Google Cloud Console
    2. Enable Google Drive API
    3. Buat Service Account, download JSON credentials
    4. Buat folder di Google Drive, share ke email service account
    5. Copy folder ID dari URL Drive
    6. Isi credentials di secrets.toml
    """

    def __init__(self, credentials_json: str, folder_id: str,
                 provider_name: str, provider_label: str):
        self._name = provider_name
        self._label = provider_label
        self.folder_id = folder_id
        self._credentials_json = credentials_json
        self._service = None  # Lazy init

    @property
    def name(self) -> str:
        return self._name

    @property
    def label(self) -> str:
        return self._label

    @property
    def service(self):
        if self._service is None:
            self._service = _build_service(self._credentials_json)
        return self._service

    def _mime_from_filename(self, filename: str) -> str:
        ext = filename.lower().rsplit('.', 1)[-1]
        return MIME_MAP.get(ext, 'image/jpeg')

    def _parse_file(self, file: dict) -> FileInfo:
        """Parse response API Drive menjadi FileInfo."""
        try:
            meta = json.loads(file.get('description', '{}') or '{}')
        except Exception:
            meta = {}

        file_id = file['id']
        created = file.get('createdTime', datetime.datetime.utcnow().isoformat())
        try:
            uploaded_at = datetime.datetime.fromisoformat(created.replace('Z', '+00:00'))
        except Exception:
            uploaded_at = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

        return FileInfo(
            id=file_id,
            name=meta.get('title', file.get('name', file_id)),
            filename=file.get('name', file_id),
            url=f"https://drive.google.com/uc?export=view&id={file_id}",
            thumbnail_url=f"https://drive.google.com/thumbnail?id={file_id}&sz=w400",
            size=int(file.get('size', 0)),
            uploaded_at=uploaded_at,
            album=meta.get('album', 'default'),
            provider=self._name,
            provider_label=self._label,
        )

    def upload(self, file_bytes: bytes, filename: str,
               title: str = "", album: str = "default") -> FileInfo:
        from googleapiclient.http import MediaIoBaseUpload

        mime_type = self._mime_from_filename(filename)
        meta_json = json.dumps({
            'title': title or filename,
            'album': album,
            'uploaded_at': datetime.datetime.utcnow().isoformat(),
        })

        file_metadata = {
            'name': filename,
            'parents': [self.folder_id],
            'description': meta_json,
        }

        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,name,size,createdTime,description',
        ).execute()

        # Jadikan file bisa dilihat publik (link sharing)
        self.service.permissions().create(
            fileId=file['id'],
            body={'role': 'reader', 'type': 'anyone'},
        ).execute()

        return self._parse_file(file)

    def delete(self, file_id: str) -> bool:
        try:
            self.service.files().delete(fileId=file_id).execute()
            return True
        except Exception:
            return False

    def list_files(self, album: Optional[str] = None) -> list:
        mime_filter = " or ".join(f"mimeType='{m}'" for m in IMAGE_MIMETYPES)
        query = (
            f"({mime_filter}) and "
            f"'{self.folder_id}' in parents and trashed=false"
        )

        files = []
        page_token = None
        while True:
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='nextPageToken, files(id,name,size,createdTime,description)',
                pageToken=page_token,
                pageSize=100,
                orderBy='createdTime desc',
            ).execute()

            for f in results.get('files', []):
                fi = self._parse_file(f)
                if album is None or fi.album == album:
                    files.append(fi)

            page_token = results.get('nextPageToken')
            if not page_token:
                break

        return files

    def get_quota(self) -> dict:
        try:
            about = self.service.about().get(fields='storageQuota').execute()
            q = about.get('storageQuota', {})
            used = int(q.get('usage', 0))
            total = int(q.get('limit', 0))
            return {
                'used': used,
                'total': total,
                'available': max(0, total - used),
            }
        except Exception:
            return {'used': 0, 'total': 0, 'available': 0}

    def test_connection(self) -> bool:
        try:
            self.service.files().list(pageSize=1, fields='files(id)').execute()
            return True
        except Exception:
            return False
