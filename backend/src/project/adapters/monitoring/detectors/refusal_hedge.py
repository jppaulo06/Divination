"""Flags answers where the assistant said the context was insufficient.

Detects the structural shape rather than a list of phrasings: a reference
to the provided material near a negation. Enumerating phrasings does not
hold up — "não cobre", "não traz", "não estão incluídas" and "não há uma
definição" all mean the same thing and a pattern list will always trail
behind the model.

Matches Portuguese as well as English: the UI is Portuguese while the
corpus is English.
"""

import re

from project.ports.monitoring.SignalDetector import (
    DetectedSignal,
    InteractionView,
    SignalDetector,
)

#: Ways the assistant refers to what it was given.
_SOURCE_WORDS = (
    r"context[oe]?|material|informa[çc][õo]es|information|"
    r"regras\s+fornecidas|dados\s+fornecidos|"
    r"provided\s+(?:rules|text|material)|rules\s+provided|excerpts?"
)

#: Negations that, next to a source word, mean "it is not in there".
_NEGATIONS = (
    r"n[ãa]o|nenhum[ao]?|sem\b|does\s+not|doesn't|do\s+not|don't|"
    r"cannot|can't|unable|lacks?|missing|absent|without\b|no\b"
)

# Proximity window rather than fixed phrases: the two halves can appear in
# either order and with words between them ("o contexto fornecido não
# traz", "não estão incluídas no contexto apresentado").
_WINDOW = r"[^.!?\n]{0,60}"

_INSUFFICIENT_CONTEXT = re.compile(
    rf"(?:(?:{_SOURCE_WORDS}){_WINDOW}(?:{_NEGATIONS})"
    rf"|(?:{_NEGATIONS}){_WINDOW}(?:{_SOURCE_WORDS}))",
    re.IGNORECASE,
)

#: Explicit refusals that never mention the source at all.
_BARE_REFUSAL = re.compile(
    r"n[ãa]o\s+(?:posso|consigo|sei)\s+responder"
    r"|cannot\s+answer|unable\s+to\s+answer"
    r"|seria\s+necess[áa]rio\s+consultar",
    re.IGNORECASE,
)


class RefusalHedgeDetector(SignalDetector):
    name = "refusal_or_hedge"
    #: 2: phrase list replaced by proximity matching, which the previous
    #: version missed real refusals through.
    version = "2"

    def detect(self, interaction: InteractionView) -> list[DetectedSignal]:
        answer = interaction.answer or ""

        context_matches = [m.group(0) for m in
                           _INSUFFICIENT_CONTEXT.finditer(answer)]
        bare_matches = [m.group(0) for m in _BARE_REFUSAL.finditer(answer)]
        if not context_matches and not bare_matches:
            return []

        # A refusal that still conveys something ("no entanto, há uma
        # menção específica sobre...") points at retrieval precision;
        # a flat refusal points at corpus coverage.
        partial = _looks_partial(answer)

        return [
            DetectedSignal(
                type=self.name,
                score=float(len(context_matches) + len(bare_matches)),
                details={
                    "matches": (context_matches + bare_matches)[:6],
                    "partial": partial,
                },
            )
        ]


_CONCESSIVE = re.compile(
    r"no\s+entanto|por[ée]m\b|contudo|entretanto|apenas\s+"
    r"|however|although|but\s+the\s+(?:provided|context)",
    re.IGNORECASE,
)


def _looks_partial(answer: str) -> bool:
    return bool(_CONCESSIVE.search(answer))
