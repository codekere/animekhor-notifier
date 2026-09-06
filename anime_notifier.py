# -*- coding: utf-8 -*-
"""
AnimeKhor Notifier & Watermark Remover (Clean & Minimalist)
==========================================================
Features:
1. Monitors AnimeKhor RSS feed for new episodes.
2. Sends clean Telegram alerts with 1-tap copyable `/dl <url>` command.
3. Telegram command `/dl <url>`:
   - Immediately deletes user's command message to prevent chat clutter.
   - Shows loading message: "⏳ Processing Video...".
   - Downloads 1080p stream with yt-dlp.
   - Removes watermark cleanly using FFmpeg delogo filter (top-left).
   - Uploads clean video to GitHub Releases CDN for high-speed direct download.
   - Edits loading message into a success message with download button and "Dismiss" button.
4. Telegram command `/last`: Checks the latest episode and direct links.
5. GitHub Actions workflow_dispatch: Trigger instant download & clean on-demand.
"""

import os
import sys
import re
import time
import json
import subprocess
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

HISTORY_FILE = "notified_history.json"
BOT_OFFSET_FILE = "bot_offset.json"
RSS_FEED_URL = "https://animekhor.org/feed/"

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
    'Referer': 'https://animekhor.org/',
}

DISMISS_KEYBOARD = {
    "inline_keyboard": [
        [{"text": "🗑️ Dismiss / Close", "callback_data": "dismiss"}]
    ]
}


