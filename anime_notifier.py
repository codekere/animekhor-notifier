# -*- coding: utf-8 -*-
"""
AnimeKhor Auto Notifier & Interactive Telegram Bot
===================================================
Fitur:
1. Otomatis cek episode terbaru dari RSS feed AnimeKhor (setiap 15 menit di GitHub Actions).
2. Bot Telegram Interaktif:
   - /cari <judul>     : Mencari anime/donghua dan menampilkan episode terbaru.
   - /download <link>  : Mengubah link halaman web menjadi link download Dailymotion langsung.
   - Kirim link apa saja: Bot otomatis mengekstrak video dan membuat judul & deskripsi YouTube via AI.
3. Mengubah URL web Animekhor menjadi URL video murni (Dailymotion) yang siap diunduh.
4. Tombol interaktif langsung di Telegram ([📲 Buka di Seal], [⬇️ Direct Video Link]).
"""

import os
import sys
import re
import json
import time
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
    """Mengekstrak link player embed Dailymotion dari halaman episode."""
    try:
        req = urllib.request.Request(page_url, headers=HEADERS)
        html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')

        # 1. Cari embed Dailymotion
        dm_match = re.search(
            r'(?:https?:)?//(?:www\.|geo\.)?dailymotion\.com/(?:embed/video/|player\.html\?video=)([\w-]+)',
            html
        )
        if dm_match:
            video_id = dm_match.group(1)
            return f"https://www.dailymotion.com/video/{video_id}"

        # 2. Cari tag iframe video lainnya
        iframe_match = re.search(
            r'<iframe[^>]+src=["\']([^"\']*(?:dailymotion|embed|video|player)[^"\']*)["\']',
            html,
            re.I
        )
        if iframe_match:
            src = iframe_match.group(1)
            if src.startswith('//'):
                src = 'https:' + src
            return src
    except Exception as e:
        print(f"[WARN] Gagal mengekstrak player dari {page_url}: {e}")
    return page_url


def search_animekhor(query: str) -> list:
    """Mencari judul anime di Animekhor."""
    results = []
    try:
        url = f"https://animekhor.org/?s={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers=HEADERS)
        html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')

        articles = re.findall(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
        for art in articles[:6]:
            match = re.search(
                r'<h2[^>]*class=["\']entry-title["\'][^>]*>.*?<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                art,
                re.DOTALL
            )
            if not match:
                match = re.search(r'<a[^>]+href=["\'](https://animekhor\.org/[^"\']+)["\'][^>]*title=["\']([^"\']+)["\']', art)
            if match:
                link = match.group(1).strip()
                title = re.sub('<[^<]+?>', '', match.group(2)).strip()
                results.append({"title": title, "link": link})
    except Exception as e:
        print(f"[ERROR] Gagal mencari di Animekhor: {e}")
    return results


def get_series_episodes(series_url: str) -> list:
    """Mengambil daftar episode terbaru dari halaman series."""
    episodes = []
    try:
        req = urllib.request.Request(series_url, headers=HEADERS)
        html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')
        matches = re.findall(r'<a[^>]+href=["\'](https://animekhor\.org/[^"\']+)["\'][^>]*>(.*?)</a>', html)
        seen = set()
        for href, title in matches:
            if ('episode' in href or 'subtitles' in href) and href not in seen:
                clean_title = re.sub('<[^<]+?>', '', title).strip()
                episodes.append({"title": clean_title, "link": href})
                seen.add(href)
    except Exception as e:
        print(f"[ERROR] Gagal mengambil episode dari series: {e}")
    return episodes[:5]


def generate_youtube_metadata_ai(title: str, raw_desc: str = "", api_key: str = None) -> dict:
    """Generate Judul, Deskripsi, dan Tag YouTube SEO via Google Gemini AI."""
    clean_title = re.sub(r'\s*Subtitles\s*\[.*?\]', '', title, flags=re.I).strip()
    clean_title = re.sub(r'Episode\s*(\d+)', r'Ep \1', clean_title, flags=re.I)

    default_result = {
        "yt_title": f"{clean_title} Sub Indo Full HD",
        "yt_description": (
            f"Nonton & Download {clean_title} Subtitle Indonesia.\n\n"
            f"Jangan lupa Like, Comment, dan Subscribe untuk update episode terbaru setiap hari!\n\n"
            f"#donghua #anime #subindo #{re.sub(r'[^a-zA-Z0-9]', '', clean_title.split('Ep')[0])}"
        ),
        "tags": f"donghua, sub indo, anime terbaru, {clean_title}"
    }

    if not api_key:
        return default_result

    prompt = (
        f"Sebagai uploader YouTube Donghua/Anime profesional, buatkan judul YouTube yang menarik dan SEO friendly, "
        f"serta deskripsi YouTube singkat lengkap dengan hashtags untuk episode berikut:\n"
        f"Judul Asli: {title}\n"
        f"Sinopsis: {raw_desc}\n\n"
        f"Format balasan JSON murni tanpa markdown lain:\n"
        f'{{"yt_title": "...", "yt_description": "...", "tags": "..."}}'
    )

    try:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}]
        }).encode('utf-8')

        req = urllib.request.Request(endpoint, data=payload, headers={'Content-Type': 'application/json'})
        res = urllib.request.urlopen(req, timeout=15).read().decode('utf-8')
        data = json.loads(res)
        text_reply = data['candidates'][0]['content']['parts'][0]['text']

        json_match = re.search(r'\{.*\}', text_reply, re.DOTALL)
        if json_match:
            ai_data = json.loads(json_match.group(0))
            return {
                "yt_title": ai_data.get("yt_title", default_result["yt_title"]),
                "yt_description": ai_data.get("yt_description", default_result["yt_description"]),
                "tags": ai_data.get("tags", default_result["tags"])
            }
    except Exception as e:
        print(f"[WARN] AI generation gagal, menggunakan format default: {e}")

    return default_result


