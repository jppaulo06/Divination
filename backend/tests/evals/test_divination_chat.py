from importlib import import_module

import pytest

from deepeval import assert_test
from deepeval.dataset import EvaluationDataset
from deepeval.simulator import ConversationSimulator

from eval_model import maritaca_judge
from metrics import MULTI_TURN_METRICS

MAX_TURNS = 6
chatbot_app = import_module("chatbot_app")

simulator = ConversationSimulator(
    model_callback=chatbot_app.chatbot_callback,
    simulator_model=maritaca_judge,
    max_concurrent=1,
)
dataset = EvaluationDataset()
dataset.add_goldens_from_json_file(file_path="tests/evals/.dataset.json")

# Matches the persona line in defaultTemplate.txt ("You are a Dungeon
# Master Assistant"); RoleAdherenceMetric checks turns against this and
# ConversationSimulator has no way to infer it on its own.
CHATBOT_ROLE = "Dungeon Master Assistant"

simulated_test_cases = simulator.simulate(
    conversational_goldens=dataset.goldens,
    max_user_simulations=MAX_TURNS,
)
for _test_case in simulated_test_cases:
    _test_case.chatbot_role = CHATBOT_ROLE


@pytest.mark.parametrize("test_case", simulated_test_cases)
def test_divination_chat(test_case):
    assert_test(test_case=test_case, metrics=MULTI_TURN_METRICS)
