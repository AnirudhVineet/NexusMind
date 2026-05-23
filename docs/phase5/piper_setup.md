# Phase 5 — Piper TTS setup

Piper is the preferred local TTS engine for NexusMind. It runs entirely
offline and produces natural narration suitable for reels and brief
audio. The TTS provider chain falls through to pyttsx3 (Windows SAPI) if
Piper isn't available, so this step is **optional** — but recommended.

## Install path A — pip wheel (preferred, if available)

```powershell
cd backend
.venv\Scripts\activate
pip install piper-tts
```

If pip finds a wheel for your platform, you're done. The TTS service
will auto-detect `piper` on the PATH.

## Install path B — standalone binary (Windows fallback)

If the pip install fails (Piper Windows wheels are sometimes lagging),
download the official binary release:

1. Visit <https://github.com/rhasspy/piper/releases/latest>.
2. Download `piper_windows_amd64.zip`.
3. Extract `piper.exe` to `./data/bin/piper.exe` (create the directory if
   needed). The TTS service auto-detects this location.

## Voice models

Piper needs ONNX voice model files. Download at least one to
`./data/models/piper/`:

```powershell
mkdir data\models\piper -ErrorAction SilentlyContinue
cd data\models\piper

# en_US-amy-medium (default voice the system picks if none specified)
curl -L -o en_US-amy-medium.onnx `
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx
curl -L -o en_US-amy-medium.onnx.json `
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json
```

Each voice is ~60 MB. The first synthesis will be the slowest as Piper
warms up the model; subsequent calls reuse the loaded weights for
sub-second latency.

## Recommended voice set

| Voice ID | Gender | Language | Notes |
|---|---|---|---|
| en_US-amy-medium | F | en-US | Default, balanced |
| en_US-ryan-medium | M | en-US | Conversational |
| en_GB-alba-medium | F | en-GB | British accent |
| en_US-libritts-high | both | en-US | Multi-speaker, higher quality |

All voices listed are released under CC-BY-4.0 or similar permissive
licenses; see each voice's `.onnx.json` for exact attribution.

## Verifying the install

```powershell
# After starting the API + worker:
curl http://localhost:8000/api/media/voices
```

If Piper is wired up, you'll see entries with `"provider": "piper"`.
Try a short sample:

```powershell
curl -X POST http://localhost:8000/api/media/voices/sample `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"voice_id": "en_US-amy-medium"}' `
  --output sample.wav
```

## Fallback behavior

If Piper isn't installed or no voice models are found, narration falls
back to **pyttsx3** (Windows SAPI). This is always available on Windows
and produces serviceable audio for testing, but Piper sounds substantially
more natural.

If you set `ELEVENLABS_API_KEY` or `OPENAI_API_KEY`, those providers come
ahead of the local fallbacks for any voice ID they recognize.