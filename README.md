# AnimeKhor Notifier (Clean & Minimalist)

Sistem notifikasi otomatis episode baru AnimeKhor ke Telegram via **GitHub Actions** (100% cloud, gratis 24/7).

---

## 📱 1. Fitur Notifier Telegram
* **Notifikasi Otomatis**: Setiap AnimeKhor upload episode baru, bot langsung mengirim:
  * 📌 Judul Episode
  * 🔗 Link Seal (Dailymotion) siap copy-paste
* **Perintah Bot**:
  * `/last` : Menampilkan episode paling baru & link Seal-nya.

---

## ⚙️ 2. Konfigurasi GitHub Secrets
Di repository ini, buka **Settings** > **Secrets and variables** > **Actions**:
* `TELEGRAM_BOT_TOKEN` : Token bot dari [@BotFather](https://t.me/BotFather)
* `TELEGRAM_CHAT_ID` : Chat ID angka Anda dari [@userinfobot](https://t.me/userinfobot)

---

## 🎬 3. Cara Hapus Watermark Otomatis di Seal (Android)
Agar Seal di HP otomatis menghapus watermark `AnimeKhor.org` di pojok kiri atas saat download:

1. Buka aplikasi **Seal** di HP.
2. Masuk ke **Settings (Pengaturan)** > **Format / Unduhan** > **Custom Arguments (Argumen Kustom)**.
3. Masukkan perintah berikut:
   ```text
   --ppa "ffmpeg:-vf delogo=x=2:y=2:w=170:h=48"
   ```
4. Simpan. Sekarang setiap kali Anda mendownload link dari bot ke Seal, watermark pojok kiri atas otomatis terhapus bersih!
