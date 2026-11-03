"""
Manajemen konfigurasi aplikasi.
Config disimpan di session_state dan dapat disimpan ke storage primer.
"""
import json
import streamlit as st

from .storage import (
    StorageManager, GoogleDriveStorage,
    CloudinaryStorage, YandexDiskStorage,
    RcloneStorage, STRATEGIES,
)

CONFIG_SESSION_KEY = "galeri_app_config"

DEFAULT_CONFIG = {
    "gallery_title": "Galeri Foto",
    "gallery_subtitle": "Koleksi foto kami",
    "images_per_row": 3,
    "strategy": "fallback",
    "active_providers": [],    # Diisi saat init dari secrets
    "show_uploader_info": False,
    "allow_download": True,
    "theme_color": "#FF6B6B",
}


def load_config() -> dict:
    """Load konfigurasi dari session state atau defaults."""
    if CONFIG_SESSION_KEY not in st.session_state:
        cfg = DEFAULT_CONFIG.copy()
        # Override dari secrets jika ada
        try:
            app_cfg = st.secrets.get("app_config", {})
            for k, v in app_cfg.items():
                if k in cfg:
                    cfg[k] = v
        except Exception:
            pass
        st.session_state[CONFIG_SESSION_KEY] = cfg
    return st.session_state[CONFIG_SESSION_KEY]


def save_config(config: dict):
    """Simpan konfigurasi ke session state."""
    st.session_state[CONFIG_SESSION_KEY] = config


def update_config(**kwargs):
    """Update beberapa field konfigurasi sekaligus."""
    cfg = load_config()
    cfg.update(kwargs)
    save_config(cfg)


def get_config_value(key: str, default=None):
    """Ambil satu nilai konfigurasi."""
    return load_config().get(key, default)


# ─── Storage Manager ─────────────────────────────────────────────────────────

MANAGER_SESSION_KEY = "galeri_storage_manager"


def build_storage_manager() -> StorageManager:
    """
    Bangun StorageManager dari konfigurasi secrets.toml.
    Provider yang dikonfigurasi di secrets akan otomatis dideteksi.
    """
    providers = []
    secrets = st.secrets

    # ── Google Drive accounts ────────────────────────────────────────────────
    # Format di secrets.toml:
    # [gdrive_1]
    # credentials_json = '{"type":"service_account",...}'
    # folder_id = "1BxiMVs0XRA5..."
    # label = "Google Drive Utama"  (opsional)
    for i in range(1, 6):  # Maksimum 5 GDrive accounts
        key = f"gdrive_{i}"
        if key in secrets:
            try:
                cfg = secrets[key]
                providers.append(GoogleDriveStorage(
                    credentials_json=cfg.get("credentials_json", "{}"),
                    folder_id=cfg.get("folder_id", ""),
                    provider_name=key,
                    provider_label=cfg.get("label", f"Google Drive #{i}"),
                ))
            except Exception as e:
                st.warning(f"Gagal inisialisasi {key}: {e}")

    # ── Cloudinary accounts ──────────────────────────────────────────────────
    # [cloudinary_1]
    # cloud_name = "mycloud"
    # api_key = "123456"
    # api_secret = "abc..."
    # folder = "galeri"          (opsional, default: "galeri")
    # label = "Cloudinary"       (opsional)
    for i in range(1, 4):
        key = f"cloudinary_{i}"
        if key in secrets:
            try:
                cfg = secrets[key]
                providers.append(CloudinaryStorage(
                    cloud_name=cfg.get("cloud_name", ""),
                    api_key=cfg.get("api_key", ""),
                    api_secret=cfg.get("api_secret", ""),
                    folder=cfg.get("folder", "galeri"),
                    provider_name=key,
                    provider_label=cfg.get("label", f"Cloudinary #{i}"),
                ))
            except Exception as e:
                st.warning(f"Gagal inisialisasi {key}: {e}")

    # ── Yandex Disk accounts ─────────────────────────────────────────────────
    # [yandex_1]
    # oauth_token = "y0_Ag..."
    # base_folder = "Galeri"     (opsional)
    # label = "Yandex Disk"      (opsional)
    for i in range(1, 4):
        key = f"yandex_{i}"
        if key in secrets:
            try:
                cfg = secrets[key]
                providers.append(YandexDiskStorage(
                    oauth_token=cfg.get("oauth_token", ""),
                    base_folder=cfg.get("base_folder", "Galeri"),
                    provider_name=key,
                    provider_label=cfg.get("label", f"Yandex Disk #{i}"),
                ))
            except Exception as e:
                st.warning(f"Gagal inisialisasi {key}: {e}")

    # ── Rclone remotes ───────────────────────────────────────────────────────
    # [rclone_1]
    # label           = "OneDrive Pribadi"
    # remote_name     = "onedrive"
    # base_path       = "Galeri"
    # public_url_type = "link"   # "link" | "s3" | "dropbox" | "proxy"
    # config          = '''
    # [onedrive]
    # type = onedrive
    # token = {"access_token":"...","refresh_token":"..."}
    # drive_id = ...
    # '''
    for i in range(1, 10):  # Mendukung hingga 9 rclone remote
        key = f"rclone_{i}"
        if key in secrets:
            try:
                rcfg = secrets[key]
                config_content = rcfg.get("config", "")
                remote_name = rcfg.get("remote_name", "")
                if not config_content or not remote_name:
                    st.warning(
                        f"Konfigurasi {key} tidak lengkap: "
                        f"'config' dan 'remote_name' wajib diisi."
                    )
                    continue
                providers.append(RcloneStorage(
                    config_content=config_content,
                    remote_name=remote_name,
                    base_path=rcfg.get("base_path", "Galeri"),
                    provider_name=key,
                    provider_label=rcfg.get("label", f"Rclone Remote #{i}"),
                    public_url_type=rcfg.get("public_url_type", "link"),
                ))
            except Exception as e:
                st.warning(f"Gagal inisialisasi {key}: {e}")

    cfg = load_config()
    strategy = cfg.get("strategy", "fallback")

    return StorageManager(providers=providers, strategy=strategy)


def get_storage_manager() -> StorageManager:
    """Ambil StorageManager dari session state (cache)."""
    if MANAGER_SESSION_KEY not in st.session_state:
        st.session_state[MANAGER_SESSION_KEY] = build_storage_manager()
    return st.session_state[MANAGER_SESSION_KEY]


def refresh_storage_manager():
    """Rebuild StorageManager (setelah konfigurasi berubah)."""
    if MANAGER_SESSION_KEY in st.session_state:
        del st.session_state[MANAGER_SESSION_KEY]
    return get_storage_manager()
