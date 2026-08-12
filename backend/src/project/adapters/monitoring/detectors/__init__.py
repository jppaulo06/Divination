"""Registry of the detectors run against recorded interactions."""

from project.adapters.monitoring.detectors.format_guardrail import (
    FormatGuardrailDetector,
)
from project.adapters.monitoring.detectors.refusal_hedge import (
    RefusalHedgeDetector,
)
from project.adapters.monitoring.detectors.repeated_question import (
    RepeatedQuestionDetector,
)
from project.adapters.monitoring.detectors.unsupported_claim import (
    UnsupportedClaimDetector,
)
from project.adapters.monitoring.detectors.weak_retrieval import (
    WeakRetrievalDetector,
)


def default_detectors():
    return [
        WeakRetrievalDetector(),
        UnsupportedClaimDetector(),
        RefusalHedgeDetector(),
        FormatGuardrailDetector(),
        RepeatedQuestionDetector(),
    ]


__all__ = [
    "FormatGuardrailDetector",
    "RefusalHedgeDetector",
    "RepeatedQuestionDetector",
    "UnsupportedClaimDetector",
    "WeakRetrievalDetector",
    "default_detectors",
]
