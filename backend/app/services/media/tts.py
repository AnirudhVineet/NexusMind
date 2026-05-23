"""Phase 5 Track B — TTS narration engine (provider chain).

Provider order:
  1. PiperProvider       — local Piper TTS (preferred; ships with bundled voice)
  2. Pyttsx3Provider     — offline Windows SAPI fallback (works without models)
  3. ElevenLabsProvider  — ELEVENLABS_API_KEY (optional upgrade)
  4. OpenAITTSProvider   — OPENAI_API_KEY (optional upgrade)

Track A only needs `synthesize()`. Track B will flesh out batching, per-word
timing extraction, voice catalog, sample endpoints, and brief chapter
narration.
"""
from __future__ import annotations

import asyncio
import hashlib
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.media import audio_dir, media_root

log = get_logger(__name__)


@dataclass
class AudioResult:
    path: Path
    duration_seconds: float
    sample_rate: int
    provider_used: str
    cost_usd: float = 0.0


class TTSProvider(Protocol):
    name: str

    async def available(self) -> bool: ...

    async def synthesize(
        self, text: str, voice_id: Optional[str], speed: float, out_path: Path
    ) -> Optional[AudioResult]: ...


def _hash(text: str, voice_id: Optional[str], speed: float) -> str:
    raw = f"{voice_id or ''}|{speed:.2f}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _wave_duration(path: Path) -> tuple[float, int]:
    try:
        with wave.open(str(path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            return frames / float(rate), rate
    except Exception:
        return 0.0, 22050


# ─── Piper ──────────────────────────────────────────────────────────────────


class PiperProvider:
    """Local Piper TTS. Tries the pip-installed `piper` first; otherwise
    looks for a Piper binary at DATA_DIR/bin/piper.exe."""

    name = "piper"

    DEFAULT_VOICE = "en_US-amy-medium"

    def _piper_exe(self) -> Optional[str]:
        # Pip-installed piper (best case)
        exe = shutil.which("piper")
        if exe:
            return exe
        # Standalone binary path
        candidate = Path(media_root().parent / "bin" / "piper.exe")
        if candidate.exists():
            return str(candidate)
        candidate2 = Path(media_root().parent / "bin" / "piper")
        if candidate2.exists():
            return str(candidate2)
        return None

    def _voice_model_path(self, voice_id: str) -> Optional[Path]:
        models_dir = media_root().parent / "models" / "piper"
        candidate = models_dir / f"{voice_id}.onnx"
        if candidate.exists():
            return candidate
        # Bundled fallback
        bundled = Path(__file__).parent.parent.parent / "assets" / "piper_voices" / f"{voice_id}.onnx"
        if bundled.exists():
            return bundled
        return None

    async def available(self) -> bool:
        exe = self._piper_exe()
        model = self._voice_model_path(self.DEFAULT_VOICE)
        return bool(exe and model)

    async def synthesize(
        self, text: str, voice_id: Optional[str], speed: float, out_path: Path
    ) -> Optional[AudioResult]:
        exe = self._piper_exe()
        if not exe:
            return None
        vid = voice_id or self.DEFAULT_VOICE
        model = self._voice_model_path(vid)
        if not model:
            log.warning("tts.piper.voice_missing", voice=vid)
            return None

        def _run() -> int:
            try:
                proc = subprocess.run(
                    [exe, "--model", str(model), "--output_file", str(out_path)],
                    input=text.encode("utf-8"),
                    capture_output=True,
                    timeout=120,
                )
                if proc.returncode != 0:
                    log.warning(
                        "tts.piper.fail",
                        rc=proc.returncode,
                        stderr=proc.stderr[-500:].decode("utf-8", errors="replace"),
                    )
                return proc.returncode
            except Exception as e:
                log.warning("tts.piper.exception", error=str(e)[:200])
                return -1

        rc = await asyncio.to_thread(_run)
        if rc != 0 or not out_path.exists():
            return None
        dur, rate = _wave_duration(out_path)
        return AudioResult(
            path=out_path,
            duration_seconds=dur,
            sample_rate=rate,
            provider_used=self.name,
        )


# ─── Pyttsx3 (offline Windows SAPI) ─────────────────────────────────────────


class Pyttsx3Provider:
    name = "pyttsx3"

    async def available(self) -> bool:
        try:
            import pyttsx3  # noqa: F401

            return True
        except ImportError:
            return False

    async def synthesize(
        self, text: str, voice_id: Optional[str], speed: float, out_path: Path
    ) -> Optional[AudioResult]:
        def _run() -> bool:
            try:
                import pyttsx3

                engine = pyttsx3.init()
                # Speed: pyttsx3 rate is words-per-minute; default ~200
                engine.setProperty("rate", int(200 * speed))
                if voice_id:
                    for v in engine.getProperty("voices"):
                        if voice_id.lower() in (v.id or "").lower() or voice_id.lower() in (v.name or "").lower():
                            engine.setProperty("voice", v.id)
                            break
                engine.save_to_file(text, str(out_path))
                engine.runAndWait()
                return out_path.exists()
            except Exception as e:
                log.warning("tts.pyttsx3.exception", error=str(e)[:200])
                return False

        ok = await asyncio.to_thread(_run)
        if not ok:
            return None
        dur, rate = _wave_duration(out_path)
        if dur <= 0:
            # pyttsx3 may emit non-PCM .wav on some systems — approximate
            dur = max(1.0, len(text.split()) / max(1.0, 2.5 * speed))
        return AudioResult(
            path=out_path,
            duration_seconds=dur,
            sample_rate=rate,
            provider_used=self.name,
        )


# ─── ElevenLabs (optional paid) ─────────────────────────────────────────────


class ElevenLabsProvider:
    name = "elevenlabs"
    DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # "Rachel" default

    def __init__(self) -> None:
        self.key = get_settings().elevenlabs_api_key

    async def available(self) -> bool:
        return bool(self.key)

    async def synthesize(
        self, text: str, voice_id: Optional[str], speed: float, out_path: Path
    ) -> Optional[AudioResult]:
        if not self.key:
            return None
        import httpx

        vid = voice_id or self.DEFAULT_VOICE_ID
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}"
        headers = {"xi-api-key": self.key, "Content-Type": "application/json"}
        payload = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.7},
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                out_path.write_bytes(resp.content)
            from app.services.media.ffmpeg_runner import ffprobe_duration

            dur = ffprobe_duration(out_path)
            # Rough cost: ElevenLabs is ~30 USD per 1M chars on turbo
            cost = (len(text) / 1_000_000.0) * 30.0
            return AudioResult(
                path=out_path,
                duration_seconds=dur,
                sample_rate=22050,
                provider_used=self.name,
                cost_usd=cost,
            )
        except Exception as e:
            log.warning("tts.elevenlabs.fail", error=str(e)[:200])
            return None


