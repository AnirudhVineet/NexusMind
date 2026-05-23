"""AI Content Repurposing Engine — Track H.

All public functions are async. They accept a list of source-chunk dicts
(each containing at minimum "id", "text_content", and optionally "embedding")
and return structured dicts ready to be stored in generated_content.content_json.

Fidelity checking computes cosine similarity between a generated claim and
the embeddings of the source chunks used. Claims that fall below the
configured threshold are flagged but not removed.
"""
from __future__ import annotations

import json
import math
import os
import re
import uuid
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.embedding import get_embedding_service

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants / paths
# ---------------------------------------------------------------------------

FIDELITY_THRESHOLD_DEFAULT = 0.75
STYLE_PROMPTS_DIR = Path(__file__).parent.parent / "prompts" / "content_styles"
ASSETS_DIR = Path(__file__).parent.parent / "assets"
MEME_TEMPLATES_DIR = ASSETS_DIR / "meme_templates"

# ---------------------------------------------------------------------------
# Meme templates
# ---------------------------------------------------------------------------
# Narrative-structure hints + slot specs for every template defined in
# `assets/meme_templates/sidecars.py`. The LLM is given THIS list (not just
# names) so it can match the template to the joke shape it's writing. The
# "structure" field is the deciding factor — pick the template whose
# structure matches the source claim.
#
# `slots` is the ordered list of region IDs the LLM must populate in
# `alt_panel_texts`. We validate after the LLM call: if the list is the
# wrong length we pad/truncate, and the renderer reads positions from
# TEMPLATE_SIDECARS to draw text in exactly the right place.
_MEME_TEMPLATE_GUIDE: list[dict[str, Any]] = [
    {
        "name": "Drake",
        "key": "drake",
        "structure": "reject vs prefer — contrast a bad/old option (top) with a better/new option (bottom)",
        "slots": ["reject", "approve"],
        "best_for": "binary preference, before/after, this-not-that takes",
    },
    {
        "name": "Two Buttons",
        "key": "two_buttons",
        "structure": "agonising choice between two equally tempting (or terrible) options",
        "slots": ["button_left", "button_right"],
        "best_for": "dilemmas, hard tradeoffs, paradoxes",
    },
    {
        "name": "Expanding Brain",
        "key": "expanding_brain",
        "structure": "4-step escalation — each level is a more enlightened (or absurd) version of the previous",
        "slots": ["level_1", "level_2", "level_3", "level_4"],
        "best_for": "progressive ideas, gradient takes, novice→expert→galaxy-brain",
    },
    {
        "name": "Distracted Boyfriend",
        "key": "distracted_boyfriend",
        "structure": "tempted by new shiny over loyal current — three roles: the boyfriend (the person/team), the girlfriend (current commitment), the other woman (the new temptation)",
        "slots": ["boyfriend", "girlfriend", "other_woman"],
        "best_for": "framework hopping, hype-driven distractions, jumping ship",
    },
    {
        "name": "Change My Mind",
        "key": "change_my_mind",
        "structure": "single provocative claim someone is daring you to disprove",
        "slots": ["claim"],
        "best_for": "spicy one-liners, contrarian takes, hot opinions",
    },
    {
        "name": "Galaxy Brain",
        "key": "galaxy_brain",
        "structure": "4-step cosmic-enlightenment escalation — last panel is the most absurd",
        "slots": ["level_1", "level_2", "level_3", "level_4"],
        "best_for": "tongue-in-cheek over-thinking, satirical big-brain takes",
    },
    {
        "name": "This Is Fine",
        "key": "this_is_fine",
        "structure": "denial-in-the-face-of-disaster — top text describes the chaos, bottom text is the cope",
        "slots": ["top", "bottom"],
        "best_for": "self-deprecating dev/ops humour, things-on-fire takes",
    },
    {
        "name": "Surprised Pikachu",
        "key": "surprised_pikachu",
        "structure": "setup→inevitable consequence — top text is the action, bottom text is the shocked reaction",
        "slots": ["top", "bottom"],
        "best_for": "ironic 'who could have predicted', cause→effect jokes",
    },
    {
        "name": "Roll Safe",
        "key": "roll_safe",
        "structure": "smug pseudo-insight — sets up a 'can't X if you Y' loophole",
        "slots": ["top", "bottom"],
        "best_for": "lazy-genius logic, sarcastic life hacks",
    },
    {
        "name": "Always Has Been",
        "key": "always_has_been",
        "structure": "astronaut realisation — one character says 'wait it's all X?', another replies 'always has been'",
        "slots": ["realization", "reply"],
        "best_for": "deflating mysteries, exposing obvious truths",
    },
    {
        "name": "Woman Yelling at Cat",
        "key": "woman_yelling_at_cat",
        "structure": "yelling accuser vs unbothered defendant — left panel is the angry argument, right panel is the deadpan reply",
        "slots": ["woman", "cat"],
        "best_for": "internet arguments, manager-vs-engineer, accusation-vs-denial",
    },
    {
        "name": "Hide the Pain Harold",
        "key": "hide_the_pain_harold",
        "structure": "smiling through suffering — top sets up the awful thing, bottom is the forced-smile cope",
        "slots": ["top", "bottom"],
        "best_for": "professional politeness, masked frustration",
    },
    {
        "name": "Gru's Plan",
        "key": "gru_plan",
        "structure": "4-step plan where the last step ruins everything — step_4 is the catastrophic realisation",
        "slots": ["step_1", "step_2", "step_3", "step_4"],
        "best_for": "well-intentioned plans with predictable failure modes",
    },
    {
        "name": "Mocking SpongeBob",
        "key": "mocking_spongebob",
        "structure": "mocking-repeat — top is the earnest claim someone made, bottom is the same claim rendered in mocking aLtErNaTiNg CaPs",
        "slots": ["top", "bottom"],
        "best_for": "rebuttals, sarcastic dismissals (bottom will be auto-alt-cased)",
    },
    {
        "name": "Success Kid",
        "key": "success_kid",
        "structure": "small triumph — top sets up the modest goal, bottom is the win",
        "slots": ["top", "bottom"],
        "best_for": "tiny wins, dev-life victories, finally-it-works takes",
    },
]

