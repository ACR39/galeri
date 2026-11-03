"""
Storage Manager - Mengelola beberapa provider dan strategi penyimpanan.
"""
from typing import Optional
import streamlit as st

from .base import StorageProvider, FileInfo

STRATEGIES = {
    'fallback': 'Fallback – Gunakan provider berikutnya jika yang aktif hampir penuh (>90%)',
    'load_balance': 'Load Balance – Distribusi merata ke semua provider',
    'backup': 'Backup Ganda – Simpan ke SEMUA provider sekaligus',
    'primary': 'Primary – Selalu gunakan provider pertama',
}

QUOTA_THRESHOLD = 0.90  # 90% penuh = switch ke provider berikutnya


class StorageManager:
    """
    Mengelola beberapa storage provider dengan berbagai strategi.
    """

    def __init__(self, providers: list[StorageProvider], strategy: str = 'fallback'):
        self.providers = providers  # Urutan penting untuk fallback/primary
        self.strategy = strategy
        self._round_robin_index = 0

    @property
    def active_providers(self) -> list[StorageProvider]:
        return self.providers

    def _get_quota_usage_ratio(self, provider: StorageProvider) -> float:
        """Kembalikan rasio penggunaan quota (0.0 - 1.0)."""
        try:
            q = provider.get_quota()
            if q['total'] == 0:
                return 0.0
            return q['used'] / q['total']
        except Exception:
            return 0.0

    def _select_provider_fallback(self) -> Optional[StorageProvider]:
        """Pilih provider pertama yang belum penuh."""
        for p in self.providers:
            if self._get_quota_usage_ratio(p) < QUOTA_THRESHOLD:
                return p
        # Jika semua hampir penuh, gunakan yang paling sedikit terisi
        if self.providers:
            return min(self.providers, key=self._get_quota_usage_ratio)
        return None

    def _select_provider_load_balance(self) -> Optional[StorageProvider]:
        """Round-robin ke semua provider."""
        if not self.providers:
            return None
        idx = self._round_robin_index % len(self.providers)
        self._round_robin_index += 1
        return self.providers[idx]

    def _select_provider_primary(self) -> Optional[StorageProvider]:
        """Selalu gunakan provider pertama."""
        return self.providers[0] if self.providers else None

    def select_upload_provider(self) -> Optional[StorageProvider]:
        """Pilih provider untuk upload berikutnya berdasarkan strategi."""
        if not self.providers:
            return None
        if self.strategy == 'fallback':
            return self._select_provider_fallback()
        elif self.strategy == 'load_balance':
            return self._select_provider_load_balance()
        elif self.strategy == 'backup':
            return self.providers[0]  # Primary, tapi upload ke semua
        elif self.strategy == 'primary':
            return self._select_provider_primary()
        return self._select_provider_fallback()

    def upload(self, file_bytes: bytes, filename: str,
               title: str = "", album: str = "default",
               target_provider: Optional[str] = None) -> list[FileInfo]:
        """
        Upload file ke provider berdasarkan strategi.
        Kembalikan list FileInfo (bisa lebih dari 1 jika strategy='backup').
        """
        if not self.providers:
            raise RuntimeError("Tidak ada storage provider yang terkonfigurasi.")

        results = []

        if target_provider:
            # Upload ke provider spesifik (dipilih manual oleh admin)
            provider = next((p for p in self.providers if p.name == target_provider), None)
            if provider:
                fi = provider.upload(file_bytes, filename, title, album)
                results.append(fi)

        elif self.strategy == 'backup':
            # Upload ke SEMUA provider
            for p in self.providers:
                try:
                    fi = p.upload(file_bytes, filename, title, album)
                    results.append(fi)
                except Exception as e:
                    st.warning(f"Gagal upload ke {p.label}: {e}")

        else:
            # Upload ke provider terpilih
            provider = self.select_upload_provider()
            if provider:
                fi = provider.upload(file_bytes, filename, title, album)
                results.append(fi)

        if not results:
            raise RuntimeError("Upload gagal ke semua provider.")

        return results

    def list_all_files(self, album: Optional[str] = None) -> list[FileInfo]:
        """Ambil semua file dari semua provider, sorted terbaru dulu."""
        all_files = []
        seen_ids = set()

        for provider in self.providers:
            try:
                files = provider.list_files(album)
                for f in files:
                    key = f"{provider.name}:{f.id}"
                    if key not in seen_ids:
                        seen_ids.add(key)
                        all_files.append(f)
            except Exception as e:
                st.warning(f"Gagal mengambil file dari {provider.label}: {e}")

        # Sort: terbaru dulu
        all_files.sort(key=lambda x: x.uploaded_at, reverse=True)
        return all_files

    def delete_file(self, provider_name: str, file_id: str) -> bool:
        """Hapus file dari provider tertentu."""
        provider = next((p for p in self.providers if p.name == provider_name), None)
        if provider:
            return provider.delete(file_id)
        return False

    def get_all_quotas(self) -> list[dict]:
        """Ambil info quota dari semua provider."""
        result = []
        for p in self.providers:
            try:
                q = p.get_quota()
                q['provider'] = p.name
                q['label'] = p.label
                result.append(q)
            except Exception:
                result.append({
                    'provider': p.name,
                    'label': p.label,
                    'used': 0, 'total': 0, 'available': 0
                })
        return result

    def get_all_albums(self) -> list[str]:
        """Ambil daftar semua album dari semua provider."""
        albums = set(['default'])
        for fi in self.list_all_files():
            albums.add(fi.album)
        return sorted(albums)
