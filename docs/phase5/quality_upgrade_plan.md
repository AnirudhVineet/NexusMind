# Phase 5.x — Quality Upgrade: Memes + Videos

**Status:** in progress
**Goal:** Make memes feel intentional (not random) and videos feel semi-professionally produced (motion + transitions instead of static stills + voiceover).

This document is a session checkpoint. If the conversation is compacted or
context is lost, a future agent should be able to pick up from here.

---

## 1. Session context — what already shipped before this work

Earlier in the session we already landed:

1. **Generations dashboard** — extended the Studio Library tab
   (`frontend/app/(app)/studio/page.tsx`) with filter pills + a new
   `MediaJobCard` that lists rendered reels/narrations/memes/storyboards
   alongside generated_content. Backed by `GET /api/media/jobs`
   (`backend/app/api/media.py:340-369`) and the `useMediaJobs` hook
   (`frontend/hooks/useMediaJobs.ts`).
2. **Dynamic voice catalog** — rewrote `list_voices()` in
   `backend/app/services/media/tts.py:355+` to probe each TTS provider
   (Piper, pyttsx3 SAPI, ElevenLabs, OpenAI), enumerate locally installed
   Windows SAPI voices via `pyttsx3.getProperty("voices")`, and tag Piper
   presets with `installed: true/false`. UI in `RenderReelModal.tsx` now
   groups voices by `<optgroup>` and disables uninstalled presets.
3. **Long-form video support** — threaded `length: "short" | "long"` from
   the script-generation request all the way through to the renderer.
   Long-form: 8–14 beats, 5–15 min, raised duration cap
   `reel_long_max_duration_seconds=900` in config.py.

The reel quota Redis keys (pattern `nm:quota:*:*:reel`) were also wiped
once at the user's request.

---

## 2. Current task — what this upgrade does

The user asked for **higher-quality memes and videos with stronger creative
direction**. Specifically:

- Memes: visuals, captions, and punchlines should align naturally, feel
  intentional rather than random.
- Videos: no more "still + voiceover". Need animations, motion graphics,
  dynamic transitions, engaging visual storytelling — semi-professional
  feel.

User approved the scope below and asked us to write this doc first.

### 2a. Memes — concrete plan

| # | Change | File | Why |
|---|--------|------|-----|
| M1 | Rewrite the meme LLM prompt to describe **each template's narrative structure** and required slot count | `backend/app/services/content_engine.py` (`generate_meme`, ~L329-401) | Today the LLM just gets a name list. With structural hints (Drake = "reject vs prefer", Expanding Brain = "4-step escalation", Distracted Boyfriend = "tempted by new over old", etc.) it'll pick intentionally. |
| M2 | Drop LLM temperature from 0.5 → 0.2 for meme generation | same file | More deterministic template selection. |
| M3 | Expose **all 16 templates** in `TEMPLATE_SIDECARS` to the LLM, not just the 5 in `_VALID_MEME_TEMPLATES` | same file (the constant near top of file) | The sidecars already exist with regions; only 5 of 16 are reachable today. |
| M4 | **Validate** the LLM output against `TEMPLATE_SIDECARS[chosen]["regions"]` — auto-correct panel-text count to match (truncate extra, pad with empties, retry with structured slots if too few). | same file, after the JSON parse | Stops Expanding Brain getting only 1 text. Also normalizes named-slot output (`{"level_1": ..., "level_2": ...}`) into `alt_panel_texts`. |
| M5 | Two-stage prompt option: ask LLM for the joke structure first ("comparison" / "escalation" / "binary choice" / "tempted by X over Y" / "single claim"), then map structure→template→generate text with structural slots. | same file | Higher quality, slower. Implement as a single prompt that emits both `structure` and `template_name`. |
| M6 | **Switch font** in `_draw_text_in_box` from Arial → Impact (the canonical meme font). Add fallback search: Impact.ttf → impact.ttf → arial.ttf → default. | `backend/app/services/content_engine.py` (`_draw_text_in_box`, ~L538-588) | Classic meme aesthetic. |
| M7 | **Replace `_resolve_panels` hardcoded heuristics with data-driven layout** from `TEMPLATE_SIDECARS`. Use fractional coords from the sidecar, multiply by `(width, height)`. Pull `font_size_pct`, `align`, `outline`, `uppercase` per region too. | `backend/app/services/content_engine.py` (`_resolve_panels`, ~L457-535) and `_draw_text_in_box` | Eliminates duplication. Unlocks the 11 templates whose layouts are defined but unreachable. Also fixes the silent text padding/dropping bug. |

**Skip for now:** generating fully custom background images per meme
(`custom` template) — high effort, only marginal aesthetic gain.

### 2b. Videos — concrete plan

