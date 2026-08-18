"""Port for finding the recorded interaction behind a stored answer."""

from abc import ABC, abstractmethod


class InteractionLookup(ABC):
    @abstractmethod
    def ids_by_answer(self, chat_id: str) -> dict[str, list[str]]:
        """Interaction ids for one chat, grouped by answer text.

        Each list is in turn order, so repeated identical answers can be
        handed out in the order they were produced.
        """


class NullInteractionLookup(InteractionLookup):
    """Finds nothing. Default when monitoring is not wired."""

    def ids_by_answer(self, chat_id: str) -> dict[str, list[str]]:
        return {}
