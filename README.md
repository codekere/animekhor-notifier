# AnimeKhor Notifier

Minimalist automated notification system for new AnimeKhor episodes via **GitHub Actions** and **Telegram Bot**.

---

## 📱 Features
* **Automated 24/7 Notifications**:
  Whenever AnimeKhor publishes a new episode, the bot automatically sends:
  * 📌 Episode Title
  * 🔗 Direct Seal Link (Dailymotion)
* **Bot Command**:
  * `/last` : Fetch the latest published episode and its direct Seal download link on demand.

---

## ⚙️ GitHub Secrets Configuration
In this repository, navigate to **Settings** > **Secrets and variables** > **Actions**:
* `TELEGRAM_BOT_TOKEN` : Bot token from [@BotFather](https://t.me/BotFather)
* `TELEGRAM_CHAT_ID` : Your numeric Chat ID from [@userinfobot](https://t.me/userinfobot)

---

## 🎬 Automatic Watermark Removal in Seal (Android)
To automatically remove the `AnimeKhor.org` top-left watermark when downloading via Seal:

1. Open **Seal** on your Android device.
2. Go to **Settings** > **Format / Download** > **Custom Arguments** (or Command Template).
3. Add the following argument:
   ```text
   --ppa "ffmpeg:-vf delogo=x=2:y=2:w=170:h=48"
   ```
4. Save. All downloaded videos will have the top-left watermark cleanly removed.
