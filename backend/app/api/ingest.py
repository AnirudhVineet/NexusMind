"""Multi-source ingestion endpoints.

POST /api/ingest/url          — web page by URL
POST /api/ingest/youtube      — YouTube video by URL
POST /api/ingest/audio        — audio file upload (mp3/wav/m4a/ogg/flac)
POST /api/ingest/notion       — Notion page by page ID
POST /api/ingest/zip          — ZIP bundle of mixed files
"""

import hashlib
import io
import uuid
import zipfile
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import PayloadTooLargeError, UnsupportedMediaError, ValidationError
from app.db.session import get_session
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentCreatedResponse
from app.services.storage import StorageService

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

AUDIO_MIME_TYPES = {
    "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
    "audio/mp4", "audio/m4a", "audio/x-m4a", "audio/ogg",
    "audio/flac", "audio/x-flac", "audio/webm",
}

ZIP_SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".mp3", ".wav", ".m4a", ".ogg", ".flac"}

EXTENSION_TO_SOURCE = {
    ".pdf": ("pdf", "application/pdf"),
    ".txt": ("txt", "text/plain"),
    ".md": ("md", "text/markdown"),
    ".mp3": ("audio", "audio/mpeg"),
    ".wav": ("audio", "audio/wav"),
    ".m4a": ("audio", "audio/m4a"),
    ".ogg": ("audio", "audio/ogg"),
    ".flac": ("audio", "audio/flac"),
}


def _enqueue_pipeline(document_id: uuid.UUID) -> None:
    from app.workers.chunk import chunk_document
    from app.workers.credibility import compute_credibility_task, recompute_credibility_cohort_task
    from app.workers.embed import embed_chunks
    from app.workers.intelligence import compute_intelligence_task
    from app.workers.ner import extract_entities_task
    from app.workers.parse import parse_document
    from app.workers.relations import extract_relations_task
    from celery import chain as celery_chain

    pipeline = celery_chain(
        parse_document.s(str(document_id)),
        chunk_document.s(),
        embed_chunks.s(),
        extract_entities_task.s(),
        extract_relations_task.s(),
        compute_intelligence_task.s(),
        compute_credibility_task.s(),
        recompute_credibility_cohort_task.s(),
    )
    pipeline.apply_async()


