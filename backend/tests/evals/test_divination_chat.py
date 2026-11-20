import json
from importlib import import_module

import pytest

from deepeval import assert_test
from deepeval.dataset import EvaluationDataset
from deepeval.simulator import ConversationSimulator

from eval_model import maritaca_judge
from metrics import MULTI_TURN_METRICS
from result_recorder import run_and_record

MAX_TURNS = 6
chatbot_app = import_module("chatbot_app")

with open("tests/evals/.dataset.json") as f:
    _GOLDENS = json.load(f)

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
if len(simulated_test_cases) != len(_GOLDENS):
    raise RuntimeError(
        "Simulated conversation count does not match dataset goldens: "
        f"{len(simulated_test_cases)} != {len(_GOLDENS)}"
    )
_CASES = []
for _golden, _test_case in zip(_GOLDENS, simulated_test_cases):
    _name = _golden.get("name")
    if not isinstance(_name, str) or not _name.strip():
        raise RuntimeError("Every evaluation golden must have a non-empty name.")
    _test_case.chatbot_role = CHATBOT_ROLE
    _CASES.append((_name, _test_case))


@pytest.mark.parametrize(
    ("case_name", "test_case"),
    _CASES,
    ids=[name for name, _ in _CASES],
)
def test_divination_chat(case_name, test_case):
    run_and_record(
        case_name=case_name,
        test_case=test_case,
        metrics=MULTI_TURN_METRICS,
        assert_fn=assert_test,
    )
