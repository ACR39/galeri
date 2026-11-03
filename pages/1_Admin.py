"""
pages/1_Admin.py — Panel Admin
Hanya bisa diakses setelah login.
"""
import streamlit as st
from utils.auth import require_login, logout, get_current_user, is_logged_in
from utils.config import get_storage_manager, load_config, refresh_storage_manager
from utils.storage.manager import STRATEGIES

st.set_page_config(
    page_title="Admin – Galeri",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .upload-area { border: 2px dashed #444; border-radius: 10px; padding: 1rem; }
    .file-row { background: #1a1a2e; border-radius: 8px; padding: 8px 12px; margin-bottom: 6px; }
</style>
""", unsafe_allow_html=True)

# ─── Auth Check ───────────────────────────────────────────────────────────────
st.title("🔐 Panel Admin")

if not require_login():
    st.stop()

# ─── Header ───────────────────────────────────────────────────────────────────
header_col, logout_col = st.columns([5, 1])
with header_col:
    st.caption(f"👤 Login sebagai: **{get_current_user()}**")
with logout_col:
    if st.button("Logout", type="secondary"):
        logout()
        st.rerun()

st.markdown("---")

# ─── Load Manager ─────────────────────────────────────────────────────────────
manager = get_storage_manager()
cfg = load_config()

if not manager.active_providers:
    st.warning("⚠️ Belum ada storage provider yang terkonfigurasi. "
               "Silakan isi `secrets.toml` terlebih dahulu dan restart app.")
    st.stop()

# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab_upload, tab_manage, tab_stats = st.tabs(["📤 Upload", "🗂️ Kelola Foto", "📊 Storage"])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: UPLOAD
# ══════════════════════════════════════════════════════════════════════════════
with tab_upload:
    st.subheader("📤 Upload Foto Baru")

    up_col1, up_col2 = st.columns([2, 1])

    with up_col1:
        uploaded_files = st.file_uploader(
            "Pilih gambar",
            type=["jpg", "jpeg", "png", "gif", "webp", "bmp"],
            accept_multiple_files=True,
            help="Bisa upload beberapa foto sekaligus",
        )

    with up_col2:
        # Album selection
        existing_albums = []
        try:
            with st.spinner("Memuat daftar album..."):
                existing_albums = sorted(set(
                    f.album for f in manager.list_all_files()
                ))
        except Exception:
            existing_albums = ["default"]

        album_choice = st.radio(
            "Album tujuan",
            ["Pilih album yang ada", "Buat album baru"],
        )

        if album_choice == "Pilih album yang ada":
            album_options = existing_albums if existing_albums else ["default"]
            target_album = st.selectbox("Album", album_options)
        else:
            target_album = st.text_input(
                "Nama album baru",
                placeholder="contoh: liburan-2024",
            ).strip().lower().replace(" ", "-")
            if not target_album:
                target_album = "default"

        # Provider selection
        provider_options = {p.label: p.name for p in manager.active_providers}
        strategy_label = STRATEGIES.get(manager.strategy, manager.strategy)

        upload_mode = st.radio(
            "Target penyimpanan",
            ["Otomatis (pakai strategi)", "Pilih provider manual"],
        )
        target_provider = None
        if upload_mode == "Pilih provider manual":
            selected_label = st.selectbox("Provider", list(provider_options.keys()))
            target_provider = provider_options[selected_label]
        else:
            st.caption(f"🤖 Strategi aktif: **{strategy_label.split('–')[0].strip()}**")

    # Preview & Upload
    if uploaded_files:
        st.markdown("---")
        st.subheader(f"Preview ({len(uploaded_files)} file)")

        # Custom titles
        titles = {}
        with st.expander("✏️ Edit judul foto (opsional)", expanded=False):
            for uf in uploaded_files:
                titles[uf.name] = st.text_input(
                    f"Judul untuk `{uf.name}`",
                    value=uf.name.rsplit('.', 1)[0],
                    key=f"title_{uf.name}",
                )

        # Preview grid
        preview_cols = st.columns(min(len(uploaded_files), 4))
        for i, uf in enumerate(uploaded_files):
            with preview_cols[i % 4]:
                st.image(uf, caption=uf.name, use_column_width=True)

        st.markdown("---")
        if st.button(
            f"🚀 Upload {len(uploaded_files)} foto ke album **{target_album}**",
            type="primary",
            use_container_width=True,
        ):
            progress = st.progress(0, text="Memulai upload...")
            success_count = 0
            fail_count = 0

            for i, uf in enumerate(uploaded_files):
                progress.progress(
                    (i + 1) / len(uploaded_files),
                    text=f"Mengupload {uf.name}... ({i+1}/{len(uploaded_files)})"
                )
                try:
                    file_bytes = uf.read()
                    title = titles.get(uf.name, uf.name.rsplit('.', 1)[0])
                    manager.upload(
                        file_bytes=file_bytes,
                        filename=uf.name,
                        title=title,
                        album=target_album,
                        target_provider=target_provider,
                    )
                    success_count += 1
                except Exception as e:
                    st.error(f"Gagal upload `{uf.name}`: {e}")
                    fail_count += 1

            progress.empty()

            if success_count:
                st.success(f"✅ Berhasil upload {success_count} foto!")
                # Clear cache galeri
                if "cached_files" in st.session_state:
                    del st.session_state["cached_files"]

            if fail_count:
                st.warning(f"⚠️ Gagal upload {fail_count} foto.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: KELOLA FOTO
# ══════════════════════════════════════════════════════════════════════════════
with tab_manage:
    st.subheader("🗂️ Kelola Foto")

    col_filter1, col_filter2, col_refresh = st.columns([2, 2, 1])
    with col_filter1:
        filter_album = st.selectbox(
            "Filter album", ["Semua"], key="manage_album_filter"
        )
    with col_filter2:
        filter_provider = st.selectbox(
            "Filter provider",
            ["Semua"] + [p.label for p in manager.active_providers],
            key="manage_provider_filter",
        )
    with col_refresh:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh", key="manage_refresh"):
            if "cached_files" in st.session_state:
                del st.session_state["cached_files"]
            st.rerun()

    # Load files
    with st.spinner("Memuat daftar foto..."):
        try:
            all_files = manager.list_all_files()
        except Exception as e:
            st.error(f"Gagal memuat foto: {e}")
            all_files = []

    if not all_files:
        st.info("📭 Belum ada foto yang diupload.")
    else:
        # Update filter options
        album_options_manage = ["Semua"] + sorted(set(f.album for f in all_files))

        filtered_manage = all_files
        if filter_album != "Semua":
            filtered_manage = [f for f in filtered_manage if f.album == filter_album]
        if filter_provider != "Semua":
            filtered_manage = [f for f in filtered_manage if f.provider_label == filter_provider]

        st.caption(f"Menampilkan **{len(filtered_manage)}** dari **{len(all_files)}** foto")

        # Confirmation state
        if "confirm_delete" not in st.session_state:
            st.session_state["confirm_delete"] = None

        # Render list
        for fi in filtered_manage:
            with st.container():
                c_img, c_info, c_actions = st.columns([1, 4, 2])

                with c_img:
                    try:
                        st.image(fi.thumbnail_url or fi.url, width=80)
                    except Exception:
                        st.markdown("🖼️")

                with c_info:
                    st.markdown(f"**{fi.name}**")
                    st.caption(
                        f"📁 {fi.album} &nbsp;|&nbsp; "
                        f"☁️ {fi.provider_label} &nbsp;|&nbsp; "
                        f"📅 {fi.uploaded_at.strftime('%d %b %Y')} &nbsp;|&nbsp; "
                        f"💾 {fi.format_size(fi.size) if fi.size else '-'}"
                    )

                with c_actions:
                    ac1, ac2 = st.columns(2)
                    with ac1:
                        st.link_button("🔍", fi.url, use_container_width=True,
                                       help="Buka foto")
                    with ac2:
                        del_key = f"del_{fi.provider}_{fi.id}"
                        if st.session_state["confirm_delete"] == del_key:
                            if st.button("⚠️ Hapus?", key=f"confirm_{del_key}",
                                         type="primary", use_container_width=True):
                                with st.spinner("Menghapus..."):
                                    ok = manager.delete_file(fi.provider, fi.id)
                                if ok:
                                    st.success("Foto dihapus.")
                                    st.session_state["confirm_delete"] = None
                                    if "cached_files" in st.session_state:
                                        del st.session_state["cached_files"]
                                    st.rerun()
                                else:
                                    st.error("Gagal hapus foto.")
                        else:
                            if st.button("🗑️", key=del_key,
                                         use_container_width=True, help="Hapus foto"):
                                st.session_state["confirm_delete"] = del_key
                                st.rerun()

                st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: STORAGE STATS
# ══════════════════════════════════════════════════════════════════════════════
with tab_stats:
    st.subheader("📊 Statistik Storage")

    if st.button("🔄 Refresh Data Storage"):
        st.rerun()

    quotas = manager.get_all_quotas()

    if not quotas:
        st.info("Tidak ada provider aktif.")
    else:
        for q in quotas:
            st.markdown(f"**☁️ {q['label']}** (`{q['provider']}`)")
            if q['total'] > 0:
                used_gb = q['used'] / 1024**3
                total_gb = q['total'] / 1024**3
                pct = q['used'] / q['total']
                color = "🟢" if pct < 0.7 else ("🟡" if pct < 0.9 else "🔴")
                st.progress(pct, text=f"{color} {used_gb:.2f} GB / {total_gb:.2f} GB ({pct*100:.1f}%)")
            else:
                st.caption("Info quota tidak tersedia.")
            st.markdown("")

        # Summary
        total_used = sum(q['used'] for q in quotas)
        total_cap = sum(q['total'] for q in quotas)
        if total_cap > 0:
            st.markdown("---")
            st.markdown("**Total Kapasitas Gabungan**")
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Total Kapasitas", f"{total_cap/1024**3:.1f} GB")
            with col_b:
                st.metric("Terpakai", f"{total_used/1024**3:.2f} GB")
            with col_c:
                st.metric("Tersisa", f"{(total_cap-total_used)/1024**3:.2f} GB")

        # Strategy info
        st.markdown("---")
        st.markdown("**Strategi Upload Aktif**")
        st.info(STRATEGIES.get(manager.strategy, manager.strategy))
        st.caption("Ubah strategi di halaman **⚙️ Pengaturan**.")
