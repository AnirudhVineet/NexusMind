"""Phase 5 Track A — Reel video rendering orchestrator.

Pipeline stages (status / progress_pct persisted at each step):
  1. preparing   (0  → 10)   — load content, validate, allocate scratch
  2. tts         (10 → 35)   — narrate each beat
  3. visuals     (35 → 70)   — fetch/generate one image per beat
  4. compose     (70 → 92)   — concat per-beat clips + audio (Ken Burns + xfade)
  5. finalize    (92 → 100)  — apply watermark/music, write final MP4

Reels are audio + video only — no burned-in subtitles. Music is mixed under
the voice with sidechain ducking. CC0 ambient tracks are bundled per style at
backend/app/assets/music/{style}.mp3.
"""
from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.media import reels_dir, scratch_dir
from app.services.media.ffmpeg_runner import ffprobe_duration, run_ffmpeg
from app.services.media.tts import synthesize as tts_synthesize
from app.services.media.visual_provider import (
    ASPECT_TO_DIM,
    generate_visuals_parallel,
)

log = get_logger(__name__)

# Aspect-ratio → (width, height) inherited from visual_provider for consistency
ASPECT_DIMS = ASPECT_TO_DIM


@dataclass
class Beat:
    kind: str  # "hook" | "beat" | "cta"
    text: str
    on_screen_text: str
    visual_direction: str
    duration: float


def _as_beat_dict(raw: Any) -> dict[str, Any]:
    # Reel scripts may use either flat-string or nested-dict shape per beat.
    if isinstance(raw, str):
        return {"text": raw}
    if isinstance(raw, dict):
        return raw
    return {}


def _coerce_beats(reel_json: dict[str, Any], length: str = "short") -> list[Beat]:
    # Long-form gives each beat ~3x airtime by default to stretch a short
    # script across a longer runtime. Explicit per-beat `duration_seconds`
    # in the script always wins.
    hook_default = 8.0 if length == "long" else 5.0
    beat_default = 30.0 if length == "long" else 10.0
    cta_default = 8.0 if length == "long" else 4.0

    out: list[Beat] = []
    hook = _as_beat_dict(reel_json.get("hook"))
    if hook.get("text"):
        out.append(
            Beat(
                kind="hook",
                text=str(hook.get("text", "")),
                on_screen_text=str(hook.get("on_screen_text") or hook.get("text", "")),
                visual_direction=str(hook.get("visual_direction") or hook.get("text", "")),
                duration=float(hook.get("duration_seconds") or hook_default),
            )
        )
    for raw_beat in reel_json.get("beats") or []:
        b = _as_beat_dict(raw_beat)
        if not b.get("text"):
            continue
        out.append(
            Beat(
                kind="beat",
                text=str(b.get("text", "")),
                on_screen_text=str(b.get("on_screen_text") or b.get("text", "")),
                visual_direction=str(b.get("visual_direction") or b.get("text", "")),
                duration=float(b.get("duration_seconds") or beat_default),
            )
        )
    cta = _as_beat_dict(reel_json.get("cta"))
    if cta.get("text"):
        out.append(
            Beat(
                kind="cta",
                text=str(cta.get("text", "")),
                on_screen_text=str(cta.get("on_screen_text") or cta.get("text", "")),
                visual_direction=str(cta.get("visual_direction") or cta.get("text", "")),
                duration=float(cta.get("duration_seconds") or cta_default),
            )
        )
    return out


def _validate_duration(beats: list[Beat], length: str = "short") -> float:
    settings = get_settings()
    cap = (
        settings.reel_long_max_duration_seconds
        if length == "long"
        else settings.reel_max_duration_seconds
    )
    total = sum(b.duration for b in beats)
    if total > cap:
        raise ValueError(
            f"Reel total duration {total:.1f}s exceeds cap {cap}s "
            f"(length={length})"
        )
    if total <= 0:
        raise ValueError("Reel has zero total duration")
    return total


# ─── Pipeline orchestrator ──────────────────────────────────────────────────


