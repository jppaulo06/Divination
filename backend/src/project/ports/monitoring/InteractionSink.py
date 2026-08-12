"""Port for recording production interactions."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RetrievedChunkRecord:
    rank: int
    content: str
    score: float | None = None
    page: int | None = None


@dataclass
class InteractionRecord:
    chat_id: str
    question: str
    answer: str
    source: str = "production"
    model: str = ""
    template_name: str = ""
    template_hash: str = ""
    corpus_version: str = ""
    latency_ms: int = 0
    error: str | None = None
    chunks: list[RetrievedChunkRecord] = field(default_factory=list)


class InteractionSink(ABC):
    @abstractmethod
    def record_interaction(self, record: InteractionRecord) -> str | None:
        """Persist one interaction, returning its id (None if not stored).

        Implementations must not raise: a monitoring failure cannot fail a
        user request.
        """

    @abstractmethod
    def record_feedback(
        self, interaction_id: str, rating: int, comment: str | None = None
    ) -> int:
        """Persist a user rating, returning the feedback row id.

        May raise, unlike record_interaction: a rating that was not stored
        is unrecoverable, so the caller needs to know.
        """


class NullInteractionSink(InteractionSink):
    """Discards everything. Default when monitoring is not wired."""

    def record_interaction(self, record: InteractionRecord) -> str | None:
        return None

    def record_feedback(
        self, interaction_id: str, rating: int, comment: str | None = None
    ) -> int:
        raise RuntimeError("monitoring is disabled; no feedback sink wired")