# ─── OpenAI TTS (optional paid) ─────────────────────────────────────────────


class OpenAITTSProvider:
    name = "openai_tts"

    def __init__(self) -> None:
        self.key = get_settings().openai_api_key

    async def available(self) -> bool:
        return bool(self.key)

    async def synthesize(
        self, text: str, voice_id: Optional[str], speed: float, out_path: Path
    ) -> Optional[AudioResult]:
        if not self.key:
            return None
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self.key)
            voice = voice_id or "nova"
            resp = await client.audio.speech.create(
                model="tts-1",
                voice=voice,  # type: ignore[arg-type]
                input=text,
                speed=speed,
            )
            audio_bytes = await asyncio.to_thread(resp.read)
            out_path.write_bytes(audio_bytes)
            from app.services.media.ffmpeg_runner import ffprobe_duration

            dur = ffprobe_duration(out_path)
            # OpenAI TTS-1 ~ $15 / 1M characters
            cost = (len(text) / 1_000_000.0) * 15.0
            return AudioResult(
                path=out_path,
                duration_seconds=dur,
                sample_rate=24000,
                provider_used=self.name,
                cost_usd=cost,
            )
        except Exception as e:
            log.warning("tts.openai.fail", error=str(e)[:200])
            return None


# ─── Orchestrator ───────────────────────────────────────────────────────────


_PROVIDER_CACHE: list[TTSProvider] | None = None


def _providers() -> list[TTSProvider]:
    global _PROVIDER_CACHE
    if _PROVIDER_CACHE is None:
        _PROVIDER_CACHE = [
            PiperProvider(),
            Pyttsx3Provider(),
            ElevenLabsProvider(),
            OpenAITTSProvider(),
        ]
    return _PROVIDER_CACHE


