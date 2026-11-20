"""Offline regression test exercising result_recorder with real DeepEval.

Uses a deterministic BaseMetric subclass so no API keys or network calls are
required, while catching DeepEval execution-path bugs (such as async metric
copying) that mock assert_fn tests cannot observe.
"""

import json
import sys
from pathlib import Path

import pytest
from deepeval import assert_test
from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

EVALS_DIR = Path(__file__).resolve().parent
if str(EVALS_DIR) not in sys.path:
    sys.path.insert(0, str(EVALS_DIR))

import result_recorder  # noqa: E402


class _FixedMetric(BaseMetric):
    def __init__(self, *, score, threshold=0.5, name="FixedMetric"):
        self._fixed_score = score
        self.threshold = threshold
        self._name = name
        self.score = None
        self.success = None
        self.reason = None
        self.error = None

    @property
    def __name__(self):
        return self._name

    def measure(self, test_case, *args, **kwargs):
        self.score = self._fixed_score
        self.success = self.score >= self.threshold
        self.reason = "deterministic"
        return self.score

    async def a_measure(self, test_case, *args, **kwargs):
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self):
        return bool(self.success)


def test_real_assert_test_records_passing_metric(tmp_path, monkeypatch):
    monkeypatch.setenv("EVAL_RESULTS_DIR", str(tmp_path))
    metric = _FixedMetric(score=0.9, threshold=0.5, name="Deterministic")
    test_case = LLMTestCase(input="q", actual_output="a")

    result_recorder.run_and_record(
        case_name="fireball-pass",
        test_case=test_case,
        metrics=[metric],
        assert_fn=assert_test,
    )

    saved = json.loads((tmp_path / "fireball-pass.json").read_text())
    assert saved["status"] == "passed"
    assert saved["metrics"][0]["score"] == 0.9
    assert saved["metrics"][0]["success"] is True


def test_real_assert_test_records_failing_metric(tmp_path, monkeypatch):
    monkeypatch.setenv("EVAL_RESULTS_DIR", str(tmp_path))
    metric = _FixedMetric(score=0.2, threshold=0.5, name="Deterministic")
    test_case = LLMTestCase(input="q", actual_output="a")

    with pytest.raises(AssertionError):
        result_recorder.run_and_record(
            case_name="fireball-fail",
            test_case=test_case,
            metrics=[metric],
            assert_fn=assert_test,
        )

    saved = json.loads((tmp_path / "fireball-fail.json").read_text())
    assert saved["status"] == "failed"
    assert saved["metrics"][0]["score"] == 0.2
    assert saved["metrics"][0]["success"] is False
