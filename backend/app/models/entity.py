import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


# Built-in spaCy types: PERSON, ORG, GPE, DATE, EVENT
# GLiNER custom types: CONCEPT, TOOL, METHOD, METRIC
# Phase 3.5: user_insight — entities projected from user annotations
ENTITY_TYPES = (
    "PERSON",
    "ORG",
    "GPE",
    "DATE",
    "EVENT",
    "CONCEPT",
    "TOOL",
    "METHOD",
    "METRIC",
    "user_insight",
)


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (
        Index("idx_entities_user_type", "user_id", "type"),
        Index("idx_entities_canon", "user_id", "type", "canonical_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(512), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    evidence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    aliases = relationship(
        "EntityAlias", back_populates="entity", cascade="all, delete-orphan"
    )
    chunk_links = relationship(
        "ChunkEntity", back_populates="entity", cascade="all, delete-orphan"
    )


class EntityAlias(Base):
    __tablename__ = "entity_aliases"
    __table_args__ = (
        UniqueConstraint("entity_id", "surface_form", name="uq_entity_aliases_form"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    surface_form: Mapped[str] = mapped_column(String(512), nullable=False)

    entity = relationship("Entity", back_populates="aliases")


class ChunkEntity(Base):
    __tablename__ = "chunk_entities"
    __table_args__ = (
        Index("idx_ce_entity", "entity_id"),
    )

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    char_start: Mapped[int] = mapped_column(Integer, primary_key=True)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)

    entity = relationship("Entity", back_populates="chunk_links")
