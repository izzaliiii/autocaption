# Lafz Studio

**Lafz Studio** makes Roman Urdu and Hinglish captions locally on Windows,
macOS, and Linux. *Lafz* means “word”.

The app combines CPU transcription with an editable caption screen, creator
style templates, local voice cleanup, and optional person cutout for captions
behind the speaker. Media stays on the local server. Model weights download
from Hugging Face when first needed.

## Quick start (Windows PowerShell)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 7860
```

Open <http://127.0.0.1:7860>. FFmpeg must be on `PATH` for media input and
exports. The default Hinglish model is
`MSpider3/whisper-hindi2hinglish-swift-ct2` (about 78 MB); select Urdu mode to
use multilingual Whisper transcription followed by the local Roman Urdu
transliterator. Review captions before publishing.

## Current scope

- Upload local audio/video and transcribe on CPU.
- Hindi/Hinglish mode preserves English words and uses the fine-tuned model.
- Urdu mode uses multilingual Whisper and approximate Roman Urdu transliteration.
- Nine templates: Classic, Bold Viral, Karaoke, Boxed, Neon Glow, Editorial,
  Minimal, Word Pop, and Mint Highlight. Word timing drives pop and karaoke.
- Clean noisy audio before transcription or enhance it afterward, preview, and
  download the cleaned WAV. Three conservative denoise strengths are available.
- Optional “behind the person” MP4 export uses local rembg cutout and places the
  speaker foreground above the captions.
- Edit caption text/timing and export SRT, ASS, or burned MP4.
- No API keys or paid services are required.

## Optional speaker cutout

Install the CPU background-removal package only if you need the behind-person
effect:

```powershell
python -m pip install -r requirements-effects.txt
```

The first render downloads the U²-Net `u2net` weights. Subject cutout processes
frames on CPU and can take several minutes. It works best with a clear,
well-lit person separated from the background.

## Voice cleanup

Cleanup uses FFmpeg high/low-pass filters, adaptive spectral denoising, gentle
compression, and a peak limiter. It can reduce steady hiss/fan noise and make
speech level more consistent. It cannot restore speech hidden by loud noise or
repair severe clipping, and aggressive denoising can create watery/metallic
artifacts. Compare the cleaned audio with the original before using it.

## License

MIT. ASR and cutout model weights retain their own licenses and terms. See
`THIRD_PARTY.md` for source attribution. Caption-template references include
[CapCut’s caption type guide](https://www.capcut.com/resource/types-of-captions).
