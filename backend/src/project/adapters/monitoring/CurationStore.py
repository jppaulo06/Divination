"""Sampling and review storage for curation (CD4AI stage 3)."""

from dataclasses import dataclass, field

from sqlalchemy import func, select

from project.adapters.monitoring.models import (
    CurationReview,
    Feedback,
    Interaction,
    Signal,
    VERDICT_DEFECT,
)

DEFAULT_SAMPLE_SIZE = 20
DEFAULT_FLAGGED_SHARE = 0.5


@dataclass
class Turn:
    turn_index: int
    question: str
    answer: str
    is_subject: bool


@dataclass
class SampledInteraction:
    """One interaction to review, with the conversation around it.

    `signals` is carried so the client can reveal it *after* a verdict.
    Showing it first would anchor the reviewer, and the whole point of
    sampling unflagged traffic is to get a judgement the detectors did not
    influence.
    """

    interaction_id: str
    chat_id: str
    turn_index: int
    question: str
    answer: str
    source: str
    model: str
    template_name: str
    corpus_version: str
    latency_ms: int
    created_at: str
    stratum: str
    signals: list[dict] = field(default_factory=list)
    feedback: list[dict] = field(default_factory=list)
    retrieval_context: list[str] = field(default_factory=list)
    top_score: float | None = None
    thread: list[Turn] = field(default_factory=list)


