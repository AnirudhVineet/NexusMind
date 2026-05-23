"""Fetch a Notion page and convert its block content to plain text."""

from notion_client import Client, APIResponseError

from app.core.logging import get_logger

log = get_logger(__name__)

_RICH_TEXT_TYPES = {"paragraph", "heading_1", "heading_2", "heading_3",
                    "bulleted_list_item", "numbered_list_item", "toggle",
                    "quote", "callout", "code"}


def _rich_text_to_str(rich_text: list[dict]) -> str:
    return "".join(rt.get("plain_text", "") for rt in rich_text)


def _block_to_text(block: dict) -> str:
    btype = block.get("type", "")
    if btype not in _RICH_TEXT_TYPES:
        return ""
    payload = block.get(btype, {})
    text = _rich_text_to_str(payload.get("rich_text", []))
    if btype == "code":
        lang = payload.get("language", "")
        return f"```{lang}\n{text}\n```"
    if btype.startswith("heading"):
        level = int(btype[-1])
        return "#" * level + " " + text
    return text


def fetch_page(page_id: str, access_token: str) -> tuple[str, str]:
    """Return (title, markdown_text) for a Notion page.

    Raises ValueError on auth failure or page not found.
    """
    client = Client(auth=access_token)
    try:
        page = client.pages.retrieve(page_id=page_id)
    except APIResponseError as e:
        raise ValueError(f"Notion API error: {e}") from e

    props = page.get("properties", {})
    title = ""
    for prop in props.values():
        if prop.get("type") == "title":
            title = _rich_text_to_str(prop.get("title", []))
            break

    lines: list[str] = []
    cursor: str | None = None
    while True:
        kwargs: dict = {"block_id": page_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        blocks_resp = client.blocks.children.list(**kwargs)
        for block in blocks_resp.get("results", []):
            line = _block_to_text(block)
            if line:
                lines.append(line)
        if not blocks_resp.get("has_more"):
            break
        cursor = blocks_resp.get("next_cursor")

    text = "\n\n".join(lines)
    log.info("notion_ingest.fetched", page_id=page_id, chars=len(text))
    return title or page_id, text
