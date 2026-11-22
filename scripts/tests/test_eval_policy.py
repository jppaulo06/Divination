"""Unit tests for reference comparison, delivery policy, and result capture."""

import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend/tests/evals"))

import eval_policy  # noqa: E402
import result_recorder  # noqa: E402

# Plain text, so assertions read the words, not color codes.
os.environ["NO_COLOR"] = "1"


POLICY = dict(eval_policy.DEFAULT_POLICY)


def _attempt(name, outcome, *, reason="judge says no"):
    """One recorded attempt: outcome is 'p' (pass), 'f' (fail) or 'i'."""
    if outcome == "i":
        return {
            "name": name,
            "status": "incomplete",
            "error": "Error code: 429 - Rate limit exceeded",
            "metrics": [],
        }
    passed = outcome == "p"
    return {
        "name": name,
        "status": "passed" if passed else "failed",
        "error": None,
        "metrics": [
            {
                "name": "Rules Correctness [GEval]",
                "score": 0.9 if passed else 0.2,
                "threshold": 0.5,
                "success": passed,
                "status": "passed" if passed else "failed",
                "error": None,
                "reason": None if passed else reason,
            }
        ],
    }


def _attempts(**patterns):
    """{case: 'ppf'} -> {case: [attempt, attempt, attempt]}."""
    return {
        name: [_attempt(name, outcome) for outcome in pattern]
        for name, pattern in patterns.items()
    }


def _baseline(**counts):
    """{case: (passed, attempts)} -> a committed reference."""
    return {
        "schema_version": 2,
        "suite": "single-turn",
        "cases": {
            name: {"passed": passed, "attempts": attempts}
            for name, (passed, attempts) in counts.items()
        },
    }


class SettingsTests(unittest.TestCase):
    def _load(self, policy):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text(json.dumps(policy))
            return eval_policy.load_policy(path)

    def test_repo_policy_file_is_valid(self):
        policy = eval_policy.load_policy(ROOT / "backend/tests/evals/policy.json")
        self.assertEqual(policy["baseline_attempts"], 20)

    def test_rejects_unknown_keys_and_bad_values(self):
        for policy in (
            {"known_limitations": {}},
            {"suspect_below": 0.05},
            {"confirmation_attempts": 0},
            {"regression_below": 1.5},
            {"change_below": 0},
        ):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                self._load(policy)

    def test_settings_must_be_able_to_confirm_a_regression(self):
        # 2 failed attempts against a 1/1 reference: p = 1/3, never < 0.01.
        with self.assertRaises(ValueError):
            self._load({"baseline_attempts": 1, "confirmation_attempts": 1})
        self.assertEqual(self._load({"confirmation_attempts": 2})["confirmation_attempts"], 2)

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


class FisherTests(unittest.TestCase):
    def p(self, reference, recent, function=eval_policy.decline_p_value):
        return function(
            {"passed": reference[0], "attempts": reference[1]},
            {"passed": recent[0], "attempts": recent[1]},
        )

    def test_matches_known_one_sided_values(self):
        # Values checked against scipy.stats.fisher_exact(alternative="greater").
        self.assertAlmostEqual(self.p((29, 30), (7, 10)), 0.041689, places=6)
        self.assertAlmostEqual(self.p((29, 30), (8, 10)), 0.148785, places=6)
        self.assertAlmostEqual(self.p((30, 30), (1, 3)), 0.005682, places=6)
        self.assertAlmostEqual(self.p((30, 30), (0, 1)), 1 / 31)
        self.assertAlmostEqual(self.p((30, 30), (24, 30)), 0.011860, places=6)

    def test_no_failures_or_no_attempts_is_never_unusual(self):
        self.assertEqual(self.p((3, 30), (1, 1)), 1.0)
        self.assertEqual(self.p((30, 30), (0, 0)), 1.0)

    def test_improvement_is_the_mirror_test(self):
        improvement = eval_policy.improvement_p_value
        self.assertLess(self.p((5, 30), (28, 30), improvement), 0.0001)
        self.assertEqual(self.p((30, 30), (0, 1), improvement), 1.0)


