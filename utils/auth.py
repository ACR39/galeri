"""
Autentikasi admin — username + password dari Streamlit Secrets.
"""
import hmac
import hashlib
import streamlit as st

SESSION_KEY = "galeri_logged_in"
USER_KEY = "galeri_username"


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def check_credentials(username: str, password: str) -> bool:
    """Verifikasi username dan password dari secrets.toml."""
    try:
        admins = st.secrets.get("admins", {})
        if not admins:
            # Fallback: cek single admin
            stored_user = st.secrets.get("admin_username", "")
            stored_pass = st.secrets.get("admin_password", "")
            return (
                hmac.compare_digest(username, stored_user) and
                hmac.compare_digest(_hash_password(password), _hash_password(stored_pass))
            )
        # Multi-admin support: admins = {username: password_hash}
        if username in admins:
            stored_hash = admins[username]
            return hmac.compare_digest(_hash_password(password), stored_hash)
        return False
    except Exception:
        return False


def is_logged_in() -> bool:
    """Cek apakah admin sudah login di session ini."""
    return st.session_state.get(SESSION_KEY, False)


def get_current_user() -> str:
    """Kembalikan username admin yang sedang login."""
    return st.session_state.get(USER_KEY, "")


def login(username: str, password: str) -> bool:
    """Coba login. Kembalikan True jika berhasil."""
    if check_credentials(username, password):
        st.session_state[SESSION_KEY] = True
        st.session_state[USER_KEY] = username
        return True
    return False


def logout():
    """Logout admin dari session."""
    st.session_state[SESSION_KEY] = False
    st.session_state[USER_KEY] = ""


def require_login():
    """
    Decorator-style: tampilkan form login jika belum login.
    Kembalikan True jika sudah login, False jika belum (dan tampilkan form).
    """
    if is_logged_in():
        return True

    st.markdown("---")
    st.subheader("🔐 Login Admin")

    with st.form("login_form", clear_on_submit=True):
        col1, col2 = st.columns([1, 2])
        with col2:
            username = st.text_input("Username", placeholder="masukkan username")
            password = st.text_input("Password", type="password", placeholder="masukkan password")
            submit = st.form_submit_button("Masuk", use_container_width=True)

        if submit:
            if login(username, password):
                st.success("Login berhasil!")
                st.rerun()
            else:
                st.error("Username atau password salah.")

    return False
