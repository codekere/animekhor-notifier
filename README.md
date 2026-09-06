# AnimeKhor Notifier & Best HD Downloader

Automated pipeline for AnimeKhor episode notifications, 16:9 thumbnail extraction for YouTube, and cloud watermark-free video downloads via **GitHub Actions** and **Telegram Bot**.

---

## 📱 Features

* **Automated 24/7 Notifications**:
  Monitors AnimeKhor updates and delivers clean Telegram alerts containing:
  * 🖼️ **16:9 Full HD Thumbnail** (embedded preview + direct 1080p link for your YouTube thumbnails).
  * 📌 Clean Episode Title.
  * 🔗 Direct Dailymotion Link (tap the code block to copy the link alone).
* **Best HD Cloud Processing (`/dl`)**:
  * Automatically downloads the **Best HD quality available (1080p) + Audio**.
  * Removes the top-left `AnimeKhor.org` watermark cleanly with FFmpeg `delogo`.
  * Extracts and cleans Indonesian (`.id.srt`) & English (`.en.srt`) subtitles (watermark promo lines stripped).
  * Displays the exact **final file size** and video quality.
  * Uploads to **GitHub Releases CDN** for direct, high-speed downloads without Telegram's 50MB file size limit.
  * Edits the processing message in-place and includes a `🗑️ Dismiss / Close` button.
* **On-Demand Check (`/last` or `/link`)**:
  * Retrieve the latest published episode with its 16:9 thumbnail and direct link on demand.

---

## ⚙️ GitHub Secrets Configuration

In this repository, navigate to **Settings** > **Secrets and variables** > **Actions**:
* `TELEGRAM_BOT_TOKEN` : Bot token from [@BotFather](https://t.me/BotFather)
* `TELEGRAM_CHAT_ID` : Your numeric Chat ID from [@userinfobot](https://t.me/userinfobot)

---

## 🚀 How to Use

1. **Copy Link:**
   * Tap the direct link in the notification to copy it immediately.
2. **Download Best HD Video:**
   * Send `/dl` to download the latest episode in Best HD.
   * Or send `/dl <link>` to download a specific video.
3. **Get Clean Files:**
   * The bot updates with the clean 1080p MP4 and subtitle `.srt` download links along with the actual file size.
