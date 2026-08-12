"""Queries over flagged interactions awaiting review."""

from dataclasses import dataclass, field

from sqlalchemy import func, select

from project.adapters.monitoring.models import (
    CurationReview,
    Feedback,
    Interaction,
    Signal,
)


@dataclass
class CandidateSignal:
    type: str
    scope: str
    score: float | None
    details: dict
    detector_version: str


@dataclass
class CandidateFeedback:
    rating: int
    comment: str | None


@dataclass
class Candidate:
    """A flagged interaction with its signals, feedback and context."""

    interaction_id: str
    chat_id: str
    turn_index: int
    question: str
    answer: str
    source: str
    model: str
    template_name: str
    template_hash: str
    corpus_version: str
    latency_ms: int
    error: str | None
    created_at: str
    signals: list[CandidateSignal] = field(default_factory=list)
    feedback: list[CandidateFeedback] = field(default_factory=list)
    retrieval_context: list[str] = field(default_factory=list)
    top_score: float | None = None


class CandidateQuery:
    def __init__(self, database):
        self.database = database

    def pending(
        self,
        limit: int = 50,
        signal_type: str | None = None,
        source: str | None = None,
    ) -> list[Candidate]:
        """Interactions with >=1 signal and no curation review yet."""
        with self.database.session() as session:
            reviewed = select(CurationReview.interaction_id).scalar_subquery()

            query = (
                select(Interaction)
                .join(Signal, Signal.interaction_id == Interaction.id)
                .where(Interaction.id.not_in(reviewed))
                .group_by(Interaction.id)
                # Most-flagged first.
                .order_by(
                    func.count(Signal.id).desc(), Interaction.created_at.desc()
                )
                .limit(limit)
            )

            if signal_type is not None:
                query = query.where(Signal.type == signal_type)
            if source is not None:
                query = query.where(Interaction.source == source)

            interactions = list(session.scalars(query))
            return [
                self._to_candidate(session, interaction)
                for interaction in interactions
            ]

    def summary(self) -> dict:
        """Interaction, candidate and per-type signal counts."""
        with self.database.session() as session:
            total = session.scalar(
                select(func.count()).select_from(Interaction)
            )
            reviewed = select(CurationReview.interaction_id).scalar_subquery()
            pending = session.scalar(
                select(func.count(func.distinct(Signal.interaction_id))).where(
                    Signal.interaction_id.not_in(reviewed)
                )
            )
            by_type = session.execute(
                select(Signal.type, func.count(Signal.id)).group_by(
                    Signal.type
                )
            ).all()

            return {
                "interactions": total or 0,
                "pending_candidates": pending or 0,
                "signals_by_type": {row[0]: row[1] for row in by_type},
            }

    def _to_candidate(self, session, interaction: Interaction) -> Candidate:
        signals = list(
            session.scalars(
                select(Signal).where(Signal.interaction_id == interaction.id)
            )
        )
        feedback = list(
            session.scalars(
                select(Feedback)
                .where(Feedback.interaction_id == interaction.id)
                .order_by(Feedback.created_at)
            )
        )
        scores = [c.score for c in interaction.chunks if c.score is not None]

        return Candidate(
            interaction_id=interaction.id,
            chat_id=interaction.chat_id,
            turn_index=interaction.turn_index,
            question=interaction.question,
            answer=interaction.answer,
            source=interaction.source,
            model=interaction.model,
            template_name=interaction.template_name,
            template_hash=interaction.template_hash,
            corpus_version=interaction.corpus_version,
            latency_ms=interaction.latency_ms,
            error=interaction.error,
            created_at=interaction.created_at.isoformat(),
            signals=[
                CandidateSignal(
                    type=s.type,
                    scope=s.scope,
                    score=s.score,
                    details=s.details or {},
                    detector_version=s.detector_version,
                )
                for s in signals
            ],
            feedback=[
                CandidateFeedback(rating=f.rating, comment=f.comment)
                for f in feedback
            ],
            retrieval_context=[c.content for c in interaction.chunks],
            top_score=max(scores) if scores else None,
        )
