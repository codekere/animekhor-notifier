# AnimeKhor Notifier & Best HD Downloader

Automated pipeline for AnimeKhor episode notifications, 16:9 thumbnail extraction for YouTube, and cloud watermark-free video downloads with live progress bars via **GitHub Actions**, **Cloudflare Workers**, and **Telegram Bot**.

---

## 📱 Bot Commands

* `/link` : Retrieve the latest episode with clean 16:9 thumbnail, release date (WIB), and direct link.
* `/link <page-url>` : Convert an AnimeKhor webpage URL to a clean Dailymotion video link.
* `/dl` : Download the latest episode in Best HD with live progress bar (Watermark removed + Subtitle).
* `/dl <link>` : Download a specific video in Best HD with watermark removed.
* `/start` : Bot overview and command guide.

---

## ⚡ Instant Responses via Cloudflare Workers

The bot responds in **under 1 second** by routing incoming Telegram webhooks through Cloudflare Workers, while heavy video rendering (FFmpeg delogo) runs on GitHub Actions runners:

1. Copy the code in [`cloudflare_worker.js`](file:///c:/Users/User/Desktop/Downloader/cloudflare_worker.js) into your Cloudflare Worker.
2. In Worker **Settings** > **Variables and Secrets**, configure:
   * `TELEGRAM_BOT_TOKEN` : Bot token from [@BotFather](https://t.me/BotFather)
   * `TELEGRAM_CHAT_ID` : (Optional) Your numeric Chat ID to restrict access
   * `GITHUB_TOKEN` : GitHub Personal Access Token (Classic PAT with `repo` scope)
   * `GITHUB_REPO` : `codekere/animekhor-notifier`
3. Set Webhook:
   ```text
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://<YOUR_WORKER>.workers.dev
   ```

---

## 📊 Live Download Progress

During `/dl`, the bot displays an animated progress bar in Telegram:
* `10%` : Connecting & extracting media streams.
* `10% - 60%` : Live stream download progress (Size, Speed, ETA).
* `70%` : Removing watermark via FFmpeg delogo.
* `90%` : Uploading clean assets to GitHub Releases CDN.
* `100%` : Clean MP4 & subtitle ready for download.
