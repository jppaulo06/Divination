"""Flags answers where the assistant declined or hedged.

Matches Portuguese as well as English: the UI is Portuguese while the
corpus is English.
"""

import re

from project.ports.monitoring.SignalDetector import (
    DetectedSignal,
    InteractionView,
    SignalDetector,
)

_REFUSAL_PATTERNS = [
    r"do(?:es)?\s+not\s+cover",
    r"don't\s+cover",
    r"not\s+covered\s+(?:by|in)",
    r"no\s+information\s+(?:about|on)",
    r"(?:i\s+)?(?:do\s+not|don't)\s+have\s+(?:enough\s+)?information",
    r"context\s+(?:does\s+not|doesn't)\s+(?:cover|mention|include)",
    r"cannot\s+answer",
    r"unable\s+to\s+answer",
    r"n[ãa]o\s+(?:cobre|abrange|menciona)",
    r"n[ãa]o\s+(?:h[áa]|tenho)\s+informa[çc][õo]es",
    r"n[ãa]o\s+(?:est[áa]|consta)\s+(?:no|nos)\s+",
    r"n[ãa]o\s+posso\s+responder",
    r"regras\s+fornecidas\s+n[ãa]o",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _REFUSAL_PATTERNS]


class RefusalHedgeDetector(SignalDetector):
    name = "refusal_or_hedge"
    version = "1"

    def detect(self, interaction: InteractionView) -> list[DetectedSignal]:
        matches = [
            pattern.pattern
            for pattern in _COMPILED
            if pattern.search(interaction.answer)
        ]
        if not matches:
            return []

        return [
            DetectedSignal(
                type=self.name,
                score=float(len(matches)),
                details={"matched_patterns": matches},
            )
        ]
