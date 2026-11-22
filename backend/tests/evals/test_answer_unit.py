"""Single-turn "unit tests" for the Divination chatbot.

One known question in, one known expected answer checked against — no
ConversationSimulator, no simulated user, no multi-turn history. Reuses
the same 25 goldens' opening question (`turns[0]`) and `expected_outcome`
that test_divination_chat.py drives conversations from, so a much
cheaper/faster signal than the full conversational suite.
"""

import json
from importlib import import_module
import uuid

import pytest

from deepeval import assert_test
from deepeval.test_case import LLMTestCase

from result_recorder import record_execution_error, run_and_record, select_cases
from single_turn_metrics import NOT_COVERED_METRICS, SINGLE_TURN_METRICS

chatbot_app = import_module("chatbot_app")

with open("tests/evals/.dataset.json") as f:
    # EVAL_CASES limits a run to some cases (baseline rebuilds, confirmations).
    _GOLDENS = select_cases(json.load(f))


@pytest.mark.parametrize(
    "golden", _GOLDENS, ids=[g["name"] for g in _GOLDENS]
)
def test_single_turn_answer(golden):
    case_name = golden["name"]
    question = golden["turns"][0]["content"]
    try:
        answer, retrieved_docs = (
            chatbot_app._chat_service.get_answer_with_context(
                # A fresh chat per attempt: repeated attempts must not see
                # each other's questions and answers as history.
                query=question,
                chat_id=f"unit-{case_name}-{uuid.uuid4().hex[:12]}",
            )
        )
    except Exception as error:
        record_execution_error(case_name, error)
        raise

    test_case = LLMTestCase(
        input=question,
        actual_output=answer,
        retrieval_context=[doc.page_content for doc in retrieved_docs],
        expected_output=golden["expected_outcome"],
    )

    metrics = (
        NOT_COVERED_METRICS
        if "not-covered" in case_name
        else SINGLE_TURN_METRICS
    )
    run_and_record(
        case_name=case_name,
        test_case=test_case,
        metrics=metrics,
        assert_fn=assert_test,
    )