async def synthesize(
    text: str,
    voice_id: Optional[str] = None,
    speed: float = 1.0,
    out_path: Optional[Path] = None,
) -> Optional[AudioResult]:
    """Try providers in order; return the first AudioResult that succeeds."""
    if not text or not text.strip():
        return None
    if out_path is None:
        # Generate a deterministic cache path based on (text, voice, speed)
        cache_dir = audio_dir() / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        h = _hash(text, voice_id, speed)
        out_path = cache_dir / f"{h}.wav"
        if out_path.exists():
            dur, rate = _wave_duration(out_path)
            return AudioResult(
                path=out_path,
                duration_seconds=dur,
                sample_rate=rate,
                provider_used="cache",
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)

    for p in _providers():
        try:
            if not await p.available():
                continue
            result = await p.synthesize(text, voice_id, speed, out_path)
            if result and result.path.exists():
                return result
        except Exception as e:
            log.warning("tts.provider.error", provider=p.name, error=str(e)[:200])
            continue
    return None


# Curated Piper voice presets — surfaced when the piper binary is installed
# even if the .onnx model file isn't downloaded yet (the user can install on
# demand). When a model file IS present, the label gets a " (installed)" tag.
_PIPER_PRESETS: list[dict[str, str]] = [
    {"voice_id": "en_US-amy-medium", "language": "en-US", "gender": "female", "label": "Amy"},
    {"voice_id": "en_US-ryan-medium", "language": "en-US", "gender": "male", "label": "Ryan"},
    {"voice_id": "en_US-lessac-medium", "language": "en-US", "gender": "female", "label": "Lessac"},
    {"voice_id": "en_US-libritts-high", "language": "en-US", "gender": "female", "label": "LibriTTS"},
    {"voice_id": "en_US-joe-medium", "language": "en-US", "gender": "male", "label": "Joe"},
    {"voice_id": "en_US-kathleen-low", "language": "en-US", "gender": "female", "label": "Kathleen"},
    {"voice_id": "en_GB-alan-medium", "language": "en-GB", "gender": "male", "label": "Alan (UK)"},
    {"voice_id": "en_GB-jenny_dioco-medium", "language": "en-GB", "gender": "female", "label": "Jenny (UK)"},
]

# ElevenLabs default catalogue (their stock voices). When the API key is
# configured we additionally query their API to list private/cloned voices.
_ELEVENLABS_PRESETS: list[dict[str, str]] = [
    {"voice_id": "21m00Tcm4TlvDq8ikWAM", "language": "en", "gender": "female", "label": "Rachel"},
    {"voice_id": "AZnzlk1XvdvUeBnXmlld", "language": "en", "gender": "female", "label": "Domi"},
    {"voice_id": "EXAVITQu4vr4xnSDxMaL", "language": "en", "gender": "female", "label": "Bella"},
    {"voice_id": "ErXwobaYiN019PkySvjV", "language": "en", "gender": "male", "label": "Antoni"},
    {"voice_id": "MF3mGyEYCl7XYWbV9V6O", "language": "en", "gender": "female", "label": "Elli"},
    {"voice_id": "TxGEqnHWrfWFTfGW9XjX", "language": "en", "gender": "male", "label": "Josh"},
    {"voice_id": "VR6AewLTigWG4xSOukaG", "language": "en", "gender": "male", "label": "Arnold"},
    {"voice_id": "pNInz6obpgDQGcFmaJgB", "language": "en", "gender": "male", "label": "Adam"},
    {"voice_id": "yoZ06aMxZJJ28mfd3POQ", "language": "en", "gender": "male", "label": "Sam"},
]

# OpenAI TTS-1 stock voices.
_OPENAI_PRESETS: list[dict[str, str]] = [
    {"voice_id": "alloy", "language": "en", "gender": "neutral", "label": "Alloy"},
    {"voice_id": "echo", "language": "en", "gender": "male", "label": "Echo"},
    {"voice_id": "fable", "language": "en", "gender": "neutral", "label": "Fable"},
    {"voice_id": "onyx", "language": "en", "gender": "male", "label": "Onyx"},
    {"voice_id": "nova", "language": "en", "gender": "female", "label": "Nova"},
    {"voice_id": "shimmer", "language": "en", "gender": "female", "label": "Shimmer"},
]