class AttemptTests(unittest.TestCase):
    def test_collect_groups_attempt_files_by_case_across_rounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            for index, outcome in enumerate("pfp"):
                round_dir = Path(tmp) / f"round-{1 if index == 0 else 2}"
                round_dir.mkdir(exist_ok=True)
                (round_dir / f"fireball.{index}.json").write_text(
                    json.dumps(_attempt("fireball", outcome))
                )
            (Path(tmp) / ".fireball.tmp.json").write_text("not json")
            attempts = eval_policy.collect_attempts(tmp, ["fireball", "shield"])
        self.assertEqual(len(attempts["fireball"]), 3)
        self.assertEqual(attempts["shield"], [])
        self.assertEqual(
            eval_policy.tally(attempts["fireball"]),
            {"passed": 2, "attempts": 3, "incomplete": 0},
        )

    def test_incomplete_attempts_are_counted_apart(self):
        records = _attempts(fireball="pfi")["fireball"]
        self.assertEqual(
            eval_policy.tally(records),
            {"passed": 1, "attempts": 2, "incomplete": 1},
        )


class DecisionTests(unittest.TestCase):
    def decide(self, attempts, baseline, *, suspects=(), extra=5):
        return eval_policy.decide(
            attempts,
            baseline,
            POLICY,
            suspects=suspects,
            expected_attempts={
                name: 1 + (extra if name in suspects else 0) for name in attempts
            },
        )

    def test_failure_that_is_normal_for_the_case_is_not_a_suspect(self):
        attempts = _attempts(fireball="f", shield="p")
        baseline = _baseline(fireball=(3, 30), shield=(30, 30))
        self.assertEqual(eval_policy.find_suspects(attempts, baseline, POLICY), [])
        decision = self.decide(attempts, baseline)
        self.assertTrue(decision["allow_delivery"])
        self.assertEqual(decision["cases"]["fireball"]["verdict"], "consistent")

    def test_failure_of_a_case_that_usually_passes_becomes_a_suspect(self):
        attempts = _attempts(shield="f", haste="f")
        # 19/20 used to be invisible: one failure alone gives p = 2/21.
        baseline = _baseline(shield=(30, 30), haste=(19, 20))
        self.assertEqual(
            eval_policy.find_suspects(attempts, baseline, POLICY),
            ["shield", "haste"],
        )

    def test_case_whose_decline_cannot_be_proven_is_not_confirmed(self):
        # Even six failures out of six would not be unusual for 7/12.
        attempts = _attempts(daylight="f")
        self.assertEqual(
            eval_policy.find_suspects(attempts, _baseline(daylight=(7, 12)), POLICY),
            [],
        )

    def test_partial_decline_of_a_mostly_passing_case_is_confirmed(self):
        # 19/20 before; now 4 of 6 attempts fail: p = 1071/230230 = 0.0047.
        decision = self.decide(
            _attempts(haste="ffffpp"), _baseline(haste=(19, 20)), suspects=["haste"]
        )
        self.assertEqual(decision["cases"]["haste"]["verdict"], "regression")

    def test_confirmed_suspect_is_a_blocking_regression(self):
        attempts = _attempts(shield="ffffff")
        decision = self.decide(
            attempts, _baseline(shield=(30, 30)), suspects=["shield"]
        )
        self.assertFalse(decision["allow_delivery"])
        self.assertEqual(decision["cases"]["shield"]["verdict"], "regression")
        self.assertLess(decision["cases"]["shield"]["p_value"], 0.001)

    def test_unconfirmed_suspect_does_not_block(self):
        attempts = _attempts(shield="fppppp")
        decision = self.decide(
            attempts, _baseline(shield=(30, 30)), suspects=["shield"]
        )
        self.assertTrue(decision["allow_delivery"])
        self.assertEqual(decision["cases"]["shield"]["verdict"], "suspect_cleared")

    def test_missing_evidence_blocks(self):
        cases = {
            "no reference": (_attempts(new="p"), _baseline()),
            "incomplete attempt": (_attempts(shield="i"), _baseline(shield=(30, 30))),
            "no attempt recorded": ({"shield": []}, _baseline(shield=(30, 30))),
        }
        for label, (attempts, baseline) in cases.items():
            with self.subTest(label):
                decision = self.decide(attempts, baseline)
                self.assertFalse(decision["allow_delivery"])

    def test_suspect_without_its_confirmation_attempts_is_incomplete(self):
        # The confirmation run crashed: only the first attempt was recorded.
        decision = self.decide(
            _attempts(shield="f"), _baseline(shield=(30, 30)), suspects=["shield"]
        )
        self.assertEqual(decision["cases"]["shield"]["verdict"], "incomplete")
        self.assertFalse(decision["allow_delivery"])

    def test_without_reference_requirement_failures_are_only_reported(self):
        decision = eval_policy.decide(
            _attempts(chat="f"), None, POLICY, require_reference=False
        )
        self.assertTrue(decision["allow_delivery"])
        self.assertEqual(decision["cases"]["chat"]["verdict"], "unreferenced")

    def test_reference_entries_for_removed_cases_are_reported(self):
        decision = self.decide(
            _attempts(shield="p"), _baseline(shield=(30, 30), gone=(30, 30))
        )
        self.assertEqual(decision["stale_reference_entries"], ["gone"])
        self.assertTrue(decision["allow_delivery"])


