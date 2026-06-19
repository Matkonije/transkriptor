"""
Transkriptor server - minimalan backend koji prima audio fajlove i
transkribira ih preko OpenAI Whisper API-ja.

Ovaj server NE skida YouTube videe (to radi lokalna skripta kod kolega,
da se izbjegne YouTube bot detection na cloud serverima). Server samo
čuva OpenAI API key i prosljeđuje transkripcijske requeste - key nikad
ne napušta server.
"""

import os
import uuid
import shutil
from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

ALLOWED_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".wav", ".webm", ".ogg", ".flac", ".opus", ".mpeg"}
MAX_FILE_SIZE_MB = 25  # OpenAI Whisper API limit

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("Nedostaje OPENAI_API_KEY environment variable!")
client = OpenAI(api_key=api_key)

app = FastAPI(title="Transkriptor server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs = {}


def transcribe(audio_path: str) -> dict:
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
        )
    segments = []
    if hasattr(result, "segments") and result.segments:
        for seg in result.segments:
            segments.append({
                "start": round(getattr(seg, "start", 0), 1),
                "end": round(getattr(seg, "end", 0), 1),
                "text": getattr(seg, "text", "").strip(),
            })
    return {
        "text": result.text,
        "language": getattr(result, "language", "nepoznat"),
        "segments": segments,
    }


def process_job(job_id: str, audio_path: str):
    try:
        jobs[job_id]["step"] = "Transkripcija u tijeku..."
        result = transcribe(audio_path)
        jobs[job_id].update({
            "status": "done",
            "transcript": result["text"],
            "language": result["language"],
            "segments": result["segments"],
            "step": None,
        })
    except Exception as e:
        jobs[job_id].update({"status": "error", "error": str(e), "step": None})
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)


@app.post("/transcribe-file")
async def transcribe_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Format '{ext}' nije podržan.")

    job_id = str(uuid.uuid4())
    audio_path = f"/tmp/{job_id}{ext}"

    with open(audio_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        os.remove(audio_path)
        raise HTTPException(status_code=400, detail=f"Fajl je prevelik ({size_mb:.0f}MB). Maksimum {MAX_FILE_SIZE_MB}MB.")

    jobs[job_id] = {"status": "processing", "step": "Priprema..."}
    background_tasks.add_task(process_job, job_id, audio_path)
    return {"job_id": job_id}


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


@app.get("/")
async def root():
    return {"status": "ok", "service": "transkriptor-server"}
