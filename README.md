# 🖼️ Galeri Foto

Aplikasi web galeri foto berbasis Streamlit dengan dukungan multi-storage cloud.

## ✨ Fitur

- 🌐 **Galeri publik** — bisa dibagikan ke siapa saja tanpa login
- 🔐 **Panel admin** — upload & kelola foto dengan login
- ☁️ **Multi-storage** — Google Drive, Cloudinary, Yandex Disk (bisa kombinasi)
- 🎯 **Strategi fleksibel** — Fallback, Load Balance, Backup Ganda, Primary
- 📱 **Responsive** — tampil baik di HP maupun komputer
- 🔍 **Lightbox** — klik foto untuk melihat ukuran penuh
- 🔎 **Filter & search** — cari foto berdasarkan judul atau album

## 🗂️ Struktur Project

```
galeri/
├── Home.py                      # Galeri publik (entry point)
├── packages.txt                 # Install rclone di Streamlit Cloud
├── pages/
│   ├── 1_Admin.py               # Panel admin (upload & kelola)
│   └── 2_Pengaturan.py          # Pengaturan app, storage & rclone tools
├── utils/
│   ├── auth.py                  # Autentikasi admin
│   ├── config.py                # Manajemen konfigurasi & storage manager
│   └── storage/
│       ├── base.py              # Base class & FileInfo
│       ├── gdrive.py            # Google Drive (service account)
│       ├── cloudinary_store.py  # Cloudinary provider
│       ├── yandex_disk.py       # Yandex Disk provider
│       ├── rclone_store.py      # Rclone provider (70+ backend)
│       └── manager.py           # Storage manager & 4 strategi
├── .streamlit/
│   ├── config.toml              # Tema & konfigurasi Streamlit
│   └── secrets.toml.example     # Template lengkap semua provider
├── requirements.txt
└── README.md
```

## 🚀 Setup & Deploy

### 1. Clone Repository

```bash
git clone https://github.com/username/galeri.git
cd galeri
```

### 2. Install Dependencies (untuk development lokal)

```bash
pip install -r requirements.txt
```

### 3. Buat secrets.toml

Salin template:
```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` dan isi kredensial. Lihat panduan setup storage di bawah.

### 4. Jalankan Lokal

```bash
streamlit run Home.py
```

### 5. Deploy ke Streamlit Cloud

1. Push kode ke GitHub (pastikan `secrets.toml` masuk `.gitignore`)
2. Buka [share.streamlit.io](https://share.streamlit.io)
3. Connect repository → pilih `Home.py` sebagai main file
4. **Settings → Secrets** → paste isi `secrets.toml` kamu
5. Deploy! ✅

## ☁️ Provider Storage yang Didukung

### Built-in Provider

| Provider | Cara Setup | Gratis |
|---|---|---|
| **Google Drive** | Service Account JSON | 15 GB |
| **Cloudinary** | API Key + Secret | 25 GB |
| **Yandex Disk** | OAuth Token | 10 GB |

### Via Rclone (70+ backend)

| Provider | `public_url_type` | Gratis |
|---|---|---|
| Google Drive | `link` | 15 GB |
| OneDrive | `link` | 5 GB |
| Dropbox | `dropbox` | 2 GB |
| Amazon S3 | `s3` | berbayar |
| Backblaze B2 | `link` | 10 GB |
| MEGA | `proxy` | 20 GB |
| FTP/SFTP | `proxy` | — |
| ...+ 60 lainnya | — | — |

---

## ☁️ Setup Storage Provider

### Google Drive (Gratis 15GB)

1. Buka [Google Cloud Console](https://console.cloud.google.com)
2. Buat project baru
3. Enable **Google Drive API**
4. **IAM & Admin → Service Accounts → Create Service Account**
5. **Keys → Add Key → JSON** → download file
6. Buat folder di Google Drive
7. Share folder ke email service account sebagai **Editor**
8. Copy **Folder ID** dari URL Drive (bagian setelah `/folders/`)
9. Isi di secrets.toml:

```toml
[gdrive_1]
label = "Google Drive Utama"
folder_id = "1BxiMVs0XRA5..."
credentials_json = '{"type":"service_account",...}'
```

Untuk akun kedua, gunakan `[gdrive_2]`, dan seterusnya.

---

### Cloudinary (Gratis 25GB)

1. Daftar di [cloudinary.com](https://cloudinary.com)
2. Dashboard → Copy **Cloud Name**, **API Key**, **API Secret**
3. Isi di secrets.toml:

```toml
[cloudinary_1]
label = "Cloudinary"
cloud_name = "namakamu"
api_key = "123456789"
api_secret = "xxxxx"
```

---

### Yandex Disk (Gratis 10GB)

1. Daftar/login di [yandex.com](https://yandex.com)
2. Buka [oauth.yandex.com](https://oauth.yandex.com) → Buat aplikasi
3. Aktifkan scope: `cloud_api:disk.read` dan `cloud_api:disk.write`
4. Generate token
5. Isi di secrets.toml:

```toml
[yandex_1]
label = "Yandex Disk"
oauth_token = "y0_AgAAAA..."
```

---

### Kombinasi Contoh (~65GB gratis total)

```toml
[gdrive_1]
label = "Google Drive Utama (15GB)"
...

[gdrive_2]
label = "Google Drive Backup (15GB)"
...

[cloudinary_1]
label = "Cloudinary (25GB)"
...

[yandex_1]
label = "Yandex Disk (10GB)"
...
```

### Rclone (70+ Provider Lainnya)

1. Install rclone: [rclone.org/install](https://rclone.org/install/)
2. Jalankan `rclone config` → ikuti wizard interaktif
3. Setelah selesai, jalankan `rclone config show`
4. Copy bagian `[nama_remote]` ke secrets.toml:

```toml
[rclone_1]
label           = "OneDrive Pribadi"
remote_name     = "onedrive"
base_path       = "Galeri"
public_url_type = "link"
config = '''
[onedrive]
type = onedrive
token = {"access_token":"...","refresh_token":"..."}
...
'''
```

---

| Strategi | Cara Kerja |
|---|---|
| **Fallback** *(default)* | Gunakan provider #1, otomatis pindah ke #2 jika >90% penuh |
| **Load Balance** | Distribusi bergantian ke semua provider |
| **Backup Ganda** | Simpan ke SEMUA provider sekaligus |
| **Primary** | Selalu ke provider pertama |

Strategi bisa diubah kapan saja dari halaman **⚙️ Pengaturan** tanpa restart.

---

## 🔐 Keamanan

- ✅ Galeri publik dapat dilihat siapa saja **tanpa login**
- ✅ Admin panel memerlukan **username + password**
- ✅ Credentials storage tersimpan aman di **Streamlit Secrets** (tidak di kode)
- ✅ Pengunjung galeri **tidak bisa melihat** link storage asli atau credentials
- ✅ File `.streamlit/secrets.toml` masuk `.gitignore` (tidak akan ter-push ke GitHub)

---

## 🔗 URL Aplikasi

Setelah deploy:
- **Galeri publik**: `https://nama-app.streamlit.app`
- **Admin**: `https://nama-app.streamlit.app/Admin`
- **Pengaturan**: `https://nama-app.streamlit.app/Pengaturan`

---

## 📄 Lisensi

MIT License — bebas digunakan dan dimodifikasi.
