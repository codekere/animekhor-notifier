# -*- coding: utf-8 -*-
"""
Universal Video Downloader
==========================
Script untuk mendownload video dari berbagai sumber/platform.
Mendukung URL embed (seperti geo.dailymotion.com), URL standar,
dan 1000+ situs lainnya melalui yt-dlp.

Penggunaan:
    python video_downloader.py <URL>
    python video_downloader.py <URL> --quality best/worst/720/1080
    python video_downloader.py <URL> --output "folder/nama_file"
    python video_downloader.py <URL> --list-formats
    python video_downloader.py <URL> --audio-only

Contoh:
    python video_downloader.py "https://geo.dailymotion.com/player.html?video=k3zIKWCodESUo7JvAKy"
    python video_downloader.py "https://www.youtube.com/watch?v=xxxxx" --quality 720
    python video_downloader.py "https://vimeo.com/123456" --audio-only
"""

import argparse
import os
import re
import sys
import time

# Pastikan stdout bisa handle semua karakter
import io
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

try:
    import yt_dlp
except ImportError:
    print("=" * 60)
    print("  ERROR: yt-dlp belum terinstall!")
    print("  Jalankan: pip install yt-dlp")
    print("  Jalankan juga: pip install curl_cffi")
    print("=" * 60)
    sys.exit(1)


# ────────────────────────────────────────────────────────────
# URL Normalizer - mengubah embed URL ke format yang dikenali
# ────────────────────────────────────────────────────────────

def normalize_url(url: str) -> str:
    """
    Mengubah embed/player URL ke format standar yang lebih mudah
    dikenali oleh yt-dlp extractor.
    """
    # Dailymotion geo embed -> dailymotion standar
    # https://geo.dailymotion.com/player.html?video=XXXXX
    match = re.search(r'geo\.dailymotion\.com/player\.html\?video=(\w+)', url)
    if match:
        video_id = match.group(1)
        normalized = f'https://www.dailymotion.com/video/{video_id}'
        print(f"[INFO] URL dinormalisasi: {normalized}")
        return normalized

    # Dailymotion embed -> dailymotion standar
    # https://www.dailymotion.com/embed/video/XXXXX
    match = re.search(r'dailymotion\.com/embed/video/(\w+)', url)
    if match:
        video_id = match.group(1)
        normalized = f'https://www.dailymotion.com/video/{video_id}'
        print(f"[INFO] URL dinormalisasi: {normalized}")
        return normalized

    # YouTube embed -> youtube standar
    # https://www.youtube.com/embed/XXXXX
    match = re.search(r'youtube\.com/embed/([\w-]+)', url)
    if match:
        video_id = match.group(1)
        normalized = f'https://www.youtube.com/watch?v={video_id}'
        print(f"[INFO] URL dinormalisasi: {normalized}")
        return normalized

    # YouTube short URL
    match = re.search(r'youtu\.be/([\w-]+)', url)
    if match:
        video_id = match.group(1)
        normalized = f'https://www.youtube.com/watch?v={video_id}'
        print(f"[INFO] URL dinormalisasi: {normalized}")
        return normalized

    # Vimeo embed
    match = re.search(r'player\.vimeo\.com/video/(\d+)', url)
    if match:
        video_id = match.group(1)
        normalized = f'https://vimeo.com/{video_id}'
        print(f"[INFO] URL dinormalisasi: {normalized}")
        return normalized

    # Facebook embed
    match = re.search(r'facebook\.com/plugins/video\.php\?href=(.+?)(&|$)', url)
    if match:
        from urllib.parse import unquote
        normalized = unquote(match.group(1))
        print(f"[INFO] URL dinormalisasi: {normalized}")
        return normalized

    # Animekhor or generic site with embedded player
    if 'animekhor.org' in url:
        try:
            import urllib.request
            print(f"[INFO] Mendeteksi URL Animekhor, mengekstrak video player...")
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': (
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/120.0.0.0 Safari/537.36'
                    ),
                    'Referer': 'https://animekhor.org/',
                }
            )
            html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')

            # 1. Cari embed dailymotion langsung di halaman
            dm_match = re.search(r'(?:https?:)?//(?:www\.|geo\.)?dailymotion\.com/(?:embed/video/|player\.html\?video=)([\w-]+)', html)
            if dm_match:
                video_id = dm_match.group(1)
                normalized = f'https://www.dailymotion.com/video/{video_id}'
                print(f"[INFO] Video Dailymotion berhasil diekstrak: {normalized}")
                return normalized

            # 2. Cari tag iframe video lainnya
            iframe_match = re.search(r'<iframe[^>]+src=["\']([^"\']*(?:dailymotion|embed|video|player)[^"\']*)["\']', html, re.I)
            if iframe_match:
                iframe_src = iframe_match.group(1)
                if iframe_src.startswith('//'):
                    iframe_src = 'https:' + iframe_src
                print(f"[INFO] Iframe video ditemukan: {iframe_src}")
                return normalize_url(iframe_src)

            print("[WARN] Tidak menemukan iframe video di halaman Animekhor ini.")
        except Exception as e:
            print(f"[WARN] Gagal mengambil halaman Animekhor: {e}")

    return url


