# AnimeKhor Notifier & Cloud Processor

Automated pipeline for AnimeKhor episode notifications, cloud watermark removal, subtitle extraction, and audio conversion via **GitHub Actions** and **Telegram Bot**.

---

## 📱 Features

* **Automated 24/7 Notifications**:
  Monitors AnimeKhor updates and sends clean Telegram alerts containing:
  * 📌 Clean Episode Title
  * 🔗 Direct Dailymotion Link (tap code block to copy link alone, no prefixes)
  * ⚡ 1-Tap Interactive Buttons:
    * `[ 🎬 1080p Clean ]`
    * `[ ⚡ 720p Clean ]`
    * `[ 🎵 Audio (MP3) ]`
    * `[ 🔇 Mute Video ]`
* **Cloud Processing (`/dl`)**:
  * Automatically removes the top-left `AnimeKhor.org` watermark using FFmpeg `delogo`.
  * Extracts and cleans Indonesian (`.id.srt`) & English (`.en-auto.srt`) subtitles (promo watermarks stripped).
  * Converts audio to `.mp3` for quick audio-only listening.
  * Uploads all assets to **GitHub Releases CDN** for fast, direct downloads without Telegram's 50MB file size limits.
  * Your command message is automatically deleted to keep the chat clean.
  * Includes a `🗑️ Dismiss / Close` button to instantly clear the result message like a popup.
* **On-Demand Check (`/last`)**:
  * `/last` : Retrieve the latest published episode, direct link, and interactive download buttons.

---

## ⚙️ GitHub Secrets Configuration

In this repository, navigate to **Settings** > **Secrets and variables** > **Actions**:
* `TELEGRAM_BOT_TOKEN` : Bot token from [@BotFather](https://t.me/BotFather)
* `TELEGRAM_CHAT_ID` : Your numeric Chat ID from [@userinfobot](https://t.me/userinfobot)

---

## 🚀 How to Use

* **Option 1: 1-Tap Buttons (Easiest)**
  When an episode alert arrives, simply tap any button below the message:
  * `[ 🎬 1080p Clean ]` : Full HD watermark-free video + subtitle + audio.
  * `[ ⚡ 720p Clean ]` : Smaller 720p clean video (faster download).
  * `[ 🎵 Audio (MP3) ]` : Pure MP3 audio track.
  * `[ 🔇 Mute Video ]` : Video without audio track.

* **Option 2: Text Commands**
  * `/dl <link>` : Download 1080p clean video.
  * `/dl 720p <link>` : Download 720p clean video.
  * `/dl audio <link>` : Extract MP3 audio only.
  * `/dl mute <link>` : Video without audio track.
  * `/dl` : Download the latest published episode automatically.
