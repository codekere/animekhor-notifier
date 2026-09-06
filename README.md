# AnimeKhor Notifier & YouTube Auto Helper

Sistem pemantau episode baru AnimeKhor otomatis berbasis **GitHub Actions + Telegram Bot** dengan generator judul & deskripsi YouTube via **AI**, serta penghapus watermark otomatis.

---

## 🚀 Fitur Utama

1. **Notifikasi Otomatis Cloud 24/7 (Gratis)**:
   - Dijalankan oleh GitHub Actions setiap 15 menit.
   - Mengirim notifikasi episode baru ke Telegram lengkap dengan judul menarik, sinopsis, hashtags, dan tombol download langsung.
2. **Bot Interaktif di Telegram**:
   - `/cari <judul>` : Mencari anime/donghua dan menampilkan daftar episode terbaru untuk diunduh.
   - `/download <link>` atau **Kirim Link Langsung**: Otomatis mengekstrak video player Dailymotion asli dan membuat format YouTube siap pakai.
3. **Penghapus Watermark Otomatis (`watermark_tool.py`)**:
   - Menyamarkan/memburamkan watermark `AnimeKhor.org` di pojok kiri atas secara rapi dengan 1 perintah.

---

## ⚙️ Konfigurasi GitHub Secrets

Masuk ke menu **Settings** > **Secrets and variables** > **Actions** pada repository ini, lalu tambahkan:

| Nama Secret | Deskripsi |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token bot dari [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Chat ID akun Telegram Anda dari [@userinfobot](https://t.me/userinfobot) |
| `GEMINI_API_KEY` | *(Opsional)* API Key Google Gemini dari [Google AI Studio](https://aistudio.google.com/) |

---

## 🛠️ Penggunaan Lokal

### 1. Menjalankan Bot Telegram (Realtime Polling)
```bash
set TELEGRAM_BOT_TOKEN=token_anda
set TELEGRAM_CHAT_ID=chat_id_anda
python anime_notifier.py --bot
```

### 2. Download Video Universal (PC / Termux)
```bash
python video_downloader.py "https://animekhor.org/apotheosis-season-3-episode-26-subtitles-english-indonesian/"
```

### 3. Hapus Watermark Pojok Kiri Atas
```bash
python watermark_tool.py "downloads/video.mp4" --blur-animekhor
```
*(Hasil video bersih tersimpan dengan akhiran `_clean.mp4`).*
