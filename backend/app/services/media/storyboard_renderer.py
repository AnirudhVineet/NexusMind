"""Phase 5 Track D — Visual storyboard renderer.

Inputs:
  • A Phase 4 generated_content row of content_type='storyboard' whose
    content_json has shape:
       { frames: [{ index, narration, visual, audio_note,
                    duration_seconds, source_chunk_id }] }

Outputs (one of):
  • PDF  — one frame per page (reportlab)
  • image_series — frame_NN.png + manifest.json under
       DATA_DIR/generated/storyboards/{job_id}/
  • html_slides  — index.html (reveal.js minimal) under same dir

Each frame's visual is fetched via the Track A visual_provider chain and
narration is synthesised via the Track B TTS chain. The render hard-caps
at storyboard_max_frames (default 12).
"""
from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.media import scratch_dir, storyboards_dir
from app.services.media.tts import synthesize as tts_synthesize
from app.services.media.visual_provider import generate_visuals_parallel

log = get_logger(__name__)

REVEAL_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8">
<title>{title}</title>
<style>
  body{{margin:0;font-family:system-ui,sans-serif;background:#0c0c0e;color:#eee}}
  .slide{{padding:48px;min-height:90vh;border-bottom:1px solid #222}}
  .slide img{{max-width:100%;border-radius:8px}}
  .narration{{font-size:1.1rem;line-height:1.5;margin:24px 0}}
  .meta{{font-size:.85rem;color:#888;margin-top:12px}}
  .frame-number{{display:inline-block;background:#3a3a55;padding:4px 12px;border-radius:999px;font-size:.8rem}}
  audio{{width:100%;margin-top:12px}}
</style>
</head><body>
{slides}
</body></html>"""

REVEAL_SLIDE_TEMPLATE = """<section class="slide">
  <span class="frame-number">Frame {index}</span>
  {image_html}
  <p class="narration">{narration}</p>
  {audio_html}
  <p class="meta">Visual: {visual}<br>Duration: {duration}s</p>
</section>"""


@dataclass
class Frame:
    index: int
    narration: str
    visual: str
    audio_note: str
    duration: float
    source_chunk_id: Optional[str] = None


def coerce_frames(content_json: dict[str, Any]) -> list[Frame]:
    raw = content_json.get("frames") or []
    out: list[Frame] = []
    for i, f in enumerate(raw, start=1):
        if not isinstance(f, dict):
            continue
        out.append(
            Frame(
                index=int(f.get("index") or i),
                narration=str(f.get("narration") or ""),
                visual=str(f.get("visual") or ""),
                audio_note=str(f.get("audio_note") or ""),
                duration=float(f.get("duration_seconds") or 5.0),
                source_chunk_id=str(f.get("source_chunk_id")) if f.get("source_chunk_id") else None,
            )
        )
    return out


def _enforce_frame_cap(frames: list[Frame]) -> list[Frame]:
    settings = get_settings()
    if len(frames) > settings.storyboard_max_frames:
        raise ValueError(
            f"Storyboard has {len(frames)} frames; cap is {settings.storyboard_max_frames}"
        )
    return frames


# ─── Public pipeline ────────────────────────────────────────────────────────


async def render_storyboard(media_job_id: str) -> None:
    """Top-level orchestrator. Persists status + progress to media_jobs."""
    from app.db.session import AsyncSessionLocal
    from app.models.generated_content import GeneratedContent
    from app.models.media_job import MediaJob

    jid = uuid.UUID(media_job_id)

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

    async with AsyncSessionLocal() as session:
        job = (
            await session.execute(select(MediaJob).where(MediaJob.id == jid))
        ).scalar_one_or_none()
        if job is None:
            log.error("storyboard.job_missing", media_job_id=media_job_id)
            return
        params = job.params or {}
        fmt = params.get("format", "pdf")
        content_id = job.content_id
        content_json: dict[str, Any] = {}
        if content_id:
            cont = (
                await session.execute(
                    select(GeneratedContent).where(GeneratedContent.id == content_id)
                )
            ).scalar_one_or_none()
            if cont and isinstance(cont.content_json, dict):
                content_json = cont.content_json

    out_dir = storyboards_dir() / str(jid)
    out_dir.mkdir(parents=True, exist_ok=True)
    scratch = scratch_dir() / f"sb_{jid}"
    scratch.mkdir(parents=True, exist_ok=True)

    try:
        await _update(
            status="preparing",
            stage="preparing",
            progress_pct=5,
            started_at=datetime.now(timezone.utc),
        )
        frames = coerce_frames(content_json)
        if not frames:
            raise ValueError("Storyboard has no frames")
        frames = _enforce_frame_cap(frames)

        await _update(stage="visuals", progress_pct=20)
        prompts = [f.visual or f.narration for f in frames]
        visuals = await generate_visuals_parallel(prompts, "landscape")

        await _update(stage="audio", progress_pct=50)
        audio_paths: list[Optional[Path]] = []
        for i, f in enumerate(frames):
            if not f.narration.strip():
                audio_paths.append(None)
                continue
            out = scratch / f"narr_{i:02d}.wav"
            r = await tts_synthesize(f.narration, out_path=out)
            audio_paths.append(r.path if r else None)
            await _update(progress_pct=int(50 + 30 * ((i + 1) / len(frames))))

        await _update(stage="compose", progress_pct=82)

        if fmt == "pdf":
            output_path = out_dir / "storyboard.pdf"
            _render_pdf(output_path, frames, visuals, audio_paths)
        elif fmt == "image_series":
            output_path = _render_image_series(out_dir, frames, visuals, audio_paths)
        elif fmt == "html_slides":
            output_path = _render_html_slides(out_dir, frames, visuals, audio_paths)
        else:
            raise ValueError(f"Unknown storyboard format: {fmt}")

        await _update(stage="finalizing", progress_pct=95)
        size = output_path.stat().st_size if output_path.is_file() else _dir_size(output_path)
        await _update(
            status="complete",
            stage="complete",
            progress_pct=100,
            output_path=str(output_path),
            output_size_bytes=size,
            completed_at=datetime.now(timezone.utc),
        )
        log.info("storyboard.complete", media_job_id=str(jid), format=fmt)
    except Exception as e:
        log.exception("storyboard.failed", media_job_id=str(jid))
        await _update(
            status="failed",
            stage="failed",
            error_message=str(e)[:2000],
            completed_at=datetime.now(timezone.utc),
        )
    finally:
        try:
            shutil.rmtree(scratch, ignore_errors=True)
        except Exception:
            pass


# ─── Internal renderers ─────────────────────────────────────────────────────


def _dir_size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def _render_pdf(
    out_path: Path,
    frames: list[Frame],
    visuals: list[tuple[Path, str]],
    audio_paths: list[Optional[Path]],
) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Image as RLImage,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    doc = SimpleDocTemplate(str(out_path), pagesize=letter)
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    body = styles["BodyText"]
    meta = ParagraphStyle(
        "meta", parent=body, fontSize=9, textColor="#777777"
    )

    story = []
    for i, frame in enumerate(frames):
        vis_path = visuals[i][0] if i < len(visuals) else None
        story.append(Paragraph(f"Frame {frame.index}", h1))
        if vis_path and vis_path.exists():
            try:
                story.append(RLImage(str(vis_path), width=6 * inch, height=3.4 * inch))
            except Exception:
                pass
        story.append(Spacer(1, 8))
        if frame.narration:
            story.append(Paragraph(f"<b>Narration:</b> {frame.narration}", body))
        if frame.visual:
            story.append(Paragraph(f"<b>Visual:</b> {frame.visual}", meta))
        if frame.audio_note:
            story.append(Paragraph(f"<b>Audio:</b> {frame.audio_note}", meta))
        story.append(Paragraph(f"Duration: {frame.duration:.1f}s", meta))
        # Attach audio as a file if available — reportlab supports embedded files
        ap = audio_paths[i] if i < len(audio_paths) else None
        if ap and ap.exists():
            story.append(Paragraph(f"<i>Audio file attached: {ap.name}</i>", meta))
        if i < len(frames) - 1:
            story.append(PageBreak())
    doc.build(story)


def _render_image_series(
    out_dir: Path,
    frames: list[Frame],
    visuals: list[tuple[Path, str]],
    audio_paths: list[Optional[Path]],
) -> Path:
    """Copy visuals + write manifest.json into out_dir."""
    manifest: list[dict[str, Any]] = []
    for i, frame in enumerate(frames):
        vis = visuals[i][0] if i < len(visuals) else None
        if vis and vis.exists():
            dst = out_dir / f"frame_{frame.index:02d}{vis.suffix}"
            shutil.copyfile(vis, dst)
        else:
            dst = None
        audio = audio_paths[i] if i < len(audio_paths) else None
        if audio and audio.exists():
            adst = out_dir / f"frame_{frame.index:02d}_audio.wav"
            shutil.copyfile(audio, adst)
        else:
            adst = None
        manifest.append(
            {
                "index": frame.index,
                "image": str(dst.name) if dst else None,
                "audio": str(adst.name) if adst else None,
                "narration": frame.narration,
                "visual": frame.visual,
                "duration_seconds": frame.duration,
                "source_chunk_id": frame.source_chunk_id,
            }
        )
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return out_dir


def _render_html_slides(
    out_dir: Path,
    frames: list[Frame],
    visuals: list[tuple[Path, str]],
    audio_paths: list[Optional[Path]],
) -> Path:
    """Self-contained HTML slide deck under out_dir/index.html."""
    slides_html: list[str] = []
    for i, frame in enumerate(frames):
        vis = visuals[i][0] if i < len(visuals) else None
        image_html = ""
        if vis and vis.exists():
            dst = out_dir / f"frame_{frame.index:02d}{vis.suffix}"
            shutil.copyfile(vis, dst)
            image_html = f'<img src="{dst.name}" alt="Frame {frame.index}">'
        audio_html = ""
        ap = audio_paths[i] if i < len(audio_paths) else None
        if ap and ap.exists():
            adst = out_dir / f"frame_{frame.index:02d}.wav"
            shutil.copyfile(ap, adst)
            audio_html = f'<audio controls src="{adst.name}"></audio>'
        slides_html.append(
            REVEAL_SLIDE_TEMPLATE.format(
                index=frame.index,
                image_html=image_html,
                narration=_html_escape(frame.narration),
                audio_html=audio_html,
                visual=_html_escape(frame.visual),
                duration=f"{frame.duration:.1f}",
            )
        )

    index = out_dir / "index.html"
    index.write_text(
        REVEAL_TEMPLATE.format(title="Storyboard", slides="\n".join(slides_html)),
        encoding="utf-8",
    )
    return index


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
