import uuid

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ChunkTopic(Base):
    """BERTopic cluster assignment for a chunk (one cluster per chunk)."""

    __tablename__ = "chunk_topics"
    __table_args__ = (Index("idx_chunk_topics_cluster", "cluster_id"),)

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    cluster_id: Mapped[int] = mapped_column(Integer, nullable=False)
    cluster_label: Mapped[str] = mapped_column(Text, nullable=False)

    chunk = relationship("Chunk", backref="chunk_topic")
