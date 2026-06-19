#!/usr/bin/env python3
"""
Transkriptiraj - lokalna skripta za YouTube -> transkript.

Skida audio s YouTubea lokalno (zato YouTube ne blokira kao na cloud
serverima) i uploada ga na Transkriptor server koji radi transkripciju
preko OpenAI Whisper API-ja. Nikakav API key se ne koristi lokalno -
sve to čuva server.

Korištenje:
    python3 transkriptiraj.py "https://youtube.com/watch?v=..."
"""

import sys
import os
import argparse
import tempfile
import time

import requests
import yt_dlp
import imageio_ffmpeg

# Zamijeni s URL-om svog Render servisa
SERVER_URL = "https://transkriptor-u5kp.onrender.com"

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "transkripti")


def download_audio(url: str, output_dir: str) -> tuple[str, str]:
    """Skida audio s YouTubea lokalno. Vraća (putanja_do_fajla, naslov)."""
    output_template = os.path.join(output_dir, "audio")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "ffmpeg_location": FFMPEG_PATH,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "64",
        }],
        "quiet": True,
        "no_warnings": True,
    }

    print("Skidanje audia s YouTubea...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "Nepoznato")

    audio_path = output_template + ".mp3"
    if not os.path.exists(audio_path):
        raise FileNotFoundError("Audio fajl nije pronađen nakon skidanja.")

    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"Skinuto: '{title}' ({size_mb:.1f} MB)")
    return audio_path, title


def upload_and_transcribe(audio_path: str) -> dict:
    """Uploada audio na server i čeka rezultat transkripcije."""
    print("Slanje na server...")

    with open(audio_path, "rb") as f:
        files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
        response = requests.post(f"{SERVER_URL}/transcribe-file", files=files, timeout=120)

    if not response.ok:
        raise RuntimeError(f"Server greška ({response.status_code}): {response.text}")

    job_id = response.json()["job_id"]
    print("Transkripcija u tijeku...")

    last_step = None
    while True:
        time.sleep(2)
        status_res = requests.get(f"{SERVER_URL}/status/{job_id}", timeout=30)
        data = status_res.json()

        if data.get("step") and data["step"] != last_step:
            print(f"   {data['step']}")
            last_step = data["step"]

        if data["status"] == "done":
            return data
        if data["status"] == "error":
            raise RuntimeError(f"Greška u transkripciji: {data.get('error')}")


def save_transcript(title: str, text: str, output_dir: str) -> str:
    """Sprema transkript u .txt fajl, vraća punu (apsolutnu) putanju."""
    os.makedirs(output_dir, exist_ok=True)

    safe_name = "".join(c for c in title if c.isalnum() or c in " -_").strip()
    safe_name = safe_name.replace(" ", "_").lower()[:60] or "transkript"
    output_path = os.path.join(output_dir, f"{safe_name}.txt")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    return os.path.abspath(output_path)


def main():
    parser = argparse.ArgumentParser(description="Transkribiraj YouTube video preko Transkriptor servera.")
    parser.add_argument("url", help="YouTube link")
    parser.add_argument(
        "-o", "--output",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Folder za spremanje transkripta (default: {DEFAULT_OUTPUT_DIR})"
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            audio_path, title = download_audio(args.url, tmp_dir)
            result = upload_and_transcribe(audio_path)
            output_path = save_transcript(title, result["transcript"], args.output)

            print()
            print("=" * 60)
            print("GOTOVO")
            print(f"   Transkript: {output_path}")
            print(f"   Jezik: {result.get('language', 'nepoznat')}")
            print(f"   Segmenata: {len(result.get('segments', []))}")
            print("=" * 60)

        except Exception as e:
            print(f"\nGreška: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