# ────────────────────────────────────────────────────────────
# Progress Hook - menampilkan progress download
# ────────────────────────────────────────────────────────────

def progress_hook(d: dict):
    """Menampilkan progress download di terminal."""
    if d['status'] == 'downloading':
        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
        downloaded = d.get('downloaded_bytes', 0)
        speed = d.get('speed')
        eta = d.get('eta')

        if total > 0:
            percent = downloaded / total * 100
            total_mb = total / (1024 * 1024)
            downloaded_mb = downloaded / (1024 * 1024)
            bar_len = 30
            filled = int(bar_len * downloaded / total)
            bar = '#' * filled + '-' * (bar_len - filled)

            speed_str = ""
            if speed:
                if speed > 1024 * 1024:
                    speed_str = f" | {speed / (1024*1024):.1f} MB/s"
                else:
                    speed_str = f" | {speed / 1024:.0f} KB/s"

            eta_str = ""
            if eta:
                mins, secs = divmod(int(eta), 60)
                if mins > 0:
                    eta_str = f" | ETA {mins}m {secs}s"
                else:
                    eta_str = f" | ETA {secs}s"

            print(
                f"\r  [{bar}] {percent:5.1f}% "
                f"({downloaded_mb:.1f}/{total_mb:.1f} MB{speed_str}{eta_str})   ",
                end='', flush=True
            )
        else:
            downloaded_mb = downloaded / (1024 * 1024)
            print(f"\r  Downloading... {downloaded_mb:.1f} MB   ", end='', flush=True)

    elif d['status'] == 'finished':
        print(f"\n  [OK] Download selesai! Memproses file...")

    elif d['status'] == 'error':
        print(f"\n  [ERROR] Error saat download!")


# ────────────────────────────────────────────────────────────
# FFmpeg Check
# ────────────────────────────────────────────────────────────

def is_ffmpeg_available() -> bool:
    """Cek apakah ffmpeg tersedia di PATH."""
    import shutil
    return shutil.which('ffmpeg') is not None


# ────────────────────────────────────────────────────────────
# Format Selector - memilih kualitas video
# ────────────────────────────────────────────────────────────

