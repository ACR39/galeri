"""
Rclone Storage Provider.
Mendukung 70+ cloud storage backend via rclone CLI.

Keunggulan:
- Satu provider untuk semua backend (GDrive, OneDrive, Dropbox, S3, MEGA, FTP, dll.)
- Metadata disimpan dalam file JSON di remote → listing efisien (1 request)
- Auto-install rclone jika belum ada
"""
import json
import os
import shutil
import stat
import subprocess
import tempfile
import datetime
import hashlib
import urllib.request
import zipfile
from typing import Optional

from .base import StorageProvider, FileInfo

METADATA_FILE = ".galeri_meta.json"
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.tif'}
RCLONE_TIMEOUT = 120  # detik
PROXY_PREFIX = "RCLONE_PROXY::"


def _get_rclone_binary() -> str:
    """Cari atau download binary rclone. Kembalikan path-nya."""
    # 1. Cari di PATH sistem
    found = shutil.which('rclone')
    if found:
        return found

    # 2. Cari di lokasi umum
    for loc in ['/usr/bin/rclone', '/usr/local/bin/rclone',
                os.path.expanduser('~/.local/bin/rclone')]:
        if os.path.isfile(loc) and os.access(loc, os.X_OK):
            return loc

    # 3. Download binary (Linux/Mac)
    cache_dir = os.path.join(tempfile.gettempdir(), 'galeri_rclone_bin')
    os.makedirs(cache_dir, exist_ok=True)
    rclone_path = os.path.join(cache_dir, 'rclone')

    if os.path.isfile(rclone_path) and os.access(rclone_path, os.X_OK):
        return rclone_path

    import platform
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == 'linux':
        arch = 'amd64' if 'x86_64' in machine or 'amd64' in machine else 'arm64'
        url = f"https://downloads.rclone.org/rclone-current-linux-{arch}.zip"
    elif system == 'darwin':
        arch = 'amd64' if 'x86_64' in machine else 'arm64'
        url = f"https://downloads.rclone.org/rclone-current-osx-{arch}.zip"
    else:
        raise RuntimeError(
            "rclone tidak ditemukan. Install manual di: https://rclone.org/install/"
        )

    zip_path = rclone_path + '.zip'
    try:
        urllib.request.urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as z:
            for name in z.namelist():
                if name.endswith('/rclone') and '/' in name:
                    with z.open(name) as src, open(rclone_path, 'wb') as dst:
                        dst.write(src.read())
                    break
        os.chmod(rclone_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

    return rclone_path


class RcloneStorage(StorageProvider):
    """
    Storage provider berbasis rclone.
    Mendukung semua backend yang didukung rclone (70+).

    Konfigurasi di secrets.toml:
    ─────────────────────────────
    [rclone_1]
    label      = "Google Drive (rclone)"
    config     = '''
    [gdrive]
    type = drive
    scope = drive
    token = {"access_token":"...","refresh_token":"...","expiry":"..."}
    root_folder_id = "1BxiMVs0..."
    '''
    remote_name      = "gdrive"
    base_path        = "Galeri"
    public_url_type  = "link"   # "link" | "s3" | "dropbox" | "proxy"

    Tipe URL Publik:
    ─────────────────
    "link"    → rclone link (GDrive, OneDrive, Dropbox, Box, dll.)
    "s3"      → S3-compatible (AWS S3, Wasabi, MinIO, R2, dll.)
    "dropbox" → Dropbox direct download
    "proxy"   → Tidak ada URL publik, file ditampilkan via app (lebih lambat)
    """

    def __init__(
        self,
        config_content: str,
        remote_name: str,
        base_path: str,
        provider_name: str,
        provider_label: str,
        public_url_type: str = "link",
    ):
        self._name = provider_name
        self._label = provider_label
        self.remote_name = remote_name.strip()
        self.base_path = base_path.strip('/') or 'Galeri'
        self.public_url_type = public_url_type
        self._config_path = self._write_config(config_content)
        self._rclone_bin = _get_rclone_binary()
        self._cache_dir = os.path.join(tempfile.gettempdir(), 'galeri_img_cache', provider_name)
        os.makedirs(self._cache_dir, exist_ok=True)

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _write_config(self, config_content: str) -> str:
        """Tulis rclone config ke temp file."""
        cfg_dir = os.path.join(tempfile.gettempdir(), 'galeri_rclone_cfg')
        os.makedirs(cfg_dir, exist_ok=True)
        cfg_path = os.path.join(cfg_dir, f'{self._name}.conf')
        with open(cfg_path, 'w', encoding='utf-8') as f:
            f.write(config_content)
        # Amankan permission file config (berisi credentials sensitif)
        os.chmod(cfg_path, stat.S_IRUSR | stat.S_IWUSR)
        return cfg_path

    def _run(self, args: list, timeout: int = RCLONE_TIMEOUT) -> subprocess.CompletedProcess:
        """Jalankan perintah rclone."""
        cmd = [self._rclone_bin, '--config', self._config_path] + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def _remote(self, *parts) -> str:
        """Bangun path remote: remote_name:base_path/part1/part2"""
        path = self.base_path
        for p in parts:
            if p and p.strip('/'):
                path = f"{path}/{p.strip('/')}"
        return f"{self.remote_name}:{path}"

    # ── Metadata (JSON disimpan di remote) ───────────────────────────────────

    def _load_metadata(self) -> dict:
        """Download metadata JSON dari remote. Kembalikan dict kosong jika belum ada."""
        tmp_dir = tempfile.mkdtemp(prefix='galeri_meta_')
        try:
            meta_remote = f"{self.remote_name}:{self.base_path}/{METADATA_FILE}"
            result = self._run(['copy', meta_remote, tmp_dir], timeout=30)
            meta_path = os.path.join(tmp_dir, METADATA_FILE)
            if result.returncode == 0 and os.path.exists(meta_path):
                with open(meta_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return {"files": []}

    def _save_metadata(self, meta: dict):
        """Upload metadata JSON ke remote."""
        tmp_dir = tempfile.mkdtemp(prefix='galeri_meta_')
        try:
            meta_path = os.path.join(tmp_dir, METADATA_FILE)
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=2, default=str)
            remote_dir = f"{self.remote_name}:{self.base_path}"
            self._run(['copy', meta_path, remote_dir], timeout=30)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ── URL Publik ────────────────────────────────────────────────────────────

    def _get_public_url(self, remote_file_path: str, filename: str) -> str:
        """
        Dapatkan URL publik berdasarkan tipe provider.
        remote_file_path: path relatif dari base_path, contoh: "album/foto.jpg"
        """
        if self.public_url_type == 'link':
            # rclone link → bekerja untuk GDrive, OneDrive, Dropbox, Box, dll.
            full_remote = f"{self.remote_name}:{self.base_path}/{remote_file_path}"
            result = self._run(['link', full_remote], timeout=30)
            if result.returncode == 0:
                url = result.stdout.strip()
                # GDrive: konversi ke direct view URL
                if 'drive.google.com' in url and 'id=' in url:
                    file_id = url.split('id=')[-1].split('&')[0]
                    return f"https://drive.google.com/uc?export=view&id={file_id}"
                # Dropbox: dl=0 → dl=1 untuk direct download
                if 'dropbox.com' in url:
                    return url.replace('dl=0', 'dl=1').replace('?dl=', '?raw=')
                return url

        elif self.public_url_type == 'dropbox':
            full_remote = f"{self.remote_name}:{self.base_path}/{remote_file_path}"
            result = self._run(['link', full_remote], timeout=30)
            if result.returncode == 0:
                url = result.stdout.strip()
                return url.replace('dl=0', 'dl=1').replace('?dl=', '?raw=')

        elif self.public_url_type == 's3':
            # S3-compatible: construct URL langsung
            # Format: remote_name → ambil bucket & endpoint dari config
            # Ini perlu dikembangkan per kasus S3
            full_remote = f"{self.remote_name}:{self.base_path}/{remote_file_path}"
            result = self._run(['link', full_remote], timeout=30)
            if result.returncode == 0:
                return result.stdout.strip()

        # Fallback: proxy (tampil via app)
        return f"{PROXY_PREFIX}{self._name}::{self.base_path}/{remote_file_path}"

    # ── StorageProvider Interface ─────────────────────────────────────────────

    @property
    def name(self) -> str:
        return self._name

    @property
    def label(self) -> str:
        return self._label

    def upload(self, file_bytes: bytes, filename: str,
               title: str = "", album: str = "default") -> FileInfo:
        tmp_dir = tempfile.mkdtemp(prefix='galeri_up_')
        try:
            # Tulis ke temp file
            tmp_file = os.path.join(tmp_dir, filename)
            with open(tmp_file, 'wb') as f:
                f.write(file_bytes)

            # Upload ke remote
            remote_dir = self._remote(album)
            result = self._run(['copy', tmp_file, remote_dir])
            if result.returncode != 0:
                raise RuntimeError(
                    f"rclone copy gagal: {result.stderr.strip() or result.stdout.strip()}"
                )

            # Dapatkan URL publik
            rel_path = f"{album}/{filename}" if album != 'default' else filename
            url = self._get_public_url(rel_path, filename)

            now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
            file_info = FileInfo(
                id=rel_path,
                name=title or filename.rsplit('.', 1)[0],
                filename=filename,
                url=url,
                thumbnail_url=url,
                size=len(file_bytes),
                uploaded_at=now,
                album=album,
                provider=self._name,
                provider_label=self._label,
            )

            # Simpan ke metadata
            meta = self._load_metadata()
            meta.setdefault('files', [])
            meta['files'].append({
                'id': file_info.id,
                'name': file_info.name,
                'filename': file_info.filename,
                'url': file_info.url,
                'size': file_info.size,
                'uploaded_at': file_info.uploaded_at.isoformat(),
                'album': file_info.album,
            })
            self._save_metadata(meta)

            return file_info

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def delete(self, file_id: str) -> bool:
        """file_id = path relatif, contoh: 'liburan/foto.jpg'"""
        try:
            remote_file = f"{self.remote_name}:{self.base_path}/{file_id}"
            result = self._run(['deletefile', remote_file])
            if result.returncode != 0:
                return False
            # Update metadata
            meta = self._load_metadata()
            meta['files'] = [f for f in meta.get('files', []) if f.get('id') != file_id]
            self._save_metadata(meta)
            return True
        except Exception:
            return False

    def list_files(self, album: Optional[str] = None) -> list:
        """List file dari metadata JSON (1 request, efisien)."""
        meta = self._load_metadata()
        files = []

        for item in meta.get('files', []):
            if album and item.get('album') != album:
                continue
            try:
                uploaded_at = datetime.datetime.fromisoformat(
                    item.get('uploaded_at', datetime.datetime.utcnow().isoformat())
                )
                if uploaded_at.tzinfo is None:
                    uploaded_at = uploaded_at.replace(tzinfo=datetime.timezone.utc)
            except Exception:
                uploaded_at = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

            files.append(FileInfo(
                id=item.get('id', ''),
                name=item.get('name', item.get('filename', '')),
                filename=item.get('filename', ''),
                url=item.get('url', ''),
                thumbnail_url=item.get('url', ''),
                size=item.get('size', 0),
                uploaded_at=uploaded_at,
                album=item.get('album', 'default'),
                provider=self._name,
                provider_label=self._label,
            ))

        return files

    def get_quota(self) -> dict:
        """Ambil info quota dari remote (rclone about)."""
        try:
            result = self._run(['about', f"{self.remote_name}:", '--json'], timeout=20)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                total = data.get('total', 0)
                used = data.get('used', 0)
                return {
                    'used': used,
                    'total': total,
                    'available': max(0, total - used),
                }
        except Exception:
            pass
        return {'used': 0, 'total': 0, 'available': 0}

    def test_connection(self) -> bool:
        """Test koneksi dengan list directory."""
        try:
            result = self._run(
                ['lsd', f"{self.remote_name}:", '--max-depth', '1'],
                timeout=20,
            )
            return result.returncode == 0
        except Exception:
            return False

    def download_bytes(self, rel_path: str) -> Optional[bytes]:
        """
        Download file dari remote dan kembalikan sebagai bytes.
        Digunakan untuk provider tanpa URL publik (proxy mode).
        Hasil di-cache di disk untuk performa.
        """
        # Cek cache dulu
        cache_key = hashlib.md5(rel_path.encode()).hexdigest()
        cache_file = os.path.join(self._cache_dir, cache_key)
        if os.path.exists(cache_file):
            with open(cache_file, 'rb') as f:
                return f.read()

        # Download dari remote
        tmp_dir = tempfile.mkdtemp(prefix='galeri_dl_')
        try:
            filename = rel_path.split('/')[-1]
            remote_file = f"{self.remote_name}:{self.base_path}/{rel_path}"
            result = self._run(['copy', remote_file, tmp_dir], timeout=60)
            tmp_file = os.path.join(tmp_dir, filename)
            if result.returncode == 0 and os.path.exists(tmp_file):
                with open(tmp_file, 'rb') as f:
                    data = f.read()
                # Simpan ke cache
                with open(cache_file, 'wb') as f:
                    f.write(data)
                return data
        except Exception:
            pass
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return None

    def sync_metadata_from_remote(self):
        """
        Sync ulang metadata dari file aktual di remote.
        Berguna jika file diupload manual (di luar app) atau metadata korup.
        """
        result = self._run([
            'lsjson', f"{self.remote_name}:{self.base_path}",
            '--recursive', '--files-only',
        ])
        if result.returncode != 0:
            return

        try:
            items = json.loads(result.stdout)
        except Exception:
            return

        new_files = []
        for item in items:
            filename = item.get('Name', '')
            path = item.get('Path', filename)  # relatif dari base_path

            # Skip metadata file itu sendiri
            if filename == METADATA_FILE:
                continue

            ext = os.path.splitext(filename)[1].lower()
            if ext not in IMAGE_EXTS:
                continue

            # Parsing album dari path
            parts = path.split('/')
            album = parts[-2] if len(parts) > 1 else 'default'

            # Ambil URL
            url = self._get_public_url(path, filename)

            try:
                mod_time = item.get('ModTime', '')
                uploaded_at = (
                    datetime.datetime.fromisoformat(mod_time.replace('Z', '+00:00'))
                    if mod_time else
                    datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
                )
            except Exception:
                uploaded_at = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)

            new_files.append({
                'id': path,
                'name': filename.rsplit('.', 1)[0],
                'filename': filename,
                'url': url,
                'size': item.get('Size', 0),
                'uploaded_at': uploaded_at.isoformat(),
                'album': album,
            })

        self._save_metadata({'files': new_files})
