"""Fetch a web URL and extract clean text using httpx + BeautifulSoup."""

import re

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NexusMind/1.0; +https://nexusmind.local)"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

_NOISE_TAGS = {"script", "style", "noscript", "header", "footer", "nav", "aside"}


def _extract_text(html: str) -> tuple[str, str]:
    """Return (title, body_text) from raw HTML."""
    soup = BeautifulSoup(html, "lxml")

    title = (soup.title.string or "").strip() if soup.title else ""

    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(id=re.compile(r"content|main|body", re.I))
        or soup.body
    )
    raw = (main or soup).get_text(separator="\n")
    lines = [ln.strip() for ln in raw.splitlines()]
    text = "\n".join(ln for ln in lines if ln)
    return title, text


async def scrape_url(url: str) -> tuple[str, str, str]:
    """Fetch URL and return (title, text, final_url).

    Raises httpx.HTTPError on network/HTTP failures.
    """
    settings = get_settings()
    async with httpx.AsyncClient(
        headers=_HEADERS,
        follow_redirects=True,
        timeout=settings.web_scrape_timeout_s,
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        final_url = str(resp.url)
        body = resp.text

    if "html" not in content_type and "xml" not in content_type:
        return url, body, final_url

    title, text = _extract_text(body)
    if not title:
        title = url
    log.info("web_scraper.scraped", url=url, chars=len(text))
    return title, text, final_url
