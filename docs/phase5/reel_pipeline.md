# Phase 5 — Track A: Reel Video Generation Pipeline

## Overview

The reel pipeline turns a Phase 4 `generated_content` row of type `reel_script`
into an MP4 video with TTS narration, per-beat visuals, burned-in subtitles,
and a NexusMind watermark.

```
preparing  →  tts  →  visuals  →  subtitles  →  compose  →  finalizing
(0-10%)      (10-35%)   (35-65%)    (65-75%)     (75-92%)   (92-100%)
```

All work happens on the `reel` Celery queue. Status, stage, and `progress_pct`
are persisted at every transition.

## Running it locally

1. Install FFmpeg (one of):
   - `winget install Gyan.FFmpeg`
   - Or rely on `imageio-ffmpeg` (added to `requirements.txt`) which ships a
     binary inside its wheel. The runner detects it automatically.
2. Apply migrations (do not auto-run — copy the command):
   ```powershell
   cd backend
   .venv\Scripts\activate
   alembic upgrade head
   ```
   This brings the head from `0025_generated_content` → `0027_media_assets`.
3. Restart workers — `scripts/start-worker.ps1` now launches an extra
   `NM-media` process consuming the `reel` queue.
4. In the Studio UI, click "🎬 Render Video" on any reel content row. The
   modal lets you pick aspect ratio, voice, music style, watermark, and
   preview vs. final quality.

## Provider chains

### Visuals (per beat)
1. **Pollinations.ai** — free, no key required
2. **Hugging Face SDXL** — gated on `HUGGINGFACE_API_KEY` (free tier)
3. **Pexels stock** — gated on `PEXELS_API_KEY` (free tier)
4. **SolidColorFallback** — never fails

Each provider has a 25 s soft timeout. Results are cached by
`sha256(prompt + aspect + provider)` under `MEDIA_DATA_DIR/visual_cache/`.

### TTS (per beat)
1. **Piper TTS** — local, preferred (`piper` on PATH or `DATA_DIR/bin/piper`)
2. **pyttsx3** — offline Windows SAPI fallback (always available)
3. **ElevenLabs** — `ELEVENLABS_API_KEY` (optional paid upgrade)
4. **OpenAI TTS** — `OPENAI_API_KEY` (optional paid upgrade)

If all providers fail for a beat, the pipeline injects a silent track of the
planned duration so the reel still completes.

## File layout

```
DATA_DIR/generated/
  reels/{job_id}.mp4              ← final output
  audio/cache/{hash}.wav          ← TTS cache (Track B will share)
  visual_cache/{hash}.{png,jpg}   ← provider-keyed image cache
  scratch/{job_id}/               ← per-job working dir, deleted on completion
```

## Hard caps

| Setting | Default | Env var |
|---|---|---|
| Max reel duration | 90 s | `REEL_MAX_DURATION_SECONDS` |
| FFmpeg hard kill | 8 min | (hardcoded) |
| Daily reels per user | 10 | `REEL_DAILY_CAP` |
| Per-user disk quota | 2 GB | `MEDIA_USER_QUOTA_BYTES` (enforced by Track H) |
| Worker concurrency | 2 | `REEL_WORKER_CONCURRENCY` |

## SSE progress stream

`GET /api/media/jobs/{id}/stream` emits `progress` events whenever any of
`status`, `stage`, `progress_pct`, or `error_message` change. A final `done`
event is sent when the job hits a terminal state.

## Known limitations (improved in later tracks)

- Music mixing is currently a placeholder. Track G ships per-style ambient
  beds and brand-kit-driven duck levels.
- Subtitles are beat-aligned, not word-aligned. Forced alignment via
  faster-whisper lands in Track B.
- Preview quality drops to CRF 28 / `veryfast` but doesn't skip slow
  visual providers — Track H wires a `quality=preview` shortcut into
  `visual_provider`.
