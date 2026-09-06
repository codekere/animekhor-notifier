# AnimeKhor Notifier & Watermark Remover

Automated pipeline for AnimeKhor episode notifications and cloud watermark removal via **GitHub Actions** and **Telegram Bot**.

---

## 📱 Features

* **Automated 24/7 Notifications**:
  Monitors AnimeKhor updates and sends clean Telegram alerts containing:
  * 📌 Clean Episode Title
  * 🔗 Direct Dailymotion Link
  * ⚡ 1-Tap copyable `/dl <url>` command
* **Cloud Watermark Removal (`/dl`)**:
  * Send `/dl <link>` to download and remove the top-left `AnimeKhor.org` watermark in the cloud.
  * Your command message is automatically deleted to keep the chat clean.
  * The bot displays a processing status and edits it in-place to provide a high-speed direct download link from GitHub Releases.
  * Includes a `🗑️ Dismiss` button to easily clear the message.
* **On-Demand Check (`/last`)**:
  * `/last` : Retrieve the latest published episode and its download command.

---

## ⚙️ GitHub Secrets Configuration

In this repository, navigate to **Settings** > **Secrets and variables** > **Actions**:
* `TELEGRAM_BOT_TOKEN` : Bot token from [@BotFather](https://t.me/BotFather)
* `TELEGRAM_CHAT_ID` : Your numeric Chat ID from [@userinfobot](https://t.me/userinfobot)

---

## 🚀 How to Download Watermark-Free Videos

1. When a new episode notification arrives on Telegram, copy the provided `/dl <url>` command (tap on the code block to copy).
2. Send `/dl <url>` to the bot (or type `/dl` alone to automatically download the latest episode).
3. Wait ~2-3 minutes while GitHub Actions downloads the 1080p stream and re-encodes the video with FFmpeg `delogo`.
4. Click the download link provided by the bot to save the clean MP4 directly to your phone.
