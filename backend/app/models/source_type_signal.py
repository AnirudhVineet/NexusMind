from sqlalchemy import (
    CheckConstraint,
    Float,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SourceTypeSignal(Base):
    __tablename__ = "source_type_signals"
    __table_args__ = (
        CheckConstraint(
            "match_kind IN ('mime', 'host_regex', 'path_regex')",
            name="ck_sts_match_kind",
        ),
        CheckConstraint("signal_value BETWEEN 0 AND 1", name="ck_sts_signal_value"),
        UniqueConstraint("match_kind", "match_value", name="uq_sts_match"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    match_value: Mapped[str] = mapped_column(String(256), nullable=False)
    source_label: Mapped[str] = mapped_column(String(32), nullable=False)
    signal_value: Mapped[float] = mapped_column(Float, nullable=False)
    half_life_days: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("100")
    )