class BaselineTests(unittest.TestCase):
    def build(self, attempts, previous, *, full=True):
        return eval_policy.build_baseline(
            attempts,
            previous,
            POLICY,
            suite="single-turn",
            commit="abc123",
            recorded_at="2026-11-22",
            full=full,
        )

    def test_reports_failing_worse_improved_and_new_cases(self):
        attempts = _attempts(
            stable="p" * 30,
            weak="p" * 3 + "f" * 27,
            worse="p" * 24 + "f" * 6,
            better="p" * 28 + "f" * 2,
            fresh="p" * 30,
        )
        previous = _baseline(
            stable=(30, 30), weak=(4, 30), worse=(30, 30), better=(5, 30)
        )
        baseline, changes = self.build(attempts, previous)
        self.assertEqual(
            [item["case"] for item in changes["fails"]], ["weak", "worse", "better"]
        )
        self.assertEqual([item["case"] for item in changes["worse"]], ["worse"])
        self.assertEqual([item["case"] for item in changes["improved"]], ["better"])
        self.assertEqual([item["case"] for item in changes["new"]], ["fresh"])
        self.assertEqual(
            baseline["cases"]["weak"],
            {"passed": 3, "attempts": 30, "commit": "abc123",
             "recorded_at": "2026-11-22"},
        )

    def test_single_case_rebuild_keeps_other_entries(self):
        previous = _baseline(shield=(30, 30), fireball=(3, 30))
        baseline, changes = self.build(
            _attempts(fireball="p" * 30), previous, full=False
        )
        self.assertEqual(baseline["cases"]["shield"], {"passed": 30, "attempts": 30})
        self.assertEqual(baseline["cases"]["fireball"]["passed"], 30)
        self.assertEqual(changes["removed"], [])

    def test_full_rebuild_drops_removed_cases(self):
        _, changes = self.build(
            _attempts(shield="p" * 30), _baseline(shield=(30, 30), gone=(1, 30))
        )
        self.assertEqual(changes["removed"], ["gone"])

    def test_case_with_too_few_complete_attempts_keeps_its_old_entry(self):
        previous = _baseline(shield=(30, 30))
        baseline, changes = self.build(
            _attempts(shield="p" * 19 + "i" * 11), previous
        )
        self.assertEqual(changes["not_recorded"][0]["case"], "shield")
        self.assertEqual(baseline["cases"]["shield"], {"passed": 30, "attempts": 30})

    def test_some_incomplete_attempts_are_noted_but_recorded(self):
        baseline, _ = self.build(_attempts(shield="p" * 28 + "ii"), None)
        self.assertEqual(baseline["cases"]["shield"]["attempts"], 28)
        self.assertEqual(baseline["cases"]["shield"]["incomplete_attempts"], 2)