async def render_reel(media_job_id: str) -> None:
    """Run the full reel pipeline. Persists status + progress at each stage."""
    from app.db.session import AsyncSessionLocal
    from app.models.media_job import MediaJob
    from app.services.brandkit import load_brandkit

    jid = uuid.UUID(media_job_id)
    started = datetime.now(timezone.utc)

    async def _update(**fields: Any) -> None:
        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(select(MediaJob).where(MediaJob.id == jid))
            ).scalar_one_or_none()
            if row is None:
                return
            for k, v in fields.items():
                setattr(row, k, v)
            await session.commit()

    async def _load() -> tuple[MediaJob, dict[str, Any]] | None:
        async with AsyncSessionLocal() as session:
            row = (
                await session.execute(select(MediaJob).where(MediaJob.id == jid))
            ).scalar_one_or_none()
            if row is None:
                return None
            # Eager-load content row JSON if linked
            content_json: dict[str, Any] = {}
            if row.content_id:
                from app.models.generated_content import GeneratedContent

                cont = (
                    await session.execute(
                        select(GeneratedContent).where(
                            GeneratedContent.id == row.content_id
                        )
                    )
                ).scalar_one_or_none()
                if cont and isinstance(cont.content_json, dict):
                    content_json = cont.content_json
            # Detach from session before returning
            session.expunge(row)
            return row, content_json

    job_data = await _load()
    if job_data is None:
        log.error("reel.job_missing", media_job_id=media_job_id)
        return
    job, content_json = job_data
    params = job.params or {}
    aspect = params.get("aspect_ratio", "vertical")
    voice_id = params.get("voice_id")
    quality = params.get("quality", "final")
    watermark = bool(params.get("watermark", True))
    length = params.get("length") or content_json.get("_meta", {}).get("length") or "short"
    music_style = params.get("music_style")

    # Load brand kit (Phase 5 Track G propagation)
    async with AsyncSessionLocal() as bk_session:
        brand_kit = await load_brandkit(bk_session, job.user_id)

    scratch = scratch_dir() / str(jid)
    scratch.mkdir(parents=True, exist_ok=True)

    try:
        # Stage 1 — preparing
        await _update(
            status="preparing", stage="preparing", progress_pct=2, started_at=started
        )
        beats = _coerce_beats(content_json, length=length)
        if not beats:
            raise ValueError("Reel script has no beats")
        # Raises if the planned reel exceeds the per-length duration cap.
        _validate_duration(beats, length=length)
        await _update(progress_pct=10, stage="tts")

        # Stage 2 — TTS per beat
        audio_paths: list[Path] = []
        actual_durations: list[float] = []
        speaking_durations: list[float] = []  # true TTS audio length (silence excluded)
        tts_step = (35 - 10) / max(1, len(beats))
        for i, beat in enumerate(beats):
            out_path = scratch / f"beat_{i:02d}.wav"
            result = await tts_synthesize(beat.text, voice_id=voice_id, out_path=out_path)
            if result and result.path.exists():
                audio_paths.append(result.path)
                actual_durations.append(max(beat.duration, result.duration_seconds))
                speaking_durations.append(result.duration_seconds)
            else:
                # Silent fallback of the planned beat duration
                silent = await _make_silent_wav(scratch / f"beat_{i:02d}.wav", beat.duration)
                audio_paths.append(silent)
                actual_durations.append(beat.duration)
                # No real speech here — captions still need a target window.
                speaking_durations.append(beat.duration)
            await _update(progress_pct=int(10 + tts_step * (i + 1)))

        # Stage 3 — Visuals
        await _update(stage="visuals", progress_pct=35)
        visual_prompts = [_visual_prompt(b) for b in beats]
        # quality=preview skips slow providers via env hint — for now, just gen normally
        visual_results = await generate_visuals_parallel(visual_prompts, aspect)
        await _update(progress_pct=70)

        # Stage 4 — Compose
        await _update(stage="compose", progress_pct=72)
        per_clip = []
        for i, (beat, (vis_path, _prov)) in enumerate(zip(beats, visual_results)):
            clip = await _build_beat_clip(
                idx=i,
                visual_path=vis_path,
                audio_path=audio_paths[i],
                duration=actual_durations[i],
                aspect=aspect,
                scratch=scratch,
                quality=quality,
            )
            per_clip.append(clip)
            await _update(progress_pct=int(72 + (92 - 72) * ((i + 1) / len(beats))))

        # Stage 5 — Finalize
        await _update(stage="finalizing", progress_pct=93)
        output_path = reels_dir() / f"{jid}.mp4"
        rc = await _concat_and_finalize(
            per_clip,
            output_path,
            aspect=aspect,
            watermark=watermark,
            quality=quality,
            brand_kit=brand_kit,
            clip_durations=actual_durations,
            music_style=music_style,
        )
        if rc != 0:
            raise RuntimeError(f"FFmpeg concat exit code {rc}")

        size_bytes = output_path.stat().st_size if output_path.exists() else 0
        out_dur = ffprobe_duration(output_path) or sum(actual_durations)

        await _update(
            status="complete",
            stage="complete",
            progress_pct=100,
            output_path=str(output_path),
            output_size_bytes=size_bytes,
            duration_seconds=Decimal(f"{out_dur:.3f}"),
            completed_at=datetime.now(timezone.utc),
        )
        log.info("reel.complete", media_job_id=str(jid), duration_s=out_dur, size=size_bytes)
    except Exception as e:
        log.exception("reel.failed", media_job_id=str(jid))
        await _update(
            status="failed",
            stage="failed",
            error_message=str(e)[:2000],
            completed_at=datetime.now(timezone.utc),
        )
    finally:
        # Clean scratch dir (best effort)
        try:
            shutil.rmtree(scratch, ignore_errors=True)
        except Exception:  # pragma: no cover
            pass


