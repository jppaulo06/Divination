"""Queries over flagged interactions awaiting review."""

from dataclasses import dataclass, field

from sqlalchemy import func, select

from project.adapters.monitoring.detectors.weak_retrieval import (
    DEFAULT_SCORE_THRESHOLD,
)
from project.adapters.monitoring.models import (
    CurationReview,
    Feedback,
    Interaction,
    RetrievedChunk,
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
        """Aggregate counts and distributions for the monitoring view."""
        with self.database.session() as session:
            total = session.scalar(
                select(func.count()).select_from(Interaction)
            )
            reviewed_ids = select(
                CurationReview.interaction_id
            ).scalar_subquery()
            pending = session.scalar(
                select(func.count(func.distinct(Signal.interaction_id))).where(
                    Signal.interaction_id.not_in(reviewed_ids)
                )
            )
            flagged = session.scalar(
                select(func.count(func.distinct(Signal.interaction_id)))
            )
            reviewed = session.scalar(
                select(func.count(func.distinct(CurationReview.interaction_id)))
            )
            by_type = session.execute(
                select(Signal.type, func.count(Signal.id)).group_by(
                    Signal.type
                )
            ).all()
            by_source = session.execute(
                select(Interaction.source, func.count(Interaction.id)).group_by(
                    Interaction.source
                )
            ).all()
            positive = session.scalar(
                select(func.count())
                .select_from(Feedback)
                .where(Feedback.rating > 0)
            )
            negative = session.scalar(
                select(func.count())
                .select_from(Feedback)
                .where(Feedback.rating <= 0)
            )
            # One row per interaction: the best score its retrieval found.
            top_scores = [
                score
                for (score,) in session.execute(
                    select(func.max(RetrievedChunk.score)).group_by(
                        RetrievedChunk.interaction_id
                    )
                ).all()
                if score is not None
            ]
            latencies = [
                value
                for value in session.scalars(
                    select(Interaction.latency_ms).where(
                        Interaction.latency_ms > 0
                    )
                )
            ]

        return {
            "interactions": total or 0,
            "flagged_interactions": flagged or 0,
            "pending_candidates": pending or 0,
            "reviewed_interactions": reviewed or 0,
            "signals_by_type": {row[0]: row[1] for row in by_type},
            "interactions_by_source": {row[0]: row[1] for row in by_source},
            "feedback": {
                "positive": positive or 0,
                "negative": negative or 0,
            },
            "retrieval_scores": {
                "count": len(top_scores),
                "threshold": DEFAULT_SCORE_THRESHOLD,
                "below_threshold": sum(
                    1 for s in top_scores if s < DEFAULT_SCORE_THRESHOLD
                ),
                "bins": _histogram(top_scores),
            },
            "latency_ms": {
                "p50": _percentile(latencies, 0.5),
                "p95": _percentile(latencies, 0.95),
                "max": max(latencies) if latencies else 0,
            },
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


def _percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def _histogram(values: list[float], bin_count: int = 12) -> list[dict]:
    """Buckets over the observed range rather than a fixed 0-1 span.

    Retrieval scores have clustered inside a narrow band in practice, and
    fixed bins over the full range would collapse the whole distribution
    into one bar.
    """
    if not values:
        return []

    low, high = min(values), max(values)
    if high == low:
        return [{"lo": low, "hi": high, "count": len(values)}]

    width = (high - low) / bin_count
    bins = [
        {"lo": low + index * width, "hi": low + (index + 1) * width,
         "count": 0}
        for index in range(bin_count)
    ]
    for value in values:
        index = min(bin_count - 1, int((value - low) / width))
        bins[index]["count"] += 1
    return bins