class OutputTests(unittest.TestCase):
    def test_quick_results_table_lists_failures_first_with_reasons(self):
        lines = eval_policy.format_results(
            _attempts(zeta="p", alpha="f")
        ).splitlines()
        self.assertEqual(lines[0].split(), ["Case", "Rules", "Correctness", "Result"])
        self.assertTrue(lines[2].startswith("alpha"))
        self.assertTrue(lines[2].endswith("FAIL"))
        self.assertIn("0.20 ✗", lines[2])
        self.assertIn("1 of 2 cases passed every metric.", lines)
        self.assertIn("  alpha / Rules Correctness: judge says no", lines)

    def test_decision_report_shows_attention_accepted_failures_and_steps(self):
        attempts = _attempts(shield="ffffff", fireball="f", new="p")
        baseline = _baseline(shield=(30, 30), fireball=(3, 30))
        decision = eval_policy.decide(
            attempts,
            baseline,
            POLICY,
            suspects=["shield"],
            expected_attempts={"shield": 6, "fireball": 1, "new": 1},
        )
        text = eval_policy.format_decision(decision, attempts, suite="single-turn")
        self.assertIn("REGRESSION (p < 0.0001)", text)
        self.assertIn("NO REFERENCE", text)
        self.assertIn("Fails in the reference (accepted behavior", text)
        self.assertIn("fireball  3/30", text)
        self.assertIn("make eval-baseline CASE=<name>", text)
        self.assertTrue(
            text.endswith("Decision: BLOCK (1 regression, 1 no reference)")
        )

    def test_rate_limit_reasons_collapse_to_one_line(self):
        attempts = _attempts(shield="i")
        decision = eval_policy.decide(
            attempts, _baseline(shield=(30, 30)), POLICY
        )
        text = eval_policy.format_decision(decision, attempts, suite="single-turn")
        self.assertIn("Rate limit exceeded (HTTP 429)", text)
        self.assertNotIn("Error code", text)
        # The judge's retry wrapper names the error without the HTTP code.
        self.assertEqual(
            eval_policy._short_reason(
                "RetryError[<Future at 0x7f state=finished raised RateLimitError>]"
            ),
            "Rate limit exceeded (HTTP 429); retry with fewer workers.",
        )

    def test_baseline_changes_report(self):
        _, changes = eval_policy.build_baseline(
            _attempts(worse="p" * 24 + "f" * 6),
            _baseline(worse=(30, 30)),
            POLICY,
            suite="single-turn",
            commit="abc",
            recorded_at="2026-11-22",
            full=True,
        )
        text = eval_policy.format_baseline_changes(
            changes, path="baselines/single-turn.json", attempts_per_case=30
        )
        self.assertIn("Fails in the new baseline:", text)
        self.assertIn("Got worse than the previous baseline", text)
        self.assertIn("worse  30/30 -> 24/30  (p = 0.0119)", text)
        self.assertTrue(text.endswith("then commit the baseline file."))