def get_format_selector(quality: str, audio_only: bool) -> str:
    """Menentukan format selector berdasarkan pilihan kualitas."""
    has_ffmpeg = is_ffmpeg_available()

    if not has_ffmpeg:
        print("  [INFO] ffmpeg tidak ditemukan - download single format (tanpa merge)")
        print("  [INFO] Install ffmpeg untuk kualitas terbaik: winget install Gyan.FFmpeg")

    if audio_only:
        return 'bestaudio/best'

    if quality == 'best':
        if has_ffmpeg:
            return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
        else:
            return 'best[ext=mp4]/best'
    elif quality == 'worst':
        if has_ffmpeg:
            return 'worstvideo+worstaudio/worst'
        else:
            return 'worst'
    elif quality.isdigit():
        height = quality
        if has_ffmpeg:
            return (
                f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/'
                f'bestvideo[height<={height}]+bestaudio/'
                f'best[height<={height}]/best'
            )
        else:
            return f'best[height<={height}][ext=mp4]/best[height<={height}]/best'
    else:
        if has_ffmpeg:
            return 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
        else:
            return 'best[ext=mp4]/best'


# ────────────────────────────────────────────────────────────
# Core Download Functions
# ────────────────────────────────────────────────────────────

def list_formats(url: str):
    """Menampilkan daftar format/kualitas yang tersedia."""
    url = normalize_url(url)
    ydl_opts = {
        'listformats': True,
        'quiet': False,
    }
    print(f"\n{'='*60}")
    print(f"  Format yang tersedia untuk:")
    print(f"  {url}")
    print(f"{'='*60}\n")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def get_video_info(url: str) -> dict:
    """Mengambil informasi video tanpa mendownload."""
    url = normalize_url(url)
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def download_video(url: str, quality: str = 'best', output: str = None,
                   audio_only: bool = False, cookies_browser: str = None):
    """
    Download video dari URL yang diberikan.

    Args:
        url:             URL video (bisa embed URL)
        quality:         Kualitas video: best, worst, 720, 1080, dll.
        output:          Path output file (opsional)
        audio_only:      Jika True, hanya download audio
        cookies_browser: Nama browser untuk mengambil cookies (chrome, firefox, dll)
    """
    url = normalize_url(url)
    format_selector = get_format_selector(quality, audio_only)

    # Output template
    if output:
        outtmpl = output
        if not os.path.splitext(output)[1]:
            outtmpl += '.%(ext)s'
    else:
        # Default: simpan di folder 'downloads' dengan nama judul video
        download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
        os.makedirs(download_dir, exist_ok=True)
        outtmpl = os.path.join(download_dir, '%(title)s.%(ext)s')

    ydl_opts = {
        'format': format_selector,
        'outtmpl': outtmpl,
        'progress_hooks': [progress_hook],
        'merge_output_format': 'mp4' if (not audio_only and is_ffmpeg_available()) else None,
        'quiet': False,
        'no_warnings': False,
        'consoletitle': True,
        'retries': 5,
        'fragment_retries': 5,
        # Postprocessor untuk audio-only
        'postprocessors': [],
        # Header agar tidak diblokir
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
            'Referer': url,
        },
    }

    # Tambah cookies dari browser jika diminta
    if cookies_browser:
        ydl_opts['cookiesfrombrowser'] = (cookies_browser,)

    # Postprocessor untuk audio-only: convert ke mp3
    if audio_only:
        ydl_opts['postprocessors'].append({
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        })
        # Hapus merge_output_format untuk audio
        ydl_opts.pop('merge_output_format', None)

    # Tampilkan info sebelum download
    print(f"\n{'='*60}")
    print(f"  Universal Video Downloader")
    print(f"{'='*60}")
    print(f"  URL     : {url}")
    print(f"  Kualitas: {quality}")
    print(f"  Mode    : {'Audio Only (MP3)' if audio_only else 'Video (MP4)'}")

    try:
        # Ambil info dulu
        print(f"\n  Mengambil informasi video...")
        info_opts = {**ydl_opts, 'skip_download': True, 'quiet': True, 'no_warnings': True}
        # Hapus progress hooks untuk info
        info_opts.pop('progress_hooks', None)

        with yt_dlp.YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if info:
            title = info.get('title', 'Tidak diketahui')
            duration = info.get('duration')
            uploader = info.get('uploader', 'Tidak diketahui')
            ext = info.get('ext', 'mp4')

            print(f"  Judul   : {title}")
            print(f"  Uploader: {uploader}")
            if duration:
                mins, secs = divmod(int(duration), 60)
                hours, mins = divmod(mins, 60)
                if hours > 0:
                    print(f"  Durasi  : {hours}j {mins}m {secs}d")
                else:
                    print(f"  Durasi  : {mins}m {secs}d")
        print(f"{'='*60}")

    except Exception:
        print(f"  (Tidak bisa mengambil info, langsung download...)")
        print(f"{'='*60}")

    # Mulai download
    print(f"\n  Memulai download...\n")
    start_time = time.time()

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.download([url])

        elapsed = time.time() - start_time
        mins, secs = divmod(int(elapsed), 60)

        print(f"\n{'='*60}")
        if mins > 0:
            print(f"  [OK] Selesai dalam {mins}m {secs}d")
        else:
            print(f"  [OK] Selesai dalam {secs} detik")
        print(f"  File tersimpan di folder: {os.path.dirname(outtmpl)}")
        print(f"{'='*60}\n")
        return True

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        print(f"\n{'='*60}")
        print(f"  [GAGAL] Gagal mendownload video!")
        print(f"  Error: {error_msg}")

        # Saran troubleshooting
        if 'Unsupported URL' in error_msg:
            print(f"\n  Saran:")
            print(f"  - Pastikan URL valid dan video masih tersedia")
            print(f"  - Coba update yt-dlp: pip install -U yt-dlp")
        elif '403' in error_msg or 'Forbidden' in error_msg:
            print(f"\n  Saran:")
            print(f"  - Video mungkin memerlukan login")
            print(f"  - Coba dengan cookies: --cookies-browser chrome")
        elif 'Private' in error_msg or 'private' in error_msg:
            print(f"\n  Saran:")
            print(f"  - Video bersifat private, perlu login")
            print(f"  - Gunakan: --cookies-browser chrome")

        print(f"{'='*60}\n")
        return False

    except Exception as e:
        print(f"\n  [ERROR] Error tak terduga: {e}")
        return False


