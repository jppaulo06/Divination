"""Flags a user re-asking something already asked in the same thread.

Similarity is token overlap, so it catches rephrasings that reuse
vocabulary and misses fully reworded ones.
"""

import re

from project.ports.monitoring.SignalDetector import (
    DetectedSignal,
    InteractionView,
    SignalDetector,
)

DEFAULT_SIMILARITY_THRESHOLD = 0.6

_STOPWORDS = frozenset(
    """
    a an and are as at be but by can do does for from how i if in into is it
    its me my of on or que the their there they this to um uma was what when
    where which who why with you your
    como de do da das dos e em o os as para por qual quais que se um uma
    voce você é são no na nos nas com sobre
    """.split()
)

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


class RepeatedQuestionDetector(SignalDetector):
    name = "repeated_question"
    version = "1"

    def __init__(self, threshold: float = DEFAULT_SIMILARITY_THRESHOLD):
        self.threshold = threshold

    def detect(self, interaction: InteractionView) -> list[DetectedSignal]:
        current = _content_tokens(interaction.question)
        if not current:
            return []

        best_score = 0.0
        best_match = None
        for prior in interaction.prior_questions:
            score = _jaccard(current, _content_tokens(prior))
            if score > best_score:
                best_score, best_match = score, prior

        if best_match is None or best_score < self.threshold:
            return []

        return [
            DetectedSignal(
                type=self.name,
                score=best_score,
                scope="thread",
                details={
                    "similarity": round(best_score, 3),
                    "threshold": self.threshold,
                    "prior_question": best_match,
                    "current_question": interaction.question,
                },
            )
        ]


def _content_tokens(text: str) -> frozenset[str]:
    tokens = _TOKEN_PATTERN.findall((text or "").lower())
    return frozenset(t for t in tokens if t not in _STOPWORDS and len(t) > 1)


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    union = len(left | right)
    return len(left & right) / union if union else 0.0