# ─── Internal helpers ───────────────────────────────────────────────────────


async def _make_silent_wav(path: Path, duration: float) -> Path:
    """Write a silent WAV of the given duration via ffmpeg."""
    await run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=mono:sample_rate=22050",
            "-t",
            f"{duration:.3f}",
            str(path),
        ]
    )
    return path


def _visual_prompt(b: Beat) -> str:
    base = b.visual_direction or b.text
    # Light steer to keep images legible and brand-safe
    return f"{base.strip()[:240]} — cinematic, high contrast, simple composition"


async def _build_beat_clip(
    *,
    idx: int,
    visual_path: Path,
    audio_path: Path,
    duration: float,
    aspect: str,
    scratch: Path,
    quality: str = "final",
) -> Path:
    """Compose one beat with Ken Burns motion on the still image.

    Final quality: applies a slow `zoompan` zoom (alternating zoom-in /
    zoom-out per beat index) so static stills feel cinematic.
    Preview quality: skips zoom for ~2× faster render at slightly lower
    polish — still scales + crops to the target aspect.

    Source images are requested at 1.5× the output dimensions (see
    visual_provider.ASPECT_TO_SOURCE_DIM) which gives the zoom headroom
    without pixelation.
    """
    w, h = ASPECT_DIMS.get(aspect, ASPECT_DIMS["vertical"])
    fps = 30
    out = scratch / f"clip_{idx:02d}.mp4"

    if quality == "preview":
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},format=yuv420p"
        )
    else:
        # Ken Burns parameters. We zoom over the full beat duration. Even
        # beats zoom IN (start wide → end tight); odd beats zoom OUT.
        # The pan target (x,y) is slightly off-centre so the move feels
        # composed rather than mechanical.
        zoom_max = 1.20  # 20% zoom range — enough to feel alive, not nauseating.
        nframes = max(int(duration * fps), 1)
        # zoompan needs a per-frame zoom formula. We rebuild the source
        # image at the target output size internally and zoom inside it.
        # First scale the source up to a fixed-ratio canvas (1.5× output)
        # so we have room to crop.
        canvas_w, canvas_h = int(w * 1.5), int(h * 1.5)
        if idx % 2 == 0:
            # Zoom IN: zoom rises from 1.0 → zoom_max linearly across nframes.
            zoom_expr = f"min(1+({zoom_max - 1})*on/{nframes},{zoom_max})"
            # Pan from top-left to centre.
            x_expr = f"iw/2-(iw/zoom/2) + (iw*0.05)*(on/{nframes} - 0.5)"
            y_expr = f"ih/2-(ih/zoom/2) - (ih*0.05)*(on/{nframes} - 0.5)"
        else:
            # Zoom OUT: zoom falls from zoom_max → 1.0.
            zoom_expr = f"max({zoom_max}-({zoom_max - 1})*on/{nframes},1)"
            x_expr = f"iw/2-(iw/zoom/2) - (iw*0.05)*(on/{nframes} - 0.5)"
            y_expr = f"ih/2-(ih/zoom/2) + (ih*0.05)*(on/{nframes} - 0.5)"

        vf = (
            # Pre-scale + pad to a stable canvas so zoompan has a known size.
            f"scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,"
            f"crop={canvas_w}:{canvas_h},setsar=1,"
            # zoompan reads `on` (output frame index). We force exact
            # output dims here too because zoompan's `s=` is post-zoom.
            f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':"
            f"d=1:s={w}x{h}:fps={fps},"
            f"format=yuv420p"
        )

    args = [
        "-loop",
        "1",
        "-i",
        str(visual_path),
        "-i",
        str(audio_path),
        "-t",
        f"{duration:.3f}",
        "-vf",
        vf,
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast" if quality == "preview" else "fast",
        "-tune",
        "stillimage",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        # NOTE: deliberately no `-shortest` — if TTS audio is shorter than
        # the planned beat duration we still want the visual + silence to
        # play for the full `-t` window. Otherwise the clip on disk would
        # be shorter than `actual_durations` claims, and the downstream
        # xfade math would compute offsets past the end of the clip.
        str(out),
    ]
    rc = await run_ffmpeg(args)
    if rc != 0 or not out.exists():
        raise RuntimeError(f"Failed to build beat clip {idx}")
    return out


