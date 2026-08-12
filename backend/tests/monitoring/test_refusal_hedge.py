"""Tests for the refusal detector, seeded from real production answers.

PRODUCTION_REFUSAL is a verbatim answer from a live session that version 1
of this detector missed entirely.
"""

import pytest

from project.adapters.monitoring.detectors import RefusalHedgeDetector
from project.ports.monitoring.SignalDetector import ChunkView, InteractionView

PRODUCTION_REFUSAL = """O contexto fornecido não traz uma explicação geral \
sobre as condições de vantagem em uma rolagem nas regras padrão de \
Dungeons & Dragons.

No entanto, dentro do material fornecido, há uma menção específica sobre \
vantagem no efeito "Roll Redo", onde é dito que você pode forçar a \
rerrolagem de um dado com Vantagem ou Desvantagem, e escolher se usa o \
resultado da rerrolagem ou o original.

Para saber sobre as regras gerais de Vantagem (como quando ela normalmente \
se aplica em combate, testes de habilidade ou salvamentos), seria \
necessário consultar as regras básicas do jogo, que não estão incluídas no \
contexto apresentado.

Portanto, com base apenas nas informações fornecidas, não há uma definição \
geral das condições de vantagem em uma rolagem — apenas a indicação de que \
o efeito "Roll Redo" permite rolagens com Vantagem.

thanks for asking!
"""


def view(answer: str, question: str = "Pergunta?") -> InteractionView:
    return InteractionView(
        id="i-1",
        chat_id="c-1",
        question=question,
        answer=answer,
        chunks=[ChunkView(rank=0, content="algum trecho", score=0.63)],
    )


def test_the_real_production_refusal_is_flagged():
    signals = RefusalHedgeDetector().detect(
        view(
            PRODUCTION_REFUSAL,
            "Quais são as condições de vantagem em uma rolagem?",
        )
    )

    assert len(signals) == 1
    assert signals[0].type == "refusal_or_hedge"


def test_the_production_refusal_is_marked_partial():
    # It declined the general question but still answered about Roll Redo,
    # which points at retrieval precision rather than corpus coverage.
    signals = RefusalHedgeDetector().detect(view(PRODUCTION_REFUSAL))

    assert signals[0].details["partial"] is True


@pytest.mark.parametrize(
    "answer",
    [
        "O contexto fornecido não traz uma explicação sobre isso.",
        "Essas regras não estão incluídas no contexto apresentado.",
        "Com base apenas nas informações fornecidas, não há definição.",
        "As regras fornecidas não cobrem ataques de oportunidade.",
        "Não há informações sobre isso no material.",
        "Não posso responder com o que foi fornecido.",
        "Seria necessário consultar as regras básicas do jogo.",
        "The provided rules do not cover opportunity attacks.",
        "The context does not mention Action Surge.",
        "I don't have enough information in the provided material.",
        "No information about that is present in the excerpts.",
    ],
)
def test_refusal_phrasings_are_flagged(answer):
    assert RefusalHedgeDetector().detect(view(answer))


@pytest.mark.parametrize(
    "answer",
    [
        "Fireball deals 8d6 fire damage on a failed save. thanks for asking!",
        "Counterspell interrompe a magia do alvo. thanks for asking!",
        "Cure Wounds cura 2d8 + seu modificador de conjuração.",
        "A área é uma esfera de 20 pés de raio.",
    ],
)
def test_ordinary_answers_are_not_flagged(answer):
    assert RefusalHedgeDetector().detect(view(answer)) == []


def test_a_flat_refusal_is_not_marked_partial():
    signals = RefusalHedgeDetector().detect(
        view("As regras fornecidas não cobrem esse assunto.")
    )

    assert signals[0].details["partial"] is False


def test_negation_far_from_the_source_word_is_not_flagged():
    # "não" here belongs to a different clause than "contexto"; the window
    # exists so a sentence boundary stops the match.
    answer = (
        "O contexto descreve a magia Bola de Fogo. "
        "Ela não permite reação do alvo."
    )

    assert RefusalHedgeDetector().detect(view(answer)) == []


def test_version_is_bumped_so_history_gets_reflagged():
    # Version 1 missed PRODUCTION_REFUSAL; interactions already scored
    # under v1 must be re-evaluated rather than treated as done.
    assert RefusalHedgeDetector().version != "1"
