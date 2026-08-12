"""Flags interactions whose best retrieved chunk scored poorly."""

from project.ports.monitoring.SignalDetector import (
    DetectedSignal,
    InteractionView,
    SignalDetector,
)

#: Placeholder. Calibrate against the observed spread of
#: retrieved_chunks.score before treating this signal as meaningful.
DEFAULT_SCORE_THRESHOLD = 0.7


class WeakRetrievalDetector(SignalDetector):
    name = "weak_retrieval"
    version = "1"

    def __init__(self, threshold: float = DEFAULT_SCORE_THRESHOLD):
        self.threshold = threshold

    def detect(self, interaction: InteractionView) -> list[DetectedSignal]:
        if not interaction.chunks:
            return [
                DetectedSignal(
                    type=self.name,
                    score=0.0,
                    details={
                        "reason": "no chunks retrieved",
                        "threshold": self.threshold,
                    },
                )
            ]

        top_score = interaction.top_score
        if top_score is None or top_score >= self.threshold:
            return []

        return [
            DetectedSignal(
                type=self.name,
                score=top_score,
                details={
                    "top_score": top_score,
                    "threshold": self.threshold,
                    "chunk_count": len(interaction.chunks),
                },
            )
        ]
