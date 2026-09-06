# -*- coding: utf-8 -*-
"""
AnimeKhor Notifier & Cloud Processor (Clean & Minimalist)
=========================================================
Features:
1. Monitors AnimeKhor RSS feed for new episodes.
2. Sends clean Telegram alerts with:
   - Episode Title
   - 1-Tap copyable direct link (no /dl prefix)
   - Interactive download options: 1080p, 720p, Audio MP3, Mute
3. Commands:
   - /dl [1080p|720p|audio|mute] <link> : Download & remove watermark
   - /last : Check the latest episode and direct link
   - /start : Bot instructions
4. Cloud Processing:
   - Downloads via yt-dlp.
   - Extracts and cleans subtitles (.srt).
   - Generates clean video with FFmpeg delogo.
   - Extracts MP3 audio.
   - Uploads to GitHub Releases for direct high-speed download.
   - In-place message updates with instant Dismiss button.
"""

import os
import sys
import re
import time
import glob
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
    """Remove watermark tags like [www.AnimeKhor.org] from title."""
    cleaned = re.sub(r'\[?www\.AnimeKhor\.org\]?', '', raw_title, flags=re.I)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()


def sanitize_filename(name: str, ext: str = "mp4") -> str:
    """Generate safe filename."""
    cleaned = clean_title_for_display(name)
    cleaned = re.sub(r'[\\/*?:"<>|]', "", cleaned)
    cleaned = re.sub(r'\s+', "_", cleaned.strip())
    return f"{cleaned[:45]}_Clean.{ext}"


def extract_video_link(page_url: str) -> str:
    """Extract clean Dailymotion video URL from AnimeKhor page."""
    try:
        req = urllib.request.Request(page_url, headers=HEADERS)
        html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')

        dm_match = re.search(
            r'(?:https?:)?//(?:www\.|geo\.)?dailymotion\.com/(?:embed/video/|player\.html\?video=)([\w-]+)',
            html
        )
        if dm_match:
            video_id = dm_match.group(1)
            return f"https://www.dailymotion.com/video/{video_id}"

        iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
        if iframe_match:
            src = iframe_match.group(1)
            if src.startswith('//'):
                src = 'https:' + src
            return src
    except Exception as e:
        print(f"[WARN] Failed to extract video from {page_url}: {e}")
    return page_url


def extract_dm_id(url: str) -> str:
    """Extract Dailymotion video ID from URL."""
    match = re.search(r'dailymotion\.com/video/([\w-]+)', url)
    return match.group(1) if match else url


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
            {"command": "last", "description": "Get latest episode & direct link"},
            {"command": "dl", "description": "Download clean video (1080p/720p/audio/mute)"},
            {"command": "start", "description": "Bot instructions and features"}
        ]
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(req, timeout=10)
        print("[OK] Commands registered with Telegram API.")
    except Exception as e:
        print(f"[WARN] Failed to setMyCommands: {e}")


def get_video_dimensions(video_path: str):
    """Get video resolution using ffprobe."""
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
        print(f"[WARN] ffprobe failed: {e}, falling back to 1080p")
        return 1920, 1080


def get_delogo_filter(height: int) -> str:
    """Calculate exact delogo bounding box for top-left watermark."""
    scale = height / 1080.0
    x = max(1, int(round(2 * scale)))
    y = max(1, int(round(2 * scale)))
    w = int(round(170 * scale))
    h = int(round(48 * scale))
    return f"delogo=x={x}:y={y}:w={w}:h={h}"


