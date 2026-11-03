"""
Yandex Disk Storage Provider.
Menggunakan Yandex Disk REST API dengan OAuth token.
"""
import io
import datetime
import hashlib
from typing import Optional

import requests

from .base import StorageProvider, FileInfo

YANDEX_API_BASE = "https://cloud-api.yandex.net/v1/disk"
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}


class YandexDiskStorage(StorageProvider):
    """
    Storage provider menggunakan Yandex Disk.

    Setup:
    1. Daftar/login di yandex.com (gratis 10GB)
    2. Buat app di https://oauth.yandex.com
    3. Dapatkan OAuth token
    4. Isi di secrets.toml
    """

    def __init__(self, oauth_token: str, base_folder: str = "Galeri",
                 provider_name: str = "yandex", provider_label: str = "Yandex Disk"):
        self._name = provider_name
        self._label = provider_label
        self.base_folder = base_folder
        self.headers = {
            'Authorization': f'OAuth {oauth_token}',
            'Content-Type': 'application/json',
        }
        self._ensure_base_folder()

    @property
    def name(self) -> str:
        return self._name

    @property
    def label(self) -> str:
        return self._label

    def _ensure_base_folder(self):
        """Pastikan folder dasar ada di Yandex Disk."""
        try:
            requests.put(
                f"{YANDEX_API_BASE}/resources",
                headers=self.headers,
                params={'path': self.base_folder},
            )
        except Exception:
            pass

    def _ensure_album_folder(self, album: str):
        """Pastikan subfolder album ada."""
        folder_path = f"{self.base_folder}/{album}"
        try:
            requests.put(
                f"{YANDEX_API_BASE}/resources",
                headers=self.headers,
                params={'path': folder_path},
            )
        except Exception:
            pass
        return folder_path

    def _get_upload_url(self, path: str) -> str:
        """Dapatkan URL upload dari Yandex Disk."""
        resp = requests.get(
            f"{YANDEX_API_BASE}/resources/upload",
            headers=self.headers,
            params={'path': path, 'overwrite': 'true'},
        )
        resp.raise_for_status()
        return resp.json()['href']

    def _get_public_url(self, path: str) -> Optional[str]:
        """Publish file dan dapatkan URL publik."""
        # Publish file
        requests.put(
            f"{YANDEX_API_BASE}/resources/publish",
            headers=self.headers,
            params={'path': path},
        )
        # Get public URL
        resp = requests.get(
            f"{YANDEX_API_BASE}/resources",
            headers=self.headers,
            params={'path': path, 'fields': 'public_url,public_key'},
        )
        if resp.ok:
            data = resp.json()
            return data.get('public_url')
        return None

    def upload(self, file_bytes: bytes, filename: str,
               title: str = "", album: str = "default") -> FileInfo:
        album_folder = self._ensure_album_folder(album)
        file_path = f"{album_folder}/{filename}"

        upload_url = self._get_upload_url(file_path)
        requests.put(upload_url, data=file_bytes)

        public_url = self._get_public_url(file_path)

        # Update file description/comment with metadata
        # Yandex API supports custom_properties
        requests.patch(
            f"{YANDEX_API_BASE}/resources",
            headers=self.headers,
            params={'path': file_path},
            json={'custom_properties': {
                'title': title or filename,
                'album': album,
            }},
        )

        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        file_id = hashlib.md5(file_path.encode()).hexdigest()

        return FileInfo(
            id=file_path,  # Gunakan path sebagai ID
            name=title or filename,
            filename=filename,
            url=public_url or '',
            thumbnail_url=public_url,
            size=len(file_bytes),
            uploaded_at=now,
            album=album,
            provider=self._name,
            provider_label=self._label,
        )

    def delete(self, file_id: str) -> bool:
        """file_id adalah path file di Yandex Disk."""
        try:
            resp = requests.delete(
                f"{YANDEX_API_BASE}/resources",
                headers=self.headers,
                params={'path': file_id, 'permanently': 'true'},
            )
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def list_files(self, album: Optional[str] = None) -> list:
        files = []
        folder = f"{self.base_folder}/{album}" if album else self.base_folder

        def _list_folder(path: str, album_name: str):
            offset = 0
            limit = 100
            while True:
                resp = requests.get(
                    f"{YANDEX_API_BASE}/resources",
                    headers=self.headers,
                    params={
                        'path': path,
                        'fields': '_embedded.items,_embedded.total',
                        'limit': limit,
                        'offset': offset,
                    },
                )
                if not resp.ok:
                    break
                data = resp.json()
                items = data.get('_embedded', {}).get('items', [])

                for item in items:
                    if item['type'] == 'dir' and not album:
                        # Rekursif untuk subfolder (album)
                        _list_folder(item['path'], item['name'])
                    elif item['type'] == 'file':
                        name = item['name']
                        ext = '.' + name.rsplit('.', 1)[-1].lower() if '.' in name else ''
                        if ext not in IMAGE_EXTENSIONS:
                            continue

                        custom = item.get('custom_properties', {}) or {}
                        try:
                            modified = item.get('modified', '')
                            uploaded_at = datetime.datetime.fromisoformat(
                                modified.replace('Z', '+00:00')
                            )
                        except Exception:
                            uploaded_at = datetime.datetime.utcnow().replace(
                                tzinfo=datetime.timezone.utc
                            )

                        files.append(FileInfo(
                            id=item['path'],
                            name=custom.get('title', name),
                            filename=name,
                            url=item.get('public_url', ''),
                            thumbnail_url=item.get('public_url', ''),
                            size=item.get('size', 0),
                            uploaded_at=uploaded_at,
                            album=custom.get('album', album_name),
                            provider=self._name,
                            provider_label=self._label,
                        ))

                total = data.get('_embedded', {}).get('total', 0)
                offset += limit
                if offset >= total:
                    break

        try:
            _list_folder(folder, album or 'default')
        except Exception:
            pass

        return files

    def get_quota(self) -> dict:
        try:
            resp = requests.get(
                f"{YANDEX_API_BASE}",
                headers=self.headers,
                params={'fields': 'total_space,used_space'},
            )
            if resp.ok:
                data = resp.json()
                total = data.get('total_space', 0)
                used = data.get('used_space', 0)
                return {'used': used, 'total': total, 'available': max(0, total - used)}
        except Exception:
            pass
        return {'used': 0, 'total': 0, 'available': 0}

    def test_connection(self) -> bool:
        try:
            resp = requests.get(
                f"{YANDEX_API_BASE}",
                headers=self.headers,
                params={'fields': 'user'},
            )
            return resp.ok
        except Exception:
            return False
