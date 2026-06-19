#!/usr/bin/env python3
"""
Transkriptiraj - samostalna lokalna skripta za YouTube -> transkript.

Skida audio s YouTubea lokalno (zato YouTube ne blokira kao na cloud serverima)
i šalje ga direktno na OpenAI Whisper API za transkripciju. Nema potrebe za
posebnim serverom.

Korištenje:
    python transkriptiraj.py "https://youtube.com/watch?v=..."

Prije prvog korištenja postavi OpenAI API key:
    Windows:      set OPENAI_API_KEY=sk-...
    Mac/Linux:    export OPENAI_API_KEY=sk-...
"""

import sys
import os
import tempfile

import yt_dlp
import imageio_ffmpeg
from openai import OpenAI

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()


def get_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Nedostaje OPENAI_API_KEY environment varijabla.")
        print()
        print("Postavi je ovako pa pokreni skriptu opet:")
        print("  Windows:    set OPENAI_API_KEY=sk-tvoj-kljuc")
        print("  Mac/Linux:  export OPENAI_API_KEY=sk-tvoj-kljuc")
        sys.exit(1)
    return OpenAI(api_key=api_key)


def download_audio(url: str, output_dir: str) -> tuple[str, str]:
    """Skida audio s YouTubea lokalno. Vraća (putanja_do_fajla, naslov)."""
    output_template = os.path.join(output_dir, "audio")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "ffmpeg_location": FFMPEG_PATH,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "64",
        }],
        "quiet": True,
        "no_warnings": True,
    }

    print("📥 Skidanje audia s YouTubea...")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "Nepoznato")

    audio_path = output_template + ".mp3"
    if not os.path.exists(audio_path):
        raise FileNotFoundError("Audio fajl nije pronađen nakon skidanja.")

    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    print(f"✅ Skinuto: '{title}' ({size_mb:.1f} MB)")
    return audio_path, title


def transcribe(client: OpenAI, audio_path: str) -> dict:
    """Šalje audio na OpenAI Whisper API i vraća rezultat."""
    print("🧠 Transkripcija preko OpenAI API-ja...")

    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
        )

    return {
        "text": result.text,
        "language": getattr(result, "language", "nepoznat"),
        "segments": getattr(result, "segments", []) or [],
    }


def save_transcript(title: str, text: str) -> str:
    """Sprema transkript u .txt fajl, vraća putanju."""
    safe_name = "".join(c for c in title if c.isalnum() or c in " -_").strip()
    safe_name = safe_name.replace(" ", "_").lower()[:60] or "transkript"
    output_path = f"{safe_name}.txt"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    return output_path


def main():
    if len(sys.argv) < 2:
        print("Korištenje: python transkriptiraj.py <youtube_link>")
        sys.exit(1)

    url = sys.argv[1]
    client = get_client()

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            audio_path, title = download_audio(url, tmp_dir)
            result = transcribe(client, audio_path)
            output_file = save_transcript(title, result["text"])

            print()
            print("=" * 50)
            print(f"✅ GOTOVO — transkript spremljen u: {output_file}")
            print(f"   Jezik: {result['language']}")
            print(f"   Segmenata: {len(result['segments'])}")
            print("=" * 50)

        except Exception as e:
            print(f"\n❌ Greška: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
