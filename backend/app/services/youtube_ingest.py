"""Fetch a YouTube video transcript via youtube-transcript-api (v1.2+)."""

import re

from youtube_transcript_api import YouTubeTranscriptApi, CouldNotRetrieveTranscript

from app.core.logging import get_logger

log = get_logger(__name__)

_YT_ID_RE = re.compile(
    r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})"
)


def _extract_video_id(url: str) -> str | None:
    m = _YT_ID_RE.search(url)
    return m.group(1) if m else None


def fetch_transcript(url: str) -> tuple[str, str]:
    """Return (video_id, full_transcript_text).

    Uses the v1.2+ API: YouTubeTranscriptApi().fetch(video_id, languages=[...])
    which tries the requested languages in order (manual then auto-generated).
    Raises ValueError if no transcript is available.
    """
    video_id = _extract_video_id(url)
    if not video_id:
        raise ValueError(f"Cannot extract YouTube video ID from URL: {url}")

    try:
        ytt = YouTubeTranscriptApi()
        transcript = ytt.fetch(video_id, languages=["en", "en-US", "en-GB"])
    except CouldNotRetrieveTranscript as e:
        raise ValueError(f"Could not retrieve transcript for {video_id}: {e}") from e

    text = " ".join(snippet.text for snippet in transcript)
    log.info("youtube_ingest.fetched", video_id=video_id, chars=len(text))
    return video_id, text
