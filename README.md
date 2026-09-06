# AnimeKhor Notifier & Best HD Downloader

Automated pipeline for AnimeKhor episode notifications, 16:9 thumbnail extraction for YouTube, and cloud watermark-free video downloads via **GitHub Actions** and **Telegram Bot**.

---

## ⚡ Instant Response via Cloudflare Worker

To have your Telegram bot reply **instantly (sub-second)** to `/last`, `/link`, and `/dl`:

1. Go to your [Cloudflare Dashboard](https://dash.cloudflare.com/) > **Workers & Pages** > **Create application** > **Create Worker**.
2. Name it (e.g. `animekhor-bot`), click **Deploy**, then click **Edit code**.
3. Replace the code with the contents of [`cloudflare_worker.js`](file:///c:/Users/User/Desktop/Downloader/cloudflare_worker.js) and click **Deploy**.
4. Go to **Settings** > **Variables and Secrets** of the Worker and add:
   * `TELEGRAM_BOT_TOKEN` : Your bot token from [@BotFather](https://t.me/BotFather)
   * `TELEGRAM_CHAT_ID` : (Optional) Your numeric Chat ID to restrict access
   * `GITHUB_TOKEN` : A GitHub Personal Access Token (Classic PAT with `repo` scope from [GitHub Tokens](https://github.com/settings/tokens))
   * `GITHUB_REPO` : `codekere/animekhor-notifier`
5. Set the Telegram Webhook:
   Open your browser and visit:
   ```text
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://<YOUR_WORKER_SUBDOMAIN>.workers.dev
   ```
   *(Replace `<YOUR_BOT_TOKEN>` and your Worker URL)*.
   Once set, all `/last`, `/link`, and `/dl` commands will reply in **under 1 second**!

---

## 📱 Bot Commands

* `/last` : Retrieve the latest episode from AnimeKhor with clean 16:9 thumbnail and direct link.
* `/link <page-url>` : Convert an AnimeKhor webpage URL to a clean Dailymotion video link + 16:9 thumbnail (defaults to latest if no URL provided).
* `/dl` : Download the latest episode in Best HD (1080p + Audio + Subtitle with watermark removed).
* `/dl <link>` : Download a specific episode in Best HD with watermark removed.
* `/start` : Bot overview and command guide.

---

## ⚙️ GitHub Secrets Configuration

In this repository, navigate to **Settings** > **Secrets and variables** > **Actions**:
* `TELEGRAM_BOT_TOKEN` : Bot token from [@BotFather](https://t.me/BotFather)
* `TELEGRAM_CHAT_ID` : Your numeric Chat ID from [@userinfobot](https://t.me/userinfobot)

---

## 🧹 Automatic Storage & Log Cleanup

* **GitHub Actions Runners**: Fully ephemeral. Every job runs in an isolated virtual machine; all temporary videos and logs are destroyed upon job completion.
* **GitHub Releases CDN**: Automatically pruned to keep only the newest 3 releases, preventing repository storage accumulation.
