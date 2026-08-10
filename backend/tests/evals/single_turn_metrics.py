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

# For "-not-covered" goldens, correctly declining to answer IS the expected
# behavior - AnswerRelevancyMetric penalizes exactly that (it scores low
# whenever the response doesn't directly answer the literal question), so
# it's the wrong check here. Rules Correctness (GEval, judged against
# expected_outcome) already captures whether declining was the right call.
NOT_COVERED_METRICS = [
    FaithfulnessMetric(model=maritaca_judge),
    _CORRECTNESS_GEVAL,
]
