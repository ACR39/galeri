"""
Cloudinary Storage Provider.
Menggunakan Cloudinary SDK untuk upload dan manajemen gambar.
"""
import io
import datetime
from typing import Optional

import cloudinary
import cloudinary.uploader
import cloudinary.api

from .base import StorageProvider, FileInfo


class CloudinaryStorage(StorageProvider):
    """
    Storage provider menggunakan Cloudinary.

    Setup:
    1. Daftar di cloudinary.com (gratis 25GB)
    2. Dapatkan cloud_name, api_key, api_secret dari dashboard
    3. Isi di secrets.toml
    """

    def __init__(self, cloud_name: str, api_key: str, api_secret: str,
                 folder: str = "galeri", provider_name: str = "cloudinary",
                 provider_label: str = "Cloudinary"):
        self._name = provider_name
        self._label = provider_label
        self.folder = folder
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def label(self) -> str:
        return self._label

    def upload(self, file_bytes: bytes, filename: str,
               title: str = "", album: str = "default") -> FileInfo:
        folder_path = f"{self.folder}/{album}"
        context = f"title={title or filename}|album={album}|uploaded_by=galeri_app"

        result = cloudinary.uploader.upload(
            file_bytes,
            folder=folder_path,
            use_filename=True,
            unique_filename=True,
            overwrite=False,
            resource_type='image',
            context=context,
            tags=[album, 'galeri'],
        )

        public_id = result['public_id']
        url = result['secure_url']
        # Thumbnail dengan transformasi Cloudinary
        thumbnail_url = cloudinary.CloudinaryImage(public_id).build_url(
            width=400, height=400, crop='fill', quality='auto', format='webp'
        )

        try:
            uploaded_at = datetime.datetime.fromisoformat(
                result.get('created_at', '').replace('Z', '+00:00')
            )
        except Exception:
            uploaded_at = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

        return FileInfo(
            id=public_id,
            name=title or filename,
            filename=filename,
            url=url,
            thumbnail_url=thumbnail_url,
            size=int(result.get('bytes', 0)),
            uploaded_at=uploaded_at,
            album=album,
            provider=self._name,
            provider_label=self._label,
        )

    def delete(self, file_id: str) -> bool:
        try:
            result = cloudinary.uploader.destroy(file_id)
            return result.get('result') == 'ok'
        except Exception:
            return False

    def list_files(self, album: Optional[str] = None) -> list:
        files = []
        prefix = f"{self.folder}/{album}" if album else self.folder
        next_cursor = None

        while True:
            params = {
                'type': 'upload',
                'prefix': prefix,
                'max_results': 100,
                'context': True,
                'tags': True,
            }
            if next_cursor:
                params['next_cursor'] = next_cursor

            result = cloudinary.api.resources(**params)

            for resource in result.get('resources', []):
                public_id = resource['public_id']
                ctx = resource.get('context', {}).get('custom', {})

                # Extract album from folder path
                parts = public_id.split('/')
                # folder structure: galeri/album/filename
                file_album = parts[-2] if len(parts) >= 3 else 'default'

                try:
                    uploaded_at = datetime.datetime.fromisoformat(
                        resource.get('created_at', '').replace('Z', '+00:00')
                    )
                except Exception:
                    uploaded_at = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

                thumbnail_url = cloudinary.CloudinaryImage(public_id).build_url(
                    width=400, height=400, crop='fill', quality='auto', format='webp'
                )

                files.append(FileInfo(
                    id=public_id,
                    name=ctx.get('title', public_id.split('/')[-1]),
                    filename=resource.get('filename', public_id.split('/')[-1]),
                    url=resource['secure_url'],
                    thumbnail_url=thumbnail_url,
                    size=int(resource.get('bytes', 0)),
                    uploaded_at=uploaded_at,
                    album=file_album,
                    provider=self._name,
                    provider_label=self._label,
                ))

            next_cursor = result.get('next_cursor')
            if not next_cursor:
                break

        return files

    def get_quota(self) -> dict:
        try:
            usage = cloudinary.api.usage()
            used = usage.get('storage', {}).get('usage', 0)
            # Cloudinary free tier: 25GB = 25 * 1024^3 bytes
            total = usage.get('storage', {}).get('limit', 25 * 1024 ** 3)
            return {
                'used': used,
                'total': total,
                'available': max(0, total - used),
            }
        except Exception:
            return {'used': 0, 'total': 0, 'available': 0}

    def test_connection(self) -> bool:
        try:
            cloudinary.api.ping()
            return True
        except Exception:
            return False
