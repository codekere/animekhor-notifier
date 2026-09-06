# -*- coding: utf-8 -*-
"""
AnimeKhor Notifier (Clean & Minimalist)
=======================================
Features:
1. Monitors AnimeKhor RSS feed for new episodes.
2. Sends automatic Telegram notification: Title + Direct Seal Link (Dailymotion).
3. Telegram command: /last to fetch the latest episode and link on demand.
"""

import os
import sys
import re
import json
import urllib.request
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


def extract_video_link(page_url: str) -> str:
    """Extract clean Dailymotion video URL ready for Seal."""
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


def send_telegram(bot_token: str, chat_id: str, text: str):
    """Send clean HTML message to Telegram."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[ERROR] Failed to send Telegram message: {e}")


def register_commands(bot_token: str):
    """Register official commands in Telegram menu."""
    url = f"https://api.telegram.org/bot{bot_token}/setMyCommands"
    payload = json.dumps({
        "commands": [
            {"command": "last", "description": "Check latest episode and Seal link"},
            {"command": "start", "description": "Bot overview and instructions"}
        ]
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(req, timeout=10)
        print("[OK] Successfully registered commands menu with Telegram API (/last, /start).")
    except Exception as e:
        print(f"[WARN] Failed to setMyCommands: {e}")


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
            msg = (
                f"🎬 <b>New Episode Released!</b>\n\n"
                f"📌 <b>Title:</b>\n<code>{title}</code>\n\n"
                f"🔗 <b>Seal Link:</b>\n<code>{video_url}</code>"
            )
            send_telegram(bot_token, chat_id, msg)
            history.add(link)
            new_items.append(title)

    save_json(HISTORY_FILE, list(history)[-100:])
    print(f"[*] Done. Sent {len(new_items)} new episode(s).")


def process_user_commands(bot_token: str):
    """Process incoming Telegram commands (/last, /start)."""
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
        msg = update.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = msg.get("text", "").strip()

        if not text or not chat_id:
            continue

        print(f"[USER] Command from {chat_id}: {text}")

        if text.startswith("/last"):
            latest = get_latest_rss_item()
            if latest:
                video_url = extract_video_link(latest["link"])
                reply = (
                    f"📌 <b>Latest Episode:</b>\n<code>{latest['title']}</code>\n\n"
                    f"🔗 <b>Seal Link:</b>\n<code>{video_url}</code>"
                )
            else:
                reply = "❌ Failed to fetch latest episode."
            send_telegram(bot_token, chat_id, reply)

        elif text.startswith("/start") or text.startswith("/help"):
            welcome = (
                "👋 <b>AnimeKhor Notifier Bot</b>\n\n"
                "Commands:\n"
                "• /last - Check the latest episode and get the direct Seal link"
            )
            send_telegram(bot_token, chat_id, welcome)

    save_json(BOT_OFFSET_FILE, last_offset)


def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("[ERROR] TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are not set!")
        sys.exit(1)

    register_commands(bot_token)
    check_rss_updates(bot_token, chat_id)
    process_user_commands(bot_token)


if __name__ == "__main__":
    main()
