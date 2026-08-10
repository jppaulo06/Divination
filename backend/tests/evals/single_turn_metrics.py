from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, GEval
from deepeval.test_case import LLMTestCaseParams

from eval_model import maritaca_judge

# Single-turn counterpart to metrics.py's conversational metrics: checks a
# known question against a known expected answer, no ConversationSimulator
# involved.

_CORRECTNESS_GEVAL = GEval(
    name="Rules Correctness",
    criteria=(
        "Determine whether the actual output correctly conveys the key "
        "facts (numbers, dice, conditions) present in the expected output, "
        "without contradicting them."
    ),
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.EXPECTED_OUTPUT,
    ],
    model=maritaca_judge,
)

SINGLE_TURN_METRICS = [
    FaithfulnessMetric(model=maritaca_judge),
    AnswerRelevancyMetric(model=maritaca_judge),
    _CORRECTNESS_GEVAL,
]
