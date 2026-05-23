import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


RELATION_TYPES = (
    "depends_on",
    "contradicts",
    "authored_by",
    "relates_to",
    "is_part_of",
    "references",
    "co_occurs_with",
)


class EntityEdge(Base):
    __tablename__ = "entity_edges"
    __table_args__ = (
        CheckConstraint(
            "relation_type IN (" + ", ".join(f"'{r}'" for r in RELATION_TYPES) + ")",
            name="ck_entity_edges_relation_type",
        ),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_entity_edges_confidence"),
        UniqueConstraint(
            "src_id",
            "dst_id",
            "relation_type",
            "evidence_chunk_id",
            name="uq_entity_edges_dedup",
        ),
        Index("idx_edges_src", "src_id", "relation_type"),
        Index("idx_edges_dst", "dst_id", "relation_type"),
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
    src_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    dst_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        nullable=False,
    )
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )

    src = relationship("Entity", foreign_keys=[src_id])
    dst = relationship("Entity", foreign_keys=[dst_id])