def load_json(filepath: str, default=None):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(filepath: str, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def clean_title_for_display(raw_title: str) -> str:
    """Clean watermark tags like [www.AnimeKhor.org] from title."""
    cleaned = re.sub(r'\[?www\.AnimeKhor\.org\]?', '', raw_title, flags=re.I)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()


def sanitize_filename(name: str) -> str:
    """Generate safe filename for the clean video."""
    cleaned = clean_title_for_display(name)
    cleaned = re.sub(r'[\\/*?:"<>|]', "", cleaned)
    cleaned = re.sub(r'\s+', "_", cleaned.strip())
    return f"{cleaned[:50]}_Clean.mp4"


def extract_video_link(page_url: str) -> str:
    """Extract clean Dailymotion video URL ready for downloading."""
    try:
        req = urllib.request.Request(page_url, headers=HEADERS)
        html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')

        # Find Dailymotion embed / player link
        dm_match = re.search(
            r'(?:https?:)?//(?:www\.|geo\.)?dailymotion\.com/(?:embed/video/|player\.html\?video=)([\w-]+)',
            html
        )
        if dm_match:
            video_id = dm_match.group(1)
            return f"https://www.dailymotion.com/video/{video_id}"

        # Fallback to other iframe sources if available
        iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
        if iframe_match:
            src = iframe_match.group(1)
            if src.startswith('//'):
                src = 'https:' + src
            return src
    except Exception as e:
        print(f"[WARN] Failed to extract video from {page_url}: {e}")
    return page_url


def send_telegram(bot_token: str, chat_id: str, text: str, reply_markup=None) -> int:
    """Send clean HTML message to Telegram and return message_id."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get("ok"):
                return data["result"]["message_id"]
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")
    return 0


def edit_telegram_message(bot_token: str, chat_id: str, message_id: int, text: str, reply_markup=None):
    """Edit existing Telegram message in-place."""
    if not message_id:
        return
    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print(f"[WARN] Failed to edit Telegram message: {e}")


def delete_telegram_message(bot_token: str, chat_id: str, message_id: int):
    """Delete a Telegram message."""
    if not message_id:
        return
    url = f"https://api.telegram.org/bot{bot_token}/deleteMessage"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[WARN] Failed to delete Telegram message: {e}")


def answer_callback_query(bot_token: str, callback_query_id: str, text: str = ""):
    """Answer Telegram callback query."""
    url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    payload = {
        "callback_query_id": callback_query_id,
        "text": text
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[WARN] Failed to answer callback query: {e}")


def register_commands(bot_token: str):
    """Register official commands in Telegram menu."""
    url = f"https://api.telegram.org/bot{bot_token}/setMyCommands"
    payload = json.dumps({
        "commands": [
            {"command": "last", "description": "Check latest episode"},
            {"command": "dl", "description": "Download episode and remove watermark"},
            {"command": "start", "description": "Bot overview and instructions"}
        ]
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(req, timeout=10)
        print("[OK] Successfully registered commands menu with Telegram API (/last, /dl, /start).")
    except Exception as e:
        print(f"[WARN] Failed to setMyCommands: {e}")


def get_video_dimensions(video_path: str):
    """Get video width and height using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            video_path
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()
        w, h = map(int, out.split("x"))
        return w, h
    except Exception as e:
        print(f"[WARN] ffprobe failed: {e}, using default 1920x1080")
        return 1920, 1080


def get_delogo_filter(height: int) -> str:
    """Calculate exact top-left delogo box proportional to resolution."""
    scale = height / 1080.0
    x = max(1, int(round(2 * scale)))
    y = max(1, int(round(2 * scale)))
    w = int(round(170 * scale))
    h = int(round(48 * scale))
    return f"delogo=x={x}:y={y}:w={w}:h={h}"


def download_and_clean(target_url: str, bot_token: str, chat_id: str, loading_msg_id: int):
    """Download video, remove watermark with FFmpeg delogo, and upload to GitHub Releases."""
    video_url = extract_video_link(target_url) if "dailymotion.com" not in target_url else target_url
    print(f"[*] Processing video URL: {video_url}")

    timestamp = int(time.time())
    raw_filename = f"temp_raw_{timestamp}.mp4"

    # Get title with yt-dlp
    try:
        title_cmd = [sys.executable, "-m", "yt_dlp", "--simulate", "--get-title", video_url]
        raw_title = subprocess.check_output(title_cmd, stderr=subprocess.STDOUT).decode(errors="ignore").strip()
    except Exception:
        raw_title = "Anime Episode"

    display_title = clean_title_for_display(raw_title)
    final_filename = sanitize_filename(raw_title)

    try:
        # Download video
        print(f"[*] Downloading stream using yt-dlp: {video_url}")
        dl_cmd = [
            sys.executable, "-m", "yt_dlp",
            "-f", "bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
            "-o", raw_filename,
            video_url
        ]
        subprocess.run(dl_cmd, check=True)

        if not os.path.exists(raw_filename):
            raise FileNotFoundError("Downloaded video file was not found.")

        # Detect resolution & delogo filter
        w, h = get_video_dimensions(raw_filename)
        delogo_vf = get_delogo_filter(h)
        print(f"[*] Resolution: {w}x{h}, using filter: {delogo_vf}")

        # Run FFmpeg delogo re-encoding
        print(f"[*] Removing watermark with FFmpeg delogo...")
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", raw_filename,
            "-vf", delogo_vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "copy",
            final_filename
        ]
        subprocess.run(ffmpeg_cmd, check=True)

        if not os.path.exists(final_filename):
            raise FileNotFoundError("Watermark-free video file was not generated.")

        # Upload to GitHub Releases
        tag = f"dl-{timestamp}"
        repo = os.environ.get("GITHUB_REPOSITORY", "codekere/animekhor-notifier")
        print(f"[*] Uploading clean video to GitHub Release {tag} in {repo}...")

        gh_cmd = [
            "gh", "release", "create", tag,
            final_filename,
            "--title", f"{display_title}",
            "--notes", f"Clean watermark-free video for {display_title}"
        ]
        subprocess.run(gh_cmd, check=True)

        download_url = f"https://github.com/{repo}/releases/download/{tag}/{urllib.parse.quote(final_filename)}"

        # Cleanup old releases: keep only the newest 3 releases
        try:
            out = subprocess.check_output(["gh", "release", "list", "--limit", "10"]).decode()
            tags = [line.split()[0] for line in out.strip().splitlines() if line]
            if len(tags) > 3:
                for old_tag in tags[3:]:
                    subprocess.run(["gh", "release", "delete", old_tag, "--yes", "--cleanup-tag"])
        except Exception as e:
            print(f"[WARN] Failed to clean old releases: {e}")

        # Edit loading message to success
        success_msg = (
            f"✅ <b>Clean Video Ready!</b>\n\n"
            f"📌 <b>Title:</b>\n<code>{display_title}</code>\n\n"
            f"⬇️ <a href=\"{download_url}\"><b>[ TAP HERE TO DOWNLOAD CLEAN MP4 ]</b></a>\n\n"
            f"<i>ℹ️ Direct high-speed download from GitHub CDN.</i>"
        )
        edit_telegram_message(bot_token, chat_id, loading_msg_id, success_msg, reply_markup=DISMISS_KEYBOARD)
        print(f"[OK] Successfully processed and notified: {display_title}")

    except Exception as e:
        print(f"[ERROR] Failed to process video: {e}")
        err_msg = f"❌ <b>Download Failed:</b>\n<code>{str(e)[:200]}</code>"
        edit_telegram_message(bot_token, chat_id, loading_msg_id, err_msg, reply_markup=DISMISS_KEYBOARD)

    finally:
        # Clean local temporary files
        for f in [raw_filename, final_filename]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass


