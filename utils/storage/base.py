"""
Base class untuk semua storage provider.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import datetime


@dataclass
class FileInfo:
    """Representasi file/gambar yang tersimpan di storage."""
    id: str                          # ID unik dari provider
    name: str                        # Judul tampilan
    filename: str                    # Nama file asli
    url: str                         # URL publik untuk ditampilkan
    thumbnail_url: Optional[str]     # URL thumbnail (lebih kecil)
    size: int                        # Ukuran file dalam bytes
    uploaded_at: datetime.datetime   # Waktu upload
    album: str                       # Nama album
    provider: str                    # Identifier provider (e.g., 'gdrive1')
    provider_label: str              # Label human-readable (e.g., 'Google Drive #1')


class StorageProvider(ABC):
    """Abstract base class untuk semua storage provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifier unik untuk instance provider ini."""
        pass

    @property
    @abstractmethod
    def label(self) -> str:
        """Label human-readable."""
        pass

    @abstractmethod
    def upload(self, file_bytes: bytes, filename: str,
               title: str = "", album: str = "default") -> FileInfo:
        """Upload file ke storage dan kembalikan info file."""
        pass

    @abstractmethod
    def delete(self, file_id: str) -> bool:
        """Hapus file berdasarkan ID. Kembalikan True jika berhasil."""
        pass

    @abstractmethod
    def list_files(self, album: Optional[str] = None) -> list:
        """Ambil daftar semua file (atau filter berdasarkan album)."""
        pass

    @abstractmethod
    def get_quota(self) -> dict:
        """Kembalikan {'used': int, 'total': int, 'available': int} dalam bytes."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test apakah koneksi ke provider berhasil."""
        pass

    def format_size(self, size_bytes: int) -> str:
        """Format ukuran bytes ke string human-readable."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
