"""SQL implementation of the InteractionSink port."""

import logging
import uuid

from sqlalchemy import func, select

from project.adapters.monitoring.models import (
    SCOPE_TURN,
    Feedback,
    Interaction,
    RetrievedChunk,
    Signal,
)
from project.ports.monitoring.InteractionSink import (
    InteractionRecord,
    InteractionSink,
)

logger = logging.getLogger(__name__)

NEGATIVE_FEEDBACK_SIGNAL = "user_negative_feedback"
NEGATIVE_FEEDBACK_DETECTOR_VERSION = "1"


class SqlInteractionSink(InteractionSink):
    def __init__(self, database, negative_rating_threshold: int = 0):
        self.database = database
        self.negative_rating_threshold = negative_rating_threshold

    def record_interaction(self, record: InteractionRecord) -> str | None:
        interaction_id = str(uuid.uuid4())
        try:
            with self.database.session() as session:
                turn_index = session.scalar(
                    select(func.count())
                    .select_from(Interaction)
                    .where(Interaction.chat_id == record.chat_id)
                )

                session.add(
                    Interaction(
                        id=interaction_id,
                        chat_id=record.chat_id,
                        turn_index=turn_index or 0,
                        question=record.question,
                        answer=record.answer,
                        source=record.source,
                        model=record.model,
                        template_name=record.template_name,
                        template_hash=record.template_hash,
                        corpus_version=record.corpus_version,
                        latency_ms=record.latency_ms,
                        error=record.error,
                    )
                )
                session.add_all(
                    RetrievedChunk(
                        interaction_id=interaction_id,
                        rank=chunk.rank,
                        score=chunk.score,
                        page=chunk.page,
                        content=chunk.content,
                    )
                    for chunk in record.chunks
                )
                session.commit()
            return interaction_id
        except Exception:
            logger.exception("failed to record interaction; continuing")
            return None

    def record_feedback(
        self, interaction_id: str, rating: int, comment: str | None = None
    ) -> int:
        """Insert a rating and, when negative, its signal in one transaction.

        Committing them together is what guarantees a negative rating can
        never end up with no signal attached.
        """
        with self.database.session() as session:
            interaction = session.get(Interaction, interaction_id)
            if interaction is None:
                raise LookupError(f"unknown interaction {interaction_id!r}")

            feedback = Feedback(
                interaction_id=interaction_id,
                rating=rating,
                comment=comment,
            )
            session.add(feedback)
            # Assign feedback.id so the signal can reference it.
            session.flush()

            if rating <= self.negative_rating_threshold:
                self._flag_once(session, interaction, feedback, rating, comment)

            session.commit()
            return feedback.id

    def _flag_once(self, session, interaction, feedback, rating, comment):
        # Feedback is append-only, so the same interaction can be rated
        # negatively more than once. A second signal would violate the
        # uniqueness key and roll the feedback row back with it.
        already_flagged = session.scalar(
            select(Signal.id).where(
                Signal.interaction_id == interaction.id,
                Signal.type == NEGATIVE_FEEDBACK_SIGNAL,
                Signal.detector_version == NEGATIVE_FEEDBACK_DETECTOR_VERSION,
            )
        )
        if already_flagged is not None:
            return

        session.add(
            Signal(
                interaction_id=interaction.id,
                chat_id=interaction.chat_id,
                scope=SCOPE_TURN,
                type=NEGATIVE_FEEDBACK_SIGNAL,
                score=float(rating),
                details={
                    "feedback_id": feedback.id,
                    "rating": rating,
                    "comment": comment,
                },
                detector_version=NEGATIVE_FEEDBACK_DETECTOR_VERSION,
            )
        )
