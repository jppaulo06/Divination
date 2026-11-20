"""Unit tests for reference comparison, delivery policy, and result capture."""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend/tests/evals"))

import eval_policy  # noqa: E402
import result_recorder  # noqa: E402


def _metric(name, score, *, threshold=0.5, success=True, error=None):
    if error is not None:
        status = "error"
    elif success is None:
        status = "incomplete"
    elif success:
        status = "passed"
    else:
        status = "failed"
    return {
        "name": name,
        "score": score,
        "threshold": threshold,
        "success": success,
        "status": status,
        "error": error,
    }


def _case(name, status, metrics, error=None):
    return {
        "name": name,
        "status": status,
        "error": error,
        "metrics": metrics,
    }


def _report(cases, *, commit="abc123", suite="single-turn"):
    return {
        "schema_version": 1,
        "suite": suite,
        "run_id": "test-run",
        "commit": commit,
        "recorded_at": "2026-11-20T00:00:00+00:00",
        "deepeval_exit_code": 0,
        "cases": {case["name"]: case for case in cases},
    }


class EvalPolicyTests(unittest.TestCase):
    def test_classifies_all_four_matched_outcomes(self):
        baseline = _report(
            [
                _case("stable", "passed", [_metric("Faithfulness", 0.9)]),
                _case("regressed", "passed", [_metric("Faithfulness", 0.8)]),
                _case(
                    "improved",
                    "failed",
                    [_metric("Faithfulness", 0.3, success=False)],
                ),
                _case(
                    "known",
                    "failed",
                    [_metric("Faithfulness", 0.4, success=False)],
                ),
            ],
            commit="base111",
        )
        candidate = _report(
            [
                _case("stable", "passed", [_metric("Faithfulness", 0.95)]),
                _case(
                    "regressed",
                    "failed",
                    [_metric("Faithfulness", 0.4, success=False)],
                ),
                _case("improved", "passed", [_metric("Faithfulness", 0.9)]),
                _case(
                    "known",
                    "failed",
                    [_metric("Faithfulness", 0.38, success=False)],
                ),
            ],
            commit="cand222",
        )
        policy = dict(
            eval_policy.DEFAULT_POLICY,
            known_limitations={
                "known": {"blocking": False, "reason": "Tracked issue #12"},
                "improved": {"blocking": False, "reason": "Old limitation"},
            },
        )
        decision = eval_policy.compare_and_decide(candidate, baseline, policy)

        self.assertFalse(decision["allow_delivery"])
        self.assertEqual(decision["summary"]["still_passing"], 1)
        self.assertEqual(decision["summary"]["potential_regression"], 1)
        self.assertEqual(decision["summary"]["improvement_observed"], 1)
        self.assertEqual(decision["summary"]["continuing_limitation"], 1)
        self.assertEqual(
            [item["case"] for item in decision["blocking_reasons"]],
            ["regressed"],
        )
        notice_categories = {
            (item["case"], item["category"])
            for item in decision["non_blocking_notices"]
        }
        self.assertIn(("known", "continuing_limitation"), notice_categories)
        self.assertIn(("improved", "resolved_limitation"), notice_categories)
        self.assertEqual(
            decision["cases"]["regressed"]["metric_deltas"]["Faithfulness"],
            -0.4,
        )

    def test_non_blocking_limitation_allows_delivery_when_stable(self):
        baseline = _report(
            [
                _case("ok", "passed", [_metric("Rules", 1.0)]),
                _case(
                    "limitation",
                    "failed",
                    [_metric("Rules", 0.4, success=False)],
                ),
            ]
        )
        candidate = _report(
            [
                _case("ok", "passed", [_metric("Rules", 1.0)]),
                _case(
                    "limitation",
                    "failed",
                    [_metric("Rules", 0.35, success=False)],
                ),
            ]
        )
        policy = dict(
            eval_policy.DEFAULT_POLICY,
            known_limitations={
                "limitation": {
                    "blocking": False,
                    "reason": "Known chunking issue",
                }
            },
        )
        decision = eval_policy.compare_and_decide(candidate, baseline, policy)
        self.assertTrue(decision["allow_delivery"])
        self.assertEqual(decision["blocking_reasons"], [])
        rendered = eval_policy.format_report(decision)
        self.assertIn("Evaluation delivery policy: ALLOW", rendered)
        self.assertIn("Known chunking issue", rendered)

    def test_non_blocking_limitation_blocks_when_score_worsens(self):
        baseline = _report(
            [
                _case(
                    "limitation",
                    "failed",
                    [_metric("Rules", 0.45, success=False)],
                )
            ]
        )
        candidate = _report(
            [
                _case(
                    "limitation",
                    "failed",
                    [_metric("Rules", 0.2, success=False)],
                )
            ]
        )
        policy = dict(
            eval_policy.DEFAULT_POLICY,
            max_limitation_score_drop=0.1,
            known_limitations={
                "limitation": {"blocking": False, "reason": "Tracked"}
            },
        )
        decision = eval_policy.compare_and_decide(candidate, baseline, policy)
        self.assertFalse(decision["allow_delivery"])
        self.assertEqual(
            decision["blocking_reasons"][0]["category"],
            "continuing_limitation_worsened",
        )

    def test_blocking_or_undeclared_continuing_limitation_blocks(self):
        baseline = _report(
            [
                _case(
                    "declared-blocking",
                    "failed",
                    [_metric("Rules", 0.3, success=False)],
                ),
                _case(
                    "undeclared",
                    "failed",
                    [_metric("Rules", 0.3, success=False)],
                ),
            ]
        )
        candidate = _report(
            [
                _case(
                    "declared-blocking",
                    "failed",
                    [_metric("Rules", 0.3, success=False)],
                ),
                _case(
                    "undeclared",
                    "failed",
                    [_metric("Rules", 0.3, success=False)],
                ),
            ]
        )
        policy = dict(
            eval_policy.DEFAULT_POLICY,
            known_limitations={
                "declared-blocking": {
                    "blocking": True,
                    "reason": "Must fix before release",
                }
            },
        )
        decision = eval_policy.compare_and_decide(candidate, baseline, policy)
        self.assertFalse(decision["allow_delivery"])
        self.assertEqual(
            {item["case"] for item in decision["blocking_reasons"]},
            {"declared-blocking", "undeclared"},
        )

    def test_incomplete_assessment_blocks_and_is_reported(self):
        baseline = _report(
            [_case("judge-err", "passed", [_metric("Rules", 0.9)])]
        )
        candidate = _report(
            [
                _case(
                    "judge-err",
                    "incomplete",
                    [
                        _metric(
                            "Rules",
                            None,
                            success=None,
                            error="Judge returned invalid JSON",
                        )
                    ],
                )
            ]
        )
        decision = eval_policy.compare_and_decide(
            candidate, baseline, eval_policy.DEFAULT_POLICY
        )
        self.assertFalse(decision["allow_delivery"])
        self.assertEqual(decision["summary"]["incomplete_assessment"], 1)
        self.assertEqual(
            decision["blocking_reasons"][0]["category"],
            "incomplete_assessment",
        )

    def test_collect_run_report_marks_missing_expected_cases_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            results_dir = Path(tmp)
            (results_dir / "case-a.json").write_text(
                json.dumps(
                    _case("case-a", "passed", [_metric("Rules", 0.9)])
                )
            )
            report = eval_policy.collect_run_report(
                results_dir,
                suite="single-turn",
                run_id="run-1",
                commit="abc",
                expected_cases=["case-a", "case-b"],
                deepeval_exit_code=0,
            )
        self.assertEqual(report["cases"]["case-a"]["status"], "passed")
        self.assertEqual(report["cases"]["case-b"]["status"], "incomplete")
        self.assertTrue(eval_policy.report_has_incomplete_cases(report))

    def test_no_baseline_evaluates_new_cases_and_respects_known_limitation(
        self,
    ):
        candidate = _report(
            [
                _case("passing", "passed", [_metric("Rules", 0.9)]),
                _case(
                    "known",
                    "failed",
                    [_metric("Rules", 0.2, success=False)],
                ),
            ]
        )
        policy = dict(
            eval_policy.DEFAULT_POLICY,
            known_limitations={
                "known": {"blocking": False, "reason": "Documented gap"}
            },
        )
        decision = eval_policy.compare_and_decide(candidate, None, policy)
        self.assertTrue(decision["allow_delivery"])
        self.assertEqual(decision["summary"]["new_case"], 2)
        categories = [
            item["category"] for item in decision["non_blocking_notices"]
        ]
        self.assertIn("no_baseline", categories)
        self.assertIn("known_limitation", categories)

    def test_removed_cases_are_reported(self):
        baseline = _report(
            [
                _case("kept", "passed", [_metric("Rules", 0.9)]),
                _case("dropped", "passed", [_metric("Rules", 0.8)]),
            ]
        )
        candidate = _report(
            [_case("kept", "passed", [_metric("Rules", 0.9)])]
        )
        decision = eval_policy.compare_and_decide(
            candidate, baseline, eval_policy.DEFAULT_POLICY
        )
        self.assertTrue(decision["allow_delivery"])
        self.assertEqual(decision["removed_cases"], ["dropped"])
        self.assertEqual(decision["summary"]["removed_cases"], 1)

    def test_load_policy_rejects_unknown_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text(json.dumps({"block_on_regressions": False}))
            with self.assertRaises(ValueError):
                eval_policy.load_policy(path)

    def test_known_limitation_blocks_newly_failing_other_metric(self):
        baseline = _report(
            [
                _case(
                    "limitation",
                    "failed",
                    [
                        _metric("Rules", 0.3, success=False),
                        _metric("Faithfulness", 0.52, success=True),
                    ],
                )
            ]
        )
        candidate = _report(
            [
                _case(
                    "limitation",
                    "failed",
                    [
                        _metric("Rules", 0.3, success=False),
                        _metric("Faithfulness", 0.48, success=False),
                    ],
                )
            ]
        )
        policy = dict(
            eval_policy.DEFAULT_POLICY,
            max_limitation_score_drop=0.1,
            known_limitations={
                "limitation": {"blocking": False, "reason": "Tracked"}
            },
        )
        decision = eval_policy.compare_and_decide(candidate, baseline, policy)
        self.assertFalse(decision["allow_delivery"])
        self.assertEqual(
            decision["blocking_reasons"][0]["category"],
            "continuing_limitation_metric_regression",
        )
        self.assertEqual(
            decision["cases"]["limitation"]["newly_failing_metrics"],
            ["Faithfulness"],
        )

    def test_improvement_reminds_to_rerecord_baseline(self):
        baseline = _report(
            [_case("fixed", "failed", [_metric("Rules", 0.3, success=False)])]
        )
        candidate = _report(
            [_case("fixed", "passed", [_metric("Rules", 0.9, success=True)])]
        )
        decision = eval_policy.compare_and_decide(
            candidate, baseline, eval_policy.DEFAULT_POLICY
        )
        self.assertTrue(decision["allow_delivery"])
        messages = [n["message"] for n in decision["non_blocking_notices"]]
        self.assertTrue(any("record-baseline" in msg for msg in messages))

    def test_load_expected_case_names_rejects_duplicates_and_collisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            dup = Path(tmp) / "dup.json"
            dup.write_text(json.dumps([{"name": "a"}, {"name": "a"}]))
            with self.assertRaises(ValueError):
                eval_policy.load_expected_case_names(dup)

            collide = Path(tmp) / "collide.json"
            collide.write_text(json.dumps([{"name": "a/b"}, {"name": "a_b"}]))
            with self.assertRaises(ValueError):
                eval_policy.load_expected_case_names(collide)

    def test_repo_policy_file_is_valid(self):
        policy = eval_policy.load_policy(
            ROOT / "backend/tests/evals/policy.json"
        )
        self.assertTrue(policy["block_on_regression"])
        self.assertTrue(policy["block_on_incomplete"])


