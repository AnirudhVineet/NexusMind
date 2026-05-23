import hashlib
import uuid

from celery import chain as celery_chain
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.core.exceptions import (
    NotFoundError,
    PayloadTooLargeError,
    UnsupportedMediaError,
)
from app.db.session import get_session
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.user import User
from app.schemas.document import (
    DocumentChunkResponse,
    DocumentCreatedResponse,
    DocumentResponse,
    DocumentStatusResponse,
)
from app.services.storage import StorageService

router = APIRouter(prefix="", tags=["documents"])

MIME_TO_SOURCE = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "text/markdown": "md",
}


def _enqueue_pipeline(document_id: uuid.UUID) -> None:
    from app.workers.chunk import chunk_document
    from app.workers.credibility import (
        compute_credibility_task,
        recompute_credibility_cohort_task,
    )
    from app.workers.embed import embed_chunks
    from app.workers.intelligence import compute_intelligence_task
    from app.workers.ner import extract_entities_task
    from app.workers.parse import parse_document
    from app.workers.relations import extract_relations_task

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


@router.post(
    "/ingest",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentCreatedResponse,
)
async def ingest(
    response: Response,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentCreatedResponse:
    settings = get_settings()

    if file.content_type not in settings.allowed_mime_types:
        raise UnsupportedMediaError(
            f"Unsupported MIME type: {file.content_type}"
        )

    data = await file.read()
    if len(data) > settings.max_upload_bytes:
        raise PayloadTooLargeError(
            f"File exceeds maximum size of {settings.max_upload_bytes} bytes"
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
        response.status_code = status.HTTP_200_OK
        return DocumentCreatedResponse(
            document_id=existing.id,
            filename=existing.filename,
            processing_status=existing.processing_status,
        )

    document_id = uuid.uuid4()
    storage_path = f"{current_user.id}/{document_id}/{file.filename}"

    storage = StorageService()
    await storage.upload(storage_path, data, file.content_type)

    doc = Document(
        id=document_id,
        user_id=current_user.id,
        filename=file.filename,
        source_type=MIME_TO_SOURCE[file.content_type],
        mime_type=file.content_type,
        file_size_bytes=len(data),
        content_hash=content_hash,
        storage_path=storage_path,
        processing_status="queued",
    )
    session.add(doc)
    await session.commit()
    await session.refresh(doc)

    _enqueue_pipeline(doc.id)

    return DocumentCreatedResponse(
        document_id=doc.id,
        filename=doc.filename,
        processing_status=doc.processing_status,
    )


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(
    status_filter: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentResponse]:
    stmt = (
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.uploaded_at.desc())
    )
    if status_filter:
        stmt = stmt.where(Document.processing_status == status_filter)

    rows = (await session.execute(stmt)).scalars().all()
    return [DocumentResponse.model_validate(_to_dict(d)) for d in rows]


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentResponse:
    doc = (
        await session.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == current_user.id
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise NotFoundError("Document not found")
    return DocumentResponse.model_validate(_to_dict(doc))


@router.get(
    "/documents/{document_id}/status",
    response_model=DocumentStatusResponse,
)
async def get_status(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DocumentStatusResponse:
    doc = (
        await session.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == current_user.id
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise NotFoundError("Document not found")
    return DocumentStatusResponse(
        document_id=doc.id,
        processing_status=doc.processing_status,
        error_message=doc.error_message,
        chunk_count=doc.chunk_count,
        completed_at=doc.completed_at,
    )


@router.get(
    "/documents/{document_id}/chunks",
    response_model=list[DocumentChunkResponse],
)
async def get_document_chunks(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[DocumentChunkResponse]:
    doc = (
        await session.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == current_user.id
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise NotFoundError("Document not found")

    chunks = (
        await session.execute(
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index.asc())
        )
    ).scalars().all()

    return [
        DocumentChunkResponse(
            id=c.id,
            chunk_index=c.chunk_index,
            text=c.text_content,
            page_number=c.page_number,
            section=c.section,
        )
        for c in chunks
    ]


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    doc = (
        await session.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == current_user.id
            )
        )
    ).scalar_one_or_none()
    if doc is None:
        raise NotFoundError("Document not found")

    storage = StorageService()
    try:
        await storage.delete(doc.storage_path)
        await storage.delete(f"{doc.user_id}/{doc.id}/parsed.json")
    except Exception:
        pass

    await session.delete(doc)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _to_dict(d: Document) -> dict:
    return {
        "id": d.id,
        "filename": d.filename,
        "source_type": d.source_type,
        "mime_type": d.mime_type,
        "file_size_bytes": d.file_size_bytes,
        "processing_status": d.processing_status,
        "error_message": d.error_message,
        "word_count": d.word_count,
        "chunk_count": d.chunk_count,
        "language": d.language,
        "uploaded_at": d.uploaded_at,
        "completed_at": d.completed_at,
        "credibility_score": d.credibility_score,
        "credibility_breakdown": d.credibility_breakdown,
        "credibility_computed_at": d.credibility_computed_at,
        "source_url": d.source_url,
    }
