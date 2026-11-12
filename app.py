from __future__ import annotations

import json
import re
import shutil
import subprocess
import uuid
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from romanizer import romanize

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "work"
WORK.mkdir(exist_ok=True)
app = FastAPI(title="AutoCaption", version="0.1.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
VIDEO = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus"}


@lru_cache(maxsize=2)
def load_model(model_id: str):
    from faster_whisper import WhisperModel
    return WhisperModel(model_id, device="cpu", compute_type="int8")


def timestamp(seconds: float, ass: bool = False) -> str:
    centis = round(max(0, seconds) * 100)
    h, rem = divmod(centis, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}" if ass else f"{h:02}:{m:02}:{s:02},{cs:02}"


def make_captions(words: list[dict], max_words: int = 5) -> list[dict]:
    out: list[dict] = []
    batch: list[dict] = []
    for word in words:
        if batch and (len(batch) >= max_words or word["start"] - batch[-1]["end"] > 0.6):
            out.append({"start": batch[0]["start"], "end": batch[-1]["end"], "text": " ".join(w["text"].strip() for w in batch)})
            batch = []
        batch.append(word)
        if re.search(r"[.!?؟]$", word["text"].strip()):
            out.append({"start": batch[0]["start"], "end": batch[-1]["end"], "text": " ".join(w["text"].strip() for w in batch)})
            batch = []
    if batch:
        out.append({"start": batch[0]["start"], "end": batch[-1]["end"], "text": " ".join(w["text"].strip() for w in batch)})
    return out


@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "ffmpeg": shutil.which("ffmpeg") is not None}


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...), language: str = Form("auto"), mode: str = Form("hinglish")):
    suffix = Path(file.filename or "upload.mp4").suffix.lower()
    if suffix not in VIDEO | AUDIO:
        raise HTTPException(415, "Choose an audio or video file supported by FFmpeg.")
    if not shutil.which("ffmpeg"):
        raise HTTPException(503, "FFmpeg is required and must be available on PATH.")
    pid = uuid.uuid4().hex[:12]
    folder = WORK / pid
    folder.mkdir()
    source = folder / ("source" + suffix)
    source.write_bytes(await file.read())
    wav = folder / "audio.wav"
    args = ["ffmpeg", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", str(wav)]
    result = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise HTTPException(422, "Could not extract audio: " + result.stderr[-700:])
    if mode == "urdu":
        model_id = "small"
        whisper_language = "ur" if language == "auto" else language
    else:
        model_id = "MSpider3/whisper-hindi2hinglish-swift-ct2"
        whisper_language = "hi" if language == "auto" else language
    try:
        model = load_model(model_id)
        segments, info = model.transcribe(str(wav), language=whisper_language, word_timestamps=True, vad_filter=True, beam_size=3)
        words: list[dict] = []
        fallback: list[dict] = []
        for segment in segments:
            fallback.append({"start": segment.start, "end": segment.end, "text": segment.text.strip()})
            if segment.words:
                words.extend({"start": w.start, "end": w.end, "text": w.word.strip()} for w in segment.words if w.word.strip())
        captions = make_captions(words) if words else fallback
        if mode == "urdu":
            for caption in captions:
                caption["text"] = romanize(caption["text"])
    except Exception as exc:
        raise HTTPException(500, f"Transcription failed: {exc}") from exc
    project = {"id": pid, "name": file.filename, "source": source.name, "language": info.language, "duration": info.duration, "captions": captions}
    (folder / "project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    return project


def render_ass(captions: list[dict], preset: str) -> str:
    colors = {"gold": "&H0000C8FF", "mint": "&H0070E0B0", "white": "&H00FFFFFF"}
    color = colors.get(preset, colors["white"])
    rows = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "ScaledBorderAndShadow: yes", "", "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding", f"Style: Default,Arial,70,{color},&H000000FF,&H00101010,&H80000000,-1,0,1,4,1,2,70,70,180,1", "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for c in captions:
        text = c["text"].replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")
        rows.append(f"Dialogue: 0,{timestamp(c['start'], True)},{timestamp(c['end'], True)},Default,,0,0,0,,{text}")
    return "\n".join(rows) + "\n"


@app.post("/api/export/{pid}/{kind}")
def export(pid: str, kind: str, payload: dict):
    if not re.fullmatch(r"[a-f0-9]{12}", pid):
        raise HTTPException(404, "Project not found")
    folder = WORK / pid
    project_file = folder / "project.json"
    if not project_file.exists():
        raise HTTPException(404, "Project not found")
    captions = payload.get("captions", [])
    if not captions:
        raise HTTPException(400, "There are no captions to export")
    stem = Path(json.loads(project_file.read_text(encoding="utf-8"))["name"]).stem
    if kind == "srt":
        path = folder / f"{stem}.srt"
        path.write_text("\n\n".join(f"{i}\n{timestamp(c['start'])} --> {timestamp(c['end'])}\n{c['text']}" for i, c in enumerate(captions, 1)) + "\n", encoding="utf-8-sig")
        return FileResponse(path, filename=path.name)
    ass = folder / f"{stem}.ass"
    ass.write_text(render_ass(captions, payload.get("preset", "white")), encoding="utf-8-sig")
    if kind == "ass":
        return FileResponse(ass, filename=ass.name)
    if kind != "mp4":
        raise HTTPException(400, "Export kind must be srt, ass, or mp4")
    source = folder / json.loads(project_file.read_text(encoding="utf-8"))["source"]
    if source.suffix.lower() not in VIDEO:
        raise HTTPException(400, "Burned MP4 export requires a video input")
    output = folder / f"{stem}.captioned.mp4"
    ass_filter = str(ass.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    result = subprocess.run(["ffmpeg", "-y", "-i", str(source), "-vf", f"ass='{ass_filter}'", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", str(output)], capture_output=True, text=True, timeout=1800)
    if result.returncode:
        raise HTTPException(500, "FFmpeg burn-in failed: " + result.stderr[-900:])
    return FileResponse(output, filename=output.name)