class ColorTests(unittest.TestCase):
    def setUp(self):
        saved = {name: os.environ.get(name) for name in ("NO_COLOR", "FORCE_COLOR")}
        self.addCleanup(
            lambda: [
                os.environ.pop(name, None)
                if value is None
                else os.environ.__setitem__(name, value)
                for name, value in saved.items()
            ]
        )

    def report(self):
        attempts = _attempts(shield="ffffff", fireball="f", ok="p")
        decision = eval_policy.decide(
            attempts,
            _baseline(shield=(30, 30), fireball=(3, 30), ok=(30, 30)),
            POLICY,
            suspects=["shield"],
            expected_attempts={"shield": 6, "fireball": 1, "ok": 1},
        )
        return (
            eval_policy.format_results(attempts)
            + eval_policy.format_decision(decision, attempts, suite="single-turn")
        )

    def test_colors_keep_text_and_alignment(self):
        os.environ["NO_COLOR"] = "1"
        plain = self.report()
        os.environ.pop("NO_COLOR")
        os.environ["FORCE_COLOR"] = "1"
        colored = self.report()
        self.assertIn("\033[31;1mREGRESSION", colored)
        self.assertIn("\033[31;1mDecision: BLOCK", colored)
        stripped = re.sub(r"\033\[[0-9;]*m", "", colored)
        self.assertEqual(stripped, plain)

    def test_no_color_wins(self):
        os.environ["NO_COLOR"] = "1"
        os.environ["FORCE_COLOR"] = "1"
        self.assertNotIn("\033[", self.report())


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
        for name in ("EVAL_RESULTS_DIR", "EVAL_CASES"):
            previous = os.environ.get(name)
            self.addCleanup(
                lambda name=name, previous=previous: (
                    os.environ.pop(name, None)
                    if previous is None
                    else os.environ.__setitem__(name, previous)
                )
            )
        os.environ["EVAL_RESULTS_DIR"] = self.tmp.name
        os.environ.pop("EVAL_CASES", None)

    def saved(self, case):
        (path,) = Path(self.tmp.name).glob(f"{case}.*.json")
        return json.loads(path.read_text())

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
        saved = self.saved("fireball")
        self.assertEqual(saved["status"], "incomplete")
        self.assertIsNone(saved["metrics"][0]["score"])
        self.assertEqual(saved["metrics"][0]["error"], "rate limit")

    def test_records_failed_case_with_reason_and_reraises(self):
        metric = _FakeMetric("Rules Correctness")

        def fake_assert_fail(*, test_case, metrics, run_async=True):
            self.assertFalse(run_async)
            metrics[0].score = 0.2
            metrics[0].success = False
            metrics[0].reason = "Omits the 8d6 base damage."
            raise AssertionError("below threshold")

        with self.assertRaises(AssertionError):
            result_recorder.run_and_record(
                case_name="counterspell",
                test_case=object(),
                metrics=[metric],
                assert_fn=fake_assert_fail,
            )
        saved = self.saved("counterspell")
        self.assertEqual(saved["status"], "failed")
        self.assertEqual(saved["metrics"][0]["score"], 0.2)
        self.assertEqual(saved["metrics"][0]["reason"], "Omits the 8d6 base damage.")

    def test_repeated_attempts_keep_one_file_each(self):
        metric = _FakeMetric("Faithfulness")

        def fake_assert_pass(*, test_case, metrics, run_async=True):
            metrics[0].score = 1.0
            metrics[0].success = True

        for _ in range(3):
            result_recorder.run_and_record(
                case_name="shield",
                test_case=object(),
                metrics=[metric],
                assert_fn=fake_assert_pass,
            )
        self.assertEqual(len(list(Path(self.tmp.name).glob("shield.*.json"))), 3)

    def test_select_cases_filters_by_name_and_rejects_unknown(self):
        goldens = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
        self.assertEqual(result_recorder.select_cases(goldens), goldens)
        os.environ["EVAL_CASES"] = "c, a"
        self.assertEqual(
            result_recorder.select_cases(goldens), [{"name": "a"}, {"name": "c"}]
        )
        os.environ["EVAL_CASES"] = "a,missing"
        with self.assertRaises(ValueError):
            result_recorder.select_cases(goldens)


if __name__ == "__main__":
    unittest.main()