async def _create_text_document(
    session: AsyncSession,
    storage: StorageService,
    user: User,
    filename: str,
    source_type: str,
    text_content: str,
    source_url: str | None = None,
    ingestion_metadata: dict[str, Any] | None = None,
    batch_id: uuid.UUID | None = None,
) -> Document:
    data = text_content.encode("utf-8")
    content_hash = hashlib.sha256(data).hexdigest()

    existing = (
        await session.execute(
            select(Document).where(
                Document.user_id == user.id,
                Document.content_hash == content_hash,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    doc = Document(
        user_id=user.id,
        filename=filename,
        source_type=source_type,
        mime_type="text/plain",
        file_size_bytes=len(data),
        content_hash=content_hash,
        storage_path=f"{user.id}/placeholder",
        source_url=source_url,
        ingestion_metadata=ingestion_metadata,
        ingestion_batch_id=batch_id,
        processing_status="queued",
    )
    session.add(doc)
    await session.flush()

    storage_path = f"{user.id}/{doc.id}/raw.txt"
    await storage.upload(storage_path, data, "text/plain")
    doc.storage_path = storage_path
    await session.commit()
    await session.refresh(doc)
    return doc


# ─── Web URL ──────────────────────────────────────────────────────────────────

class IngestUrlRequest(BaseModel):
    url: str


@router.post("/url", status_code=status.HTTP_201_CREATED, response_model=DocumentCreatedResponse)
async def ingest_url(
    body: IngestUrlRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentCreatedResponse:
    from app.services.web_scraper import scrape_url

    try:
        title, text, final_url = await scrape_url(body.url)
    except Exception as e:
        raise ValidationError(f"Failed to fetch URL: {e}") from e

    if not text.strip():
        raise ValidationError("No text content found at the provided URL.")

    storage = StorageService()
    doc = await _create_text_document(
        session, storage, current_user,
        filename=title[:255] or body.url,
        source_type="web",
        text_content=text,
        source_url=final_url,
        ingestion_metadata={"original_url": body.url, "title": title},
    )
    _enqueue_pipeline(doc.id)
    return DocumentCreatedResponse(document_id=doc.id, filename=doc.filename, processing_status=doc.processing_status)


# ─── YouTube ──────────────────────────────────────────────────────────────────

class IngestYouTubeRequest(BaseModel):
    url: str


@router.post("/youtube", status_code=status.HTTP_201_CREATED, response_model=DocumentCreatedResponse)
async def ingest_youtube(
    body: IngestYouTubeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentCreatedResponse:
    import asyncio
    from app.services.youtube_ingest import fetch_transcript

    try:
        video_id, transcript = await asyncio.to_thread(fetch_transcript, body.url)
    except ValueError as e:
        raise ValidationError(str(e)) from e

    storage = StorageService()
    doc = await _create_text_document(
        session, storage, current_user,
        filename=f"youtube_{video_id}.txt",
        source_type="youtube",
        text_content=transcript,
        source_url=body.url,
        ingestion_metadata={"video_id": video_id, "url": body.url},
    )
    _enqueue_pipeline(doc.id)
    return DocumentCreatedResponse(document_id=doc.id, filename=doc.filename, processing_status=doc.processing_status)


# ─── Audio ────────────────────────────────────────────────────────────────────

@router.post("/audio", status_code=status.HTTP_201_CREATED, response_model=DocumentCreatedResponse)
async def ingest_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentCreatedResponse:
    settings = get_settings()

    mime = file.content_type or ""
    if mime not in AUDIO_MIME_TYPES:
        raise UnsupportedMediaError(f"Unsupported audio MIME type: {mime}")

    data = await file.read()
    if len(data) > settings.audio_max_upload_bytes:
        raise PayloadTooLargeError(
            f"Audio file exceeds {settings.audio_max_upload_bytes} bytes"
        )

    content_hash = hashlib.sha256(data).hexdigest()
    existing = (
        await session.execute(
            select(Document).where(
                Document.user_id == current_user.id,
                Document.content_hash == content_hash,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return DocumentCreatedResponse(
            document_id=existing.id,
            filename=existing.filename,
            processing_status=existing.processing_status,
        )

    storage = StorageService()
    doc = Document(
        user_id=current_user.id,
        filename=file.filename or "audio_upload",
        source_type="audio",
        mime_type=mime,
        file_size_bytes=len(data),
        content_hash=content_hash,
        storage_path="placeholder",
        processing_status="queued",
    )
    session.add(doc)
    await session.flush()

    storage_path = f"{current_user.id}/{doc.id}/raw{_ext_for_mime(mime)}"
    await storage.upload(storage_path, data, mime)
    doc.storage_path = storage_path
    await session.commit()
    await session.refresh(doc)

    _enqueue_pipeline(doc.id)
    return DocumentCreatedResponse(document_id=doc.id, filename=doc.filename, processing_status=doc.processing_status)


def _ext_for_mime(mime: str) -> str:
    return {
        "audio/mpeg": ".mp3", "audio/mp3": ".mp3",
        "audio/wav": ".wav", "audio/x-wav": ".wav",
        "audio/mp4": ".m4a", "audio/m4a": ".m4a", "audio/x-m4a": ".m4a",
        "audio/ogg": ".ogg", "audio/flac": ".flac", "audio/x-flac": ".flac",
        "audio/webm": ".webm",
    }.get(mime, ".audio")


# ─── Notion ───────────────────────────────────────────────────────────────────

class IngestNotionRequest(BaseModel):
    page_id: str
    access_token: str | None = None  # overrides NOTION_ACCESS_TOKEN in .env


@router.post("/notion", status_code=status.HTTP_201_CREATED, response_model=DocumentCreatedResponse)
async def ingest_notion(
    body: IngestNotionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentCreatedResponse:
    import asyncio
    from app.services.notion_ingest import fetch_page

    settings = get_settings()
    token = body.access_token or settings.notion_access_token
    if not token:
        raise ValidationError(
            "No Notion access token. Set NOTION_ACCESS_TOKEN in .env or pass access_token in the request."
        )

    try:
        title, text = await asyncio.to_thread(fetch_page, body.page_id, token)
    except ValueError as e:
        raise ValidationError(str(e)) from e

    if not text.strip():
        raise ValidationError("Notion page has no text content.")

    storage = StorageService()
    doc = await _create_text_document(
        session, storage, current_user,
        filename=f"{title[:200]}.md",
        source_type="notion",
        text_content=text,
        source_url=f"https://notion.so/{body.page_id.replace('-', '')}",
        ingestion_metadata={"page_id": body.page_id, "title": title},
    )
    _enqueue_pipeline(doc.id)
    return DocumentCreatedResponse(document_id=doc.id, filename=doc.filename, processing_status=doc.processing_status)


# ─── ZIP bundle ───────────────────────────────────────────────────────────────

class IngestZipResponse(BaseModel):
    batch_id: str
    documents: list[DocumentCreatedResponse]
    skipped: int


@router.post("/zip", status_code=status.HTTP_201_CREATED, response_model=IngestZipResponse)
async def ingest_zip(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> IngestZipResponse:
    settings = get_settings()

    data = await file.read()
    if len(data) > settings.zip_max_upload_bytes:
        raise PayloadTooLargeError(
            f"ZIP file exceeds {settings.zip_max_upload_bytes} bytes"
        )

    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise UnsupportedMediaError("Uploaded file is not a valid ZIP archive.")

    batch_id = uuid.uuid4()
    storage = StorageService()
    created: list[DocumentCreatedResponse] = []
    skipped = 0

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = [m for m in zf.infolist() if not m.is_dir()]
        if len(members) > settings.zip_max_files:
            raise ValidationError(
                f"ZIP contains {len(members)} files; max allowed is {settings.zip_max_files}."
            )

        for member in members:
            name = member.filename
            ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext not in ZIP_SUPPORTED_EXTENSIONS:
                skipped += 1
                continue

            source_type, mime_type = EXTENSION_TO_SOURCE[ext]
            file_data = zf.read(member)
            content_hash = hashlib.sha256(file_data).hexdigest()

            existing = (
                await session.execute(
                    select(Document).where(
                        Document.user_id == current_user.id,
                        Document.content_hash == content_hash,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                created.append(DocumentCreatedResponse(
                    document_id=existing.id,
                    filename=existing.filename,
                    processing_status=existing.processing_status,
                ))
                continue

            basename = name.rsplit("/", 1)[-1][:255]
            doc = Document(
                user_id=current_user.id,
                filename=basename,
                source_type=source_type,
                mime_type=mime_type,
                file_size_bytes=len(file_data),
                content_hash=content_hash,
                storage_path="placeholder",
                ingestion_batch_id=batch_id,
                processing_status="queued",
            )
            session.add(doc)
            await session.flush()

            storage_path = f"{current_user.id}/{doc.id}/raw{ext}"
            await storage.upload(storage_path, file_data, mime_type)
            doc.storage_path = storage_path
            await session.commit()
            await session.refresh(doc)

            _enqueue_pipeline(doc.id)
            created.append(DocumentCreatedResponse(
                document_id=doc.id,
                filename=doc.filename,
                processing_status=doc.processing_status,
            ))

    return IngestZipResponse(batch_id=str(batch_id), documents=created, skipped=skipped)