_XFADE_TRANSITIONS = ["fade", "dissolve", "slideleft", "wipeleft", "radial", "smoothleft"]
_XFADE_DURATION = 0.5  # seconds of overlap between adjacent beats


def _resolve_music_track(style: Optional[str]) -> Optional[Path]:
    """Locate `assets/music/{style}.mp3`. Returns None if missing."""
    if not style or style == "none":
        return None
    music_dir = Path(__file__).parent.parent.parent / "assets" / "music"
    # Try a couple of common extensions / casings.
    for ext in (".mp3", ".m4a", ".ogg", ".wav"):
        candidate = music_dir / f"{style}{ext}"
        if candidate.exists():
            return candidate
    return None


async def _concat_and_finalize(
    per_clip: list[Path],
    output_path: Path,
    *,
    aspect: str,
    watermark: bool,
    quality: str,
    brand_kit: dict[str, Any] | None = None,
    clip_durations: list[float] | None = None,
    music_style: Optional[str] = None,
) -> int:
    """Concat per-beat MP4s, optionally apply watermark + ducked music, and
    write the final reel.

    Quality modes:
      • preview — concat demuxer (no xfade), single-pass.
      • final — filter_complex xfade chain (0.5s overlap) cycling through
        fade/dissolve/slideleft/wipeleft/radial/smoothleft.

    When no watermark and no music style are requested, the intermediate
    xfade output IS the final output and no second encode pass runs.
    """
    if not per_clip:
        raise RuntimeError("No clips to concat")

    parent_dir = per_clip[0].parent

    music_path = _resolve_music_track(music_style)
    need_second_pass = bool(watermark) or music_path is not None

    # When no second pass will run, write directly to output_path so we avoid
    # a needless re-encode.
    intermediate = (parent_dir / "concat.mp4") if need_second_pass else output_path

    # ── Build the visual + audio concat ────────────────────────────────────
    use_xfade = (
        quality != "preview"
        and clip_durations is not None
        and len(clip_durations) == len(per_clip)
        and len(per_clip) >= 2
    )

    # Intermediate quality is high (CRF 18) when we know a second encode pass
    # follows — that way the re-encode doesn't compound compression artifacts.
    # When this IS the final file, we use the same balanced CRF as the final
    # pass (20) so the output isn't unnecessarily large.
    inter_crf = "18" if need_second_pass else "20"
    inter_preset = "fast" if need_second_pass else "medium"

    if not use_xfade:
        # Cheap path — concat demuxer (copy codec where possible).
        list_file = parent_dir / "concat.txt"
        list_file.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in per_clip), encoding="utf-8"
        )
        rc = await run_ffmpeg(
            ["-f", "concat", "-safe", "0", "-i", str(list_file),
             "-c", "copy", "-movflags", "+faststart", str(intermediate)]
        )
        if rc != 0 or not intermediate.exists():
            # Re-encode fallback if codec-copy refused (incompatible streams).
            rc = await run_ffmpeg(
                ["-f", "concat", "-safe", "0", "-i", str(list_file),
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", inter_crf,
                 "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "160k",
                 "-movflags", "+faststart", str(intermediate)]
            )
            if rc != 0:
                return rc
    else:
        # ── xfade chain ─────────────────────────────────────────────────
        # For N clips we need N-1 xfade nodes. Each xfade offset =
        # sum(prev clip durations) - (i+1)*xfade_duration; the audio is
        # joined separately via acrossfade with the same overlap.
        n = len(per_clip)
        xd = _XFADE_DURATION
        # Ensure no clip is shorter than the crossfade overlap.
        clean_durs = [max(d, xd + 0.2) for d in (clip_durations or [])]

        inputs: list[str] = []
        for p in per_clip:
            inputs.extend(["-i", str(p)])

        # Video chain
        v_chain: list[str] = []
        prev_label = "0:v"
        running_offset = clean_durs[0] - xd
        for i in range(1, n):
            transition = _XFADE_TRANSITIONS[(i - 1) % len(_XFADE_TRANSITIONS)]
            out_label = f"v{i}"
            v_chain.append(
                f"[{prev_label}][{i}:v]xfade=transition={transition}:"
                f"duration={xd}:offset={running_offset:.3f}[{out_label}]"
            )
            prev_label = out_label
            running_offset += clean_durs[i] - xd

        # Audio chain — acrossfade pairs the streams the same way.
        a_chain: list[str] = []
        prev_a = "0:a"
        for i in range(1, n):
            out_a = f"a{i}"
            a_chain.append(
                f"[{prev_a}][{i}:a]acrossfade=d={xd}:c1=tri:c2=tri[{out_a}]"
            )
            prev_a = out_a

        # Normalise pixel format on the final video node so downstream
        # consumers (and the no-second-pass fast path) get yuv420p reliably.
        v_chain.append(f"[{prev_label}]format=yuv420p[vout]")
        final_v = "[vout]"
        final_a = f"[{prev_a}]"
        filter_complex = ";".join(v_chain + a_chain)

        args = [
            *inputs,
            "-filter_complex", filter_complex,
            "-map", final_v,
            "-map", final_a,
            "-c:v", "libx264",
            "-preset", inter_preset,
            "-crf", inter_crf,
            "-c:a", "aac",
            "-b:a", "160k",
            "-movflags", "+faststart",
            str(intermediate),
        ]
        rc = await run_ffmpeg(args)
        if rc != 0 or not intermediate.exists():
            log.warning("reel.xfade.failed_falling_back_to_concat")
            # Fall back to the cheap demuxer path so the user gets a
            # video instead of a hard failure.
            list_file = parent_dir / "concat.txt"
            list_file.write_text(
                "\n".join(f"file '{p.as_posix()}'" for p in per_clip), encoding="utf-8"
            )
            rc = await run_ffmpeg(
                ["-f", "concat", "-safe", "0", "-i", str(list_file),
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", inter_crf,
                 "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "160k",
                 "-movflags", "+faststart", str(intermediate)]
            )
            if rc != 0:
                return rc

    # If neither watermark nor music is requested, the intermediate IS the
    # final output — we're done.
    if not need_second_pass:
        return 0

    # ── Watermark + optional music duck (second pass) ──────────────────────
    vf_parts: list[str] = []
    if watermark:
        wm_path = (brand_kit or {}).get("watermark_asset_path") if brand_kit else None
        wm_opacity = (brand_kit or {}).get("watermark_opacity", 0.6)
        if wm_path:
            log.info("reel.brandkit.watermark_asset_pending", path=wm_path)
        wm_text = "nexusmind"
        color_hex = "FFFFFF"
        if brand_kit and brand_kit.get("primary_color"):
            color_hex = brand_kit["primary_color"].lstrip("#")[:6] or "FFFFFF"
        vf_parts.append(
            f"drawtext=text='{wm_text}':"
            f"fontcolor=0x{color_hex}@{float(wm_opacity):.2f}:fontsize=22:"
            "x=w-tw-24:y=h-th-24"
        )
    # `format=yuv420p` keeps Quicktime/Safari/iOS happy across pipelines.
    vf_parts.append("format=yuv420p")
    vf = ",".join(vf_parts)

    preset = "veryfast" if quality == "preview" else "medium"
    crf = "26" if quality == "preview" else "20"

    if music_path is None:
        args = [
            "-i", str(intermediate),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", crf,
            "-c:a", "aac",
            "-b:a", "160k",
            "-movflags", "+faststart",
            str(output_path),
        ]
        return await run_ffmpeg(args)

    # Music present — mix it under the voice with sidechain compression
    # so the music dips by ~10dB when the narrator is speaking.
    log.info("reel.music.duck", style=music_style, track=str(music_path))
    filter_complex = (
        f"[0:v]{vf}[v];"
        # Music branch: loop indefinitely, reduce base volume to -16 dB,
        # then duck dynamically when the voice is active.
        "[1:a]aloop=loop=-1:size=2e9,volume=0.16[mus0];"
        "[mus0][0:a]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400[mus];"
        # Mix voice + ducked music, ending at the video's duration.
        "[0:a][mus]amix=inputs=2:duration=first:dropout_transition=0:weights=1.0 0.7[a]"
    )
    args = [
        "-i", str(intermediate),
        "-stream_loop", "-1", "-i", str(music_path),
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", crf,
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ]
    return await run_ffmpeg(args)