| # | Change | File | Why |
|---|--------|------|-----|
| V1 | **Ken Burns on every beat clip** — `zoompan` filter for slow zoom-in or zoom-out (alternating per beat), 30 fps, output at aspect dims | `backend/app/services/media/reel_renderer.py` (`_build_beat_clip`, ~L364-412) | Cheapest "polish" win. Static stills become subtly moving. |
| V2 | **Bump source-image resolution** so Ken Burns has room to zoom into — request 1.5× the output dimensions from the visual provider, then `zoompan` crops into it | `backend/app/services/media/visual_provider.py` (`ASPECT_TO_DIM` and provider calls) | Without higher-res sources, zoom looks pixelated. |
| V3 | **Crossfade transitions between beats** — replace concat-demuxer with `filter_complex` `xfade` chain (0.5s overlap). Each xfade uses a different transition for variety (`fade`, `slideleft`, `wipeleft`, `dissolve`) chosen per beat-index. | `backend/app/services/media/reel_renderer.py` (`_concat_and_burn_subs`, ~L428-532) | Smooth, deliberate transitions instead of hard cuts. |
| V4 | **Animated beat title cards** — for each beat, generate a 1.5s title-card overlay that slides in from the bottom (or fades in) showing a short beat label. Use ASS subtitle animation tags (`{\fad}`, `{\move}`) at the start of each beat's caption block. | `backend/app/services/media/reel_renderer.py` (`_write_ass_subtitles`) | Gives every beat a clear visual signpost. |
| V5 | **Lower-third chyron** for hook + CTA — a colored bar that slides in from the bottom-left during the hook (first beat) and CTA (last beat), with brand-kit primary color. | `_write_ass_subtitles` + the watermark/drawtext stage of `_concat_and_burn_subs` | TV-news polish for the bookends. |
| V6 | **Per-word subtitle reveals** — split each beat's caption into words, distribute the beat's `duration` proportionally across words by length, emit ASS `\k` karaoke timing so each word fills in over time. Falls back to whole-beat captions if a beat has only 1 word. | `_write_ass_subtitles` | Modern social-video aesthetic, dramatically more engaging than block captions. |
| V7 | **Background music ducking** — if `backend/app/assets/music/{style}.mp3` exists, mix it under the voice at -18 dB and duck to -28 dB during speech segments using `sidechaincompress`. If the file doesn't exist, log a warning and skip silently. | `_concat_and_burn_subs` | Already partially documented in comments (line 11-13). Code never landed. |

**Skip for now:**

- **faster-whisper word-alignment** — V6's proportional-by-character timing is
  "good enough" for now; true word-alignment is a separate Track B work
  item that needs Whisper installed and force-aligned to TTS output.
- **Multi-image-per-beat parallax** — would require visual_provider rework
  to return 2-3 images and a more complex filter graph.
- **Sourcing real CC0 music tracks** — V7 only wires the *plumbing*. User
  will need to drop actual `ambient.mp3` / `energetic.mp3` / etc. into
  `backend/app/assets/music/` for it to kick in.

### 2c. Tradeoffs the user should know

- Render time will roughly **double** vs. the current pipeline. zoompan +
  xfade + per-word ASS rendering all force a re-encode (we can't keep the
  concat-demuxer fast path). On a 60-second reel expect ~30-90s instead
  of ~15-45s.
- The `quality: "preview"` setting will skip Ken Burns and crossfades to
  stay fast. Only `quality: "final"` gets the full polish treatment.

---

## 3. Implementation order

1. **M3** (expose all 16 templates) — trivial constant change. Ships value
   immediately even without other changes.
2. **M7** (data-driven `_resolve_panels` from sidecars) — unlocks the 11
   newly-exposed templates' layouts.
3. **M1 + M2 + M4** (structural prompt + temp + validation) — done as one
   integrated change inside `generate_meme`.
4. **M6** (Impact font) — small Pillow tweak in `_draw_text_in_box`.
5. **M5** (two-stage structure-aware prompt) — optional, layer on top of M1
   if time permits.
6. **V1 + V2** (Ken Burns + higher-res sources) — pair them, can't ship
   one without the other looking bad.
7. **V3** (xfade crossfade) — replaces the concat path.
8. **V4 + V5** (animated title cards + lower-third chyron) — both edit the
   ASS writer.
9. **V6** (per-word karaoke captions) — bigger ASS-writer change.
10. **V7** (music ducking) — wire the plumbing even if assets are missing;
    user can drop tracks in later.

`quality=preview` bypass for V1+V3 is implemented at step 7.

---

## 4. Verification per change

After each numbered change, the verification is:

- **Backend python**: `python -c "import ast; ast.parse(open(PATH).read())"`
- **Frontend TS**: `npx tsc --noEmit` (one pre-existing error in
  `studio/[id]/reel/page.tsx:124` is known and unrelated — ignore it).
- **End-to-end render**: trigger a reel render via the Studio UI on a
  short reel script; download the output and eyeball it. Check
  `MediaJob.error_message` if the render fails.
- **End-to-end meme**: regenerate a meme of each major template family
  (`drake`, `expanding_brain`, `distracted_boyfriend`, `change_my_mind`,
  `two_buttons`) and visually confirm the text lands in the right
  regions.

---

## 5. Open questions / known follow-ups

- **Music assets** — `backend/app/assets/music/` doesn't exist yet. The
  plumbing in V7 looks for `{style}.mp3` (ambient / energetic / quirky /
  corporate). Sourcing CC0 tracks is out of scope here.
- **Custom meme template** — the `custom` sidecar entry describes an
  AI-generated background. Implementing that means another visual_provider
  call per meme. Punt to a follow-up.
- **Karaoke subtitle timing** — V6 uses proportional-by-character timing,
  which can drift from the actual TTS speech. Future Track B can replace
  it with faster-whisper word-level alignment.
