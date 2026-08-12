"""Unit tests for the monitoring detectors.

Deterministic and offline: no LLM, no API keys, no vector store.
"""

import pytest

from project.adapters.monitoring.detectors import (
    FormatGuardrailDetector,
    RefusalHedgeDetector,
    RepeatedQuestionDetector,
    UnsupportedClaimDetector,
    WeakRetrievalDetector,
)
from project.ports.monitoring.SignalDetector import ChunkView, InteractionView


def make_view(**overrides) -> InteractionView:
    defaults = dict(
        id="i-1",
        chat_id="c-1",
        question="How much damage does Fireball deal?",
        answer="Fireball deals 8d6 fire damage. thanks for asking!",
        chunks=[
            ChunkView(
                rank=0,
                content="Fireball. 3rd-level evocation. 8d6 fire damage.",
                score=0.9,
            )
        ],
    )
    defaults.update(overrides)
    return InteractionView(**defaults)


class TestWeakRetrieval:
    def test_strong_retrieval_is_not_flagged(self):
        detector = WeakRetrievalDetector(threshold=0.7)
        assert detector.detect(make_view()) == []

    def test_low_top_score_is_flagged(self):
        detector = WeakRetrievalDetector(threshold=0.7)
        view = make_view(
            chunks=[
                ChunkView(rank=0, content="unrelated", score=0.3),
                ChunkView(rank=1, content="also unrelated", score=0.2),
            ]
        )

        signals = detector.detect(view)

        assert len(signals) == 1
        assert signals[0].type == "weak_retrieval"
        assert signals[0].details["top_score"] == 0.3

    def test_empty_retrieval_is_flagged(self):
        signals = WeakRetrievalDetector().detect(make_view(chunks=[]))

        assert len(signals) == 1
        assert signals[0].details["reason"] == "no chunks retrieved"

    def test_missing_scores_are_not_a_finding(self):
        view = make_view(chunks=[ChunkView(rank=0, content="x", score=None)])

        assert WeakRetrievalDetector().detect(view) == []

    def test_top_score_is_the_max_not_the_first(self):
        view = make_view(
            chunks=[
                ChunkView(rank=0, content="a", score=0.4),
                ChunkView(rank=1, content="b", score=0.95),
            ]
        )

        assert WeakRetrievalDetector(threshold=0.7).detect(view) == []


class TestUnsupportedClaim:
    def test_dice_present_in_context_is_not_flagged(self):
        assert UnsupportedClaimDetector().detect(make_view()) == []

    def test_dice_absent_from_context_is_flagged(self):
        view = make_view(
            answer="Fireball deals 20d6 damage. thanks for asking!"
        )

        signals = UnsupportedClaimDetector().detect(view)

        assert len(signals) == 1
        assert signals[0].details["unsupported_dice"] == ["20d6"]

    def test_upcast_arithmetic_is_flagged_as_a_known_false_positive(self):
        # 10d6 is the correct answer for Fireball at 5th level but never
        # appears verbatim in the source text.
        view = make_view(
            question="Fireball at 5th level?",
            answer="At 5th level it deals 10d6. thanks for asking!",
            chunks=[
                ChunkView(
                    rank=0,
                    content="8d6 fire damage, plus 1d6 per slot level above 3rd",
                    score=0.9,
                )
            ],
        )

        signals = UnsupportedClaimDetector().detect(view)

        assert signals[0].details["unsupported_dice"] == ["10d6"]

    def test_unsupported_save_dc_is_flagged(self):
        view = make_view(
            answer="The target must beat DC 17. thanks for asking!",
            chunks=[ChunkView(rank=0, content="save against DC 15", score=0.9)],
        )

        signals = UnsupportedClaimDetector().detect(view)

        assert signals[0].details["unsupported_dcs"] == ["17"]

    def test_no_context_yields_no_signal(self):
        view = make_view(chunks=[], answer="It deals 99d6. thanks for asking!")

        assert UnsupportedClaimDetector().detect(view) == []

    def test_dice_matching_is_case_insensitive(self):
        view = make_view(
            answer="It deals 8D6 fire damage. thanks for asking!",
            chunks=[ChunkView(rank=0, content="deals 8d6 fire", score=0.9)],
        )

        assert UnsupportedClaimDetector().detect(view) == []


class TestRefusalHedge:
    def test_plain_answer_is_not_flagged(self):
        assert RefusalHedgeDetector().detect(make_view()) == []

    @pytest.mark.parametrize(
        "answer",
        [
            "The rules provided don't cover opportunity attacks.",
            "The context does not mention Action Surge.",
            "I don't have enough information to answer that.",
            "As regras fornecidas não cobrem esse caso.",
            "Não há informações sobre isso no contexto.",
        ],
    )
    def test_refusals_are_flagged(self, answer):
        signals = RefusalHedgeDetector().detect(make_view(answer=answer))

        assert len(signals) == 1
        assert signals[0].type == "refusal_or_hedge"


class TestFormatGuardrail:
    def test_required_closing_present(self):
        assert FormatGuardrailDetector().detect(make_view()) == []

    def test_closing_with_markdown_and_punctuation_is_accepted(self):
        view = make_view(answer="Some rules text.\n\n**thanks for asking!**")

        assert FormatGuardrailDetector().detect(view) == []

    def test_missing_closing_is_flagged(self):
        view = make_view(answer="Fireball deals 8d6 fire damage.")

        signals = FormatGuardrailDetector().detect(view)

        assert len(signals) == 1
        assert signals[0].type == "format_guardrail_violation"

    def test_closing_not_at_the_end_is_flagged(self):
        view = make_view(
            answer="thanks for asking! Now here is some extra rambling."
        )

        assert len(FormatGuardrailDetector().detect(view)) == 1

    def test_empty_answer_is_flagged(self):
        signals = FormatGuardrailDetector().detect(make_view(answer=""))

        assert signals[0].details["reason"] == "empty answer"


class TestRepeatedQuestion:
    def test_no_prior_questions(self):
        assert RepeatedQuestionDetector().detect(make_view()) == []

    def test_unrelated_prior_question_is_not_flagged(self):
        view = make_view(
            question="How much damage does Fireball deal?",
            prior_questions=["Can I use Revivify on a decapitated body?"],
        )

        assert RepeatedQuestionDetector().detect(view) == []

    def test_rephrased_question_is_flagged_as_thread_scoped(self):
        view = make_view(
            question="How much fire damage does Fireball deal?",
            prior_questions=["How much damage does Fireball deal?"],
        )

        signals = RepeatedQuestionDetector().detect(view)

        assert len(signals) == 1
        assert signals[0].scope == "thread"
        assert signals[0].details["prior_question"] == (
            "How much damage does Fireball deal?"
        )

    def test_stopwords_alone_do_not_create_a_match(self):
        view = make_view(
            question="What is the range of Bless?",
            prior_questions=["What is the duration of Haste?"],
        )

        assert RepeatedQuestionDetector().detect(view) == []
