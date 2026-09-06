# AnimeKhor Notifier & Best HD Downloader

Automated pipeline for AnimeKhor episode notifications, 16:9 thumbnail extraction for YouTube, and cloud watermark-free video downloads via **GitHub Actions** and **Telegram Bot**.

---

## 📱 Commands

* `/last` : Retrieve the latest episode from AnimeKhor with its 16:9 thumbnail and direct link.
* `/link <page-url>` : Convert an AnimeKhor webpage URL to a clean Dailymotion video link + 16:9 thumbnail.
* `/dl` : Download the latest episode in Best HD (1080p + Audio + Subtitle with watermark removed).
* `/dl <link>` : Download a specific episode in Best HD with watermark removed.
* `/start` : Bot overview and command guide.

---

## ⚙️ GitHub Secrets Configuration

In this repository, navigate to **Settings** > **Secrets and variables** > **Actions**:
* `TELEGRAM_BOT_TOKEN` : Bot token from [@BotFather](https://t.me/BotFather)
* `TELEGRAM_CHAT_ID` : Your numeric Chat ID from [@userinfobot](https://t.me/userinfobot)

---

## 🚀 Usage Guide

1. **Get Latest Episode:** Send `/last` to fetch the newest episode and 16:9 Full HD thumbnail.
2. **Convert Any Page:** Send `/link https://animekhor.org/...` to convert a webpage to a direct video link.
3. **Cloud Download (No WM):** Send `/dl` or `/dl <video-link>` to generate a watermark-free 1080p MP4 and clean `.srt` subtitles.
