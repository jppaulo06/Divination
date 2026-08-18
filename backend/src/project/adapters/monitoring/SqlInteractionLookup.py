"""SQL implementation of the InteractionLookup port."""

import logging
from collections import defaultdict

from sqlalchemy import select

from project.adapters.monitoring.models import Interaction
from project.ports.monitoring.InteractionLookup import InteractionLookup

logger = logging.getLogger(__name__)


class SqlInteractionLookup(InteractionLookup):
    def __init__(self, database):
        self.database = database

    def ids_by_answer(self, chat_id: str) -> dict[str, list[str]]:
        try:
            with self.database.session() as session:
                rows = session.execute(
                    select(Interaction.answer, Interaction.id)
                    .where(
                        Interaction.chat_id == chat_id,
                        # A failed interaction is recorded but never
                        # reaches the chat history, so it has no message
                        # to be matched against.
                        Interaction.error.is_(None),
                    )
                    .order_by(Interaction.turn_index)
                ).all()
        except Exception:
            logger.exception("interaction lookup failed for chat %s", chat_id)
            return {}

        grouped = defaultdict(list)
        for answer, interaction_id in rows:
            grouped[answer].append(interaction_id)
        return dict(grouped)