def _list_sapi_voices() -> list[dict[str, str]]:
    """Enumerate locally installed Windows SAPI voices via pyttsx3."""
    try:
        import pyttsx3  # type: ignore

        engine = pyttsx3.init()
        out: list[dict[str, str]] = []
        for v in engine.getProperty("voices") or []:
            name = (getattr(v, "name", None) or "").strip() or "SAPI Voice"
            vid = getattr(v, "id", None) or name
            languages = getattr(v, "languages", None) or []
            lang = "en-US"
            if languages:
                try:
                    raw = languages[0]
                    if isinstance(raw, bytes):
                        lang = raw.decode("utf-8", errors="replace").strip() or lang
                    elif isinstance(raw, str):
                        lang = raw.strip() or lang
                except Exception:
                    pass
            gender_raw = (getattr(v, "gender", None) or "").lower()
            gender = "male" if "male" in gender_raw else "female" if "female" in gender_raw else "unknown"
            out.append({"voice_id": vid, "language": lang, "gender": gender, "label": name})
        try:
            engine.stop()
        except Exception:
            pass
        return out
    except Exception as e:
        log.warning("tts.sapi.enumerate_failed", error=str(e)[:200])
        return []


async def _fetch_elevenlabs_remote_voices(api_key: str) -> list[dict[str, str]]:
    """Optional: list user's custom + stock ElevenLabs voices via API."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": api_key}
            )
            resp.raise_for_status()
            data = resp.json() or {}
        out: list[dict[str, str]] = []
        for v in data.get("voices", []):
            labels = v.get("labels") or {}
            out.append(
                {
                    "voice_id": v.get("voice_id", ""),
                    "language": labels.get("language") or "en",
                    "gender": (labels.get("gender") or "unknown").lower(),
                    "label": v.get("name") or "Unnamed",
                }
            )
        return out
    except Exception as e:
        log.info("tts.elevenlabs.list_voices_failed", error=str(e)[:200])
        return []


async def list_voices() -> list[dict]:
    """Voice catalog filtered + enriched by actual provider availability.

    Returns one entry per voice with: voice_id, provider, language, gender,
    label, and `installed` (true when the underlying asset is verified
    present locally — e.g. a Piper .onnx file).
    """
    out: list[dict] = []

    # ── Piper: scan disk for installed models, then add presets ────────────
    piper = PiperProvider()
    piper_exe = piper._piper_exe()
    if piper_exe:
        models_dir = media_root().parent / "models" / "piper"
        installed_ids: set[str] = set()
        try:
            if models_dir.exists():
                for p in models_dir.glob("*.onnx"):
                    installed_ids.add(p.stem)
        except Exception:
            pass

        # Surface every preset; tag whichever ones have a local .onnx.
        added: set[str] = set()
        for preset in _PIPER_PRESETS:
            vid = preset["voice_id"]
            added.add(vid)
            installed = vid in installed_ids
            out.append(
                {
                    **preset,
                    "provider": "piper",
                    "installed": installed,
                    "label": f"{preset['label']} (Piper{'' if installed else ' — model not installed'})",
                }
            )
        # Also surface any non-preset .onnx the user has dropped in.
        for vid in installed_ids - added:
            out.append(
                {
                    "voice_id": vid,
                    "provider": "piper",
                    "language": "en-US",
                    "gender": "unknown",
                    "installed": True,
                    "label": f"{vid} (Piper)",
                }
            )

    # ── Windows SAPI / pyttsx3 ─────────────────────────────────────────────
    try:
        import pyttsx3  # noqa: F401

        sapi = await asyncio.to_thread(_list_sapi_voices)
        for v in sapi:
            out.append({**v, "provider": "pyttsx3", "installed": True})
        # Always provide a generic default-SAPI entry as a safety fallback.
        out.append(
            {
                "voice_id": "default-sapi",
                "provider": "pyttsx3",
                "language": "en-US",
                "gender": "unknown",
                "installed": True,
                "label": "System Default (SAPI)",
            }
        )
    except ImportError:
        pass

    # ── ElevenLabs (cloud) ─────────────────────────────────────────────────
    eleven_key = get_settings().elevenlabs_api_key
    if eleven_key:
        remote = await _fetch_elevenlabs_remote_voices(eleven_key)
        seen = {v["voice_id"] for v in remote}
        for v in remote:
            out.append({**v, "provider": "elevenlabs", "installed": True,
                        "label": f"{v['label']} (ElevenLabs)"})
        # Add hardcoded presets only when not already returned by the API.
        for preset in _ELEVENLABS_PRESETS:
            if preset["voice_id"] in seen:
                continue
            out.append({**preset, "provider": "elevenlabs", "installed": True,
                        "label": f"{preset['label']} (ElevenLabs)"})

    # ── OpenAI TTS ─────────────────────────────────────────────────────────
    if get_settings().openai_api_key:
        for preset in _OPENAI_PRESETS:
            out.append({**preset, "provider": "openai_tts", "installed": True,
                        "label": f"{preset['label']} (OpenAI)"})

    return out
