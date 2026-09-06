# -*- coding: utf-8 -*-
"""
AnimeKhor Notifier & Best HD Cloud Processor
============================================
Features:
1. Monitors AnimeKhor RSS feed for new episodes.
2. Sends clean Telegram alerts with:
   - 16:9 Full HD Thumbnail with watermark automatically REMOVED via delogo
   - Clean Episode Title
   - 1-Tap copyable direct link (no /dl prefix, link alone)
3. Commands:
   - /last           : Retrieve the latest published episode with clean 16:9 thumbnail
   - /link <page_url>: Convert AnimeKhor webpage to direct video link (defaults to latest if no arg)
   - /dl <link>      : Download Best HD video + Audio + Subtitle with watermark removed
   - /start          : Bot overview & instructions
4. Cloud Processing:
   - Always downloads Best HD quality available (1080p).
   - Automatically removes AnimeKhor.org watermark using FFmpeg delogo.
   - Extracts and cleans Indonesian (.id.srt) & English (.en.srt) subtitles.
   - Computes exact final file size.
   - Uploads to GitHub Releases for direct high-speed CDN download.
   - In-place message edit with Dismiss button.
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


def format_file_size(size_bytes: int) -> str:
    """Format bytes into human-readable string."""
    if size_bytes <= 0:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


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
    return f"{cleaned[:50]}_Clean.{ext}"


def extract_dm_id(url: str) -> str:
    """Extract Dailymotion video ID from URL."""
    match = re.search(r'dailymotion\.com/(?:video/|embed/video/|player\.html\?video=)([\w-]+)', url)
    return match.group(1) if match else ""


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


def get_dailymotion_thumbnail(video_url: str) -> str:
    """Fetch native 16:9 1080p/720p thumbnail URL from Dailymotion API."""
    try:
        vid_id = extract_dm_id(video_url)
        if not vid_id:
            return ""
        api_url = f"https://api.dailymotion.com/video/{vid_id}?fields=thumbnail_1080_url,thumbnail_720_url,thumbnail_large_url"
        req = urllib.request.Request(api_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return (
                data.get("thumbnail_1080_url") or
                data.get("thumbnail_720_url") or
                data.get("thumbnail_large_url") or
                ""
            )
    except Exception as e:
        print(f"[WARN] Failed to fetch thumbnail: {e}")
    return ""


def prepare_clean_thumbnail(video_url: str, output_path: str = "clean_thumb.jpg") -> str:
    """Download thumbnail and remove AnimeKhor watermark using FFmpeg delogo."""
    thumb_url = get_dailymotion_thumbnail(video_url)
    if not thumb_url:
        return ""

    temp_raw_thumb = f"raw_thumb_{int(time.time())}.jpg"
    try:
        req = urllib.request.Request(thumb_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            with open(temp_raw_thumb, "wb") as f:
                f.write(resp.read())

        # Delogo the thumbnail image (top-left watermark removal)
        cmd = [
            "ffmpeg", "-y", "-i", temp_raw_thumb,
            "-vf", "delogo=x=2:y=2:w=170:h=48",
            "-frames:v", "1",
            output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        if os.path.exists(output_path):
            return output_path
    except Exception as e:
        print(f"[WARN] Failed to clean thumbnail: {e}")
    finally:
        if os.path.exists(temp_raw_thumb):
            try:
                os.remove(temp_raw_thumb)
            except Exception:
                pass
    return ""


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


def send_telegram_local_photo(bot_token: str, chat_id: str, image_path: str, caption: str, reply_markup=None) -> int:
    """Upload clean local image file directly to Telegram sendPhoto."""
    if not image_path or not os.path.exists(image_path):
        return send_telegram(bot_token, chat_id, caption, reply_markup=reply_markup)

    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    boundary = "----WebKitFormBoundary" + str(int(time.time()))

    try:
        with open(image_path, "rb") as f:
            img_bytes = f.read()

        filename = os.path.basename(image_path)
        body = bytearray()

        # chat_id field
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(b'Content-Disposition: form-data; name="chat_id"\r\n\r\n')
        body.extend(f"{chat_id}\r\n".encode())

        # caption field
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(b'Content-Disposition: form-data; name="caption"\r\n\r\n')
        body.extend(caption.encode("utf-8"))
        body.extend(b"\r\n")

        # parse_mode field
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(b'Content-Disposition: form-data; name="parse_mode"\r\n\r\n')
        body.extend(b"HTML\r\n")

        # photo file field
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="photo"; filename="{filename}"\r\n'.encode())
        body.extend(b"Content-Type: image/jpeg\r\n\r\n")
        body.extend(img_bytes)
        body.extend(b"\r\n")

        # closing boundary
        body.extend(f"--{boundary}--\r\n".encode())

        req = urllib.request.Request(
            url,
            data=bytes(body),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "Mozilla/5.0"
            }
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return data["result"]["message_id"]
    except Exception as e:
        print(f"[WARN] Failed to send local photo: {e}")

    return send_telegram(bot_token, chat_id, caption, reply_markup=reply_markup)


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
            {"command": "last", "description": "Get latest episode & 16:9 thumbnail"},
            {"command": "link", "description": "Convert webpage URL to direct video link"},
            {"command": "dl", "description": "Download clean Best HD video + subtitle"},
            {"command": "start", "description": "Bot overview & instructions"}
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


def download_and_clean(target_url: str, bot_token: str, chat_id: str, loading_msg_id: int):
    """Download Best HD video, remove watermark with delogo, clean subtitles, and upload to Releases."""
    if not target_url.startswith("http"):
        target_url = f"https://www.dailymotion.com/video/{target_url}"

    video_url = extract_video_link(target_url) if "dailymotion.com" not in target_url else target_url
    print(f"[*] Starting Best HD processing for URL: {video_url}")

    timestamp = int(time.time())
    prefix = f"raw_{timestamp}"
    clean_video = ""
    files_to_upload = []

    # 1. Fetch Title
    try:
        title_cmd = [sys.executable, "-m", "yt_dlp", "--simulate", "--get-title", video_url]
        raw_title = subprocess.check_output(title_cmd, stderr=subprocess.STDOUT).decode(errors="ignore").strip()
    except Exception:
        raw_title = "Anime Episode"

    display_title = clean_title_for_display(raw_title)
    clean_video = sanitize_filename(display_title, "mp4")

    try:
        # 2. Download Stream using yt-dlp
        print(f"[*] Downloading video & audio stream with yt-dlp...")
        dl_cmd = [
            sys.executable, "-m", "yt_dlp",
            "-f", "bestvideo+bestaudio/best",
            "--no-playlist",
            "--no-warnings",
            "--write-sub", "--sub-lang", "id,en-auto",
            "-o", f"{prefix}_video.%(ext)s",
            "-o", f"subtitle:{prefix}_sub.%(ext)s",
            video_url
        ]
        res = subprocess.run(dl_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[WARN] Initial yt-dlp failed, retrying without subs: {res.stderr[:200]}")
            dl_retry = [
                sys.executable, "-m", "yt_dlp",
                "-f", "bestvideo+bestaudio/best",
                "--no-playlist",
                "-o", f"{prefix}_video.%(ext)s",
                video_url
            ]
            res_retry = subprocess.run(dl_retry, capture_output=True, text=True)
            if res_retry.returncode != 0:
                raise RuntimeError(f"yt-dlp error: {res_retry.stderr[-300:]}")

        # Locate downloaded media files
        downloaded_files = glob.glob(f"{prefix}_video*")
        downloaded_files = [f for f in downloaded_files if not f.endswith(".ytdl") and not f.endswith(".part")]
        if not downloaded_files:
            raise FileNotFoundError("Video stream download failed: no media files found.")

        # Determine primary video file for dimension detection
        primary_video = downloaded_files[0]
        w, h = get_video_dimensions(primary_video)
        delogo_vf = get_delogo_filter(h)
        print(f"[*] Media files found: {downloaded_files}, dimensions: {w}x{h}, delogo: {delogo_vf}")

        # Construct FFmpeg input arguments
        input_args = []
        for f in downloaded_files:
            input_args.extend(["-i", f])

        # Run FFmpeg delogo re-encoding
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            *input_args,
            "-vf", delogo_vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "copy",
            clean_video
        ]
        print(f"[*] Running FFmpeg delogo re-encoding...")
        ff_res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        if ff_res.returncode != 0:
            raise RuntimeError(f"FFmpeg error: {ff_res.stderr[-300:]}")

        if not os.path.exists(clean_video):
            raise FileNotFoundError("Watermark-free video output file was not generated.")

        files_to_upload.append(clean_video)
        final_video_size = os.path.getsize(clean_video)
        file_size_str = format_file_size(final_video_size)

        # 3. Clean and include downloaded subtitles (.srt)
        sub_files = glob.glob(f"{prefix}_sub*.srt")
        for sf in sub_files:
            lang = "ID" if ".id." in sf else "EN"
            final_sub = sanitize_filename(f"{display_title}_{lang}", "srt")
            clean_srt_file(sf, final_sub)
            if os.path.exists(final_sub):
                files_to_upload.append(final_sub)

        # 4. Upload to GitHub Releases
        tag = f"dl-{timestamp}"
        repo = os.environ.get("GITHUB_REPOSITORY", "codekere/animekhor-notifier")
        print(f"[*] Uploading clean assets to release {tag} in {repo}...")

        gh_cmd = [
            "gh", "release", "create", tag,
            *files_to_upload,
            "--title", f"{display_title}",
            "--notes", f"Clean watermark-free video for {display_title}"
        ]
        subprocess.run(gh_cmd, check=True)

        base_dl_url = f"https://github.com/{repo}/releases/download/{tag}"

        # 5. Build Download Links
        video_download_url = f"{base_dl_url}/{urllib.parse.quote(clean_video)}"
        sub_links = []
        for f in files_to_upload:
            if f.endswith(".srt"):
                lang_tag = "Indonesian" if "_ID_" in f else "English"
                sub_url = f"{base_dl_url}/{urllib.parse.quote(f)}"
                sub_links.append(f"• <a href=\"{sub_url}\"><b>Download Subtitle ({lang_tag} .SRT)</b></a>")

        subs_section = "\n".join(sub_links) if sub_links else "• <i>Subtitles embedded in stream</i>"

        # 6. Prune old releases (keep latest 3)
        try:
            out = subprocess.check_output(["gh", "release", "list", "--limit", "10"]).decode()
            tags = [line.split()[0] for line in out.strip().splitlines() if line]
            if len(tags) > 3:
                for old_tag in tags[3:]:
                    subprocess.run(["gh", "release", "delete", old_tag, "--yes", "--cleanup-tag"])
        except Exception as e:
            print(f"[WARN] Failed to delete older releases: {e}")

        # 7. Update Telegram loading message
        success_msg = (
            f"✅ <b>Clean Video Ready!</b>\n\n"
            f"📌 <b>Title:</b>\n<code>{display_title}</code>\n\n"
            f"📦 <b>File Size:</b> {file_size_str}\n"
            f"🎬 <b>Quality:</b> Best HD ({h}p) + Audio\n\n"
            f"⬇️ <a href=\"{video_download_url}\"><b>[ DOWNLOAD CLEAN MP4 ]</b></a>\n\n"
            f"<b>Subtitles:</b>\n{subs_section}\n\n"
            f"<i>ℹ️ Direct high-speed download from GitHub CDN.</i>"
        )
        edit_telegram_message(bot_token, chat_id, loading_msg_id, success_msg, reply_markup=DISMISS_KEYBOARD)
        print(f"[OK] Successfully processed and released {display_title} ({file_size_str})")

    except Exception as e:
        print(f"[ERROR] Process failed: {e}")
        err_msg = f"❌ <b>Download Failed:</b>\n<code>{str(e)[:300]}</code>"
        edit_telegram_message(bot_token, chat_id, loading_msg_id, err_msg, reply_markup=DISMISS_KEYBOARD)

    finally:
        # Cleanup temporary files (Zero Storage Leaks)
        to_clean = [*glob.glob(f"{prefix}*"), *files_to_upload]
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


def format_episode_message(title: str, video_url: str) -> str:
    """Format clean episode message with 1-tap copyable link (no /dl prefix, no thumbnail link)."""
    clean_title = clean_title_for_display(title)
    return (
        f"🎬 <b>New Episode Released!</b>\n\n"
        f"📌 <b>Title:</b>\n<code>{clean_title}</code>\n\n"
        f"🔗 <b>Direct Link:</b>\n<code>{video_url}</code>"
    )


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
    clean_thumb_path = "clean_thumb.jpg"

    for item in reversed(items):
        link = item.find('link').text.strip()
        title = item.find('title').text.strip()

        if link not in history:
            video_url = extract_video_link(link)
            msg = format_episode_message(title, video_url)

            # Generate delogoed 16:9 thumbnail and upload directly to Telegram
            clean_thumb = prepare_clean_thumbnail(video_url, clean_thumb_path)
            send_telegram_local_photo(bot_token, chat_id, clean_thumb, msg)

            if os.path.exists(clean_thumb_path):
                try:
                    os.remove(clean_thumb_path)
                except Exception:
                    pass

            history.add(link)
            new_items.append(title)

    save_json(HISTORY_FILE, list(history)[-100:])
    print(f"[*] Done. Sent {len(new_items)} new episode(s).")


def process_user_commands(bot_token: str, direct_url: str = "", custom_msg_id: int = 0):
    """Process incoming Telegram commands or webhook/dispatch triggers."""
    if direct_url:
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if chat_id:
            if custom_msg_id:
                loading_id = custom_msg_id
            else:
                loading_id = send_telegram(
                    bot_token, chat_id,
                    "⏳ <b>Processing Best HD Video...</b>\nDownloading best quality and removing watermark. Please wait ~2-3 minutes..."
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

    clean_thumb_path = "clean_thumb_cmd.jpg"

    for update in updates:
        update_id = update["update_id"]
        last_offset = max(last_offset, update_id + 1)

        # 1. Handle Dismiss Button Callback
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

        # 2. Handle Text Messages
        msg = update.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id", ""))
        user_msg_id = msg.get("message_id")
        text = msg.get("text", "").strip()

        if not text or not chat_id:
            continue

        print(f"[USER] Command from {chat_id}: {text}")

        # 1. /dl <link> : Download & remove watermark
        if text.startswith("/dl"):
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

            loading_id = send_telegram(
                bot_token, chat_id,
                "⏳ <b>Processing Best HD Video...</b>\nDownloading best quality and removing watermark. Please wait ~2-3 minutes..."
            )
            download_and_clean(target_link, bot_token, chat_id, loading_id)

        # 2. /last : Get latest episode from RSS feed with clean thumbnail
        elif text.startswith("/last"):
            latest = get_latest_rss_item()
            if latest:
                video_url = extract_video_link(latest["link"])
                reply = format_episode_message(latest["title"], video_url)
                clean_thumb = prepare_clean_thumbnail(video_url, clean_thumb_path)
                send_telegram_local_photo(bot_token, chat_id, clean_thumb, reply)
                if os.path.exists(clean_thumb_path):
                    try:
                        os.remove(clean_thumb_path)
                    except Exception:
                        pass
            else:
                send_telegram(bot_token, chat_id, "❌ Failed to fetch latest episode.")

        # 3. /link <page_url> : Convert AnimeKhor webpage to direct video link
        elif text.startswith("/link"):
            parts = text.split(maxsplit=1)
            target_page = ""
            if len(parts) > 1:
                target_page = parts[1].strip()
            elif "reply_to_message" in msg and "text" in msg["reply_to_message"]:
                rep_text = msg["reply_to_message"]["text"]
                match = re.search(r'https?://[^\s<>"]+', rep_text)
                if match:
                    target_page = match.group(0)

            # If no parameter, automatically use latest episode!
            if not target_page:
                latest = get_latest_rss_item()
                if latest:
                    target_page = latest["link"]

            if not target_page:
                send_telegram(bot_token, chat_id, "❌ <b>Usage:</b> <code>/link &lt;animekhor-page-url&gt;</code>")
                continue

            video_url = extract_video_link(target_page)
            page_slug = target_page.rstrip("/").split("/")[-1].replace("-", " ").title()
            reply = (
                f"🎬 <b>Direct Video Link Ready!</b>\n\n"
                f"📌 <b>Page:</b>\n<code>{page_slug}</code>\n\n"
                f"🔗 <b>Direct Link:</b>\n<code>{video_url}</code>"
            )
            clean_thumb = prepare_clean_thumbnail(video_url, clean_thumb_path)
            send_telegram_local_photo(bot_token, chat_id, clean_thumb, reply)
            if os.path.exists(clean_thumb_path):
                try:
                    os.remove(clean_thumb_path)
                except Exception:
                    pass

        # 4. /start or /help : Bot instructions
        elif text.startswith("/start") or text.startswith("/help"):
            welcome = (
                "👋 <b>AnimeKhor Notifier & Best HD Downloader</b>\n\n"
                "<b>Features:</b>\n"
                "• Tap any link to copy it instantly\n"
                "• Watermark-free 16:9 Full HD Thumbnail included\n\n"
                "<b>Commands:</b>\n"
                "• /last - Check latest episode from AnimeKhor\n"
                "• /link &lt;page-url&gt; - Convert webpage URL to direct video link\n"
                "• /dl - Download latest episode in Best HD (Watermark removed)\n"
                "• /dl &lt;link&gt; - Download specific video in Best HD"
            )
            send_telegram(bot_token, chat_id, welcome)

    save_json(BOT_OFFSET_FILE, last_offset)


def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    # Check for direct inputs from workflow_dispatch or repository_dispatch
    input_url = os.environ.get("INPUT_URL", "").strip()
    input_msg_id = int(os.environ.get("INPUT_MSG_ID", "0") or "0")

    if not bot_token or not chat_id:
        print("[ERROR] TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are not set!")
        sys.exit(1)

    register_commands(bot_token)
    if input_url:
        print(f"[*] Direct URL trigger: {input_url} (msg_id: {input_msg_id})")
        process_user_commands(bot_token, direct_url=input_url, custom_msg_id=input_msg_id)
    else:
        check_rss_updates(bot_token, chat_id)
        process_user_commands(bot_token)


if __name__ == "__main__":
    main()