# Quick lookups
_MEME_GUIDE_BY_KEY: dict[str, dict[str, Any]] = {g["key"]: g for g in _MEME_TEMPLATE_GUIDE}
_MEME_GUIDE_BY_NAME: dict[str, dict[str, Any]] = {g["name"].lower(): g for g in _MEME_TEMPLATE_GUIDE}
_VALID_MEME_TEMPLATES = [g["name"] for g in _MEME_TEMPLATE_GUIDE]

_JSON_BLOCK_RE = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_style_prompt(style: str) -> str:
    path = STYLE_PROMPTS_DIR / f"{style}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _coerce_json(content: str) -> Any:
    """Parse JSON, falling back to extracting first balanced block."""
    content = content.strip()
    if not content:
        raise ValueError("empty LLM response")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = _JSON_BLOCK_RE.search(content)
        if not match:
            raise
        return json.loads(match.group(0))


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def _fidelity_threshold() -> float:
    """Read CONTENT_FIDELITY_THRESHOLD from env, falling back to default."""
    raw = os.environ.get("CONTENT_FIDELITY_THRESHOLD", "")
    try:
        return float(raw) if raw else FIDELITY_THRESHOLD_DEFAULT
    except ValueError:
        return FIDELITY_THRESHOLD_DEFAULT


