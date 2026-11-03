"""
pages/2_Pengaturan.py — Halaman Pengaturan
Hanya bisa diakses setelah login.
"""
import streamlit as st
from utils.auth import require_login, logout, get_current_user
from utils.config import (
    load_config, save_config, get_storage_manager,
    refresh_storage_manager,
)
from utils.storage.manager import STRATEGIES
from utils.storage.rclone_store import RcloneStorage

st.set_page_config(
    page_title="Pengaturan – Galeri",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ─── Auth ─────────────────────────────────────────────────────────────────────
st.title("⚙️ Pengaturan Galeri")

if not require_login():
    st.stop()

header_col, logout_col = st.columns([5, 1])
with header_col:
    st.caption(f"👤 Login sebagai: **{get_current_user()}**")
with logout_col:
    if st.button("Logout"):
        logout()
        st.rerun()

st.markdown("---")

# ─── Load ─────────────────────────────────────────────────────────────────────
cfg = load_config()
manager = get_storage_manager()

tab_gallery, tab_storage, tab_providers, tab_rclone = st.tabs([
    "🎨 Tampilan Galeri", "📦 Strategi Storage", "🔌 Status Provider", "🔧 Rclone Tools"
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: TAMPILAN GALERI
# ══════════════════════════════════════════════════════════════════════════════
with tab_gallery:
    st.subheader("🎨 Konfigurasi Tampilan")

    with st.form("gallery_settings"):
        gallery_title = st.text_input(
            "Judul Galeri",
            value=cfg.get("gallery_title", "Galeri Foto"),
        )
        gallery_subtitle = st.text_input(
            "Subtitle / Deskripsi",
            value=cfg.get("gallery_subtitle", "Koleksi foto kami"),
        )
        images_per_row = st.slider(
            "Jumlah kolom gambar per baris",
            min_value=2, max_value=5,
            value=cfg.get("images_per_row", 3),
        )
        allow_download = st.toggle(
            "Izinkan pengunjung download foto",
            value=cfg.get("allow_download", True),
        )
        show_uploader_info = st.toggle(
            "Tampilkan info provider di galeri publik",
            value=cfg.get("show_uploader_info", False),
        )

        save_gallery = st.form_submit_button("💾 Simpan Pengaturan Tampilan", type="primary")

        if save_gallery:
            cfg.update({
                "gallery_title": gallery_title,
                "gallery_subtitle": gallery_subtitle,
                "images_per_row": images_per_row,
                "allow_download": allow_download,
                "show_uploader_info": show_uploader_info,
            })
            save_config(cfg)
            st.success("✅ Pengaturan tampilan disimpan!")
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: STRATEGI STORAGE
# ══════════════════════════════════════════════════════════════════════════════
with tab_storage:
    st.subheader("📦 Strategi Upload Storage")

    current_strategy = cfg.get("strategy", "fallback")

    st.info(
        "Strategi menentukan ke mana foto disimpan saat upload. "
        "Perubahan langsung berlaku untuk upload berikutnya."
    )

    with st.form("strategy_settings"):
        strategy_options = list(STRATEGIES.keys())
        strategy_labels = list(STRATEGIES.values())

        selected_strategy = st.radio(
            "Pilih Strategi",
            options=strategy_options,
            format_func=lambda k: STRATEGIES[k],
            index=strategy_options.index(current_strategy) if current_strategy in strategy_options else 0,
        )

        st.markdown("---")
        st.markdown("**Detail Strategi:**")

        strategy_details = {
            "fallback": """
**Fallback (Rekomendasi)**
- Upload ke provider #1 terlebih dahulu
- Jika provider #1 sudah >90% penuh, otomatis beralih ke provider #2
- Dan seterusnya hingga provider terakhir
- Cocok untuk: mengoptimalkan penggunaan storage secara berurutan
""",
            "load_balance": """
**Load Balance**
- Distribusi foto secara bergantian (round-robin) ke semua provider
- Provider #1 → Provider #2 → Provider #3 → Provider #1 → ...
- Cocok untuk: distribusi merata agar tidak ada satu provider yang terlalu penuh
""",
            "backup": """
**Backup Ganda** ⚠️
- Setiap foto disimpan ke SEMUA provider secara bersamaan
- Foto aman meski satu provider bermasalah
- **Perhatian**: menggunakan kuota berlipat ganda!
- Cocok untuk: foto penting yang tidak boleh hilang
""",
            "primary": """
**Primary**
- Selalu upload ke provider pertama dalam daftar
- Simple dan predictable
- Cocok untuk: satu provider utama, yang lain sebagai backup manual
""",
        }

        st.markdown(strategy_details.get(selected_strategy, ""))

        save_strategy = st.form_submit_button("💾 Simpan Strategi", type="primary")
        if save_strategy:
            cfg["strategy"] = selected_strategy
            save_config(cfg)
            # Refresh manager dengan strategi baru
            if "galeri_storage_manager" in st.session_state:
                del st.session_state["galeri_storage_manager"]
            st.success(f"✅ Strategi diubah ke **{STRATEGIES[selected_strategy].split('–')[0].strip()}**!")
            st.rerun()

    # Provider order info
    if manager.active_providers:
        st.markdown("---")
        st.markdown("**Urutan Provider** (urutan penting untuk Fallback & Primary):")
        for i, p in enumerate(manager.active_providers, 1):
            try:
                q = p.get_quota()
                if q['total'] > 0:
                    pct = q['used'] / q['total'] * 100
                    status = "🟢" if pct < 70 else ("🟡" if pct < 90 else "🔴")
                    quota_str = f"{status} {q['used']/1024**3:.2f}GB / {q['total']/1024**3:.1f}GB ({pct:.0f}%)"
                else:
                    quota_str = "ℹ️ Info quota N/A"
            except Exception:
                quota_str = "❌ Tidak bisa cek quota"
            st.markdown(f"**{i}.** {p.label} (`{p.name}`) — {quota_str}")

        st.caption("Urutan provider ditentukan dari secrets.toml (gdrive_1 sebelum gdrive_2, dst.)")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: STATUS PROVIDER
# ══════════════════════════════════════════════════════════════════════════════
with tab_providers:
    st.subheader("🔌 Status Koneksi Provider")

    st.info(
        "Provider dikonfigurasi melalui `.streamlit/secrets.toml`. "
        "Untuk menambah provider baru, tambahkan section yang sesuai di secrets.toml "
        "lalu restart aplikasi."
    )

    if st.button("🔄 Cek Koneksi Semua Provider"):
        with st.spinner("Mengecek koneksi..."):
            for p in manager.active_providers:
                try:
                    ok = p.test_connection()
                    if ok:
                        st.success(f"✅ **{p.label}** (`{p.name}`) — Terhubung")
                    else:
                        st.error(f"❌ **{p.label}** (`{p.name}`) — Gagal terhubung")
                except Exception as e:
                    st.error(f"❌ **{p.label}** (`{p.name}`) — Error: {e}")

    if not manager.active_providers:
        st.warning("⚠️ Tidak ada provider yang aktif.")
        st.markdown("""
Untuk mengaktifkan provider, tambahkan ke `.streamlit/secrets.toml`:

**Google Drive:**
```toml
[gdrive_1]
credentials_json = '{"type":"service_account",...}'
folder_id = "YOUR_FOLDER_ID"
label = "Google Drive Utama"
```

**Cloudinary:**
```toml
[cloudinary_1]
cloud_name = "your_cloud_name"
api_key = "your_api_key"
api_secret = "your_api_secret"
label = "Cloudinary"
```

**Yandex Disk:**
```toml
[yandex_1]
oauth_token = "y0_AgAAAA..."
label = "Yandex Disk"
```
        """)
    else:
        for p in manager.active_providers:
            with st.expander(f"☁️ {p.label} (`{p.name}`)"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Tipe:** `{type(p).__name__}`")
                    st.markdown(f"**ID:** `{p.name}`")
                with col2:
                    try:
                        q = p.get_quota()
                        if q['total'] > 0:
                            st.markdown(f"**Terpakai:** {q['used']/1024**3:.2f} GB")
                            st.markdown(f"**Total:** {q['total']/1024**3:.1f} GB")
                        else:
                            st.markdown("**Quota:** N/A")
                    except Exception:
                        st.markdown("**Quota:** Tidak bisa dicek")

    # Cara setup secrets
    st.markdown("---")
    with st.expander("📖 Cara Setup secrets.toml"):
        st.markdown("""
File `.streamlit/secrets.toml` perlu diisi sebelum provider bisa digunakan.
Lihat file `.streamlit/secrets.toml.example` untuk template lengkap.

**Di Streamlit Cloud:**
Settings → Secrets → paste isi secrets.toml

**Lokal (development):**
Edit file `.streamlit/secrets.toml` secara langsung (jangan di-commit ke GitHub!)

**Login Admin:**
```toml
admin_username = "admin"
admin_password = "password_rahasia_kamu"
```
        """)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: RCLONE TOOLS
# ══════════════════════════════════════════════════════════════════════════════
with tab_rclone:
    st.subheader("🔧 Rclone Tools")

    # Cek apakah ada rclone provider
    rclone_providers = [p for p in manager.active_providers if isinstance(p, RcloneStorage)]

    if not rclone_providers:
        st.info(
            "Belum ada rclone provider yang aktif. "
            "Tambahkan section `[rclone_1]` di `secrets.toml` untuk menggunakannya."
        )
        st.markdown("""
### 🚀 Cara Cepat Setup Rclone Provider

**Langkah 1 – Install rclone di PC kamu:**
```bash
# Windows (PowerShell - pakai winget)
winget install Rclone.Rclone

# Mac
brew install rclone

# Linux
curl https://rclone.org/install.sh | sudo bash
```

**Langkah 2 – Konfigurasi remote:**
```bash
rclone config
# Ikuti wizard → pilih tipe storage → isi credentials
```

**Langkah 3 – Copy hasil config:**
```bash
rclone config show
# Copy bagian [nama_remote] ke secrets.toml
```

**Langkah 4 – Tambahkan ke secrets.toml:**
```toml
[rclone_1]
label           = "Nama Storage Kamu"
remote_name     = "nama_remote"      # sesuai output rclone config show
base_path       = "Galeri"
public_url_type = "link"             # atau "proxy" jika tidak ada URL publik
config = '''
[nama_remote]
type = drive
...isi dari rclone config show...
'''
```

**Provider yang didukung rclone (70+):** Google Drive, OneDrive, Dropbox, Amazon S3,
Backblaze B2, Wasabi, Cloudflare R2, MEGA, Box, pCloud, SFTP, FTP, WebDAV, dan banyak lagi.
Lihat daftar lengkap: [rclone.org/overview](https://rclone.org/overview/)
        """)

    else:
        st.success(f"✅ {len(rclone_providers)} rclone provider aktif")

        # ── Sync Metadata ──────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 🔄 Sync Metadata dari Remote")
        st.caption(
            "Gunakan ini jika file diupload langsung ke storage (bukan via app), "
            "atau jika metadata korup. Proses ini akan membaca ulang semua file "
            "dari remote dan memperbarui metadata."
        )

        selected_provider_label = st.selectbox(
            "Pilih provider untuk di-sync",
            [p.label for p in rclone_providers],
        )
        selected_rclone = next(
            p for p in rclone_providers if p.label == selected_provider_label
        )

        col_sync1, col_sync2 = st.columns(2)
        with col_sync1:
            if st.button("🔄 Sync Metadata Sekarang", type="primary", use_container_width=True):
                with st.spinner(f"Membaca file dari {selected_rclone.label}..."):
                    try:
                        selected_rclone.sync_metadata_from_remote()
                        # Clear galeri cache
                        if "cached_files" in st.session_state:
                            del st.session_state["cached_files"]
                        st.success(
                            "✅ Metadata berhasil di-sync! "
                            "File yang diupload manual sekarang muncul di galeri."
                        )
                    except Exception as e:
                        st.error(f"Gagal sync metadata: {e}")

        with col_sync2:
            if st.button("🗑️ Bersihkan Cache Gambar", use_container_width=True):
                import shutil, tempfile, os
                cache_dir = os.path.join(
                    tempfile.gettempdir(), 'galeri_img_cache', selected_rclone.name
                )
                try:
                    shutil.rmtree(cache_dir, ignore_errors=True)
                    os.makedirs(cache_dir, exist_ok=True)
                    st.success("Cache gambar dibersihkan.")
                except Exception as e:
                    st.error(f"Gagal bersihkan cache: {e}")

        # ── Test rclone Commands ───────────────────────────────────────────
        st.markdown("---")
        st.markdown("### 🧪 Test Perintah rclone")

        with st.expander("Jalankan perintah rclone langsung (untuk debugging)"):
            st.warning("⚠️ Hanya untuk admin! Perintah dijalankan dengan credentials aktif.")
            rclone_cmd = st.text_input(
                "Perintah (tanpa 'rclone --config ...')",
                placeholder=f"lsd {selected_rclone.remote_name}:",
                help="Contoh: lsd gdrive: | about gdrive: | lsjson gdrive:Galeri"
            )
            if st.button("▶️ Jalankan"):
                if rclone_cmd.strip():
                    args = rclone_cmd.strip().split()
                    with st.spinner("Menjalankan..."):
                        result = selected_rclone._run(args, timeout=30)
                    if result.returncode == 0:
                        st.success("Exit code: 0")
                        if result.stdout:
                            st.code(result.stdout[:3000])
                    else:
                        st.error(f"Exit code: {result.returncode}")
                        if result.stderr:
                            st.code(result.stderr[:3000])

        # ── Info rclone version ────────────────────────────────────────────
        st.markdown("---")
        st.markdown("### ℹ️ Info Rclone")
        if st.button("Cek Versi rclone"):
            result = selected_rclone._run(['version'], timeout=10)
            if result.returncode == 0:
                st.code(result.stdout)
            else:
                st.error(f"Tidak bisa cek versi: {result.stderr}")
