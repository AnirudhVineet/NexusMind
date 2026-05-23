"""Email Settings API — Phase 4 Track F.

Stores per-user SMTP configuration for send_email workflow actions.

GET /api/email-settings  — retrieve current settings (password masked)
PUT /api/email-settings  — create or update settings (password encrypted at rest)
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.config import get_settings
from app.db.session import get_session
from app.models.user import User
from app.models.workflow import EmailSettings
from app.services.workflows import encrypt_password

router = APIRouter(prefix="/api", tags=["settings"])


# ─── Pydantic schemas ──────────────────────────────────────────────────────────


class EmailSettingsUpdate(BaseModel):
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""  # plaintext — encrypted before storage
    from_address: str = ""
    enabled: bool = False


class EmailSettingsOut(BaseModel):
    user_id: uuid.UUID
    smtp_host: str
    smtp_port: int
    smtp_username: str
    from_address: str
    enabled: bool
    password: str = "***"  # always masked in responses


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _settings_out(row: EmailSettings) -> EmailSettingsOut:
    return EmailSettingsOut(
        user_id=row.user_id,
        smtp_host=row.smtp_host,
        smtp_port=row.smtp_port,
        smtp_username=row.smtp_username,
        from_address=row.from_address,
        enabled=row.enabled,
        password="***",
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/email-settings", response_model=EmailSettingsOut)
async def get_email_settings(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EmailSettingsOut:
    row = (
        await session.execute(
            select(EmailSettings).where(EmailSettings.user_id == current_user.id)
        )
    ).scalar_one_or_none()

    if row is None:
        # Return default (empty) settings if none exist yet
        return EmailSettingsOut(
            user_id=current_user.id,
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            smtp_username="",
            from_address="",
            enabled=False,
            password="***",
        )

    return _settings_out(row)


@router.put("/email-settings", response_model=EmailSettingsOut)
async def upsert_email_settings(
    body: EmailSettingsUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EmailSettingsOut:
    settings = get_settings()

    encrypted_password = encrypt_password(body.smtp_password, settings.jwt_secret)

    row = (
        await session.execute(
            select(EmailSettings).where(EmailSettings.user_id == current_user.id)
        )
    ).scalar_one_or_none()

    if row is None:
        row = EmailSettings(user_id=current_user.id)
        session.add(row)

    row.smtp_host = body.smtp_host
    row.smtp_port = body.smtp_port
    row.smtp_username = body.smtp_username
    row.smtp_password_encrypted = encrypted_password
    row.from_address = body.from_address
    row.enabled = body.enabled

    await session.commit()
    await session.refresh(row)
    return _settings_out(row)