async def _groq_complete(system: str, user: str, temperature: float = 0.3) -> str:
    """Call Groq (via AsyncOpenAI wrapper) for a text completion."""
    from openai import AsyncOpenAI

    from app.core.config import get_settings

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.groq_api_key, base_url=settings.groq_base_url)
    resp = await client.chat.completions.create(
        model=settings.llm_model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


async def _ollama_complete(system: str, user: str, temperature: float = 0.3) -> str:
    """Call Ollama as fallback for a text completion."""
    from openai import AsyncOpenAI

    from app.core.config import get_settings

    settings = get_settings()
    client = AsyncOpenAI(api_key="ollama", base_url=settings.ollama_base_url)
    resp = await client.chat.completions.create(
        model=settings.ollama_model_primary,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


async def _llm_complete(system: str, user: str, temperature: float = 0.3) -> str:
    """Try Groq first; fall back to Ollama on any error."""
    try:
        return await _groq_complete(system, user, temperature)
    except Exception as exc:
        log.warning("content_engine.groq_failed_fallback_ollama", error=str(exc))
        return await _ollama_complete(system, user, temperature)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def extract_key_claims(source_chunks: list[dict], n: int = 8) -> list[dict]:
    """Extract the N most important factual claims from source chunks.

    Returns a list of dicts: [{claim_text, importance (1-10), source_chunk_id}].
    """
    passages = "\n\n".join(
        f"[chunk_id={c.get('id', 'unknown')}] {c.get('text_content', '')[:300]}"
        for c in source_chunks
    )
    user_prompt = (
        f"Given these text passages, extract the {n} most important factual claims.\n"
        "Return a JSON array of objects with exactly these keys: "
        '{"claim_text": str, "importance": int 1-10, "source_chunk_id": str}\n\n'
        f"Passages:\n{passages}"
    )
    system_prompt = (
        "You extract structured factual claims from text. "
        "Respond ONLY with a valid JSON array. Do not include prose."
    )
    raw = await _llm_complete(system_prompt, user_prompt, temperature=0.1)
    try:
        parsed = _coerce_json(raw)
        if isinstance(parsed, list):
            return parsed
        # Sometimes the LLM wraps the array in an object
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    return v
    except Exception as exc:
        log.warning("content_engine.extract_key_claims_parse_error", error=str(exc))
    return []


async def classify_tone(source_chunks: list[dict]) -> str:
    """Classify the overall tone of passages.

    Returns one of: technical, narrative, opinionated, data-heavy.
    """
    passages = "\n\n".join(c.get("text_content", "")[:200] for c in source_chunks[:5])
    user_prompt = (
        "Classify the overall tone of these passages as exactly one of: "
        "technical, narrative, opinionated, data-heavy.\n"
        "Return just one word.\n\n"
        f"Passages:\n{passages}"
    )
    system_prompt = "You classify text tone. Reply with a single word only."
    valid = {"technical", "narrative", "opinionated", "data-heavy"}
    try:
        result = await _groq_complete(system_prompt, user_prompt, temperature=0.0)
        word = result.strip().lower().split()[0] if result.strip() else "technical"
        return word if word in valid else "technical"
    except Exception as exc:
        log.warning("content_engine.classify_tone_error", error=str(exc))
        return "technical"


async def check_source_fidelity(
    generated_claim: str,
    source_chunks: list[dict],
    threshold: float | None = None,
    strict_mode: bool = False,
) -> dict:
    """Cosine-similarity fidelity check between a generated claim and source chunks.

    Returns {"pass": bool, "max_sim": float, "best_source_chunk_id": str | None}.
    """
    effective_threshold = threshold
    if effective_threshold is None:
        effective_threshold = 0.85 if strict_mode else _fidelity_threshold()

    svc = get_embedding_service()
    claim_vecs = await svc.embed_batch([generated_claim])
    claim_vec = claim_vecs[0]

    best_sim = 0.0
    best_id: str | None = None

    for chunk in source_chunks:
        emb = chunk.get("embedding")
        if not emb:
            continue
        sim = _cosine(claim_vec, emb)
        if sim > best_sim:
            best_sim = sim
            best_id = str(chunk.get("id", ""))

    return {
        "pass": bool(best_sim >= effective_threshold),
        "max_sim": round(float(best_sim), 4),
        "best_source_chunk_id": best_id,
    }


async def _run_fidelity_checks(
    texts: list[tuple[str, str]],
    source_chunks: list[dict],
    strict_mode: bool = False,
) -> list[dict]:
    """Run fidelity checks over a list of (label, text) tuples.

    Returns a list of flag dicts with the label added.
    """
    flags = []
    for label, text in texts:
        if not text:
            continue
        result = await check_source_fidelity(text, source_chunks, strict_mode=strict_mode)
        flags.append({"label": label, **result})
    return flags


async def generate_reel_script(
    source_chunks: list[dict], style: str, length: str = "short"
) -> dict:
    """Generate a video reel script from source chunks.

    `length="short"` targets ~30-90s reels (3-5 beats).
    `length="long"` targets ~5-15min long-form videos (8-14 beats with
    explicit per-beat duration hints).

    Returns {"content": {...}, "fidelity_flags": [...]}.
    The content dict has: hook, beats (list), cta, caption, hashtags.
    Each beat has: text, source_chunk_id, and optionally duration_seconds.
    """
    style_prefix = _load_style_prompt(style)
    chunk_refs = "\n".join(
        f"- [chunk_id={c.get('id', '')}]: {c.get('text_content', '')[:300]}"
        for c in source_chunks
    )

    if length == "long":
        format_label = "long-form video"
        beats_instruction = (
            "Include 8-14 beats covering the source material in depth. "
            "Each beat object MUST include `duration_seconds` between 25 and "
            "75 — choose values so the total runtime lands between 5 and 15 "
            "minutes. The hook should be ~10s and the CTA ~8s. "
            "Beats should develop arguments, examples, and transitions; do "
            "not write bullet-point summaries."
        )
        structure = (
            '{"hook": {"text": str, "duration_seconds": int}, '
            '"beats": [{"text": str, "source_chunk_id": str, "duration_seconds": int}], '
            '"cta": {"text": str, "duration_seconds": int}, '
            '"caption": str, "hashtags": [str]}'
        )
    else:
        format_label = "short-form video reel"
        beats_instruction = "Include 3-5 beats."
        structure = (
            '{"hook": str, "beats": [{"text": str, "source_chunk_id": str}], '
            '"cta": str, "caption": str, "hashtags": [str]}'
        )

    user_prompt = (
        f"Create a {format_label} script based on the provided source material.\n"
        "Return ONLY a JSON object with this structure:\n"
        f"{structure}\n"
        f"{beats_instruction} Every beat must reference one of the provided chunk IDs.\n\n"
        f"Source material:\n{chunk_refs}"
    )
    system_prompt = (
        f"{style_prefix}\n"
        "You are a script writer. Respond ONLY with valid JSON. No prose."
    ).strip()

    raw = await _llm_complete(system_prompt, user_prompt, temperature=0.4)
    try:
        content = _coerce_json(raw)
        if not isinstance(content, dict):
            content = {"hook": raw, "beats": [], "cta": "", "caption": "", "hashtags": []}
    except Exception:
        content = {"hook": raw, "beats": [], "cta": "", "caption": "", "hashtags": []}

    # Persist the length choice so the renderer can pick up the right cap +
    # default per-beat durations.
    meta = content.get("_meta") if isinstance(content.get("_meta"), dict) else {}
    meta["length"] = length
    content["_meta"] = meta

    # Fidelity-check each beat
    beat_texts = [
        (f"beat_{i}", b.get("text", ""))
        for i, b in enumerate(content.get("beats", []))
    ]
    fidelity_flags = await _run_fidelity_checks(beat_texts, source_chunks)

    return {"content": content, "fidelity_flags": fidelity_flags}


def _format_template_guide_for_prompt() -> str:
    """Render the meme template guide as a numbered, LLM-friendly catalog."""
    lines: list[str] = []
    for g in _MEME_TEMPLATE_GUIDE:
        slots_str = ", ".join(g["slots"])
        lines.append(
            f"- {g['name']} ({len(g['slots'])} slots: {slots_str}) — "
            f"STRUCTURE: {g['structure']}. BEST FOR: {g['best_for']}."
        )
    return "\n".join(lines)


def _normalize_meme_output(
    content: dict[str, Any], template_name: str
) -> dict[str, Any]:
    """Validate + auto-correct the LLM's meme output against the chosen template.

    - Accept either an `alt_panel_texts` list or a dict of named slots
      ({"reject": "...", "approve": "..."}) and normalise to ordered list.
    - Pad to the template's required slot count, truncate excess.
    - For 2-slot templates, populate from top_text/bottom_text when
      `alt_panel_texts` is empty or partial.
    """
    guide = _MEME_GUIDE_BY_NAME.get(template_name.lower())
    if not guide:
        return content
    slots: list[str] = guide["slots"]

    raw_panels = content.get("alt_panel_texts")
    normalised: list[str]

    if isinstance(raw_panels, dict):
        # Named-slot dict — pull in slot order, missing keys default to "".
        normalised = [str(raw_panels.get(s, "") or "").strip() for s in slots]
    elif isinstance(raw_panels, list):
        normalised = [str(p or "").strip() for p in raw_panels]
    else:
        normalised = []

    # For 2-slot templates the LLM often only emits top/bottom — backfill.
    if len(slots) == 2:
        top = str(content.get("top_text") or "").strip()
        bottom = str(content.get("bottom_text") or "").strip()
        if not normalised or all(not p for p in normalised):
            normalised = [top, bottom]
        else:
            if len(normalised) < 1 and top:
                normalised.append(top)
            if len(normalised) < 2 and bottom:
                normalised.append(bottom)

    # For 1-slot templates ("Change My Mind") the LLM often puts the line
    # into `bottom_text` instead of `alt_panel_texts[0]`.
    if len(slots) == 1 and (not normalised or not normalised[0]):
        fallback = (
            str(content.get("bottom_text") or "").strip()
            or str(content.get("top_text") or "").strip()
            or str(content.get("caption") or "").strip()
        )
        normalised = [fallback]

    # Pad/truncate exactly to slot count.
    if len(normalised) < len(slots):
        normalised += [""] * (len(slots) - len(normalised))
    else:
        normalised = normalised[: len(slots)]

    content["alt_panel_texts"] = normalised
    # Keep top/bottom in sync with first two slots so legacy renderers
    # still display sensibly.
    if len(slots) >= 1 and not content.get("top_text"):
        content["top_text"] = normalised[0]
    if len(slots) >= 2 and not content.get("bottom_text"):
        content["bottom_text"] = normalised[1]
    return content


async def generate_meme(source_chunks: list[dict], style: str) -> dict:
    """Generate a meme from source chunks and render it with Pillow.

    Uses a structural prompt: the LLM is told each template's narrative
    shape and required slot list, then asked to first reason about which
    structure fits the source claim before picking a template. Output is
    validated against the chosen template's sidecar so panel-text counts
    always match the layout.

    Returns {"content": {...}, "file_path": str|None, "fidelity_flags": [...]}.
    """
    style_prefix = _load_style_prompt(style)
    chunk_refs = "\n".join(
        f"- [chunk_id={c.get('id', '')}]: {c.get('text_content', '')[:300]}"
        for c in source_chunks
    )

    template_catalog = _format_template_guide_for_prompt()

    user_prompt = (
        "Create a meme that meaningfully captures the source material.\n\n"
        "Step 1 — Decide the JOKE STRUCTURE that fits the source claim:\n"
        "  • binary contrast (this not that)\n"
        "  • hard tradeoff between two tempting options\n"
        "  • progressive escalation (3-4 levels)\n"
        "  • tempted by new over old (3 roles)\n"
        "  • mocking repeat of an earnest claim\n"
        "  • smug loophole / pseudo-insight\n"
        "  • shocked-by-obvious-consequence\n"
        "  • plan-that-backfires (4 steps)\n"
        "  • denial-in-disaster\n"
        "  • argument vs deadpan defendant\n"
        "  • single provocative one-liner\n\n"
        "Step 2 — Pick the SINGLE template whose STRUCTURE matches:\n"
        f"{template_catalog}\n\n"
        "Step 3 — Write the panel text. CRITICAL RULES:\n"
        "  • The number of strings in `alt_panel_texts` MUST equal the\n"
        "    template's slot count, in the order listed above.\n"
        "  • Each panel text is ONE short line (≤60 chars), no quotes,\n"
        "    no markdown, no emojis.\n"
        "  • Panels must read naturally as a single coherent joke — not\n"
        "    random unrelated lines.\n"
        "  • The punchline (last panel) should land — surprise, escalate,\n"
        "    or undercut the setup. Avoid generic 'me when X' filler.\n\n"
        "Return ONLY a JSON object with this exact structure:\n"
        "{\n"
        '  "structure": str (one of the structures from Step 1),\n'
        '  "template_name": str (EXACT name from the catalog),\n'
        '  "alt_panel_texts": [str] (length must match template slots),\n'
        '  "caption": str (one-sentence social caption, ≤140 chars),\n'
        '  "source_chunk_id": str (the chunk_id this meme is grounded in)\n'
        "}\n\n"
        f"Source material:\n{chunk_refs}"
    )
    system_prompt = (
        f"{style_prefix}\n"
        "You are a meme writer. You think about joke structure first, then "
        "pick the matching template, then write tight panel text where "
        "every line serves the punchline. Respond ONLY with valid JSON. "
        "No prose, no markdown fences."
    ).strip()

    # Low temperature: deterministic template selection.
    raw = await _llm_complete(system_prompt, user_prompt, temperature=0.2)
    try:
        content = _coerce_json(raw)
        if not isinstance(content, dict):
            raise ValueError("non-dict")
    except Exception:
        content = {
            "structure": "single provocative one-liner",
            "template_name": "Change My Mind",
            "alt_panel_texts": [raw[:100].strip()],
            "caption": "",
            "source_chunk_id": "",
        }

    # Resolve the template, falling back if the LLM picked something unknown.
    template_name = (content.get("template_name") or "").strip()
    guide = _MEME_GUIDE_BY_NAME.get(template_name.lower())
    if guide is None:
        # Best-effort: try matching the key form ("drake", "expanding_brain"),
        # otherwise fall back to Change My Mind (single-slot is forgiving).
        guide = _MEME_GUIDE_BY_KEY.get(
            template_name.lower().replace(" ", "_").replace("'", "")
        )
        if guide is None:
            log.info("content_engine.meme_unknown_template", picked=template_name)
            guide = _MEME_GUIDE_BY_NAME["change my mind"]
        content["template_name"] = guide["name"]

    # Validate + correct slot count.
    content = _normalize_meme_output(content, content["template_name"])

    # Locate the template PNG (filename derived from the key).
    template_filename = guide["key"] + ".png"
    template_path = MEME_TEMPLATES_DIR / template_filename
    if not template_path.exists():
        # Last-ditch: try Drake which is guaranteed to ship.
        template_path = MEME_TEMPLATES_DIR / "drake.png"
        if not template_path.exists():
            log.warning("content_engine.meme_template_missing", template=template_filename)

    file_path: str | None = None
    if template_path.exists():
        file_path = _render_meme(
            template_path=template_path,
            template_name=content["template_name"],
            top_text=str(content.get("top_text", "")),
            bottom_text=str(content.get("bottom_text", "")),
            alt_panel_texts=list(content.get("alt_panel_texts") or []),
        )

    # Fidelity check: use the entire panel block (more representative than
    # just the bottom text) as the claim.
    claim_text = " ".join(
        p for p in (content.get("alt_panel_texts") or []) if p
    ).strip() or content.get("caption", "")
    fidelity_flags = await _run_fidelity_checks(
        [("meme_text", claim_text)], source_chunks
    )

    return {"content": content, "file_path": file_path, "fidelity_flags": fidelity_flags}


def _render_meme(
    template_path: Path,
    top_text: str,
    bottom_text: str,
    template_name: str = "",
    alt_panel_texts: list[str] | None = None,
) -> str | None:
    """Render a meme PNG using Pillow with template-aware layout.

    Reads region coords + per-region style from `TEMPLATE_SIDECARS`
    (assets/meme_templates/sidecars.py) so every supported template
    automatically has the right text placement, alignment, font size,
    color, outline, and casing.
    """
    try:
        from PIL import Image

        from app.core.config import get_settings

        settings = get_settings()
        data_dir = Path(settings.storage_dir).resolve()
        out_dir = data_dir / "generated" / "memes"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{uuid.uuid4()}.png"

        img = Image.open(template_path).convert("RGBA")
        width, height = img.size

        panels = _resolve_panels(
            template_name=template_name,
            width=width,
            height=height,
            top_text=top_text,
            bottom_text=bottom_text,
            alt_panel_texts=alt_panel_texts or [],
        )

        for text, box, region_style in panels:
            if not text:
                continue
            _draw_text_in_box(img, text, box, region_style)

        img.save(str(out_path), format="PNG")
        return str(out_path)

    except Exception as exc:
        log.warning("content_engine.meme_render_failed", error=str(exc))
        return None


# Box = (x, y, w, h) — area on the template where text should be placed.
Box = tuple[int, int, int, int]


def _hex_to_rgba(s: str, default: tuple[int, int, int, int] = (255, 255, 255, 255)) -> tuple[int, int, int, int]:
    """Parse "#RRGGBBAA" or "#RRGGBB" into an (r,g,b,a) tuple."""
    if not s or not isinstance(s, str) or not s.startswith("#"):
        return default
    hexpart = s.lstrip("#")
    try:
        if len(hexpart) == 6:
            r = int(hexpart[0:2], 16); g = int(hexpart[2:4], 16); b = int(hexpart[4:6], 16)
            return (r, g, b, 255)
        if len(hexpart) == 8:
            r = int(hexpart[0:2], 16); g = int(hexpart[2:4], 16)
            b = int(hexpart[4:6], 16); a = int(hexpart[6:8], 16)
            return (r, g, b, a)
    except ValueError:
        pass
    return default


def _alt_caps(text: str) -> str:
    """Render text in aLtErNaTiNg CaPs (Mocking SpongeBob style)."""
    out: list[str] = []
    upper = True
    for ch in text:
        if ch.isalpha():
            out.append(ch.upper() if upper else ch.lower())
            upper = not upper
        else:
            out.append(ch)
    return "".join(out)


def _resolve_panels(
    template_name: str,
    width: int,
    height: int,
    top_text: str,
    bottom_text: str,
    alt_panel_texts: list[str],
) -> list[tuple[str, Box, dict[str, Any]]]:
    """Map text inputs onto template-specific panel boxes using sidecar metadata.

    Returns a list of (text, (x,y,w,h), region_style_dict) tuples ready to draw.
    `region_style_dict` carries font_size_pct, align, color, outline, uppercase,
    alternate_caps so the renderer can apply per-region styling.
    """
    from app.assets.meme_templates.sidecars import get_sidecar

    name = (template_name or "").strip()
    side = get_sidecar(name) or get_sidecar(name.replace(" ", "_"))

    # Unknown template: fall back to classic top/bottom layout across the
    # full width, with bottom text overlaying the lower portion.
    if not side or not side.get("regions"):
        default_style = {
            "font_size_pct": 0.07,
            "align": "center",
            "color": "#FFFFFFFF",
            "outline": "#000000FF",
        }
        return [
            (top_text, (10, int(height * 0.02), width - 20, int(height * 0.22)), default_style),
            (bottom_text, (10, int(height * 0.76), width - 20, int(height * 0.22)), default_style),
        ]

    regions = side["regions"]
    # Text supply preference: explicit alt_panel_texts (matched to slot count
    # by `_normalize_meme_output` before we get here), then top/bottom for
    # 2-region templates, then empty padding.
    if alt_panel_texts:
        texts = list(alt_panel_texts)
    else:
        texts = [t for t in (top_text, bottom_text) if t]

    # Pad/truncate to match region count
    while len(texts) < len(regions):
        texts.append("")
    texts = texts[: len(regions)]

    out: list[tuple[str, Box, dict[str, Any]]] = []
    for text, region in zip(texts, regions):
        # Sidecar coords are fractional in [0,1] — multiply by template dims.
        x = int(float(region.get("x", 0)) * width)
        y = int(float(region.get("y", 0)) * height)
        w = int(float(region.get("w", 1)) * width)
        h = int(float(region.get("h", 1)) * height)
        # Apply per-region case transforms.
        rendered = text or ""
        if region.get("uppercase"):
            rendered = rendered.upper()
        if region.get("alternate_caps"):
            rendered = _alt_caps(rendered)
        out.append((rendered, (x, y, w, h), region))
    return out


_IMPACT_FONT_CANDIDATES = [
    "impact.ttf",
    "Impact.ttf",
    "IMPACT.TTF",
    # macOS / linux ImageMagick locations
    "/Library/Fonts/Impact.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",
    # Windows system font location (PIL searches this implicitly but be explicit)
    r"C:\Windows\Fonts\impact.ttf",
    # Anton — the same condensed-bold style we already ship for reel ASS subs.
    "Anton-Regular.ttf",
    "anton.ttf",
    # Fallbacks
    "arialbd.ttf",
    "arial.ttf",
]


def _load_meme_font(size: int):
    """Load the best available meme font, preferring Impact → Anton → Arial."""
    from PIL import ImageFont

    for candidate in _IMPACT_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, size=size)
        except Exception:
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _draw_text_in_box(
    img,
    text: str,
    box: Box,
    region_style: dict[str, Any] | None = None,
) -> None:
    """Draw text inside `box` using per-region style from the sidecar.

    `region_style` may carry:
      • font_size_pct — fraction of img height to size the font (overrides
        the auto-fit ceiling but never the floor)
      • align — "left" | "center" | "right"
      • color — "#RRGGBBAA" hex string
      • outline — "#RRGGBBAA" hex string ("" disables outline)
    """
    from PIL import ImageDraw

    style = region_style or {}
    draw = ImageDraw.Draw(img)
    bx, by, bw, bh = box

    # Sidecar-driven starting font size (cap by available box dimensions).
    img_h = img.height
    pct = float(style.get("font_size_pct", 0.05) or 0.05)
    requested_size = max(12, int(img_h * pct))
    # Cap by what physically fits the box so very thin slots don't blow up.
    max_size = max(14, min(requested_size, max(14, bh // 2), max(14, bw // 6)))
    min_size = 10

    chosen_font = None
    chosen_lines: list[str] = []
    chosen_line_height = 0

    for size in range(max_size, min_size - 1, -2):
        font = _load_meme_font(size)
        if font is None:
            break
        lines = _wrap_to_width(draw, text, font, bw)
        bbox = draw.textbbox((0, 0), "Ag", font=font)
        line_height = (bbox[3] - bbox[1]) + 4
        total_h = len(lines) * line_height
        if total_h <= bh or size == min_size:
            chosen_font = font
            chosen_lines = lines
            chosen_line_height = line_height
            break

    if chosen_font is None:
        return

    align = (style.get("align") or "center").lower()
    color = _hex_to_rgba(style.get("color") or "#FFFFFFFF", default=(255, 255, 255, 255))
    outline_hex = style.get("outline") if "outline" in style else "#000000FF"
    outline = _hex_to_rgba(outline_hex or "", default=(0, 0, 0, 0))
    draw_outline = bool(outline_hex) and outline[3] > 0

    total_h = len(chosen_lines) * chosen_line_height
    y = by + max(0, (bh - total_h) // 2)

    for line in chosen_lines:
        bbox = draw.textbbox((0, 0), line, font=chosen_font)
        text_width = bbox[2] - bbox[0]
        if align == "left":
            x = bx
        elif align == "right":
            x = bx + max(0, bw - text_width)
        else:  # center
            x = bx + max(0, (bw - text_width) // 2)
        if draw_outline:
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    if dx or dy:
                        draw.text((x + dx, y + dy), line, font=chosen_font, fill=outline)
        draw.text((x, y), line, font=chosen_font, fill=color)
        y += chosen_line_height


def _wrap_to_width(draw, text: str, font, max_width: int) -> list[str]:
    """Word-wrap `text` into lines that each fit within max_width pixels."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


async def generate_thread(
    source_chunks: list[dict], style: str, platform: str = "twitter"
) -> dict:
    """Generate a social media thread from source chunks.

    Returns {"content": {"posts": [...], "total_posts": int}, "fidelity_flags": [...]}.
    """
    style_prefix = _load_style_prompt(style)
    platform_lower = platform.lower()

    if platform_lower == "linkedin":
        max_chars = 1300
        min_posts, max_posts = 3, 7
    else:
        # Default: twitter / X
        platform_lower = "twitter"
        max_chars = 280
        min_posts, max_posts = 5, 10

    chunk_refs = "\n".join(
        f"- [chunk_id={c.get('id', '')}]: {c.get('text_content', '')[:300]}"
        for c in source_chunks
    )
    user_prompt = (
        f"Create a {platform_lower} thread based on the provided source material.\n"
        f"Write {min_posts}-{max_posts} posts. Each post must be at most {max_chars} characters.\n"
        "Return ONLY a JSON array of objects with this structure:\n"
        '[{"index": int, "text": str, "source_chunk_id": str}]\n\n'
        f"Source material:\n{chunk_refs}"
    )
    system_prompt = (
        f"{style_prefix}\n"
        "You are a social media writer. Respond ONLY with a valid JSON array. No prose."
    ).strip()

    raw = await _llm_complete(system_prompt, user_prompt, temperature=0.4)
    try:
        posts = _coerce_json(raw)
        if isinstance(posts, dict):
            # Unwrap if LLM wrapped in object
            for v in posts.values():
                if isinstance(v, list):
                    posts = v
                    break
        if not isinstance(posts, list):
            posts = [{"index": 1, "text": raw[:max_chars], "source_chunk_id": ""}]
    except Exception:
        posts = [{"index": 1, "text": raw[:max_chars], "source_chunk_id": ""}]

    # Validate/truncate character counts
    for post in posts:
        if isinstance(post, dict) and len(post.get("text", "")) > max_chars:
            post["text"] = post["text"][:max_chars]

    # Fidelity-check each post
    post_texts = [
        (f"post_{p.get('index', i)}", p.get("text", ""))
        for i, p in enumerate(posts)
        if isinstance(p, dict)
    ]
    fidelity_flags = await _run_fidelity_checks(post_texts, source_chunks)

    return {
        "content": {"posts": posts, "total_posts": len(posts)},
        "fidelity_flags": fidelity_flags,
    }


async def generate_storyboard(source_chunks: list[dict], style: str) -> dict:
    """Generate a video storyboard from source chunks.

    Returns {"content": {"frames": [...]}, "fidelity_flags": [...]}.
    Each frame has: index, narration, visual, audio_note, duration_seconds, source_chunk_id.
    """
    style_prefix = _load_style_prompt(style)
    chunk_refs = "\n".join(
        f"- [chunk_id={c.get('id', '')}]: {c.get('text_content', '')[:300]}"
        for c in source_chunks
    )
    user_prompt = (
        "Create a video storyboard based on the provided source material.\n"
        "Return ONLY a JSON object with this structure:\n"
        '{"frames": [{"index": int, "narration": str, "visual": str, '
        '"audio_note": str, "duration_seconds": int, "source_chunk_id": str}]}\n'
        "Include 5-10 frames. Each frame must reference a source chunk.\n\n"
        f"Source material:\n{chunk_refs}"
    )
    system_prompt = (
        f"{style_prefix}\n"
        "You are a storyboard creator. Respond ONLY with valid JSON. No prose."
    ).strip()

    raw = await _llm_complete(system_prompt, user_prompt, temperature=0.4)
    try:
        content = _coerce_json(raw)
        if not isinstance(content, dict) or "frames" not in content:
            content = {"frames": []}
    except Exception:
        content = {"frames": []}

    # Fidelity-check each frame's narration
    frame_texts = [
        (f"frame_{f.get('index', i)}", f.get("narration", ""))
        for i, f in enumerate(content.get("frames", []))
        if isinstance(f, dict)
    ]
    fidelity_flags = await _run_fidelity_checks(frame_texts, source_chunks)

    return {"content": content, "fidelity_flags": fidelity_flags}


async def generate_caption(
    source_chunks: list[dict], style: str, platform: str = "instagram"
) -> dict:
    """Generate a social media caption from source chunks.

    Returns {"content": {"caption": str, "hashtags": [...]}, "fidelity_flags": [...]}.
    """
    style_prefix = _load_style_prompt(style)
    platform_lower = platform.lower()

    char_limits = {
        "instagram": 2200,
        "linkedin": 3000,
        "tiktok": 2200,
    }
    max_chars = char_limits.get(platform_lower, 2200)

    chunk_refs = "\n".join(
        f"- [chunk_id={c.get('id', '')}]: {c.get('text_content', '')[:300]}"
        for c in source_chunks
    )
    user_prompt = (
        f"Create a {platform_lower} caption based on the provided source material.\n"
        f"The caption must not exceed {max_chars} characters.\n"
        "Return ONLY a JSON object with this structure:\n"
        '{"caption": str, "hashtags": [str]}\n\n'
        f"Source material:\n{chunk_refs}"
    )
    system_prompt = (
        f"{style_prefix}\n"
        "You are a social media copywriter. Respond ONLY with valid JSON. No prose."
    ).strip()

    raw = await _llm_complete(system_prompt, user_prompt, temperature=0.4)
    try:
        content = _coerce_json(raw)
        if not isinstance(content, dict):
            content = {"caption": raw[:max_chars], "hashtags": []}
    except Exception:
        content = {"caption": raw[:max_chars], "hashtags": []}

    # Truncate if needed
    if len(content.get("caption", "")) > max_chars:
        content["caption"] = content["caption"][:max_chars]

    # Fidelity-check the caption
    fidelity_flags = await _run_fidelity_checks(
        [("caption", content.get("caption", ""))], source_chunks
    )

    return {"content": content, "fidelity_flags": fidelity_flags}
