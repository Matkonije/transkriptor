import os
import uuid
import shutil
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp

ALLOWED_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".wav", ".webm", ".ogg", ".flac", ".opus", ".mpeg"}
MAX_FILE_SIZE_MB = 200

# ── Backend ────────────────────────────────────────────────────────────────────
BACKEND = os.getenv("BACKEND", "local")

if BACKEND == "local":
    from faster_whisper import WhisperModel
    MODEL_SIZE = os.getenv("WHISPER_MODEL", "small")
    print(f"[local] Učitavanje Whisper modela '{MODEL_SIZE}'...")
    whisper_model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    print("[local] Model spreman!")

elif BACKEND == "api":
    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Nedostaje OPENAI_API_KEY environment variable!")
    openai_client = OpenAI(api_key=api_key)
    print("[api] OpenAI Whisper API spreman.")

else:
    raise RuntimeError(f"Nepoznat BACKEND: '{BACKEND}'. Koristi 'local' ili 'api'.")

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(title="Transkriptor")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs = {}


class TranscribeRequest(BaseModel):
    url: str


# ── Transkripcija ──────────────────────────────────────────────────────────────

def download_audio(url: str, output_path: str) -> dict:
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "64",
        }],
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return {"title": info.get("title", "Nepoznato"), "duration": info.get("duration", 0)}


def transcribe_local(audio_file: str) -> tuple[str, list, str]:
    segments_iter, meta = whisper_model.transcribe(
        audio_file,
        beam_size=5,
        language=None,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )
    parts, texts = [], []
    for seg in segments_iter:
        text = seg.text.strip()
        if text:
            parts.append({"start": round(seg.start, 1), "end": round(seg.end, 1), "text": text})
            texts.append(text)
    return " ".join(texts), parts, meta.language


def transcribe_api(audio_file: str) -> tuple[str, list, str]:
    with open(audio_file, "rb") as f:
        result = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
        )
    parts = []
    if hasattr(result, "segments") and result.segments:
        for seg in result.segments:
            parts.append({
                "start": round(seg.get("start", 0), 1),
                "end": round(seg.get("end", 0), 1),
                "text": seg.get("text", "").strip(),
            })
    return result.text, parts, getattr(result, "language", "")


def _run_transcription(job_id: str, audio_path: str):
    """Zajednička logika transkripcije za YouTube i file upload."""
    try:
        jobs[job_id]["step"] = f"Transkripcija [{BACKEND}]..."
        if BACKEND == "local":
            full_text, segments, language = transcribe_local(audio_path)
        else:
            full_text, segments, language = transcribe_api(audio_path)

        jobs[job_id].update({
            "status": "done",
            "transcript": full_text,
            "segments": segments,
            "language": language,
            "backend": BACKEND,
            "step": None,
        })
    except Exception as e:
        jobs[job_id].update({"status": "error", "error": str(e), "step": None})
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


def process_video(job_id: str, url: str):
    audio_path = f"/tmp/{job_id}"
    audio_file = audio_path + ".mp3"
    try:
        jobs[job_id]["step"] = "Preuzimanje audia s YouTubea..."
        info = download_audio(url, audio_path)
        jobs[job_id].update({"title": info["title"], "duration": info["duration"]})
        _run_transcription(job_id, audio_file)
    except Exception as e:
        jobs[job_id].update({"status": "error", "error": str(e), "step": None})
        if os.path.exists(audio_file):
            os.remove(audio_file)


def process_audio_file(job_id: str, audio_path: str):
    _run_transcription(job_id, audio_path)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.post("/transcribe")
async def transcribe(req: TranscribeRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "processing", "title": None, "step": "Pokretanje..."}
    background_tasks.add_task(process_video, job_id, req.url)
    return {"job_id": job_id}


@app.post("/transcribe-file")
async def transcribe_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format '{ext}' nije podržan. Koristi: mp3, mp4, m4a, wav, webm, ogg, flac"
        )

    job_id = str(uuid.uuid4())
    audio_path = f"/tmp/{job_id}{ext}"

    with open(audio_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        os.remove(audio_path)
        raise HTTPException(status_code=400, detail=f"Fajl je prevelik ({size_mb:.0f}MB). Maksimum je {MAX_FILE_SIZE_MB}MB.")

    jobs[job_id] = {"status": "processing", "title": file.filename, "step": "Priprema..."}
    background_tasks.add_task(process_audio_file, job_id, audio_path)
    return {"job_id": job_id}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


app.mount("/", StaticFiles(directory="static", html=True), name="static")