# ────────────────────────────────────────────────────────────
# CLI Interface
# ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Universal Video Downloader - Download video dari berbagai platform',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  %(prog)s "https://geo.dailymotion.com/player.html?video=k3zIKWCodESUo7JvAKy"
  %(prog)s "https://www.youtube.com/watch?v=xxxxx" --quality 720
  %(prog)s "https://vimeo.com/123456" --audio-only
  %(prog)s "URL" --list-formats
  %(prog)s "URL" --cookies-browser chrome
        """
    )

    parser.add_argument(
        'url',
        help='URL video yang akan didownload (mendukung embed URL)'
    )
    parser.add_argument(
        '--quality', '-q',
        default='best',
        help='Kualitas video: best, worst, 720, 1080, 480, dll. (default: best)'
    )
    parser.add_argument(
        '--output', '-o',
        default=None,
        help='Path output file (default: downloads/<judul_video>.mp4)'
    )
    parser.add_argument(
        '--audio-only', '-a',
        action='store_true',
        help='Download audio saja (format MP3)'
    )
    parser.add_argument(
        '--list-formats', '-F',
        action='store_true',
        help='Tampilkan daftar format/kualitas yang tersedia'
    )
    parser.add_argument(
        '--cookies-browser', '-c',
        default=None,
        choices=['chrome', 'firefox', 'edge', 'opera', 'brave', 'vivaldi', 'safari'],
        help='Ambil cookies dari browser (untuk video yang memerlukan login)'
    )

    args = parser.parse_args()

    if args.list_formats:
        list_formats(args.url)
    else:
        download_video(
            url=args.url,
            quality=args.quality,
            output=args.output,
            audio_only=args.audio_only,
            cookies_browser=args.cookies_browser,
        )


if __name__ == '__main__':
    main()
