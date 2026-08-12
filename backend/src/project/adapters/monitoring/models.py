"""Monitoring tables: interactions, retrieved chunks, signals, feedback,
curation reviews."""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

SOURCE_PRODUCTION = "production"
SOURCE_SYNTHETIC = "synthetic"
SOURCE_EVAL = "eval"

SCOPE_TURN = "turn"
SCOPE_THREAD = "thread"

VERDICT_DEFECT = "defect"
VERDICT_NOISE = "noise"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Interaction(Base):
    """One question/answer exchange, recorded for every request."""

    __tablename__ = "interactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(64), index=True)
    turn_index: Mapped[int] = mapped_column(Integer, default=0)

    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="")

    source: Mapped[str] = mapped_column(
        String(16), default=SOURCE_PRODUCTION, index=True
    )

    model: Mapped[str] = mapped_column(String(64), default="")
    template_name: Mapped[str] = mapped_column(String(64), default="")
    template_hash: Mapped[str] = mapped_column(String(16), default="")
    corpus_version: Mapped[str] = mapped_column(String(32), default="")

    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    chunks: Mapped[list["RetrievedChunk"]] = relationship(
        back_populates="interaction",
        cascade="all, delete-orphan",
        order_by="RetrievedChunk.rank",
    )
    signals: Mapped[list["Signal"]] = relationship(
        back_populates="interaction", cascade="all, delete-orphan"
    )
    feedback: Mapped[list["Feedback"]] = relationship(
        back_populates="interaction", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["CurationReview"]] = relationship(
        back_populates="interaction", cascade="all, delete-orphan"
    )


class RetrievedChunk(Base):
    """A document the retriever returned for one interaction."""

    __tablename__ = "retrieved_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interaction_id: Mapped[str] = mapped_column(
        ForeignKey("interactions.id", ondelete="CASCADE"), index=True
    )

    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text)

    interaction: Mapped[Interaction] = relationship(back_populates="chunks")


class Signal(Base):
    """A detector's flag on one interaction."""

    __tablename__ = "signals"
    __table_args__ = (
        # Makes detector re-runs idempotent.
        UniqueConstraint(
            "interaction_id",
            "type",
            "detector_version",
            name="uq_signal_per_detector_version",
        ),
        Index("ix_signals_type_created", "type", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interaction_id: Mapped[str] = mapped_column(
        ForeignKey("interactions.id", ondelete="CASCADE"), index=True
    )

    chat_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True
    )
    scope: Mapped[str] = mapped_column(String(8), default=SCOPE_TURN)

    type: Mapped[str] = mapped_column(String(64))
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    detector_version: Mapped[str] = mapped_column(String(16), default="1")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    interaction: Mapped[Interaction] = relationship(back_populates="signals")


class Feedback(Base):
    """A user rating. Append-only: a rating change adds a row."""

    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interaction_id: Mapped[str] = mapped_column(
        ForeignKey("interactions.id", ondelete="CASCADE"), index=True
    )

    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    interaction: Mapped[Interaction] = relationship(back_populates="feedback")


class CurationReview(Base):
    """A verdict on a flagged interaction.

    Absence of a row is what marks an interaction as still pending review.
    """

    __tablename__ = "curation_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    interaction_id: Mapped[str] = mapped_column(
        ForeignKey("interactions.id", ondelete="CASCADE"), index=True
    )

    verdict: Mapped[str] = mapped_column(String(16))
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer: Mapped[str] = mapped_column(String(16), default="llm")
    promoted_golden: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    interaction: Mapped[Interaction] = relationship(back_populates="reviews")
