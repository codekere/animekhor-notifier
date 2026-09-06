# -*- coding: utf-8 -*-
"""
Video Watermark Tool (Menyamarkan / Memburamkan Watermark Bawaan)
================================================================
Khusus untuk menghapus watermark Animekhor di pojok kiri atas
atau menimpa watermark dengan logo channel YouTube Anda sendiri.

Penggunaan:
  1. Hapus watermark Animekhor otomatis (pojok kiri atas):
     python watermark_tool.py "downloads/video.mp4" --blur-animekhor

  2. Memburamkan (blur) area khusus secara manual:
     python watermark_tool.py "downloads/video.mp4" --blur-box "2,2,170,48"
     (format: x,y,width,height)

  3. Menimpa dengan logo sendiri:
     python watermark_tool.py "downloads/video.mp4" --logo "my_logo.png" --pos top-right
"""

import argparse
import subprocess
import shutil
import os
import sys
import glob

POSITIONS = {
    'top-right': 'W-w-20:20',
    'top-left': '20:20',
    'bottom-right': 'W-w-20:H-h-20',
    'bottom-left': '20:H-h-20',
    'center': '(W-w)/2:(H-h)/2'
}

# Koordinat persis watermark AnimeKhor.org (Pojok Kiri Atas)
ANIMEKHOR_WM_BOX = "2,2,170,48"


def get_ffmpeg_path() -> str:
    """Mencari executable ffmpeg di PATH atau di folder instalasi WinGet."""
    path = shutil.which('ffmpeg')
    if path:
        return path

    # Cek folder instalasi WinGet jika belum ada di PATH
    winget_pattern = os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\*\bin\ffmpeg.exe"
    )
    matches = glob.glob(winget_pattern)
    if matches and os.path.exists(matches[0]):
        return matches[0]

    print("[ERROR] FFmpeg tidak ditemukan!")
    print("Silakan install FFmpeg terlebih dahulu: winget install Gyan.FFmpeg")
    sys.exit(1)


def process_watermark(input_video: str, logo_path: str = None, pos: str = 'top-right',
                      blur_box: str = None, blur_animekhor: bool = False, output_video: str = None):
    ffmpeg_bin = get_ffmpeg_path()

    if not os.path.exists(input_video):
        print(f"[ERROR] File video tidak ditemukan: {input_video}")
        return

    if not output_video:
        base, ext = os.path.splitext(input_video)
        output_video = f"{base}_clean{ext}"

    cmd = [ffmpeg_bin, '-y', '-i', input_video]

    if blur_animekhor:
        blur_box = ANIMEKHOR_WM_BOX
        print(f"[*] Menghapus watermark AnimeKhor di pojok kiri atas (x=2, y=2, w=170, h=48)...")

    if blur_box:
        try:
            x, y, w, h = blur_box.split(',')
        except Exception:
            print("[ERROR] Format --blur-box salah! Gunakan format x,y,w,h (misal: 2,2,170,48)")
            return

        cmd.extend([
            '-vf', f'delogo=x={x.strip()}:y={y.strip()}:w={w.strip()}:h={h.strip()}',
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '18',
            '-c:a', 'copy',
            output_video
        ])
        print(f"[*] Memproses penghapusan watermark pada area x={x}, y={y}, w={w}, h={h}...")

    elif logo_path:
        if not os.path.exists(logo_path):
            print(f"[ERROR] File logo tidak ditemukan: {logo_path}")
            return
        overlay_coords = POSITIONS.get(pos, 'W-w-20:20')
        cmd.extend([
            '-i', logo_path,
            '-filter_complex', f'[0:v][1:v]overlay={overlay_coords}[v]',
            '-map', '[v]',
            '-map', '0:a?',
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '18',
            '-c:a', 'copy',
            output_video
        ])
        print(f"[*] Menimpa watermark dengan logo: {logo_path} pada posisi {pos}...")

    else:
        print("[INFO] Tidak ada opsi dipilih. Menjalankan penghapusan watermark AnimeKhor otomatis...")
        return process_watermark(input_video, blur_animekhor=True, output_video=output_video)

    try:
        subprocess.run(cmd, check=True)
        print(f"\n[OK] Selesai! Video bersih tersimpan di: {output_video}")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] FFmpeg gagal memproses video: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Watermark Tool: Hapus / Buramkan Watermark AnimeKhor atau Timpa Logo Channel"
    )
    parser.add_argument('video', help='Path file video input')
    parser.add_argument('--blur-animekhor', '-ba', action='store_true',
                        help='Otomatis hapus/buramkan watermark Animekhor di pojok kiri atas')
    parser.add_argument('--blur-box', '-b',
                        help='Koordinat kustom blur watermark: x,y,width,height (contoh: 2,2,170,48)')
    parser.add_argument('--logo', '-l', help='Path ke file logo transparan Anda (.png)')
    parser.add_argument('--pos', '-p', default='top-right', choices=list(POSITIONS.keys()),
                        help='Posisi logo Anda (default: top-right)')
    parser.add_argument('--output', '-o', help='Nama file output')

    args = parser.parse_args()
    process_watermark(
        args.video,
        logo_path=args.logo,
        pos=args.pos,
        blur_box=args.blur_box,
        blur_animekhor=args.blur_animekhor,
        output_video=args.output
    )


if __name__ == '__main__':
    main()