def clean_srt_file(srt_path: str, clean_path: str):
    """Remove AnimeKhor promo watermark text from subtitle lines."""
    try:
        with open(srt_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        cleaned_lines = []
        for line in lines:
            if re.search(r'animekhor\.org', line, re.I):
                cleaned_lines.append("\n")
            else:
                cleaned_lines.append(line)

        with open(clean_path, "w", encoding="utf-8") as f:
            f.writelines(cleaned_lines)
        return clean_path
    except Exception as e:
        print(f"[WARN] Failed to clean srt: {e}")
        return srt_path


def make_options_keyboard(video_url: str):
    """Create clean inline buttons for 1-tap download choices."""
    vid_id = extract_dm_id(video_url)
    return {
        "inline_keyboard": [
            [
                {"text": "🎬 1080p Clean", "callback_data": f"dl:1080:{vid_id}"},
                {"text": "⚡ 720p Clean", "callback_data": f"dl:720:{vid_id}"}
            ],
            [
                {"text": "🎵 Audio (MP3)", "callback_data": f"dl:audio:{vid_id}"},
                {"text": "🔇 Mute Video", "callback_data": f"dl:mute:{vid_id}"}
            ]
        ]
    }


def download_and_clean(
    target_url: str,
    bot_token: str,
    chat_id: str,
    loading_msg_id: int,
    resolution: str = "1080",
    mode: str = "video"  # "video", "audio", "mute"
):
    """Execute download, watermark removal, audio/subtitle extraction, and upload to Releases."""
    if not target_url.startswith("http"):
        # Reconstruct Dailymotion URL if only ID is provided
        target_url = f"https://www.dailymotion.com/video/{target_url}"

    video_url = extract_video_link(target_url) if "dailymotion.com" not in target_url else target_url
    print(f"[*] Starting process for URL: {video_url} (res: {resolution}, mode: {mode})")

    timestamp = int(time.time())
    raw_video = f"raw_{timestamp}.mp4"
    clean_video = ""
    clean_audio = ""
    clean_sub = ""
    files_to_upload = []

    # Get video title
    try:
        title_cmd = [sys.executable, "-m", "yt_dlp", "--simulate", "--get-title", video_url]
        raw_title = subprocess.check_output(title_cmd, stderr=subprocess.STDOUT).decode(errors="ignore").strip()
    except Exception:
        raw_title = "Anime Episode"

    display_title = clean_title_for_display(raw_title)

    try:
        # 1. AUDIO ONLY MODE
        if mode == "audio":
            clean_audio = sanitize_filename(raw_title, "mp3")
            print(f"[*] Extracting Audio (MP3)...")
            dl_audio_cmd = [
                sys.executable, "-m", "yt_dlp",
                "-f", "bestaudio/best",
                "-x", "--audio-format", "mp3",
                "-o", clean_audio,
                video_url
            ]
            subprocess.run(dl_audio_cmd, check=True)
            if os.path.exists(clean_audio):
                files_to_upload.append(clean_audio)

        # 2. VIDEO MODES (video or mute)
        else:
            # Resolution selector
            if resolution == "720":
                fmt = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
            elif resolution == "480":
                fmt = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
            else:
                fmt = "bestvideo+bestaudio/best"

            clean_ext = "mp4"
            suffix = "_Mute" if mode == "mute" else f"_{resolution}p"
            clean_video = sanitize_filename(f"{display_title}{suffix}", clean_ext)

            print(f"[*] Downloading stream ({resolution}p) and subtitles...")
            dl_cmd = [
                sys.executable, "-m", "yt_dlp",
                "-f", fmt,
                "--merge-output-format", "mp4",
                "--write-sub", "--sub-lang", "id,en-auto",
                "-o", raw_video,
                "-o", f"subtitle:sub_{timestamp}.%(ext)s",
                video_url
            ]
            subprocess.run(dl_cmd, check=True)

            if not os.path.exists(raw_video):
                raise FileNotFoundError("Video stream download failed.")

            # Check resolution and delogo
            w, h = get_video_dimensions(raw_video)
            delogo_vf = get_delogo_filter(h)
            print(f"[*] Video dimensions: {w}x{h}, delogo: {delogo_vf}")

            ffmpeg_cmd = ["ffmpeg", "-y", "-i", raw_video, "-vf", delogo_vf]
            if mode == "mute":
                ffmpeg_cmd.extend(["-an"])
            else:
                ffmpeg_cmd.extend(["-c:a", "copy"])
            ffmpeg_cmd.extend(["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", clean_video])

            print(f"[*] Running FFmpeg watermark removal...")
            subprocess.run(ffmpeg_cmd, check=True)

            if os.path.exists(clean_video):
                files_to_upload.append(clean_video)

            # Check and clean downloaded subtitles
            sub_files = glob.glob(f"sub_{timestamp}*.srt")
            if sub_files:
                for sf in sub_files:
                    lang = "ID" if ".id." in sf else "EN"
                    final_sub = sanitize_filename(f"{display_title}_{lang}", "srt")
                    clean_srt_file(sf, final_sub)
                    if os.path.exists(final_sub):
                        files_to_upload.append(final_sub)

            # Also extract clean MP3 audio if standard video mode
            if mode == "video":
                clean_audio = sanitize_filename(raw_title, "mp3")
                subprocess.run([
                    "ffmpeg", "-y", "-i", raw_video,
                    "-vn", "-c:a", "libmp3lame", "-q:a", "2",
                    clean_audio
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(clean_audio):
                    files_to_upload.append(clean_audio)

        if not files_to_upload:
            raise RuntimeError("No output files generated.")

        # Upload to GitHub Releases
        tag = f"dl-{timestamp}"
        repo = os.environ.get("GITHUB_REPOSITORY", "codekere/animekhor-notifier")
        print(f"[*] Creating release {tag} in {repo} with files: {files_to_upload}")

        gh_cmd = [
            "gh", "release", "create", tag,
            *files_to_upload,
            "--title", f"{display_title}",
            "--notes", f"Clean watermark-free release for {display_title}"
        ]
        subprocess.run(gh_cmd, check=True)

        base_dl_url = f"https://github.com/{repo}/releases/download/{tag}"

        # Build download links list
        download_links_html = []
        for f in files_to_upload:
            encoded_name = urllib.parse.quote(f)
            file_url = f"{base_dl_url}/{encoded_name}"
            if f.endswith(".mp4"):
                label = f"🎬 Download Clean Video ({resolution}p)" if mode != "mute" else "🔇 Download Mute Video"
                download_links_html.append(f"• <a href=\"{file_url}\"><b>{label}</b></a>")
            elif f.endswith(".mp3"):
                download_links_html.append(f"• <a href=\"{file_url}\"><b>🎵 Download Audio Only (.MP3)</b></a>")
            elif f.endswith(".srt"):
                lang_tag = "Indonesian" if "_ID_" in f else "English"
                download_links_html.append(f"• <a href=\"{file_url}\"><b>📝 Download Subtitle ({lang_tag} .SRT)</b></a>")

        links_text = "\n".join(download_links_html)

        # Prune old releases (keep latest 3)
        try:
            out = subprocess.check_output(["gh", "release", "list", "--limit", "10"]).decode()
            tags = [line.split()[0] for line in out.strip().splitlines() if line]
            if len(tags) > 3:
                for old_tag in tags[3:]:
                    subprocess.run(["gh", "release", "delete", old_tag, "--yes", "--cleanup-tag"])
        except Exception as e:
            print(f"[WARN] Failed to delete older releases: {e}")

        # Update Telegram message
        success_msg = (
            f"✅ <b>Clean Episode Ready!</b>\n\n"
            f"📌 <b>Title:</b>\n<code>{display_title}</code>\n\n"
            f"<b>Direct High-Speed Downloads:</b>\n{links_text}\n\n"
            f"<i>ℹ️ Watermarks removed & subtitle cleaned.</i>"
        )
        edit_telegram_message(bot_token, chat_id, loading_msg_id, success_msg, reply_markup=DISMISS_KEYBOARD)
        print(f"[OK] Successfully finished for {display_title}")

    except Exception as e:
        print(f"[ERROR] Process failed: {e}")
        err_msg = f"❌ <b>Download Failed:</b>\n<code>{str(e)[:200]}</code>"
        edit_telegram_message(bot_token, chat_id, loading_msg_id, err_msg, reply_markup=DISMISS_KEYBOARD)

    finally:
        # Cleanup temporary files
        to_clean = [raw_video, *files_to_upload, *glob.glob(f"sub_{timestamp}*")]
        for f in to_clean:
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
            # Notification with copyable link alone (no /dl) & quick options keyboard
            msg = (
                f"🎬 <b>New Episode Released!</b>\n\n"
                f"📌 <b>Title:</b>\n<code>{clean_title}</code>\n\n"
                f"🔗 <b>Direct Link:</b>\n<code>{video_url}</code>"
            )
            keyboard = make_options_keyboard(video_url)
            send_telegram(bot_token, chat_id, msg, reply_markup=keyboard)
            history.add(link)
            new_items.append(title)

    save_json(HISTORY_FILE, list(history)[-100:])
    print(f"[*] Done. Sent {len(new_items)} new episode(s).")


def process_user_commands(bot_token: str, direct_url: str = ""):
    """Process incoming Telegram commands, callback buttons, or direct workflow trigger."""
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

        # 1. Handle Callback Query (Buttons)
        cb = update.get("callback_query")
        if cb:
            cb_id = cb.get("id")
            cb_data = cb.get("data", "")
            cb_msg = cb.get("message", {})
            cb_chat_id = str(cb_msg.get("chat", {}).get("id", ""))
            cb_msg_id = cb_msg.get("message_id")

            if cb_data == "dismiss" and cb_chat_id and cb_msg_id:
                delete_telegram_message(bot_token, cb_chat_id, cb_msg_id)
                answer_callback_query(bot_token, cb_id, "Dismissed")
                continue

            if cb_data.startswith("dl:"):
                # format: dl:<format>:<url_or_id>
                parts = cb_data.split(":", 2)
                fmt_choice = parts[1] if len(parts) > 1 else "1080"
                target = parts[2] if len(parts) > 2 else ""

                mode = "video"
                resolution = "1080"
                if fmt_choice == "audio":
                    mode = "audio"
                elif fmt_choice == "mute":
                    mode = "mute"
                elif fmt_choice == "720":
                    resolution = "720"
                elif fmt_choice == "480":
                    resolution = "480"

                answer_callback_query(bot_token, cb_id, f"Processing {fmt_choice}...")
                loading_id = send_telegram(
                    bot_token, cb_chat_id,
                    f"⏳ <b>Processing {fmt_choice.upper()}...</b>\nDownloading and removing watermark. Please wait..."
                )
                download_and_clean(target, bot_token, cb_chat_id, loading_id, resolution=resolution, mode=mode)
                continue

        # 2. Handle Text Messages
        msg = update.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id", ""))
        user_msg_id = msg.get("message_id")
        text = msg.get("text", "").strip()

        if not text or not chat_id:
            continue

        print(f"[USER] Command from {chat_id}: {text}")

        if text.startswith("/dl"):
            delete_telegram_message(bot_token, chat_id, user_msg_id)

            # Parse parameters: e.g. /dl 720p <url> or /dl audio <url>
            tokens = text.split()
            resolution = "1080"
            mode = "video"
            target_link = ""

            for t in tokens[1:]:
                low = t.lower()
                if low in ["720", "720p"]:
                    resolution = "720"
                elif low in ["480", "480p"]:
                    resolution = "480"
                elif low in ["audio", "mp3"]:
                    mode = "audio"
                elif low in ["mute", "noaudio"]:
                    mode = "mute"
                elif t.startswith("http"):
                    target_link = t

            if not target_link:
                # Check replied message
                if "reply_to_message" in msg and "text" in msg["reply_to_message"]:
                    rep_text = msg["reply_to_message"]["text"]
                    match = re.search(r'https?://[^\s<>"]+', rep_text)
                    if match:
                        target_link = match.group(0)

            if not target_link:
                latest = get_latest_rss_item()
                if latest:
                    target_link = latest["link"]

            if not target_link:
                send_telegram(bot_token, chat_id, "❌ <b>Usage:</b> <code>/dl [1080p|720p|audio|mute] &lt;link&gt;</code>")
                continue

            status_label = "AUDIO (MP3)" if mode == "audio" else f"{resolution}p"
            loading_id = send_telegram(
                bot_token, chat_id,
                f"⏳ <b>Processing {status_label}...</b>\nDownloading and removing watermark. Please wait ~2-3 minutes..."
            )
            download_and_clean(target_link, bot_token, chat_id, loading_id, resolution=resolution, mode=mode)

        elif text.startswith("/last"):
            latest = get_latest_rss_item()
            if latest:
                video_url = extract_video_link(latest["link"])
                clean_title = clean_title_for_display(latest["title"])
                reply = (
                    f"📌 <b>Latest Episode:</b>\n<code>{clean_title}</code>\n\n"
                    f"🔗 <b>Direct Link:</b>\n<code>{video_url}</code>"
                )
                keyboard = make_options_keyboard(video_url)
            else:
                reply = "❌ Failed to fetch latest episode."
                keyboard = None
            send_telegram(bot_token, chat_id, reply, reply_markup=keyboard)

        elif text.startswith("/start") or text.startswith("/help"):
            welcome = (
                "👋 <b>AnimeKhor Notifier & Cloud Processor</b>\n\n"
                "<b>Features:</b>\n"
                "• Tap any link to copy it instantly\n"
                "• Tap download buttons below each episode for 1080p, 720p, or Audio\n\n"
                "<b>Commands:</b>\n"
                "• /last - Check latest episode & options\n"
                "• /dl - Download latest episode (1080p + Audio + Subtitle)\n"
                "• /dl 720p &lt;link&gt; - Download 720p clean video\n"
                "• /dl audio &lt;link&gt; - Extract MP3 audio only\n"
                "• /dl mute &lt;link&gt; - Video without audio track"
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
        print(f"[*] Direct URL trigger: {input_url}")
        process_user_commands(bot_token, direct_url=input_url)
    else:
        check_rss_updates(bot_token, chat_id)
        process_user_commands(bot_token)


if __name__ == "__main__":
    main()
