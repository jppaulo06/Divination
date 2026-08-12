"""Flags answers missing the closing line both prompt templates require."""

import re

from project.ports.monitoring.SignalDetector import (
    DetectedSignal,
    InteractionView,
    SignalDetector,
)

REQUIRED_CLOSING = "thanks for asking!"

# Tolerates trailing punctuation, markdown emphasis and whitespace.
_CLOSING_PATTERN = re.compile(
    r"thanks\s+for\s+asking\s*!?\s*[*_`\s.]*$", re.IGNORECASE
)


class FormatGuardrailDetector(SignalDetector):
    name = "format_guardrail_violation"
    version = "1"

    def detect(self, interaction: InteractionView) -> list[DetectedSignal]:
        answer = (interaction.answer or "").strip()
        if not answer:
            return [
                DetectedSignal(
                    type=self.name,
                    score=1.0,
                    details={"reason": "empty answer"},
                )
            ]

        if _CLOSING_PATTERN.search(answer):
            return []

        return [
            DetectedSignal(
                type=self.name,
                score=1.0,
                details={
                    "required_closing": REQUIRED_CLOSING,
                    "answer_tail": answer[-120:],
                },
            )
        ]
