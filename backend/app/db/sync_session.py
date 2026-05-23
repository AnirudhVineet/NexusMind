from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def _engine():
    return create_engine(
        get_settings().database_sync_url,
        pool_pre_ping=True,
        future=True,
    )


@lru_cache
def _SessionLocal() -> sessionmaker:
    return sessionmaker(bind=_engine(), expire_on_commit=False, class_=Session)


def get_sync_session() -> Session:
    return _SessionLocal()()
