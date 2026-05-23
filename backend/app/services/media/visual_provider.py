"""Phase 5 Track A — Visual provider chain with graceful fallback.

Provider order (each times out after 25 s):
  1. PollinationsProvider   — free, no key required
  2. HuggingFaceSDProvider  — gated on HUGGINGFACE_API_KEY
  3. PexelsProvider         — gated on PEXELS_API_KEY (free tier)
  4. SolidColorFallback     — always succeeds

Each successful call writes a PNG (or JPEG) to MEDIA_DATA_DIR/scratch and
returns its path. Caching is keyed by sha256(prompt + aspect + provider).
"""
from __future__ import annotations

import asyncio
import hashlib
import urllib.parse
from pathlib import Path
from typing import Optional, Protocol

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.media import media_root

log = get_logger(__name__)

_PROVIDER_TIMEOUT_S = 25.0

# Output video dimensions per aspect ratio (the final reel resolution).
ASPECT_TO_DIM: dict[str, tuple[int, int]] = {
    "vertical": (1080, 1920),
    "square": (1080, 1080),
    "landscape": (1920, 1080),
}

# Source-image request dimensions — 1.25× the output dims so Ken Burns
# (zoompan) has headroom to crop into without pixelation. 1.5× was too
# heavy: per-beat ffmpeg encoding ran 30–46s. 1.25× still gives a 25%
# zoom range while letting CPUs finish a beat in ~10s. Providers with
# fixed-size APIs ignore this and clamp to their native sizes.
ASPECT_TO_SOURCE_DIM: dict[str, tuple[int, int]] = {
    "vertical": (1350, 2400),
    "square": (1350, 1350),
    "landscape": (2400, 1350),
}

# ── Provider-down cache ────────────────────────────────────────────────────
# When a provider returns an unrecoverable error (402 Payment Required, 401
# Unauthorized, etc.) we remember the failure for `_PROVIDER_DOWN_TTL` so
# subsequent beats in the same render — and renders for the next few minutes
# — skip the provider instantly instead of paying the full HTTP timeout
# each time.
_PROVIDER_DOWN_TTL = 300.0  # seconds


def _now() -> float:
    import time

    return time.monotonic()


_provider_down_until: dict[str, float] = {}

# HTTP status codes that signal "don't bother retrying for a while" — auth,
# billing, rate-limiting beyond what's reasonable.
_FATAL_HTTP_STATUSES: frozenset[int] = frozenset({401, 402, 403, 429})


def _provider_is_down(name: str) -> bool:
    expiry = _provider_down_until.get(name)
    if expiry is None:
        return False
    if expiry <= _now():
        _provider_down_until.pop(name, None)
        return False
    return True


def _mark_provider_down(name: str, reason: str) -> None:
    _provider_down_until[name] = _now() + _PROVIDER_DOWN_TTL
    log.warning(
        "visual.provider.marked_down",
        provider=name,
        reason=reason,
        ttl_s=_PROVIDER_DOWN_TTL,
    )


class VisualProvider(Protocol):
    name: str

    async def generate(
        self, prompt: str, aspect: str, seed: int = 0
    ) -> Optional[Path]: ...


def _cache_key(provider: str, prompt: str, aspect: str) -> str:
    raw = f"{provider}|{aspect}|{prompt}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _cache_path(provider: str, prompt: str, aspect: str, ext: str = ".png") -> Path:
    cache_dir = media_root() / "visual_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{_cache_key(provider, prompt, aspect)}{ext}"


# ─── Pollinations.ai (free, no key) ─────────────────────────────────────────


