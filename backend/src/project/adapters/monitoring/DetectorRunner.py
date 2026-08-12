"""Runs detectors over stored interactions and writes signals."""

import logging

from sqlalchemy import select

from project.adapters.monitoring.detectors import default_detectors
from project.adapters.monitoring.models import Interaction, Signal
from project.ports.monitoring.SignalDetector import ChunkView, InteractionView

logger = logging.getLogger(__name__)


class DetectorRunner:
    def __init__(self, database, detectors=None):
        self.database = database
        self.detectors = (
            detectors if detectors is not None else default_detectors()
        )

    def run_for_interaction(self, interaction_id: str) -> int:
        """Detect and store signals for one interaction.

        Returns the number of new signals written. Does not raise: this
        runs as a background task, where the log is more useful.
        """
        try:
            with self.database.session() as session:
                interaction = session.get(Interaction, interaction_id)
                if interaction is None:
                    logger.warning(
                        "interaction %s vanished before detection",
                        interaction_id,
                    )
                    return 0

                view = self._build_view(session, interaction)
                written = self._store_signals(session, interaction, view)
                session.commit()
                return written
        except Exception:
            logger.exception(
                "detector run failed for interaction %s", interaction_id
            )
            return 0

    def backfill(self, limit: int | None = None) -> int:
        """Re-run all detectors over stored interactions.

        Idempotent, so it is safe to repeat and to run after bumping a
        detector's version.
        """
        total = 0
        with self.database.session() as session:
            query = select(Interaction).order_by(Interaction.created_at)
            if limit is not None:
                query = query.limit(limit)

            for interaction in session.scalars(query):
                view = self._build_view(session, interaction)
                total += self._store_signals(session, interaction, view)

            session.commit()
        return total

    def _build_view(self, session, interaction: Interaction) -> InteractionView:
        prior_questions = list(
            session.scalars(
                select(Interaction.question)
                .where(
                    Interaction.chat_id == interaction.chat_id,
                    Interaction.turn_index < interaction.turn_index,
                )
                .order_by(Interaction.turn_index)
            )
        )

        return InteractionView(
            id=interaction.id,
            chat_id=interaction.chat_id,
            question=interaction.question,
            answer=interaction.answer,
            chunks=[
                ChunkView(rank=c.rank, content=c.content, score=c.score)
                for c in interaction.chunks
            ],
            template_name=interaction.template_name,
            error=interaction.error,
            prior_questions=prior_questions,
        )

    def _store_signals(
        self, session, interaction: Interaction, view: InteractionView
    ) -> int:
        written = 0
        for detector in self.detectors:
            try:
                detected = detector.detect(view) or []
            except Exception:
                # One failing detector must not stop the others.
                logger.exception(
                    "detector %s failed on interaction %s",
                    detector.name,
                    interaction.id,
                )
                continue

            for signal in detected:
                if self._already_stored(session, interaction.id, detector):
                    continue

                session.add(
                    Signal(
                        interaction_id=interaction.id,
                        chat_id=interaction.chat_id,
                        scope=signal.scope,
                        type=signal.type,
                        score=signal.score,
                        details=signal.details,
                        detector_version=detector.version,
                    )
                )
                session.flush()
                written += 1

        return written

    def _already_stored(self, session, interaction_id: str, detector) -> bool:
        return (
            session.scalar(
                select(Signal.id).where(
                    Signal.interaction_id == interaction_id,
                    Signal.type == detector.name,
                    Signal.detector_version == detector.version,
                )
            )
            is not None
        )
