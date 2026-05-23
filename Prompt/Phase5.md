# NexusMind — Phase 5 Prompt for Claude Code

Paste the single prompt below at the start of a new Claude Code session.
It covers orientation, ground rules, and all eight tracks (5.1–5.8) in one
shot. Claude Code will produce a full plan first, wait for your approval,
then implement in dependency order.

Phase 5 turns the **text-only** content engine from Phase 4 (Track H) into
a real **media production pipeline**: reel videos with TTS narration and
visuals, image memes with AI-generated and curated backgrounds, audio
narration of any document or brief, visual storyboards, a Content Studio
editor, and a publishing/share-link pipeline.

Phase 5 remains **free-first**. Every required feature must work end-to-end
with zero paid services using local models and free APIs. Paid services are
opt-in upgrade paths only — the user supplies their own key and the feature
gracefully degrades to the free path when no key is set.

---

## Phase 5 Prompt (paste once)

```
You are working on NexusMind — a personal AI knowledge graph system built
with FastAPI + Celery + PostgreSQL/pgvector + Next.js. Phases 1, 2, 2.5, 3,
and 4 are complete. We are starting Phase 5 now, which adds eight tracks:

  A. Reel Video Generation Pipeline
  B. TTS Narration Engine (audio-only outputs)
  C. Visual Meme Engine (AI backgrounds + extended templates)
  D. Visual Storyboard Renderer
  E. Content Studio Editor (timeline/canvas editing)
  F. Publishing Pipeline & Share Links
  G. Brand Kit & Asset Library
  H. Production Hardening (cost guardrails + media observability)

─────────────────────────────────────────────
STEP 1 — ORIENT YOURSELF (do this before anything else)
─────────────────────────────────────────────

Read these files:

1. NexusMind_Phase2_5_Changes.md (root of repo) — covers all deviations
   from Phases 1 through 3.
2. Prompt/Phase4.md — the prompt that produced Phase 4. The eight tracks
   there (A–H) are the dependency baseline. Pay special attention to
   Track H (AI Content Repurposing Engine — text edition): Phase 5 is the
   media layer that wraps it. Phase 5 MUST NOT re-implement text
   generation — it consumes Phase 4 generated_content rows.
3. The repo structure. List files under backend/app/services/ (especially
   content_engine.py), backend/app/workers/celery_app.py,
   backend/alembic/versions/, and frontend/app/studio/. Confirm:
   - generated_content table from migration 0025 exists with content_type
     in (reel_script, meme, thread, storyboard, caption)
   - The Studio frontend page exists at frontend/app/studio/
   - meme_templates assets live under backend/app/assets/meme_templates/
   - DATA_DIR/generated/memes/ writes are working
4. The current Alembic head should be 0025_generated_content from Phase 4.
   Confirm before adding 0026+.

There is no NexusMind_Phase5_Plan.md. This prompt is the plan.

After reading, confirm:
1. Phase 4 generated_content table and Studio page are in place
2. Alembic head is 0025
3. Celery queues from Phase 4 (default, ner, intelligence, claims, nli,
   credibility, ocr, transcription, cards, memory, research, alerts) are
   all registered in celery_app.py
4. content_engine.py exposes generate_reel_script, generate_meme,
   generate_storyboard — Phase 5 will call these to get JSON schemas
   then render media on top
5. Any discrepancy between this prompt and the actual repo

─────────────────────────────────────────────
STEP 2 — GROUND RULES (non-negotiable for all of Phase 5)
─────────────────────────────────────────────

- FREE-FIRST: every feature must complete its happy path with zero paid
  services. Paid is opt-in via env vars only.
    Required free paths:
      * TTS:   Piper TTS (local, MIT) → fallback pyttsx3 (offline SAPI)
      * Image: Pollinations.ai free endpoint → fallback Stable Diffusion
               via Hugging Face Inference API free tier (gated on
               HUGGINGFACE_API_KEY which the user supplies for free)
               → fallback Pexels free photo search
      * Music: local CC0 ambient track library bundled in assets/
      * Video: FFmpeg + MoviePy (BSD/MIT), all local rendering
      * Captions: existing Whisper-cpp / faster-whisper from Phase 3
    Optional paid escape hatches (must NOT be required):
      * ELEVENLABS_API_KEY → upgrade TTS quality
      * OPENAI_API_KEY     → DALL-E 3 image upgrade
      * STABILITY_API_KEY  → Stable Diffusion API upgrade
      * MUBERT_API_KEY     → genre-matched music upgrade
  If no paid key is present, the system MUST silently use the free path.
  Never call a paid endpoint without an explicit user-supplied key.

- LLM call order is unchanged from Phase 4: Groq → Ollama fallback. Phase 5
  does NOT introduce new LLM providers. Script text comes from Phase 4
  generators; Phase 5 only renders media around it.

- NO Docker. Native Windows binaries only. FFmpeg must be installed via
  winget or the user's existing chocolatey/scoop. Detect at startup and
  print install instructions if missing. Pin the required minimum version
  (ffmpeg >= 6.0).

- NO cloud storage. All media artifacts go under DATA_DIR/generated/:
    DATA_DIR/generated/reels/{id}.mp4
    DATA_DIR/generated/audio/{id}.mp3
    DATA_DIR/generated/storyboards/{id}/frame_NN.png
    DATA_DIR/generated/storyboards/{id}/storyboard.pdf
    DATA_DIR/generated/memes/{id}.png            (already Phase 4)
    DATA_DIR/generated/brandkit/{user_id}/...
    DATA_DIR/generated/scratch/{job_id}/         (temp, auto-cleaned)

- 768-dim Gemini embeddings on chunks remain the rule. Phase 5 does NOT
  touch chunk embeddings. Track A's fidelity recheck after editing reuses
  the existing embedding service.

- Mixed API prefix scheme. New Phase 5 routes go under /api UNLESS
  extending a Phase 1 unprefixed route. Studio routes from Phase 4 live
  under /api/content; Phase 5 adds /api/media, /api/publish,
  /api/brandkit.

- Single-user-per-account. No workspace_id. Collaboration is OUT OF SCOPE
  for Phase 5 (deferred to Phase 6).

- Source fidelity for every claim-bearing field is unchanged. The fidelity
  check from Phase 4 already runs on script text. Phase 5 must NOT
  re-introduce hallucinations — visual prompts derived from a chunk MUST
  cite the chunk_id, and post-render provenance MUST be preserved in the
  output metadata.

- Cost guardrails (Track H):
    * Per-job hard cap: 90 s of video, 3 min of audio, 12 storyboard
      frames, 8 meme variants. Reject requests exceeding the cap with a
      clear error.
    * Daily per-user generation cap (configurable, default 50 jobs/day)
      enforced via a Redis counter keyed by user_id + UTC date.
    * Disk quota: per-user DATA_DIR/generated/ usage hard-capped at 2 GB
      by default (env override MEDIA_USER_QUOTA_BYTES). Enforce before
      starting any render job.

- Every new feature gets at least one unit test and a doc section under
  docs/phase5/.

─────────────────────────────────────────────
STEP 3 — WORKING AGREEMENT
─────────────────────────────────────────────

- Before writing any code, produce a single consolidated plan (5–10 bullets
  per track, listing files to create or change). Present it and wait for
  approval.
- When you find a contradiction between this prompt and the actual codebase,
  flag it and ask — don't silently adapt.
- For each Alembic migration, generate the file but DO NOT run it. Print
  the exact `alembic upgrade` command for me to run.
- For each new dependency: pip install or npm install, pin the version,
  state the license. Reject any GPL/AGPL dep without explicit approval.
  Permitted licenses: MIT, Apache-2.0, BSD, ISC, LGPL (linked), MPL.
- Run existing tests after every meaningful change. If a previously passing
  test now fails, stop and fix before continuing.
- Don't refactor code outside the current track's scope.
- Implement tracks in this dependency order:
    A → B → C → D → E → F → G → H
  Tracks B and C are technically independent; A is the most complex and
  unblocks both Studio and Publishing. Track G can run in parallel with
  any of D–F. Track H is last and instruments everything.

─────────────────────────────────────────────
TRACK A — REEL VIDEO GENERATION PIPELINE
─────────────────────────────────────────────

Goal: take a generated_content row of content_type='reel_script' and
render an MP4 with TTS narration, per-beat visuals, burned-in subtitles,
and background music. Must work end-to-end with zero paid services.

Deliverables:

1. Alembic migration 0026_media_jobs:
   - Table media_jobs (id UUID PK, user_id FK, content_id FK NULLABLE,
     job_type TEXT, status TEXT, params JSONB, progress_pct INT DEFAULT 0,
     stage TEXT, output_path TEXT NULLABLE, output_size_bytes BIGINT
     NULLABLE, duration_seconds NUMERIC NULLABLE, cost_estimate_usd NUMERIC
     DEFAULT 0, error_message TEXT NULLABLE, created_at TIMESTAMPTZ,
     started_at TIMESTAMPTZ NULLABLE, completed_at TIMESTAMPTZ NULLABLE,
     expires_at TIMESTAMPTZ NULLABLE)
   - job_type values: reel | narration | storyboard | meme_image | export
   - status values: queued | preparing | rendering | finalizing | complete
                  | failed | canceled
   - Index on (user_id, created_at DESC), (status, created_at DESC)

2. Migration 0027_media_assets:
   - Table media_assets (id UUID PK, user_id FK, asset_type TEXT,
     file_path TEXT, mime_type TEXT, size_bytes BIGINT, duration_seconds
     NUMERIC NULLABLE, width INT NULLABLE, height INT NULLABLE,
     source_kind TEXT, source_ref TEXT, license TEXT, metadata JSONB,
     created_at TIMESTAMPTZ)
   - asset_type: image | video_clip | audio_clip | music | template
   - source_kind: generated | stock | uploaded | brandkit | bundled
   - license: any of cc0 | royalty_free | user_owned | api_terms
   - Index on (user_id, asset_type, created_at DESC)

3. Service backend/app/services/media/reel_renderer.py:
   - render_reel(media_job_id): orchestrate the full pipeline.
     Stages (persist `stage` and `progress_pct` at each step):
       1. preparing (0-10%):  load content row, validate reel_script JSON,
                              enforce 90 s hard cap, allocate scratch dir
       2. tts (10-35%):       call narration service per beat (Track B)
       3. visuals (35-65%):   fetch/generate one image per beat
       4. subtitles (65-75%): force-align with faster-whisper, build ASS
       5. compose (75-92%):   MoviePy/FFmpeg compose frames + audio + subs
       6. finalize (92-100%): render final MP4, write to
                              DATA_DIR/generated/reels/{id}.mp4, hash,
                              update media_jobs row, schedule cleanup of
                              scratch dir
   - Aspect-ratio support: vertical (1080x1920) default; square (1080x1080)
     and landscape (1920x1080) selectable in params.
   - Per-beat visual selection order:
       a. If beat.visual_asset_id supplied → use that media_asset row
       b. Else if Pollinations free succeeds → use generated image
       c. Else if HUGGINGFACE_API_KEY present → Stable Diffusion
       d. Else Pexels search using beat.visual_direction as query
       e. Final fallback: solid color card with on_screen_text overlay
   - On-screen text overlay: FFmpeg drawtext using brand kit font, color,
     and outline (default Anton, white text, black outline). Position
     bottom-center by default; configurable per beat.
   - Background music: pick from bundled CC0 library matching the
     style → tempo map (educational=ambient, viral=energetic,
     humorous=quirky, professional=corporate). Duck under voice -18 dB.
   - Watermark: NexusMind logo bottom-right; suppressed if brand kit
     overrides with the user's own watermark.

4. Service backend/app/services/media/visual_provider.py:
   - Pluggable provider chain: PollinationsProvider → HuggingFaceSDProvider
     → PexelsProvider → SolidColorFallback.
   - Each provider exposes generate(prompt, aspect_ratio, seed) returning
     a saved media_asset row. Time out at 25 s per provider; on timeout
     or error, fall through to the next.
   - Cache key = sha256(prompt + aspect_ratio + provider_name). Cached
     hits skip the API call and reuse the saved asset.
   - Pollinations endpoint: https://image.pollinations.ai/prompt/{prompt}
     with width/height query params. No key required.
   - Pexels: free tier, requires PEXELS_API_KEY in env (the user already
     provides this per Phase 4 rules — verify before calling).

5. Service backend/app/services/media/ffmpeg_runner.py:
   - Thin wrapper around subprocess + FFmpeg with logging and progress
     parsing (parse -progress pipe:1 output, update media_jobs.progress_pct).
   - Detects FFmpeg at startup; if missing, the worker refuses to register
     the reel queue and logs a clear error with install instructions
     (winget install Gyan.FFmpeg).
   - Hard kills any ffmpeg process running > 8 minutes.

6. Celery: new `reel` queue. Task render_reel_job(media_job_id) with
   acks_late=True, prefetch_multiplier=1 (rendering is heavy).
   Concurrency capped at 2 by default (env REEL_WORKER_CONCURRENCY).

7. Endpoints (all under /api):
   - POST /api/media/reels { content_id, aspect_ratio?, voice_id?,
     music_style?, watermark? } → 202 with { job_id }
   - GET /api/media/jobs/{job_id} (works for all media job types)
   - GET /api/media/jobs/{job_id}/stream → SSE stream of progress events
   - GET /api/media/jobs/{job_id}/output → range-supported file stream
     (for in-browser preview), gzip not applied to media
   - DELETE /api/media/jobs/{job_id} (cancel if in-flight, hard-delete
     if complete; removes file + DB row)
   - GET /api/media/reels?content_id= (list reels per content row)

8. Worker update: add `reel` queue to scripts/start-worker.ps1. Final
   queue list: default, ner, intelligence, claims, nli, credibility, ocr,
   transcription, cards, memory, research, alerts, reel

9. Frontend additions to /studio:
   - On the reel content row: "Render Video" button → modal with
     aspect ratio (vertical/square/landscape), voice picker (lists
     available voices from Track B), music style, watermark toggle.
   - Video preview pane with HTML5 <video> + range scrubber, captions
     toggle, "download MP4", "open share link" (Track F).
   - Progress UI uses the SSE stream from /api/media/jobs/{id}/stream.

10. Tests: test_reel_pipeline_stages.py, test_visual_provider_fallback.py,
    test_ffmpeg_runner.py, test_reel_api.py, test_reel_quota.py

─────────────────────────────────────────────
TRACK B — TTS NARRATION ENGINE
─────────────────────────────────────────────

Goal: convert any text (reel beat, research brief section, thread post,
full document) into natural-sounding audio. Must be reusable by Track A
for reels and standalone for "Listen to this brief" workflows.

Deliverables:

1. Service backend/app/services/media/tts.py:
   - Provider chain: PiperProvider (local) → Pyttsx3Provider (offline
     Windows SAPI) → ElevenLabsProvider (only if ELEVENLABS_API_KEY set)
     → OpenAITTSProvider (only if OPENAI_API_KEY set).
   - synthesize(text, voice_id, speed, output_path) → AudioResult
     { path, duration_seconds, sample_rate, provider_used, cost_usd }
   - synthesize_batch(segments) returns word-level timing JSON so Track A
     can use it for forced-alignment-free subtitle building when the TTS
     engine reports per-word timings (Piper does not; use faster-whisper
     forced alignment as fallback).
   - Voice catalog endpoint exposes the union of all providers' available
     voices with provenance + language + gender + sample_url.

2. Piper integration:
   - pip install piper-tts (MIT). Bundle 4 default voices under
     backend/app/assets/piper_voices/:
       en_US-amy-medium, en_US-ryan-medium, en_GB-alba-medium,
       en_US-libritts-high (multi-speaker).
   - Document model download in docs/phase5/piper_setup.md including
     license info (Apache-2.0 / CC-BY-4.0 per voice).
   - Detect missing model files at worker startup; download on first use
     to DATA_DIR/models/piper/ with a clear progress log.

3. Migration 0028_voices (or extend brandkit migration in Track G):
   - Table user_voice_preferences (user_id PK FK, default_voice_id TEXT,
     speed NUMERIC DEFAULT 1.0, last_used_at TIMESTAMPTZ)

4. Endpoints (all under /api):
   - POST /api/media/narration { text, voice_id?, speed?, source_ref? }
     → 202 with { job_id } if text length > 500 chars else 200 with inline
     audio_url
   - GET /api/media/voices → list with provider + sample URLs
   - POST /api/media/voices/sample { voice_id } → short cached MP3 stream
   - POST /api/research/briefs/{id}/narrate → enqueue narration for the
     full brief; returns job_id (reuses media_jobs table, job_type='narration')

5. Celery: reuse `reel` queue or split off a `narration` queue? Use the
   `reel` queue but with task priority. Narration tasks get priority 5,
   reel tasks priority 3, storyboard tasks priority 4 (lower number = higher
   priority in Celery). Document this in docs/phase5/queues.md.

6. Frontend additions:
   - "Listen" button on /research/briefs/[id] → opens a sticky audio
     player at bottom-right with play/pause, speed, chapter list (one
     chapter per brief section, generated automatically).
   - Voice settings panel under /settings/voice.

7. Tests: test_piper_synthesize.py, test_tts_provider_fallback.py,
   test_narration_api.py, test_brief_narration_chapters.py

─────────────────────────────────────────────
TRACK C — VISUAL MEME ENGINE
─────────────────────────────────────────────

Goal: extend Phase 4's template-based meme generator with (a) AI-generated
backgrounds for non-template memes, (b) a larger template library, and
(c) advanced layout types (Drake split, Expanding Brain 4-panel, side-by-side
contrast, screenshot-style quote card).

Deliverables:

1. Template library expansion:
   - Add 20 more CC0 / public-domain templates under
     backend/app/assets/meme_templates/. Cover at minimum: Drake, Distracted
     Boyfriend, Two Buttons, Expanding Brain (4 panel), Change My Mind,
     Galaxy Brain, This Is Fine, Surprised Pikachu, Roll Safe, Always Has
     Been (astronaut pointing).
   - Each template has a sidecar JSON describing text regions:
     {
       "name": "drake",
       "layout": "two_panel_vertical",
       "regions": [
         { "id": "reject", "x": 0.55, "y": 0.05, "w": 0.42, "h": 0.4,
           "align": "left", "font_size_pct": 0.06 },
         { "id": "approve", "x": 0.55, "y": 0.55, "w": 0.42, "h": 0.4,
           "align": "left", "font_size_pct": 0.06 }
       ],
       "license": "fair_use_meme_archive",
       "source_url": "..."
     }
   - Document all templates in docs/phase5/meme_templates.md.

2. Service backend/app/services/media/meme_renderer.py:
   - Replace the Phase 4 simple top/bottom text renderer with a region-
     driven renderer that reads the sidecar JSON.
   - Multi-region text rendering with auto font sizing, word wrap, outline,
     drop shadow. Use Pillow.
   - For multi-panel templates the LLM (call existing Phase 4
     content_engine.generate_meme but pass template hint and region list)
     returns panel_texts[] aligned to the region ids.

3. AI background generation for non-template memes:
   - When meme.template_name == "custom", call the Track A visual_provider
     to generate a 1:1 background image from the meme's concept fields,
     then overlay text using a centered single-region layout.

4. Migration 0029_meme_assets (optional — only if template metadata can't
   live entirely in JSON sidecars; prefer JSON sidecars to avoid this).

5. Endpoints (all under /api):
   - POST /api/content/{id}/render_meme — re-render a meme content_id
     into a PNG (regenerates if the user edited captions). Returns
     X-Output-Path header + 200 with PNG body.
   - GET /api/media/meme-templates → list templates with sidecar metadata
     and a small preview PNG path.

6. Frontend updates to /studio meme editor:
   - Replace the simple top/bottom text inputs with a region-aware editor
     reading the sidecar JSON. Live Canvas preview that calls
     /api/content/{id}/render_meme on every debounced change (500ms).
   - "Switch template" dropdown that re-shapes text regions sensibly
     (best-effort mapping by region count).
   - "Generate background" button (only for template_name="custom")
     calling the AI visual chain.

7. Tests: test_meme_region_rendering.py, test_meme_template_library.py,
   test_meme_custom_background.py, test_meme_api.py

─────────────────────────────────────────────
TRACK D — VISUAL STORYBOARD RENDERER
─────────────────────────────────────────────

Goal: convert Phase 4 storyboard JSON (frames[]) into a rendered PDF or
image series, with one image per frame, narration text caption, and audio
file per frame. Useful as an alternative to a full reel render for users
who want a printable/shareable doc.

Deliverables:

1. Service backend/app/services/media/storyboard_renderer.py:
   - render_storyboard(content_id, format): format in pdf | image_series |
     html_slides.
   - Per frame:
       * Generate or fetch image via visual_provider (reuse Track A
         service).
       * Generate narration audio via TTS (reuse Track B service).
       * Compose a card: image (top 70%), narration text (middle 20%),
         visual direction + duration footer (bottom 10%).
   - PDF assembly via reportlab (already in requirements per Phase 4
     research export) — one page per frame. Embed images. Optionally embed
     audio links (PDF supports attachments via reportlab's attachFile).
   - image_series: write frame_01.png ... frame_NN.png plus a manifest.json
     under DATA_DIR/generated/storyboards/{id}/.
   - html_slides: write index.html using a minimal reveal.js bundle
     (MIT, copy into frontend/public/storyboard_template/).
   - Hard cap: 12 frames per storyboard. Reject over-cap.

2. Endpoints (all under /api):
   - POST /api/media/storyboards { content_id, format } → 202 job_id
   - GET /api/media/storyboards/{job_id}/pdf
   - GET /api/media/storyboards/{job_id}/frames/{n}.png
   - GET /api/media/storyboards/{job_id}/slides → serves the HTML

3. Frontend additions to /studio:
   - "Render Storyboard" button on storyboard content rows → modal with
     format picker (PDF / image series / HTML slides).
   - Inline PDF preview using pdf.js (bundle locally) for the PDF format.
   - Per-frame audio scrubber row when image series is selected.

4. Tests: test_storyboard_pdf.py, test_storyboard_image_series.py,
   test_storyboard_html_slides.py

─────────────────────────────────────────────
TRACK E — CONTENT STUDIO EDITOR
─────────────────────────────────────────────

Goal: upgrade Phase 4's basic Studio page into a proper editor with a
timeline view for reels and a canvas editor for memes. Users can edit
inline before rendering and re-render selectively.

Deliverables:

1. Reel timeline editor (frontend/app/studio/[id]/reel/page.tsx):
   - Horizontal timeline showing beats as draggable cards.
   - Per-beat: text editor (multi-line), visual preview, on-screen text
     editor, duration slider (2–8 s), regenerate-visual button.
   - Click-to-edit hook/beat/CTA. Duration sum auto-validated (≤ 90 s).
   - "Render Preview" generates a low-res 480p version (faster) for
     in-editor playback. "Render Final" produces the full-res output.
   - Each edit triggers a Phase 4 fidelity recheck on the changed field
     (call existing content_engine.check_source_fidelity).

2. Meme canvas editor: already specified in Track C.

3. Thread / caption / storyboard editors:
   - Threads: text-area-per-post with character counter, drag-reorder,
     "split this post here" action when over limit.
   - Captions: platform tabs (Instagram / LinkedIn / TikTok) with char
     counter + hashtag suggestions.
   - Storyboard: frame-by-frame editor with image-prompt field, narration
     text, visual direction.

4. Shared edit bar:
   - "Save draft" (PATCH /api/content/{id} — already exists per Phase 4)
   - "Render" (dispatches to the right Track A/C/D endpoint)
   - "Generate variants" (calls Phase 4 POST /api/content/{id}/variants)
   - "Fidelity report" expander showing per-field status from
     fidelity_flags

5. Autosave: 500ms debounce on edits, optimistic UI. Failure shows toast
   with retry.

6. Tests are mostly Playwright e2e under frontend/tests/e2e/studio/.
   Backend unit tests for any new endpoints introduced here.

─────────────────────────────────────────────
TRACK F — PUBLISHING PIPELINE & SHARE LINKS
─────────────────────────────────────────────

Goal: turn rendered media into shareable URLs. No direct social media API
integration yet (deferred to Phase 6) — Phase 5 publishes via:
  (1) public share links with optional expiry + view counter
  (2) "download bundle" zips containing all formats for manual posting
  (3) one-tap "open share sheet" using navigator.share() on mobile

Deliverables:

1. Migration 0030_share_links:
   - Table share_links (id UUID PK, user_id FK, target_type TEXT,
     target_id UUID, slug TEXT UNIQUE, password_hash TEXT NULLABLE,
     expires_at TIMESTAMPTZ NULLABLE, view_count INT DEFAULT 0,
     last_viewed_at TIMESTAMPTZ NULLABLE, enabled BOOLEAN DEFAULT true,
     created_at TIMESTAMPTZ)
   - target_type: content | media_job | brief
   - slug is a 12-char URL-safe random string

2. Service backend/app/services/publish.py:
   - create_share_link(target_type, target_id, expires_in?, password?) →
     ShareLink row
   - render_public_page(slug, password?) — used by the public route to
     serve a sanitized HTML view with no auth headers, no JWT, no user
     references. Strip any PII. Show only the rendered media + a small
     "Made with NexusMind" footer.
   - bundle_export(target_type, target_id) — zip all rendered formats
     (MP4 + thumbnail + transcript SRT + caption variants TXT) into
     DATA_DIR/generated/bundles/{id}.zip.

3. Public endpoints (NOT under /api — these are user-facing share routes):
   - GET /s/{slug} → SSR Next.js page rendering the public preview
   - POST /s/{slug}/unlock { password } → validates, sets a session cookie
   - GET /s/{slug}/asset → streams the actual media (range-supported)
   - GET /s/{slug}/og.png → dynamic Open Graph thumbnail (1200x630)

4. Authenticated endpoints (under /api):
   - POST /api/publish/share { target_type, target_id, expires_in_hours?,
     password? } → { url, slug }
   - GET /api/publish/share?target_id= → list active links per target
   - DELETE /api/publish/share/{id}
   - POST /api/publish/bundle { target_type, target_id } → job_id
     (uses media_jobs with job_type='export')

5. Open Graph thumbnail rendering:
   - For reels: first-frame extraction + duration overlay.
   - For memes: the meme PNG.
   - For briefs: title card with topic + date.
   - All rendered server-side with Pillow and cached.

6. Frontend additions:
   - "Share" button on every Studio output → modal with copy-link,
     expiry, password, "Download bundle" actions.
   - /shares page listing the user's active share links with view counts
     and revoke action.
   - Public viewer pages at /s/[slug] with minimal nav, no login prompts.

7. Tests: test_share_link_lifecycle.py, test_share_password.py,
   test_share_expiry.py, test_bundle_export.py, test_og_thumbnail.py,
   test_public_render_isolation.py

─────────────────────────────────────────────
TRACK G — BRAND KIT & ASSET LIBRARY
─────────────────────────────────────────────

Goal: let the user configure a consistent visual identity that propagates
through every render. Plus a personal asset library for uploaded images,
logos, music tracks.

Deliverables:

1. Migration 0031_brandkit:
   - Table brand_kits (user_id PK FK, primary_color TEXT, secondary_color
     TEXT, accent_color TEXT, font_heading TEXT, font_body TEXT,
     logo_asset_id UUID NULLABLE, watermark_asset_id UUID NULLABLE,
     watermark_opacity NUMERIC DEFAULT 0.6, watermark_position TEXT
     DEFAULT 'bottom-right', music_style_default TEXT,
     subtitle_style JSONB DEFAULT '{}', created_at, updated_at)

2. Asset library:
   - Reuses the media_assets table from Track A.
   - New asset_type values: brand_logo, brand_watermark, user_upload.
   - POST /api/brandkit/upload (multipart) → media_asset row
   - GET /api/brandkit, PATCH /api/brandkit
   - GET /api/brandkit/assets?type=

3. Asset propagation:
   - reel_renderer reads brand_kit at job start. If watermark_asset_id set
     it overrides the default NexusMind logo.
   - storyboard_renderer applies brand colors to card backgrounds and
     fonts.
   - meme_renderer optionally applies brand watermark (off by default —
     memes look weird with watermarks).
   - share_link OG thumbnails use brand colors.

4. Subtitle styling JSON shape:
   { "font_family": "Anton",
     "font_size_pct": 0.05,
     "color": "#FFFFFF",
     "outline_color": "#000000",
     "outline_width_px": 3,
     "background": "transparent" | "#000000aa",
     "position": "bottom" | "middle" | "top",
     "uppercase": false,
     "word_highlight_color": "#FFD700" }

5. Frontend new page /settings/brandkit:
   - Color pickers, font dropdowns (system + Google Fonts free subset),
     logo upload, watermark upload + position + opacity.
   - Subtitle style preview frame showing live changes.
   - "Reset to defaults" button.

6. Tests: test_brandkit_api.py, test_asset_upload.py,
   test_brandkit_propagation.py

─────────────────────────────────────────────
TRACK H — PRODUCTION HARDENING (COST + MEDIA OBSERVABILITY)
─────────────────────────────────────────────

Goal: instrument the media pipeline with the same rigor Phase 3 applied
to retrieval. Quotas, cost tracking, queue health, render-failure alerts.

Deliverables:

1. Migration 0032_generation_metrics:
   - Table generation_metrics (id BIGSERIAL PK, user_id FK, job_type TEXT,
     provider TEXT, model TEXT, duration_ms INT, input_units INT,
     output_units INT, cost_estimate_usd NUMERIC, success BOOLEAN,
     error_class TEXT NULLABLE, created_at TIMESTAMPTZ)
   - Indexed on (user_id, created_at), (job_type, created_at).

2. Quota service backend/app/services/media/quota.py:
   - check_quota(user_id, job_type) → ok|denied with reason. Reads Redis
     counters (key: nm:quota:{user_id}:{utc_date}:{job_type}) against the
     per-job-type daily cap.
   - increment_usage(user_id, job_type, units=1) called atomically at job
     start.
   - check_disk_quota(user_id) — sum of media_jobs.output_size_bytes for
     incomplete-expiry rows.
   - Quota config defaults (overridable per env):
       REEL_DAILY_CAP=10, NARRATION_DAILY_CAP=50, STORYBOARD_DAILY_CAP=20,
       MEME_DAILY_CAP=100, MEDIA_USER_QUOTA_BYTES=2147483648

3. Cost estimation:
   - Per-provider rate cards in backend/app/services/media/cost_rates.py
     (free providers report 0.0). Computed on success and written to
     generation_metrics. Daily aggregate rolled up by a beat job into a
     Redis hash for fast UI lookup.

4. Prometheus metrics (extend the existing /metrics endpoint):
   - nm_media_jobs_total{job_type, status}
   - nm_media_job_duration_seconds_bucket{job_type}
   - nm_media_cost_usd_total{provider}
   - nm_visual_provider_calls_total{provider, status}
   - nm_tts_provider_calls_total{provider, status}
   - nm_media_disk_used_bytes{user_id}

5. Grafana dashboard JSON under ops/grafana/dashboards/media.json:
   - Job throughput by status, p50/p95 render times, provider success
     rate, daily cost by provider, disk usage per user.
   - Import instructions documented in docs/phase5/observability.md.

6. Render-failure dead-letter:
   - Failed media_jobs move to status='failed' with full error_message.
   - Beat job daily_media_failure_digest emails admin (user_id with
     email_settings.enabled=true) any failures from last 24h. Skip if
     none. Reuses Phase 4 email infrastructure.

7. Cleanup beat jobs (extend Phase 4 cleanup_expired_graph_exports
   pattern):
   - cleanup_expired_media every hour: delete files + DB rows where
     expires_at < now() OR (status='complete' AND created_at < now() -
     interval '30 days' AND no share_links reference this media_job).
   - cleanup_orphan_scratch_dirs every hour: rm any
     DATA_DIR/generated/scratch/* older than 6 hours.

8. UI surfacing:
   - Studio header shows: today's render count vs cap, current disk usage
     vs quota, daily cost estimate.
   - Quota-exceeded errors return 429 with a Retry-After header set to
     midnight UTC.

9. Tests: test_quota_service.py, test_cost_metrics.py,
   test_cleanup_media.py, test_dead_letter_digest.py,
   test_prometheus_metrics.py

─────────────────────────────────────────────
MIGRATION SEQUENCE
─────────────────────────────────────────────

Current head: 0025_generated_content (from Phase 4 Track H)

  0026_media_jobs            Track A
  0027_media_assets          Track A
  0028_voices                Track B  (optional — may collapse into 0031)
  0029_meme_assets           Track C  (optional — prefer JSON sidecars)
  0030_share_links           Track F
  0031_brandkit              Track G
  0032_generation_metrics    Track H

If any "optional" migration ends up not needed, renumber later migrations
and document the change in docs/phase5/migrations.md.

─────────────────────────────────────────────
QUEUE INVENTORY (FINAL)
─────────────────────────────────────────────

After Phase 5: default, ner, intelligence, claims, nli, credibility, ocr,
transcription, cards, memory, research, alerts, reel

Track B uses the `reel` queue with task priority. Track D (storyboard)
and Track F (bundle export) also use `reel` queue. Do NOT proliferate
queues — workers should consume from the `reel` queue and dispatch by
job_type.

─────────────────────────────────────────────
ENV VARS INTRODUCED IN PHASE 5
─────────────────────────────────────────────

Required (free path):
  FFMPEG_PATH               # detected if not set; mandatory at runtime
  MEDIA_DATA_DIR            # defaults to {DATA_DIR}/generated
  MEDIA_USER_QUOTA_BYTES    # default 2147483648 (2 GB)
  REEL_WORKER_CONCURRENCY   # default 2
  REEL_DAILY_CAP            # default 10
  NARRATION_DAILY_CAP       # default 50
  STORYBOARD_DAILY_CAP      # default 20
  MEME_DAILY_CAP            # default 100
  CONTENT_FIDELITY_THRESHOLD # already exists from Phase 4

Optional paid upgrades (feature degrades gracefully if absent):
  ELEVENLABS_API_KEY        # TTS upgrade
  OPENAI_API_KEY            # DALL-E images + TTS upgrade
  STABILITY_API_KEY         # SD3/SDXL API upgrade
  MUBERT_API_KEY            # music upgrade
  HUGGINGFACE_API_KEY       # free tier — recommend the user supply one

─────────────────────────────────────────────
NOW: PRODUCE THE CONSOLIDATED PLAN
─────────────────────────────────────────────

After completing Step 1 (orientation), output a single consolidated plan
covering all eight tracks. For each track list:
- Files to create
- Files to modify
- New Python / Node dependencies (package + version + license)
- New env vars
- Migration name (if any)
- Risk areas (specifically: FFmpeg cross-platform behavior, Piper voice
  download size, Pollinations rate limits)

Present the plan and wait for my approval before writing any code.
If you find any contradiction between this prompt and the actual codebase
state (especially the Phase 4 Track H outputs), call it out in the plan.

Do NOT start coding until I approve the plan.
```

