"""Port for monitoring detectors.

Detectors are pure functions over a stored interaction, so their output can
be dropped and recomputed at any time.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ChunkView:
    rank: int
    content: str
    score: float | None = None


@dataclass
class InteractionView:
    id: str
    chat_id: str
    question: str
    answer: str
    chunks: list[ChunkView] = field(default_factory=list)
    template_name: str = ""
    error: str | None = None
    #: Earlier questions in the same thread, oldest first.
    prior_questions: list[str] = field(default_factory=list)

    @property
    def context_text(self) -> str:
        return "\n".join(chunk.content for chunk in self.chunks)

    @property
    def top_score(self) -> float | None:
        scores = [c.score for c in self.chunks if c.score is not None]
        return max(scores) if scores else None


@dataclass
class DetectedSignal:
    type: str
    score: float | None = None
    details: dict = field(default_factory=dict)
    scope: str = "turn"


class SignalDetector(ABC):
    #: Stored as `signals.type`.
    name: str = ""
    #: Part of the signals uniqueness key: bumping it re-flags existing
    #: interactions instead of colliding with the previous run's rows.
    version: str = "1"

    @abstractmethod
    def detect(self, interaction: InteractionView) -> list[DetectedSignal]:
        """Return zero or more signals for this interaction."""
