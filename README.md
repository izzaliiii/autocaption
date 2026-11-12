# AutoCaption

Local-first Roman Urdu and Hinglish captions for Windows, macOS, and Linux.

AutoCaption combines a CPU-friendly Hinglish speech model with a simple local
caption editor. Media is processed by the local server; it is not uploaded to
a hosted transcription service. Model weights download from Hugging Face on
first use.

## Quick start (Windows PowerShell)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:7860>. FFmpeg must be on `PATH` for video input and
burned video export. The default model is
`MSpider3/whisper-hindi2hinglish-swift-ct2` (about 78 MB); select Urdu mode to
use multilingual Whisper transcription followed by a local Roman Urdu pass.
The Urdu transliterator is deterministic and approximate. Review captions
before publishing.

## Current scope

- Upload a local audio/video file and transcribe it on CPU.
- Hindi/Hinglish mode preserves English words and uses the fine-tuned model.
- Urdu mode uses local multilingual Whisper and Roman Urdu transliteration.
- Edit caption text and timing in the browser.
- Export SRT, styled ASS, or burn captions into MP4 with FFmpeg.
- No required API keys, accounts, or paid services.

## License

MIT. The ASR model and its weights retain their own Hugging Face license and
terms. See `THIRD_PARTY.md` for source attribution.
