"""Single-turn "unit tests" for the Divination chatbot.

One known question in, one known expected answer checked against — no
ConversationSimulator, no simulated user, no multi-turn history. Reuses
the same 25 goldens' opening question (`turns[0]`) and `expected_outcome`
that test_divination_chat.py drives conversations from, so a much
cheaper/faster signal than the full conversational suite.
"""

import json
from importlib import import_module

import pytest

from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from single_turn_metrics import NOT_COVERED_METRICS, SINGLE_TURN_METRICS

chatbot_app = import_module("chatbot_app")

with open("tests/evals/.dataset.json") as f:
    _GOLDENS = json.load(f)


@pytest.mark.parametrize(
    "golden", _GOLDENS, ids=[g["name"] for g in _GOLDENS]
)
def test_single_turn_answer(golden):
    question = golden["turns"][0]["content"]
    answer, retrieved_docs = (
        chatbot_app._chat_service.get_answer_with_context(
            query=question, chat_id=f"unit-{golden['name']}"
        )
    )

    test_case = LLMTestCase(
        input=question,
        actual_output=answer,
        retrieval_context=[doc.page_content for doc in retrieved_docs],
        expected_output=golden["expected_outcome"],
    )

    metrics = (
        NOT_COVERED_METRICS
        if "not-covered" in golden["name"]
        else SINGLE_TURN_METRICS
    )
    assert_test(test_case=test_case, metrics=metrics)