class PollinationsProvider:
    name = "pollinations"

    # Pollinations' free tier responds reliably up to ~1024 on the long
    # edge. Larger requests frequently come back as solid-colour placeholders
    # or time out, which is exactly the "blank image" failure mode users hit.
    _MAX_EDGE = 1024

    def _clamped_dims(self, aspect: str) -> tuple[int, int]:
        w, h = ASPECT_TO_SOURCE_DIM.get(aspect, ASPECT_TO_SOURCE_DIM["vertical"])
        long_edge = max(w, h)
        if long_edge <= self._MAX_EDGE:
            return w, h
        scale = self._MAX_EDGE / long_edge
        return max(1, int(w * scale)), max(1, int(h * scale))

    async def generate(
        self, prompt: str, aspect: str, seed: int = 0
    ) -> Optional[Path]:
        if _provider_is_down(self.name):
            # We saw a fatal status recently — skip without burning the
            # network timeout, the orchestrator will fall through.
            return None
        cached = _cache_path(self.name, prompt, aspect)
        if cached.exists():
            return cached
        w, h = self._clamped_dims(aspect)
        encoded = urllib.parse.quote(prompt, safe="")
        # `model=flux` gives much higher-quality compositions than the
        # default turbo model; `enhance=true` lets Pollinations expand
        # short prompts so we don't get washed-out generic stills.
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width={w}&height={h}&model=flux&enhance=true"
            f"&nologo=true&seed={seed or 42}"
        )
        try:
            # Tighter per-request timeout so a single hanging call doesn't
            # block the whole render — the orchestrator already wraps this
            # in asyncio.wait_for(_PROVIDER_TIMEOUT_S + 1).
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(url)
            if resp.status_code in _FATAL_HTTP_STATUSES:
                _mark_provider_down(self.name, f"HTTP {resp.status_code}")
                return None
            resp.raise_for_status()
            content = resp.content
            # Pollinations returns tiny placeholder bodies (a few hundred
            # bytes) when the upstream model fails — treat as failure so the
            # orchestrator falls through to the next provider instead of
            # baking that into the reel.
            if not content or len(content) < 4096:
                raise ValueError(f"empty/too-small response ({len(content) if content else 0} bytes)")
            cached.write_bytes(content)
            log.info("visual.pollinations.ok", size=len(content), prompt=prompt[:60])
            return cached
        except httpx.HTTPStatusError as e:
            status = getattr(e.response, "status_code", None)
            if status in _FATAL_HTTP_STATUSES:
                _mark_provider_down(self.name, f"HTTP {status}")
            log.warning("visual.pollinations.fail", error=str(e)[:200])
            return None
        except Exception as e:
            log.warning("visual.pollinations.fail", error=str(e)[:200])
            return None


# ─── Hugging Face Inference API (free tier; SD XL) ──────────────────────────


class HuggingFaceSDProvider:
    name = "huggingface_sd"

    def __init__(self) -> None:
        self.key = get_settings().huggingface_api_key

    async def generate(
        self, prompt: str, aspect: str, seed: int = 0
    ) -> Optional[Path]:
        if not self.key:
            return None
        cached = _cache_path(self.name, prompt, aspect)
        if cached.exists():
            return cached
        w, h = ASPECT_TO_DIM.get(aspect, ASPECT_TO_DIM["vertical"])
        # SDXL handles 1024x1024 nicely; scale aspect down to fit
        max_dim = 1024
        if w > h:
            tw, th = max_dim, int(max_dim * h / w)
        else:
            th, tw = max_dim, int(max_dim * w / h)
        url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
        headers = {"Authorization": f"Bearer {self.key}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "width": tw - tw % 8,
                "height": th - th % 8,
                "seed": seed or 42,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=_PROVIDER_TIMEOUT_S) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code in (503, 524):
                    # Model loading — give up, fall through
                    log.info("visual.hf.loading_skip")
                    return None
                resp.raise_for_status()
                content = resp.content
                if not content or len(content) < 1024:
                    raise ValueError("empty response")
                cached.write_bytes(content)
                log.info("visual.hf.ok", size=len(content), prompt=prompt[:60])
                return cached
        except Exception as e:
            log.warning("visual.hf.fail", error=str(e)[:200])
            return None


# ─── Pexels (free stock photography) ────────────────────────────────────────