def get_latest_rss_item():
    """Fetch the latest episode from AnimeKhor RSS feed."""
    try:
        req = urllib.request.Request(RSS_FEED_URL, headers=HEADERS)
        xml_data = urllib.request.urlopen(req, timeout=12).read()
        root = ET.fromstring(xml_data)
        item = root.find('.//item')
        if item is not None:
            return {
                "title": item.find('title').text.strip(),
                "link": item.find('link').text.strip()
            }
    except Exception as e:
        print(f"[ERROR] Failed to parse RSS feed: {e}")
    return None


def check_rss_updates(bot_token: str, chat_id: str):
    """Check RSS feed for newly published episodes."""
    history = set(load_json(HISTORY_FILE, []))
    print(f"[*] Checking RSS feed updates at {RSS_FEED_URL}...")

    try:
        req = urllib.request.Request(RSS_FEED_URL, headers=HEADERS)
        xml_data = urllib.request.urlopen(req, timeout=12).read()
        root = ET.fromstring(xml_data)
        items = root.findall('.//item')
    except Exception as e:
        print(f"[ERROR] Failed to fetch RSS feed: {e}")
        return

    new_items = []
    for item in reversed(items):
        link = item.find('link').text.strip()
        title = item.find('title').text.strip()

        if link not in history:
            video_url = extract_video_link(link)
            clean_title = clean_title_for_display(title)
            msg = (
                f"🎬 <b>New Episode Released!</b>\n\n"
                f"📌 <b>Title:</b>\n<code>{clean_title}</code>\n\n"
                f"🔗 <b>Dailymotion Link:</b>\n<code>{video_url}</code>\n\n"
                f"⚡ <b>To Download Clean Video:</b>\n<code>/dl {video_url}</code>"
            )
            send_telegram(bot_token, chat_id, msg)
            history.add(link)
            new_items.append(title)

    save_json(HISTORY_FILE, list(history)[-100:])
    print(f"[*] Done. Sent {len(new_items)} new episode(s).")


