from deepeval.metrics import (
    ConversationCompletenessMetric,
    ConversationalGEval,
    RoleAdherenceMetric,
    TurnFaithfulnessMetric,
)
from deepeval.test_case import MultiTurnParams

from eval_model import maritaca_judge

# Keep metrics in one module so the eval file stays focused on running the
# real app. Reuse these instances and thresholds before adding new ones.

# The assistant must not invent D&D rules, costs, or stats that aren't in
# the retrieved Free Rules chunks for that turn.
_RULES_GROUNDING_STYLE_GEVAL = ConversationalGEval(
    name="Rules Answer Style",
    criteria=(
        "Determine whether the assistant plays a Dungeon Master Assistant "
        "persona, gives detailed and well-spaced answers grounded only in "
        "the retrieved D&D rules context, admits when the rules don't cover "
        "something instead of guessing, and ends substantive answers with "
        "'thanks for asking!' as its system prompt instructs."
    ),
    evaluation_params=[
        MultiTurnParams.CONTENT,
        MultiTurnParams.RETRIEVAL_CONTEXT,
    ],
    model=maritaca_judge,
)

MULTI_TURN_METRICS = [
    TurnFaithfulnessMetric(model=maritaca_judge),
    ConversationCompletenessMetric(model=maritaca_judge),
    RoleAdherenceMetric(model=maritaca_judge),
    _RULES_GROUNDING_STYLE_GEVAL,
]