def send_telegram_msg(bot_token: str, chat_id: str, text: str, reply_markup: dict = None):
    """Kirim pesan Telegram standar."""
    send_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    req = urllib.request.Request(send_url, data=json.dumps(payload).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[ERROR] Gagal kirim Telegram: {e}")


def send_episode_alert(bot_token: str, chat_id: str, title: str, page_url: str,
                       video_url: str, yt_meta: dict):
    """Kirim alert episode baru lengkap dengan format YouTube & tombol unduh."""
    message_text = (
        f"🎬 <b>EPISODE BARU RILIS!</b>\n\n"
        f"📌 <b>Judul:</b> {title}\n\n"
        f"📺 <b>Rekomendasi Judul YouTube:</b>\n<code>{yt_meta['yt_title']}</code>\n\n"
        f"📝 <b>Deskripsi YouTube:</b>\n<pre>{yt_meta['yt_description']}</pre>\n\n"
        f"🏷️ <b>Tags:</b> <code>{yt_meta['tags']}</code>\n\n"
        f"⚡ <i>Tekan tombol di bawah untuk langsung download ke Seal di HP Anda!</i>"
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "📲 Buka di Seal (Download)", "url": f"https://junkfood02.github.io/Seal/?url={video_url}"},
            ],
            [
                {"text": "⬇️ Direct Video Link", "url": video_url},
                {"text": "🌐 Halaman Web", "url": page_url}
            ]
        ]
    }
    send_telegram_msg(bot_token, chat_id, message_text, reply_markup)


def check_rss_updates(bot_token: str, chat_id: str, gemini_key: str):
    """Mengecek RSS feed untuk episode yang baru rilis."""
    history_list = load_json(HISTORY_FILE, [])
    history = set(history_list)
    print(f"[*] Mengecek RSS update di {RSS_FEED_URL}...")

    try:
        req = urllib.request.Request(RSS_FEED_URL, headers=HEADERS)
        xml_data = urllib.request.urlopen(req, timeout=12).read()
        root = ET.fromstring(xml_data)
        items = root.findall('.//item')
    except Exception as e:
        print(f"[ERROR] Gagal membaca RSS feed: {e}")
        return

    new_count = 0
    for item in reversed(items):
        link = item.find('link').text.strip()
        title = item.find('title').text.strip()
        desc = item.find('description').text if item.find('description') is not None else ""

        if link in history:
            continue

        print(f"\n[NEW] Episode baru: {title}")
        video_url = extract_video_link(link)
        yt_meta = generate_youtube_metadata_ai(title, desc, gemini_key)
        send_episode_alert(bot_token, chat_id, title, link, video_url, yt_meta)

        history.add(link)
        new_count += 1

    save_json(HISTORY_FILE, list(history)[-100:])
    print(f"[*] Selesai. {new_count} episode baru dikirim.")


