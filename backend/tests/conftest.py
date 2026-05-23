import os
import sys
from pathlib import Path

# Required env BEFORE importing app modules
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/nexusmind_test")
os.environ.setdefault("DATABASE_SYNC_URL", "postgresql://postgres:password@localhost:5432/nexusmind_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/10")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/11")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/12")
os.environ.setdefault("STORAGE_DIR", "./data/test-files")
os.environ.setdefault("GROQ_API_KEY", "gsk-test")
os.environ.setdefault("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
os.environ.setdefault("GEMINI_API_KEY", "gemini-test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"
