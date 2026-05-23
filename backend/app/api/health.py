from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.services.embedding import _redis
from app.services.storage import StorageService

router = APIRouter(prefix="", tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/readiness")
async def readiness(response: Response) -> dict:
    failures: list[str] = []

    # Postgres
    try:
        async with AsyncSessionLocal() as s:
            await s.execute(text("SELECT 1"))
    except Exception as e:
        failures.append(f"postgres: {e}")

    # Redis
    try:
        r = _redis()
        await r.ping()
    except Exception as e:
        failures.append(f"redis: {e}")

    # Local filesystem storage
    try:
        await StorageService().ensure_bucket()
    except Exception as e:
        failures.append(f"storage: {e}")

    if failures:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", "errors": failures}
    return {"status": "ready"}