def process_telegram_commands(bot_token: str, gemini_key: str):
    """Membaca dan merespons pesan / komentar user di bot Telegram."""
    last_offset = load_json(BOT_OFFSET_FILE, 0)
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset={last_offset}&timeout=5"

    try:
        req = urllib.request.Request(url)
        res = urllib.request.urlopen(req, timeout=10).read().decode('utf-8')
        updates = json.loads(res).get("result", [])
    except Exception as e:
        print(f"[WARN] Gagal mengambil pesan Telegram: {e}")
        return

    for update in updates:
        update_id = update["update_id"]
        last_offset = max(last_offset, update_id + 1)
        msg = update.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id", ""))
        text = msg.get("text", "").strip()

        if not text or not chat_id:
            continue

        print(f"[USER COMMAND] Chat {chat_id}: {text}")

        # Perintah /start atau /help
        if text.startswith("/start") or text.startswith("/help"):
            welcome = (
                "👋 <b>Halo! Saya AnimeKhor Downloader Bot.</b>\n\n"
                "Fitur yang bisa Anda gunakan:\n"
                "🔍 <b>/cari &lt;judul&gt;</b> - Cari anime/donghua (contoh: <code>/cari apotheosis</code>)\n"
                "⬇️ <b>/download &lt;link&gt;</b> - Ambil link video Dailymotion langsung\n"
                "⚡ <b>Kirim Link Animekhor</b> - Kirim link halaman episode apa saja, bot akan otomatis mengubahnya jadi link download + teks YouTube siap upload!\n"
            )
            send_telegram_msg(bot_token, chat_id, welcome)

        # Perintah /cari <judul>
        elif text.startswith("/cari ") or text.startswith("/search "):
            query = text.split(" ", 1)[1].strip()
            send_telegram_msg(bot_token, chat_id, f"🔍 Mencari <b>{query}</b> di Animekhor...")
            results = search_animekhor(query)

            if not results:
                send_telegram_msg(bot_token, chat_id, f"❌ Tidak ditemukan hasil untuk: <b>{query}</b>")
            else:
                for res in results[:4]:
                    series_title = res["title"]
                    series_link = res["link"]
                    eps = get_series_episodes(series_link)

                    buttons = []
                    for ep in eps[:3]:
                        vid_link = extract_video_link(ep["link"])
                        buttons.append([
                            {"text": f"⬇️ {ep['title'][:25]}...", "url": vid_link}
                        ])

                    buttons.append([{"text": "🌐 Buka Halaman Series", "url": series_link}])
                    msg_series = f"📺 <b>{series_title}</b>\nLink: {series_link}\n\n<i>Pilih episode di bawah untuk download:</i>"
                    send_telegram_msg(bot_token, chat_id, msg_series, {"inline_keyboard": buttons})

        # Perintah /download <link> atau user langsung paste link
        elif text.startswith("http://") or text.startswith("https://") or text.startswith("/download "):
            page_url = text.replace("/download ", "").strip()
            send_telegram_msg(bot_token, chat_id, "⏳ Mengekstrak link video player...")

            video_url = extract_video_link(page_url)
            yt_meta = generate_youtube_metadata_ai(page_url.split("/")[-2].replace("-", " ").title(), "", gemini_key)

            reply_msg = (
                f"✅ <b>LINK VIDEO BERHASIL DIEKSTRAK!</b>\n\n"
                f"🔗 <b>Direct Link:</b>\n<code>{video_url}</code>\n\n"
                f"📺 <b>Rekomendasi Judul YouTube:</b>\n<code>{yt_meta['yt_title']}</code>\n\n"
                f"📝 <b>Deskripsi YouTube:</b>\n<pre>{yt_meta['yt_description']}</pre>\n\n"
                f"🏷️ <b>Tags:</b> <code>{yt_meta['tags']}</code>"
            )

            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "📲 Buka di Seal (Download)", "url": f"https://junkfood02.github.io/Seal/?url={video_url}"},
                    ],
                    [
                        {"text": "⬇️ Download Langsung", "url": video_url}
                    ]
                ]
            }
            send_telegram_msg(bot_token, chat_id, reply_msg, reply_markup)

    save_json(BOT_OFFSET_FILE, last_offset)


def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if not bot_token or not chat_id:
        print("[ERROR] TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID belum diatur!")
        sys.exit(1)

    # Cek mode polling bot atau notify biasa
    if "--bot" in sys.argv:
        print("[*] Menjalankan Bot Telegram Mode Realtime (Polling)...")
        while True:
            process_telegram_commands(bot_token, gemini_key)
            time.sleep(2)
    else:
        # Mode hybrid (default): jalankan pengecekan RSS + proses command user yang masuk
        check_rss_updates(bot_token, chat_id, gemini_key)
        process_telegram_commands(bot_token, gemini_key)


if __name__ == "__main__":
    main()
