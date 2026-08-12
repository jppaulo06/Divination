"""Flags dice expressions and save DCs that appear in no retrieved chunk.

Correct answers can trip this: upcast damage is derived arithmetic ("8d6
plus 1d6 per slot level" answered as 10d6) and never appears verbatim in
the source text.
"""

import re

from project.ports.monitoring.SignalDetector import (
    DetectedSignal,
    InteractionView,
    SignalDetector,
)

_DICE_PATTERN = re.compile(r"\b(\d{1,3}d\d{1,3})\b", re.IGNORECASE)
_DC_PATTERN = re.compile(r"\bDC\s*(\d{1,2})\b", re.IGNORECASE)


class UnsupportedClaimDetector(SignalDetector):
    name = "unsupported_claim"
    version = "1"

    def detect(self, interaction: InteractionView) -> list[DetectedSignal]:
        context = interaction.context_text.lower()
        if not context:
            return []

        answer = interaction.answer

        unsupported_dice = [
            dice
            for dice in _unique(_DICE_PATTERN.findall(answer))
            if dice not in context
        ]
        unsupported_dcs = [
            dc
            for dc in _unique(_DC_PATTERN.findall(answer))
            if not re.search(rf"\bdc\s*{re.escape(dc)}\b", context)
        ]

        if not unsupported_dice and not unsupported_dcs:
            return []

        return [
            DetectedSignal(
                type=self.name,
                score=float(len(unsupported_dice) + len(unsupported_dcs)),
                details={
                    "unsupported_dice": unsupported_dice,
                    "unsupported_dcs": unsupported_dcs,
                },
            )
        ]


def _unique(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        seen.setdefault(value.lower(), None)
    return list(seen)
