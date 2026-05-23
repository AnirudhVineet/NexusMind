"""Web Push subscription management API — Phase 4 Track G.

GET    /api/push/vapid-public-key          — retrieve the VAPID public key
POST   /api/push/subscribe                 — register a push subscription
DELETE /api/push/subscribe/{endpoint_hash} — remove a push subscription
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_session
from app.models.alert import PushSubscription
from app.models.user import User

router = APIRouter(prefix="/api", tags=["push"])


# ─── VAPID key management ─────────────────────────────────────────────────────

def _get_vapid_keys() -> dict[str, str]:
    """Load or generate VAPID keys from DATA_DIR/config/vapid_keys.json."""
    from app.core.config import get_settings

    settings = get_settings()
    key_path = Path(settings.storage_dir).parent / "config" / "vapid_keys.json"
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if key_path.exists():
        return json.loads(key_path.read_text())

    # Try py_vapid first, fall back to cryptography
    keys: dict[str, str]
    try:
        from py_vapid import Vapid
        from cryptography.hazmat.primitives import serialization

        vapid = Vapid()
        vapid.generate_keys()
        pub_bytes = vapid.public_key.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        priv_bytes = vapid.private_key.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        import base64
        keys = {
            "public_key": base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode(),
            "private_key": base64.urlsafe_b64encode(priv_bytes).rstrip(b"=").decode(),
        }
    except ImportError:
        # Fallback: generate using cryptography directly
        import base64
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization

        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key()
        pub_bytes = public_key.public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        )
        priv_bytes = private_key.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        keys = {
            "public_key": base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode(),
            "private_key": base64.urlsafe_b64encode(priv_bytes).rstrip(b"=").decode(),
        }

    key_path.write_text(json.dumps(keys))
    return keys


def _endpoint_hash(endpoint: str) -> str:
    """Return first 16 hex chars of SHA-256 of the endpoint URL."""
    return hashlib.sha256(endpoint.encode()).hexdigest()[:16]


# ─── schemas ──────────────────────────────────────────────────────────────────

class PushSubscriptionCreate(BaseModel):
    endpoint: str
    auth: str
    p256dh: str


# ─── endpoints ────────────────────────────────────────────────────────────────

@router.get("/push/vapid-public-key")
async def get_vapid_public_key() -> dict[str, str]:
    keys = _get_vapid_keys()
    return {"public_key": keys["public_key"]}


@router.post("/push/subscribe")
async def subscribe_push(
    body: PushSubscriptionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    # Upsert: update auth/p256dh if endpoint already exists
    stmt = (
        pg_insert(PushSubscription)
        .values(
            endpoint=body.endpoint,
            user_id=current_user.id,
            auth=body.auth,
            p256dh=body.p256dh,
        )
        .on_conflict_do_update(
            index_elements=["endpoint"],
            set_={
                "user_id": current_user.id,
                "auth": body.auth,
                "p256dh": body.p256dh,
            },
        )
    )
    await session.execute(stmt)
    await session.commit()
    return {"status": "ok"}


@router.delete(
    "/push/subscribe/{endpoint_hash}", status_code=status.HTTP_204_NO_CONTENT
)
async def unsubscribe_push(
    endpoint_hash: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    # Load all subscriptions for this user and match by hashing their endpoints
    subs = (
        await session.execute(
            select(PushSubscription).where(
                PushSubscription.user_id == current_user.id
            )
        )
    ).scalars().all()

    target: PushSubscription | None = None
    for sub in subs:
        if _endpoint_hash(sub.endpoint) == endpoint_hash:
            target = sub
            break

    if target is None:
        raise NotFoundError("Push subscription not found")

    await session.delete(target)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