class PexelsProvider:
    name = "pexels"

    def __init__(self) -> None:
        self.key = get_settings().pexels_api_key

    async def generate(
        self, prompt: str, aspect: str, seed: int = 0
    ) -> Optional[Path]:
        if not self.key:
            return None
        cached = _cache_path(self.name, prompt, aspect, ext=".jpg")
        if cached.exists():
            return cached
        orientation = (
            "portrait" if aspect == "vertical"
            else "square" if aspect == "square"
            else "landscape"
        )
        url = "https://api.pexels.com/v1/search"
        params = {
            "query": prompt[:80],
            "per_page": 5,
            "orientation": orientation,
        }
        headers = {"Authorization": self.key}
        try:
            async with httpx.AsyncClient(timeout=_PROVIDER_TIMEOUT_S) as client:
                resp = await client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                photos = data.get("photos") or []
                if not photos:
                    return None
                # Pick deterministically by seed
                photo = photos[seed % len(photos)]
                src = (
                    photo.get("src", {}).get("portrait")
                    or photo.get("src", {}).get("large")
                    or photo.get("src", {}).get("original")
                )
                if not src:
                    return None
                img_resp = await client.get(src)
                img_resp.raise_for_status()
                cached.write_bytes(img_resp.content)
                log.info("visual.pexels.ok", photographer=photo.get("photographer"))
                return cached
        except Exception as e:
            log.warning("visual.pexels.fail", error=str(e)[:200])
            return None


# ─── Solid-color final fallback ─────────────────────────────────────────────