def process_user_commands(bot_token: str, direct_url: str = ""):
    """Process incoming Telegram commands (/last, /dl, /start) or direct URL trigger."""
    if direct_url:
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if chat_id:
            loading_id = send_telegram(
                bot_token, chat_id,
                "⏳ <b>Processing Video...</b>\nDownloading and removing watermark. Please wait ~2-3 minutes..."
            )
            download_and_clean(direct_url, bot_token, chat_id, loading_id)
        return

    last_offset = load_json(BOT_OFFSET_FILE, 0)
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset={last_offset}&timeout=5"

    try:
        req = urllib.request.Request(url)
        res = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        updates = json.loads(res).get("result", [])
    except Exception as e:
        print(f"[WARN] Failed to fetch Telegram updates: {e}")
        return

    for update in updates:
        update_id = update["update_id"]
        last_offset = max(last_offset, update_id + 1)

        # Handle callback query (Dismiss button)
        cb = update.get("callback_query")
        if cb:
            cb_id = cb.get("id")
            cb_data = cb.get("data")
            cb_msg = cb.get("message", {})
            cb_chat_id = str(cb_msg.get("chat", {}).get("id", ""))
            cb_msg_id = cb_msg.get("message_id")

            if cb_data == "dismiss" and cb_chat_id and cb_msg_id:
                delete_telegram_message(bot_token, cb_chat_id, cb_msg_id)
                answer_callback_query(bot_token, cb_id, "Dismissed")
            continue

        msg = update.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id", ""))
        user_msg_id = msg.get("message_id")
        text = msg.get("text", "").strip()

        if not text or not chat_id:
            continue

        print(f"[USER] Command from {chat_id}: {text}")

        if text.startswith("/dl"):
            # Delete user's command message to keep chat spotless
            delete_telegram_message(bot_token, chat_id, user_msg_id)

            parts = text.split(maxsplit=1)
            target_link = ""
            if len(parts) > 1:
                target_link = parts[1].strip()
            elif "reply_to_message" in msg and "text" in msg["reply_to_message"]:
                rep_text = msg["reply_to_message"]["text"]
                match = re.search(r'https?://[^\s<>"]+', rep_text)
                if match:
                    target_link = match.group(0)

            if not target_link:
                latest = get_latest_rss_item()
                if latest:
                    target_link = latest["link"]

            if not target_link:
                send_telegram(bot_token, chat_id, "❌ <b>Usage:</b> <code>/dl &lt;link&gt;</code>")
                continue

            # Send loading popup
            loading_id = send_telegram(
                bot_token, chat_id,
                "⏳ <b>Processing Video...</b>\nDownloading and removing watermark. Please wait ~2-3 minutes..."
            )
            download_and_clean(target_link, bot_token, chat_id, loading_id)

        elif text.startswith("/last"):
            latest = get_latest_rss_item()
            if latest:
                video_url = extract_video_link(latest["link"])
                clean_title = clean_title_for_display(latest["title"])
                reply = (
                    f"📌 <b>Latest Episode:</b>\n<code>{clean_title}</code>\n\n"
                    f"🔗 <b>Dailymotion Link:</b>\n<code>{video_url}</code>\n\n"
                    f"⚡ <b>To Download Clean Video:</b>\n<code>/dl {video_url}</code>"
                )
            else:
                reply = "❌ Failed to fetch latest episode."
            send_telegram(bot_token, chat_id, reply)

        elif text.startswith("/start") or text.startswith("/help"):
            welcome = (
                "👋 <b>AnimeKhor Notifier Bot</b>\n\n"
                "<b>Commands:</b>\n"
                "• /last - Check the latest episode and links\n"
                "• /dl &lt;link&gt; - Download episode and remove watermark"
            )
            send_telegram(bot_token, chat_id, welcome)

    save_json(BOT_OFFSET_FILE, last_offset)


def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    input_url = os.environ.get("INPUT_URL", "").strip()

    if not bot_token or not chat_id:
        print("[ERROR] TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are not set!")
        sys.exit(1)

    register_commands(bot_token)
    if input_url:
        print(f"[*] Direct URL execution triggered: {input_url}")
        process_user_commands(bot_token, direct_url=input_url)
    else:
        check_rss_updates(bot_token, chat_id)
        process_user_commands(bot_token)


if __name__ == "__main__":
    main()