class _FakeMetric:
    def __init__(self, name, threshold=0.5):
        self.name = name
        self.threshold = threshold
        self.score = None
        self.success = None
        self.error = None
        self.reason = None


class ResultRecorderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.previous = os.environ.get("EVAL_RESULTS_DIR")
        os.environ["EVAL_RESULTS_DIR"] = self.tmp.name

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("EVAL_RESULTS_DIR", None)
        else:
            os.environ["EVAL_RESULTS_DIR"] = self.previous

    def test_resets_shared_metrics_and_records_incomplete_on_error(self):
        metric = _FakeMetric("Faithfulness")
        metric.score = 0.95
        metric.success = True
        seen_run_async = []

        def fake_assert_error(*, test_case, metrics, run_async=True):
            seen_run_async.append(run_async)
            # Simulates --ignore-errors swallowing a judge failure without
            # populating score/success.
            metrics[0].error = "rate limit"

        result_recorder.run_and_record(
            case_name="fireball",
            test_case=object(),
            metrics=[metric],
            assert_fn=fake_assert_error,
        )
        self.assertEqual(seen_run_async, [False])
        saved = json.loads((Path(self.tmp.name) / "fireball.json").read_text())
        self.assertEqual(saved["status"], "incomplete")
        self.assertIsNone(saved["metrics"][0]["score"])
        self.assertEqual(saved["metrics"][0]["error"], "rate limit")

    def test_records_failed_case_and_reraises_assertion_error(self):
        metric = _FakeMetric("Rules Correctness")

        def fake_assert_fail(*, test_case, metrics, run_async=True):
            self.assertFalse(run_async)
            metrics[0].score = 0.2
            metrics[0].success = False
            raise AssertionError("below threshold")

        with self.assertRaises(AssertionError):
            result_recorder.run_and_record(
                case_name="counterspell",
                test_case=object(),
                metrics=[metric],
                assert_fn=fake_assert_fail,
            )
        saved = json.loads(
            (Path(self.tmp.name) / "counterspell.json").read_text()
        )
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["metrics"][0]["score"], 0.2)


if __name__ == "__main__":
    unittest.main()
