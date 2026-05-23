import google.generativeai as genai

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

OCR_MODEL = "gemini-2.5-flash"
OCR_PROMPT = (
    "Extract all text from this page exactly as written, preserving line breaks "
    "and reading order. Include handwritten text. Output only the extracted "
    "text — no commentary, no markdown fences."
)

_configured = False


def _ensure_gemini() -> None:
    global _configured
    if _configured:
        return
    genai.configure(api_key=get_settings().gemini_api_key)
    _configured = True


def ocr_page_image(image_bytes: bytes, mime_type: str = "image/png") -> str:
    _ensure_gemini()
    model = genai.GenerativeModel(OCR_MODEL)
    try:
        response = model.generate_content(
            [
                {"mime_type": mime_type, "data": image_bytes},
                OCR_PROMPT,
            ]
        )
        return (response.text or "").strip()
    except Exception:
        log.exception("ocr_page_failed")
        return ""
