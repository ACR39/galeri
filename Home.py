"""
Home.py — Galeri Publik (tanpa login)
Halaman utama yang bisa dilihat semua orang.
"""
import streamlit as st
from utils.config import load_config, get_storage_manager, get_config_value
from utils.storage.base import FileInfo
from utils.storage import PROXY_PREFIX
from utils.storage.rclone_store import RcloneStorage

# ─── Page Config ──────────────────────────────────────────────────────────────
cfg = load_config()
st.set_page_config(
    page_title=cfg.get("gallery_title", "Galeri Foto"),
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Hide Streamlit menu & footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Gallery grid */
    .gallery-img {
        width: 100%;
        border-radius: 10px;
        object-fit: cover;
        aspect-ratio: 1 / 1;
        transition: transform 0.2s, box-shadow 0.2s;
        cursor: pointer;
    }
    .gallery-img:hover {
        transform: scale(1.03);
        box-shadow: 0 8px 25px rgba(0,0,0,0.25);
    }
    .img-card {
        background: #1a1a2e;
        border-radius: 12px;
        padding: 8px;
        margin-bottom: 12px;
    }
    .img-title {
        font-size: 13px;
        color: #ccc;
        text-align: center;
        padding: 4px 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .album-tag {
        font-size: 11px;
        color: #888;
        text-align: center;
    }
    .provider-badge {
        font-size: 10px;
        color: #666;
        text-align: right;
        padding-right: 4px;
    }
    .hero-title {
        font-size: 2.5rem;
        font-weight: 700;
        text-align: center;
        margin-bottom: 0;
    }
    .hero-subtitle {
        font-size: 1rem;
        color: #888;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .stat-box {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    div[data-testid="stHorizontalBlock"] {
        gap: 12px;
    }
</style>
""", unsafe_allow_html=True)

def _display_image(fi: FileInfo, manager, width_label="use_column_width"):
    """
    Tampilkan gambar dengan smart URL handling:
    - URL publik: langsung tampilkan via URL
    - Proxy URL (rclone tanpa public link): download via app lalu tampilkan
    """
    url = fi.url or fi.thumbnail_url or ""

    if url.startswith(PROXY_PREFIX):
        # Proxy mode: provider_name::rel_path
        _, pname, rel_path = url.split("::", 2)
        cache_key = f"img_cache_{pname}_{rel_path}"

        if cache_key not in st.session_state:
            provider = next(
                (p for p in manager.active_providers if p.name == pname), None
            )
            if provider and isinstance(provider, RcloneStorage):
                with st.spinner("Memuat..."):
                    img_bytes = provider.download_bytes(rel_path)
                st.session_state[cache_key] = img_bytes
            else:
                st.session_state[cache_key] = None

        img_data = st.session_state.get(cache_key)
        if img_data:
            st.image(img_data, use_column_width=True)
        else:
            st.markdown(
                "<div style='padding:20px;text-align:center;color:#666;"
                "border:1px solid #333;border-radius:8px;'>📷<br>Tidak dapat dimuat</div>",
                unsafe_allow_html=True
            )
    elif url:
        st.image(url, use_column_width=True)
    else:
        st.markdown(
            "<div style='padding:20px;text-align:center;color:#666;"
            "border:1px solid #333;border-radius:8px;'>📷<br>Tidak ada URL</div>",
            unsafe_allow_html=True
        )



title = cfg.get("gallery_title", "Galeri Foto")
subtitle = cfg.get("gallery_subtitle", "Koleksi foto kami")

st.markdown(f'<div class="hero-title">🖼️ {title}</div>', unsafe_allow_html=True)
st.markdown(f'<div class="hero-subtitle">{subtitle}</div>', unsafe_allow_html=True)

# ─── Load files ───────────────────────────────────────────────────────────────
manager = get_storage_manager()

if not manager.active_providers:
    st.info("📦 Belum ada storage yang terkonfigurasi. "
            "Minta admin untuk mengatur storage terlebih dahulu.")
    st.stop()

# Cache file list dalam session (refresh dengan tombol)
if "cached_files" not in st.session_state:
    with st.spinner("Memuat galeri..."):
        try:
            st.session_state["cached_files"] = manager.list_all_files()
        except Exception as e:
            st.error(f"Gagal memuat galeri: {e}")
            st.session_state["cached_files"] = []

all_files: list[FileInfo] = st.session_state.get("cached_files", [])

# ─── Filter Bar ───────────────────────────────────────────────────────────────
col_search, col_album, col_sort, col_refresh = st.columns([3, 2, 2, 1])

with col_search:
    search_query = st.text_input("🔍 Cari foto", placeholder="Ketik judul foto...", label_visibility="collapsed")

with col_album:
    albums = sorted(set(f.album for f in all_files)) or ["default"]
    album_options = ["Semua Album"] + albums
    selected_album = st.selectbox("Album", album_options, label_visibility="collapsed")

with col_sort:
    sort_by = st.selectbox("Urutkan", ["Terbaru", "Terlama", "Nama A-Z"], label_visibility="collapsed")

with col_refresh:
    if st.button("🔄", help="Refresh galeri"):
        if "cached_files" in st.session_state:
            del st.session_state["cached_files"]
        st.rerun()

# ─── Apply Filter & Sort ──────────────────────────────────────────────────────
filtered = all_files

if selected_album != "Semua Album":
    filtered = [f for f in filtered if f.album == selected_album]

if search_query:
    q = search_query.lower()
    filtered = [f for f in filtered if q in f.name.lower() or q in f.filename.lower()]

if sort_by == "Terlama":
    filtered = sorted(filtered, key=lambda x: x.uploaded_at)
elif sort_by == "Nama A-Z":
    filtered = sorted(filtered, key=lambda x: x.name.lower())

# ─── Stats Bar ────────────────────────────────────────────────────────────────
st.markdown("---")
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("📸 Total Foto", len(all_files))
with c2:
    st.metric("📁 Album", len(set(f.album for f in all_files)))
with c3:
    st.metric("☁️ Provider Aktif", len(manager.active_providers))
with c4:
    total_size = sum(f.size for f in all_files)
    if total_size > 1024 ** 3:
        size_str = f"{total_size / 1024**3:.1f} GB"
    elif total_size > 1024 ** 2:
        size_str = f"{total_size / 1024**2:.1f} MB"
    else:
        size_str = f"{total_size / 1024:.1f} KB"
    st.metric("💾 Total Ukuran", size_str)
st.markdown("---")

# ─── Gallery Grid ─────────────────────────────────────────────────────────────
if not filtered:
    st.markdown("""
    <div style='text-align:center; padding: 4rem; color: #666;'>
        <div style='font-size: 4rem;'>📭</div>
        <div style='font-size: 1.2rem; margin-top: 1rem;'>Belum ada foto</div>
        <div style='font-size: 0.9rem; color: #444;'>Upload foto melalui halaman Admin</div>
    </div>
    """, unsafe_allow_html=True)
else:
    images_per_row = cfg.get("images_per_row", 3)
    allow_download = cfg.get("allow_download", True)

    # Pilih foto yang diklik (untuk lightbox sederhana)
    if "lightbox_idx" not in st.session_state:
        st.session_state["lightbox_idx"] = None

    # ── Lightbox (jika ada foto yang dipilih) ─────────────────────────────
    if st.session_state["lightbox_idx"] is not None:
        idx = st.session_state["lightbox_idx"]
        if 0 <= idx < len(filtered):
            fi = filtered[idx]
            lc1, lc2, lc3 = st.columns([1, 4, 1])
            with lc2:
                st.markdown(f"### {fi.name}")
                _display_image(fi, manager)
                meta_cols = st.columns(3)
                with meta_cols[0]:
                    st.caption(f"📁 Album: **{fi.album}**")
                with meta_cols[1]:
                    st.caption(f"☁️ Provider: **{fi.provider_label}**")
                with meta_cols[2]:
                    st.caption(f"📅 {fi.uploaded_at.strftime('%d %b %Y %H:%M')}")

                btn_cols = st.columns(3)
                with btn_cols[0]:
                    if st.button("◀ Sebelumnya", use_container_width=True):
                        st.session_state["lightbox_idx"] = max(0, idx - 1)
                        st.rerun()
                with btn_cols[1]:
                    if st.button("✖ Tutup", use_container_width=True, type="primary"):
                        st.session_state["lightbox_idx"] = None
                        st.rerun()
                with btn_cols[2]:
                    if st.button("Berikutnya ▶", use_container_width=True):
                        st.session_state["lightbox_idx"] = min(len(filtered) - 1, idx + 1)
                        st.rerun()

                if allow_download:
                    st.link_button("⬇️ Download", fi.url, use_container_width=True)
            st.markdown("---")

    # ── Grid ──────────────────────────────────────────────────────────────
    for row_start in range(0, len(filtered), images_per_row):
        row_files = filtered[row_start: row_start + images_per_row]
        cols = st.columns(images_per_row)
        for col_idx, fi in enumerate(row_files):
            with cols[col_idx]:
                # Tampilkan thumbnail (smart: proxy atau URL publik)
                try:
                    _display_image(fi, manager)
                except Exception:
                    st.markdown("❌ Gagal memuat gambar")

                st.markdown(
                    f"<div class='img-title' title='{fi.name}'>{fi.name}</div>"
                    f"<div class='album-tag'>📁 {fi.album}</div>"
                    f"<div class='provider-badge'>☁️ {fi.provider_label}</div>",
                    unsafe_allow_html=True
                )

                btn_c1, btn_c2 = st.columns(2)
                actual_idx = row_start + col_idx
                with btn_c1:
                    if st.button("🔍 Lihat", key=f"view_{fi.provider}_{fi.id}",
                                 use_container_width=True):
                        st.session_state["lightbox_idx"] = actual_idx
                        st.rerun()
                with btn_c2:
                    if allow_download:
                        st.link_button("⬇️", fi.url, use_container_width=True,
                                       help="Download foto")

# ─── Footer ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    "<div style='text-align:center; color:#555; font-size:12px;'>"
    "🖼️ Galeri Foto &nbsp;|&nbsp; "
    "<a href='/Admin' style='color:#888;'>Admin</a>"
    "</div>",
    unsafe_allow_html=True,
)
