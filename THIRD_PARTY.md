# Third-party components

- Transcription model: [MSpider3/whisper-hindi2hinglish-swift-ct2](https://huggingface.co/MSpider3/whisper-hindi2hinglish-swift-ct2).
  Downloaded from Hugging Face at runtime through faster-whisper. Check its
  model card and license before redistribution of weights.
- faster-whisper and CTranslate2: BSD-3-Clause.
- FFmpeg: external executable; see its own license/build configuration.
- Optional person cutout: [rembg](https://github.com/danielgatis/rembg), MIT;
  its U²-Net model weights have separate terms. Installed from
  `requirements-effects.txt` only when the behind-subject feature is needed.

The Urdu-to-Roman mapping in `romanizer.py` is newly written for this project.