---

## Tips for Working with This Prompt

- Phase 5 is the heaviest media-engineering phase yet. The render pipeline
  in Track A is where most bugs will live — review that plan section
  especially carefully before approving.
- After plan approval, Claude Code implements in dependency order
  (A → B → C → D → E → F → G → H). Pause between any two tracks to review.
- Commit after each track. Tag commits like `phase-5-track-a-complete`.
- Run tests yourself after each track. Don't trust "tests pass" without
  verifying with `pytest -k phase5_*`.

### Free-tier limits to watch

- **Pollinations.ai** has implicit rate limits — burst-friendly but a long
  reel with 5 visual beats can hit them. The fallback chain handles this,
  but if you're rendering many reels in a row expect Pexels-mode reels.
- **Hugging Face Inference API** free tier is gated by an account token
  the user must supply. Without it, Stable Diffusion is skipped silently
  and the chain falls through to Pexels.
- **Piper TTS voice files** are ~60 MB each. The four bundled voices total
  ~240 MB. Document this in the install guide so users don't blame disk
  bloat on the app.
- **Pexels free tier**: 200 requests/hour, 20,000/month. A daily-cap of
  10 reels × 5 beats × fallback rate stays well inside this.

### Manual prerequisites the user must install

- FFmpeg >= 6.0 (winget install Gyan.FFmpeg)
- Piper voice models (downloaded on first use; pre-download with
  scripts/download_piper_voices.ps1)
- Optional: a free Hugging Face account + token for the Stable Diffusion
  upgrade path. Set HUGGINGFACE_API_KEY in .env.

### If you only have time for the high-impact subset

Skip in this order:
- Track D (Storyboard renderer) — niche output format
- Track G (Brand Kit) — defaults are usable
- Track H (Hardening) — defer to a Phase 5.5 if needed; quotas can be
  hard-coded initially

Minimum viable Phase 5: Tracks A + B + F. That gives reel video output,
TTS narration, and shareable public URLs — enough to turn NexusMind from
a knowledge tool into a content-publishing tool.

### Phase 6 preview (out of scope here)

- Direct social media publishing (Instagram Graph API, TikTok Content
  Posting API, LinkedIn Share API) — requires app approval flows that
  take weeks.
- Multi-user collaboration (workspaces, shared graphs, RBAC) — the
  Phase 4 prompt and this Phase 5 prompt have deliberately preserved a
  single-user data model to make Phase 6 a focused migration.
- Mobile app (React Native or Expo) reusing the same APIs.