class CurationStore:
    def __init__(self, database):
        self.database = database

    def sample(
        self,
        size: int = DEFAULT_SAMPLE_SIZE,
        flagged_share: float = DEFAULT_FLAGGED_SHARE,
    ) -> list[SampledInteraction]:
        """Draws an unreviewed sample from both strata.

        Flagged interactions measure how often a signal is a real defect.
        Unflagged ones are the only way to find what the detectors miss —
        a confident hallucination raises no signal at all, so a queue of
        flagged items cannot reveal it.

        A short stratum is topped up from the other one, so a small
        database still yields a full sample.
        """
        wanted_flagged = round(size * flagged_share)
        wanted_plain = size - wanted_flagged

        with self.database.session() as session:
            flagged = self._draw(session, wanted_flagged, flagged=True)
            plain = self._draw(session, wanted_plain, flagged=False)

            # Top up from whichever stratum still has unreviewed rows.
            if len(flagged) < wanted_flagged:
                plain += self._draw(
                    session,
                    wanted_flagged - len(flagged),
                    flagged=False,
                    exclude=[item.id for item in plain],
                )
            elif len(plain) < wanted_plain:
                flagged += self._draw(
                    session,
                    wanted_plain - len(plain),
                    flagged=True,
                    exclude=[item.id for item in flagged],
                )

            sampled = [(item, "flagged") for item in flagged]
            sampled += [(item, "unflagged") for item in plain]
            return [
                self._to_sampled(session, interaction, stratum)
                for interaction, stratum in sampled
            ]

    def record_review(
        self,
        interaction_id: str,
        verdict: str,
        rationale: str | None = None,
        reviewer: str = "human",
    ) -> int:
        with self.database.session() as session:
            if session.get(Interaction, interaction_id) is None:
                raise LookupError(f"unknown interaction {interaction_id!r}")

            review = CurationReview(
                interaction_id=interaction_id,
                verdict=verdict,
                rationale=rationale,
                reviewer=reviewer,
            )
            session.add(review)
            session.commit()
            return review.id

    def stats(self) -> dict:
        """Detector precision, and a recall estimate from both strata.

        Precision comes straight from the flagged stratum. Recall cannot:
        the sample is stratified, so the raw defect ratio is biased by how
        much of each pool was drawn. Each stratum's defect rate is scaled
        back up to its pool size before the two are compared.
        """
        with self.database.session() as session:
            flagged_pool = self._pool_size(session, flagged=True)
            plain_pool = self._pool_size(session, flagged=False)

            flagged_reviewed, flagged_defects = self._reviewed(
                session, flagged=True
            )
            plain_reviewed, plain_defects = self._reviewed(
                session, flagged=False
            )

        precision = (
            flagged_defects / flagged_reviewed if flagged_reviewed else None
        )

        recall = None
        if flagged_reviewed and plain_reviewed:
            true_positives = flagged_pool * (flagged_defects / flagged_reviewed)
            missed = plain_pool * (plain_defects / plain_reviewed)
            total = true_positives + missed
            recall = true_positives / total if total else None

        return {
            "flagged": {
                "pool": flagged_pool,
                "reviewed": flagged_reviewed,
                "defects": flagged_defects,
            },
            "unflagged": {
                "pool": plain_pool,
                "reviewed": plain_reviewed,
                "defects": plain_defects,
            },
            "precision": precision,
            "estimated_recall": recall,
        }

    def _signal_ids(self):
        return select(Signal.interaction_id).distinct().scalar_subquery()

    def _reviewed_ids(self):
        return select(CurationReview.interaction_id).scalar_subquery()

    def _stratum_filter(self, flagged: bool):
        if flagged:
            return Interaction.id.in_(self._signal_ids())
        return Interaction.id.not_in(self._signal_ids())

    def _draw(self, session, count, flagged, exclude=None):
        if count <= 0:
            return []

        query = (
            select(Interaction)
            .where(
                self._stratum_filter(flagged),
                Interaction.id.not_in(self._reviewed_ids()),
                # An errored interaction has no answer to judge.
                Interaction.error.is_(None),
            )
            .order_by(func.random())
            .limit(count)
        )
        if exclude:
            query = query.where(Interaction.id.not_in(exclude))

        return list(session.scalars(query))

    def _pool_size(self, session, flagged: bool) -> int:
        return (
            session.scalar(
                select(func.count())
                .select_from(Interaction)
                .where(
                    self._stratum_filter(flagged),
                    Interaction.error.is_(None),
                )
            )
            or 0
        )

    def _reviewed(self, session, flagged: bool) -> tuple[int, int]:
        reviewed = (
            session.scalar(
                select(func.count(func.distinct(CurationReview.interaction_id)))
                .select_from(CurationReview)
                .join(
                    Interaction,
                    Interaction.id == CurationReview.interaction_id,
                )
                .where(self._stratum_filter(flagged))
            )
            or 0
        )
        defects = (
            session.scalar(
                select(func.count(func.distinct(CurationReview.interaction_id)))
                .select_from(CurationReview)
                .join(
                    Interaction,
                    Interaction.id == CurationReview.interaction_id,
                )
                .where(
                    self._stratum_filter(flagged),
                    CurationReview.verdict == VERDICT_DEFECT,
                )
            )
            or 0
        )
        return reviewed, defects

    def _to_sampled(self, session, interaction, stratum):
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
        thread = list(
            session.execute(
                select(
                    Interaction.turn_index,
                    Interaction.question,
                    Interaction.answer,
                    Interaction.id,
                )
                .where(Interaction.chat_id == interaction.chat_id)
                .order_by(Interaction.turn_index)
            ).all()
        )
        scores = [c.score for c in interaction.chunks if c.score is not None]

        return SampledInteraction(
            interaction_id=interaction.id,
            chat_id=interaction.chat_id,
            turn_index=interaction.turn_index,
            question=interaction.question,
            answer=interaction.answer,
            source=interaction.source,
            model=interaction.model,
            template_name=interaction.template_name,
            corpus_version=interaction.corpus_version,
            latency_ms=interaction.latency_ms,
            created_at=interaction.created_at.isoformat(),
            stratum=stratum,
            signals=[
                {
                    "type": s.type,
                    "scope": s.scope,
                    "score": s.score,
                    "details": s.details or {},
                    "detector_version": s.detector_version,
                }
                for s in signals
            ],
            feedback=[
                {"rating": f.rating, "comment": f.comment} for f in feedback
            ],
            retrieval_context=[c.content for c in interaction.chunks],
            top_score=max(scores) if scores else None,
            thread=[
                Turn(
                    turn_index=row[0],
                    question=row[1],
                    answer=row[2],
                    is_subject=row[3] == interaction.id,
                )
                for row in thread
            ],
        )
