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
app = FastAPI(title="Lafz Studio", version="0.2.0")
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


def pack_words(batch: list[dict]) -> dict:
    return {
        "start": batch[0]["start"], "end": batch[-1]["end"],
        "text": " ".join(w["text"].strip() for w in batch),
        "words": [{"start": w["start"], "end": w["end"], "text": w["text"].strip()} for w in batch],
    }


def make_captions(words: list[dict], max_words: int = 5) -> list[dict]:
    out: list[dict] = []
    batch: list[dict] = []
    for word in words:
        if batch and (len(batch) >= max_words or word["start"] - batch[-1]["end"] > 0.6):
            out.append(pack_words(batch))
            batch = []
        batch.append(word)
        if re.search(r"[.!?؟]$", word["text"].strip()):
            out.append(pack_words(batch))
            batch = []
    if batch:
        out.append(pack_words(batch))
    return out


@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "ffmpeg": shutil.which("ffmpeg") is not None}


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...), language: str = Form("auto"), mode: str = Form("hinglish"), enhance_audio: bool = Form(False), enhancement: str = Form("gentle")):
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
    args = ["ffmpeg", "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "48000", str(wav)]
    result = subprocess.run(args, capture_output=True, text=True, timeout=600)
    if result.returncode:
        raise HTTPException(422, "Could not extract audio: " + result.stderr[-700:])
    if enhance_audio:
        enhanced = folder / "enhanced.wav"
        filter_chain = enhancement_filter(enhancement)
        cleaned = subprocess.run(["ffmpeg", "-y", "-i", str(wav), "-af", filter_chain, "-ar", "48000", str(enhanced)], capture_output=True, text=True, timeout=600)
        if cleaned.returncode:
            raise HTTPException(500, "Audio cleanup failed: " + cleaned.stderr[-700:])
        wav = enhanced
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
        audio_duration = float(info.duration or 0)
        for segment in segments:
            if segment.start < audio_duration and segment.end > segment.start:
                fallback.append({"start": segment.start, "end": min(segment.end, audio_duration), "text": segment.text.strip()})
            if segment.words:
                words.extend(
                    {"start": float(w.start), "end": min(float(w.end), audio_duration), "text": w.word.strip()}
                    for w in segment.words
                    if w.word.strip() and w.start < audio_duration and w.end > w.start
                )
        captions = make_captions(words) if words else fallback
        if mode == "urdu":
            for caption in captions:
                caption["text"] = romanize(caption["text"])
                for word in caption.get("words", []):
                    word["text"] = romanize(word["text"])
    except Exception as exc:
        raise HTTPException(500, f"Transcription failed: {exc}") from exc
    project = {"id": pid, "name": file.filename, "source": source.name, "enhanced_audio": wav.name if enhance_audio else None, "language": info.language, "duration": info.duration, "captions": captions}
    (folder / "project.json").write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    return project


PRESETS = {
    "classic": {"font": "Arial", "size": 62, "primary": "&H00FFFFFF", "secondary": "&H00FFFFFF", "outline": "&H00101010", "border": 3, "shadow": 1, "bold": 0, "align": 2, "margin": 155, "mode": "line"},
    "hormozi": {"font": "Arial", "size": 76, "primary": "&H0000DFFF", "secondary": "&H0000DFFF", "outline": "&H00000000", "border": 5, "shadow": 2, "bold": 1, "align": 2, "margin": 300, "mode": "pop"},
    "karaoke": {"font": "Arial", "size": 68, "primary": "&H00FFFFFF", "secondary": "&H0000E7FF", "outline": "&H00101010", "border": 4, "shadow": 1, "bold": 1, "align": 2, "margin": 175, "mode": "karaoke"},
    "boxed": {"font": "Arial", "size": 60, "primary": "&H00FFFFFF", "secondary": "&H00FFFFFF", "outline": "&H990D1117", "border": 1, "shadow": 0, "bold": 1, "align": 2, "margin": 155, "mode": "box"},
    "neon": {"font": "Arial", "size": 68, "primary": "&H00F6D7FF", "secondary": "&H00F6D7FF", "outline": "&H00D51FFF", "border": 3, "shadow": 2, "bold": 1, "align": 2, "margin": 180, "mode": "line"},
    "editorial": {"font": "Georgia", "size": 54, "primary": "&H00FFFFFF", "secondary": "&H00FFFFFF", "outline": "&H99000000", "border": 1, "shadow": 0, "bold": 0, "align": 2, "margin": 170, "mode": "line"},
    "minimal": {"font": "Arial", "size": 48, "primary": "&H00FFFFFF", "secondary": "&H00FFFFFF", "outline": "&H99000000", "border": 1, "shadow": 0, "bold": 0, "align": 2, "margin": 115, "mode": "line"},
    "wordpop": {"font": "Arial", "size": 76, "primary": "&H00FFFFFF", "secondary": "&H0000B7FF", "outline": "&H00101010", "border": 4, "shadow": 1, "bold": 1, "align": 2, "margin": 300, "mode": "pop"},
    "mint": {"font": "Arial", "size": 68, "primary": "&H00FFFFFF", "secondary": "&H0070E0B0", "outline": "&H00101010", "border": 4, "shadow": 1, "bold": 1, "align": 2, "margin": 175, "mode": "karaoke"},
}


def render_ass(captions: list[dict], preset: str, behind_person: bool = False) -> str:
    style = PRESETS.get(preset, PRESETS["classic"])
    rows = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "ScaledBorderAndShadow: yes", "", "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding", f"Style: Default,{style['font']},{style['size']},{style['primary']},{style['secondary']},{style['outline']},&H80000000,{style['bold']},0,{2 if style['mode']=='box' else 1},{style['border']},{style['shadow']},{style['align']},60,60,{style['margin']},1", "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for c in captions:
        text = c["text"].replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")
        words = c.get("words") or []
        if style["mode"] == "pop" and words:
            for word in words:
                label = word["text"].replace("{", "\\{").replace("}", "\\}")
                animated = f"{{\\c{style['secondary']}\\fscx72\\fscy72\\t(0,120,\\fscx100\\fscy100)}}{label}"
                rows.append(f"Dialogue: 0,{timestamp(word['start'], True)},{timestamp(word['end'], True)},Default,,0,0,0,,{animated}")
        elif style["mode"] == "karaoke" and words:
            karaoke = "".join(f"{{\\kf{max(1, round((word['end']-word['start'])*100))}}}{word['text'].replace('{','').replace('}','')} " for word in words)
            rows.append(f"Dialogue: 0,{timestamp(c['start'], True)},{timestamp(c['end'], True)},Default,,0,0,0,,{karaoke.strip()}")
        else:
            rows.append(f"Dialogue: 0,{timestamp(c['start'], True)},{timestamp(c['end'], True)},Default,,0,0,0,,{text}")
    return "\n".join(rows) + "\n"


def enhancement_filter(strength: str) -> str:
    reduction = {"gentle": 6, "balanced": 12, "strong": 18}.get(strength)
    if reduction is None:
        raise HTTPException(400, "Choose gentle, balanced, or strong cleanup")
    return f"highpass=f=70,lowpass=f=15000,afftdn=nr={reduction}:nf=-50:tn=1:gs=5,acompressor=threshold=0.12:ratio=2:attack=20:release=250:makeup=1.5,alimiter=limit=0.95"


def remove_background_to_alpha(source: Path, folder: Path) -> Path:
    try:
        from PIL import Image
        from rembg import new_session, remove
    except ImportError as exc:
        raise HTTPException(503, "Behind-subject export needs the optional CPU package. Install with: pip install -r requirements-effects.txt") from exc
    frames = folder / "subject_frames"
    frames.mkdir(exist_ok=True)
    raw = folder / "subject_input"
    raw.mkdir(exist_ok=True)
    extracted = subprocess.run(["ffmpeg", "-y", "-i", str(source), "-vf", "fps=10,scale='min(720,iw)':-2", "-vsync", "0", str(raw / "%06d.png")], capture_output=True, text=True, timeout=1200)
    if extracted.returncode:
        raise HTTPException(500, "Could not prepare frames for subject separation: " + extracted.stderr[-700:])
    session = new_session("u2net")
    for image_path in sorted(raw.glob("*.png")):
        with Image.open(image_path) as image:
            cutout = remove(image.convert("RGBA"), session=session)
            cutout.save(frames / image_path.name)
    layer = folder / "subject.mov"
    encoded = subprocess.run(["ffmpeg", "-y", "-framerate", "10", "-i", str(frames / "%06d.png"), "-an", "-c:v", "qtrle", "-pix_fmt", "argb", str(layer)], capture_output=True, text=True, timeout=1200)
    if encoded.returncode:
        raise HTTPException(500, "Could not encode separated subject: " + encoded.stderr[-700:])
    return layer


@app.post("/api/enhance/{pid}")
def enhance_existing_audio(pid: str, payload: dict):
    if not re.fullmatch(r"[a-f0-9]{12}", pid):
        raise HTTPException(404, "Project not found")
    folder = WORK / pid
    project_file = folder / "project.json"
    if not project_file.exists():
        raise HTTPException(404, "Project not found")
    project = json.loads(project_file.read_text(encoding="utf-8"))
    source = folder / "audio.wav"
    output = folder / "enhanced.wav"
    result = subprocess.run(["ffmpeg", "-y", "-i", str(source), "-af", enhancement_filter(payload.get("strength", "gentle")), "-ar", "48000", str(output)], capture_output=True, text=True, timeout=1200)
    if result.returncode:
        raise HTTPException(500, "Audio cleanup failed: " + result.stderr[-700:])
    project["enhanced_audio"] = output.name
    project_file.write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    return FileResponse(output, filename=Path(project["name"]).stem + ".enhanced.wav", media_type="audio/wav")


@app.get("/api/enhanced/{pid}")
def download_enhanced_audio(pid: str):
    if not re.fullmatch(r"[a-f0-9]{12}", pid):
        raise HTTPException(404, "Project not found")
    folder = WORK / pid
    project_file = folder / "project.json"
    if not project_file.exists():
        raise HTTPException(404, "Project not found")
    project = json.loads(project_file.read_text(encoding="utf-8"))
    enhanced = project.get("enhanced_audio")
    if not enhanced or not (folder / enhanced).is_file():
        raise HTTPException(404, "No cleaned audio is available for this project")
    return FileResponse(folder / enhanced, filename=Path(project["name"]).stem + ".enhanced.wav", media_type="audio/wav")


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
    behind_person = bool(payload.get("behind_person", False))
    if behind_person:
        try:
            import rembg  # noqa: F401
            from PIL import Image  # noqa: F401
        except ImportError as exc:
            raise HTTPException(503, "Behind-person export needs the optional CPU package. Install with: pip install -r requirements-effects.txt") from exc
    ass.write_text(render_ass(captions, payload.get("preset", "classic"), behind_person), encoding="utf-8-sig")
    if kind == "ass":
        return FileResponse(ass, filename=ass.name)
    if kind != "mp4":
        raise HTTPException(400, "Export kind must be srt, ass, or mp4")
    source = folder / json.loads(project_file.read_text(encoding="utf-8"))["source"]
    if source.suffix.lower() not in VIDEO:
        raise HTTPException(400, "Burned MP4 export requires a video input")
    output = folder / f"{stem}.captioned.mp4"
    base = folder / f"{stem}.captioned.base.mp4" if behind_person else output
    ass_filter = str(ass.resolve()).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    result = subprocess.run(["ffmpeg", "-y", "-i", str(source), "-vf", f"ass='{ass_filter}'", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", str(base)], capture_output=True, text=True, timeout=1800)
    if result.returncode:
        raise HTTPException(500, "FFmpeg burn-in failed: " + result.stderr[-900:])
    if behind_person:
        subject = remove_background_to_alpha(source, folder)
        overlay = subprocess.run(["ffmpeg", "-y", "-i", str(base), "-i", str(subject), "-filter_complex", "[1:v][0:v]scale2ref=w=main_w:h=main_h[fg][bg];[bg][fg]overlay=0:0:eof_action=pass:shortest=0[v]", "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", str(output)], capture_output=True, text=True, timeout=1800)
        if overlay.returncode:
            raise HTTPException(500, "Could not composite captions behind the subject: " + overlay.stderr[-900:])
    return FileResponse(output, filename=output.name)
