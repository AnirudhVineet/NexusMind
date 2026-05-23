import asyncio
import io
import json
import uuid

import pdfplumber
import pymupdf
from langdetect import DetectorFactory, detect
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.sync_session import get_sync_session
from app.models.document import Document
from app.services.ocr import ocr_page_image
from app.services.storage import StorageService
from app.utils.text import normalize_text, word_count
from app.workers.celery_app import celery_app

DetectorFactory.seed = 0
configure_logging()
log = get_logger(__name__)

OCR_MIN_CHARS = 30  # below this, fall back to Gemini Vision OCR
OCR_RENDER_DPI = 200


def _parsed_key(user_id: uuid.UUID, document_id: uuid.UUID) -> str:
    return f"{user_id}/{document_id}/parsed.json"


def _render_page_png(pdf_doc: pymupdf.Document, page_index: int) -> bytes:
    page = pdf_doc[page_index]
    pix = page.get_pixmap(dpi=OCR_RENDER_DPI)
    return pix.tobytes("png")


def _parse_pdf(data: bytes) -> list[dict]:
    pages: list[dict] = []
    pdf_doc: pymupdf.Document | None = None
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = (page.extract_text() or "").strip()
                if len(text) < OCR_MIN_CHARS:
                    if pdf_doc is None:
                        pdf_doc = pymupdf.open(stream=data, filetype="pdf")
                    try:
                        png = _render_page_png(pdf_doc, i - 1)
                        ocr_text = ocr_page_image(png)
                        if ocr_text:
                            text = ocr_text
                            log.info("parse_pdf.ocr_used", page_num=i, chars=len(ocr_text))
                    except Exception:
                        log.exception("parse_pdf.ocr_render_failed", page_num=i)
                pages.append({"page_num": i, "text": normalize_text(text)})
    finally:
        if pdf_doc is not None:
            pdf_doc.close()
    return pages


def _parse_text(data: bytes) -> list[dict]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        import chardet

        guess = chardet.detect(data)
        enc = guess.get("encoding") or "latin-1"
        text = data.decode(enc, errors="replace")
    return [{"page_num": None, "text": normalize_text(text)}]


def _parse_md(data: bytes) -> list[dict]:
    text = data.decode("utf-8", errors="replace")
    return [{"page_num": None, "text": text}]


def _parse_audio(data: bytes, filename: str) -> list[dict]:
    """Transcribe audio via Groq Whisper API."""
    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.groq_api_key,
        base_url=settings.groq_base_url,
    )

    import io as _io

    audio_file = _io.BytesIO(data)
    audio_file.name = filename  # Groq needs a filename hint for format detection

    async def _transcribe() -> str:
        resp = await client.audio.transcriptions.create(
            model=settings.groq_whisper_model,
            file=audio_file,
            response_format="text",
        )
        return resp if isinstance(resp, str) else getattr(resp, "text", str(resp))

    text = asyncio.run(_transcribe())
    log.info("parse_audio.transcribed", filename=filename, chars=len(text))
    return [{"page_num": None, "text": normalize_text(text)}]


# Source types that store content as plain text (already extracted before parse)
_TEXT_SOURCE_TYPES = {"web", "youtube", "notion"}


@celery_app.task(
    name="parse_document",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def parse_document(self, document_id: str) -> str:
    storage = StorageService()
    session = get_sync_session()

    try:
        doc = session.get(Document, uuid.UUID(document_id))
        if doc is None:
            raise RuntimeError(f"Document {document_id} not found")

        if doc.processing_status not in ("queued", "parsing"):
            log.info("parse_document.skipped", document_id=document_id, status=doc.processing_status)
            return document_id

        doc.processing_status = "parsing"
        session.commit()

        data = asyncio.run(storage.download(doc.storage_path))

        if doc.source_type == "pdf":
            pages = _parse_pdf(data)
        elif doc.source_type in ("txt", *_TEXT_SOURCE_TYPES):
            pages = _parse_text(data)
        elif doc.source_type == "md":
            pages = _parse_md(data)
        elif doc.source_type == "audio":
            pages = _parse_audio(data, doc.filename)
        else:
            raise RuntimeError(f"Unsupported source_type: {doc.source_type}")

        full_text = "\n\n".join(p["text"] for p in pages)
        wc = word_count(full_text)

        try:
            language = detect(full_text[:5000]) if full_text else None
        except Exception:
            language = None

        parsed_key = _parsed_key(doc.user_id, doc.id)
        asyncio.run(
            storage.upload(
                parsed_key,
                json.dumps({"pages": pages}).encode("utf-8"),
                "application/json",
            )
        )

        doc.word_count = wc
        doc.language = language
        doc.processing_status = "chunking"
        session.commit()

        return document_id

    except Exception as e:
        session.rollback()
        log.exception("parse_document.failed", document_id=document_id)
        try:
            doc = session.get(Document, uuid.UUID(document_id))
            if doc:
                doc.processing_status = "failed"
                doc.error_message = str(e)[:2000]
                session.commit()
        except Exception:
            session.rollback()
        try:
            import sentry_sdk

            sentry_sdk.capture_exception(e)
        except Exception:
            pass
        raise
    finally:
        session.close()