class SolidColorFallback:
    """Last-resort image: a coloured gradient with the prompt text drawn on
    top so even no-network renders produce something a viewer can read,
    not a blank block."""

    name = "solid_fallback"

    # Common Windows / cross-platform font candidates, in priority order.
    _FONT_CANDIDATES = (
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\seguibl.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    )

    def _load_font(self, size: int):
        from PIL import ImageFont

        for candidate in self._FONT_CANDIDATES:
            try:
                return ImageFont.truetype(candidate, size=size)
            except (OSError, IOError):
                continue
        try:
            return ImageFont.load_default()
        except Exception:
            return None

    def _display_text(self, prompt: str) -> str:
        # The orchestrator suffixes prompts with " — cinematic, high contrast,
        # simple composition" for steering — strip that off so the overlaid
        # text reads naturally.
        for sep in (" — cinematic", " - cinematic", " — "):
            if sep in prompt:
                prompt = prompt.split(sep, 1)[0]
                break
        prompt = prompt.strip()
        return prompt[:160]

    def _gradient_colors(self, prompt: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        # Deterministic from the prompt so the same beat reproduces the same
        # frame across renders, and adjacent beats look visually distinct.
        digest = hashlib.sha256(prompt.encode("utf-8")).digest()
        # Top colour: muted but saturated enough to feel intentional.
        top = (
            40 + digest[0] // 3,
            40 + digest[1] // 3,
            70 + digest[2] // 3,
        )
        # Bottom colour: darker shifted complement so the gradient reads.
        bottom = (
            15 + digest[3] // 6,
            15 + digest[4] // 6,
            30 + digest[5] // 6,
        )
        return top, bottom

    async def generate(
        self, prompt: str, aspect: str, seed: int = 0
    ) -> Optional[Path]:
        try:
            from PIL import Image, ImageDraw, ImageFilter
        except ImportError:
            return None

        cached = _cache_path(self.name, prompt, aspect)
        if cached.exists():
            return cached

        w, h = ASPECT_TO_SOURCE_DIM.get(aspect, ASPECT_TO_SOURCE_DIM["vertical"])
        top, bottom = self._gradient_colors(prompt)

        # ── Vertical gradient ──────────────────────────────────────────
        # Drawing per-row is slow at 2400px, so build a 1×h gradient strip
        # and stretch it horizontally — same visual, ~50× faster.
        strip = Image.new("RGB", (1, h))
        sp = strip.load()
        for y in range(h):
            t = y / max(1, h - 1)
            sp[0, y] = (
                int(top[0] * (1 - t) + bottom[0] * t),
                int(top[1] * (1 - t) + bottom[1] * t),
                int(top[2] * (1 - t) + bottom[2] * t),
            )
        img = strip.resize((w, h), Image.BILINEAR)

        # Soft vignette via a darkened, blurred frame composited on top —
        # gives the frame more depth than a flat gradient.
        vignette = Image.new("L", (w, h), 0)
        vd = ImageDraw.Draw(vignette)
        margin = int(min(w, h) * 0.06)
        vd.rounded_rectangle(
            (margin, margin, w - margin, h - margin),
            radius=int(min(w, h) * 0.05),
            fill=255,
        )
        vignette = vignette.filter(ImageFilter.GaussianBlur(radius=int(min(w, h) * 0.08)))
        dark = Image.new("RGB", (w, h), (0, 0, 0))
        img = Image.composite(img, dark, vignette)

        # ── Centered prompt text ──────────────────────────────────────
        display_text = self._display_text(prompt)
        if display_text:
            draw = ImageDraw.Draw(img)
            # Wrap to ~18 chars/line for vertical, wider for landscape.
            wrap_width = 14 if aspect == "vertical" else 22
            import textwrap as _tw

            lines = _tw.wrap(display_text, width=wrap_width)[:4]
            # Font size scales with the short edge so it reads on any aspect.
            short_edge = min(w, h)
            font_size = max(48, int(short_edge * 0.075))
            font = self._load_font(font_size)

            # Measure block height so we can center it vertically.
            line_heights: list[int] = []
            line_widths: list[int] = []
            for line in lines:
                if font and hasattr(font, "getbbox"):
                    bbox = font.getbbox(line)
                    line_widths.append(bbox[2] - bbox[0])
                    line_heights.append(bbox[3] - bbox[1])
                else:
                    # Rough fallback when default bitmap font is used.
                    line_widths.append(len(line) * (font_size // 2))
                    line_heights.append(font_size)
            line_gap = int(font_size * 0.35)
            block_h = sum(line_heights) + line_gap * max(0, len(lines) - 1)
            y_cursor = (h - block_h) // 2
            for line, lw, lh in zip(lines, line_widths, line_heights):
                x = (w - lw) // 2
                # Drop shadow for legibility against the gradient.
                draw.text((x + 4, y_cursor + 4), line, fill=(0, 0, 0), font=font)
                draw.text((x, y_cursor), line, fill=(245, 245, 245), font=font)
                y_cursor += lh + line_gap

        img.save(cached, "PNG")
        return cached


# ─── Orchestrator ───────────────────────────────────────────────────────────


_PROVIDER_CACHE: list[VisualProvider] | None = None


def _providers() -> list[VisualProvider]:
    global _PROVIDER_CACHE
    if _PROVIDER_CACHE is None:
        _PROVIDER_CACHE = [
            PollinationsProvider(),
            HuggingFaceSDProvider(),
            PexelsProvider(),
            SolidColorFallback(),
        ]
    return _PROVIDER_CACHE


async def generate_visual(prompt: str, aspect: str, seed: int = 0) -> tuple[Path, str]:
    """Try each provider in order; return (path, provider_name).

    Always returns a path — SolidColorFallback never fails.
    """
    for p in _providers():
        try:
            path = await asyncio.wait_for(
                p.generate(prompt, aspect, seed=seed),
                timeout=_PROVIDER_TIMEOUT_S + 1,
            )
            if path and path.exists():
                return path, p.name
        except asyncio.TimeoutError:
            log.warning("visual.provider.timeout", provider=p.name)
            continue
        except Exception as e:
            log.warning("visual.provider.error", provider=p.name, error=str(e)[:200])
            continue
    # Solid fallback is in the list, so this is unreachable in practice
    raise RuntimeError("All visual providers failed (including solid fallback)")


async def generate_visuals_parallel(
    prompts: list[str], aspect: str, max_concurrent: int = 3
) -> list[tuple[Path, str]]:
    """Generate one visual per prompt, capping at max_concurrent in flight."""
    sem = asyncio.Semaphore(max_concurrent)

    async def _one(idx: int, prompt: str) -> tuple[Path, str]:
        async with sem:
            return await generate_visual(prompt, aspect, seed=idx + 1)

    return await asyncio.gather(*(_one(i, p) for i, p in enumerate(prompts)))
