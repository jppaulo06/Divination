"""Exercise CI decisions in disposable Git repositories without paid APIs."""

import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


# Stands in for Poetry: logs each call and, for DeepEval runs, writes one
# attempt file per case and repetition. EVAL_FAKE_OUTCOMES maps a case to a
# pattern of outcomes ('p' pass, 'f' fail, 'i' no verdict), consumed in order
# across the attempts of one run directory.
FAKE_POETRY = """\
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ['CALL_LOG'], 'a') as log:
    log.write(json.dumps({'args': args, 'cwd': os.getcwd(),
        'venv': os.environ.get('POETRY_VIRTUALENVS_IN_PROJECT'),
        'cases': os.environ.get('EVAL_CASES')}) + '\\n')
if os.environ.get('MUTATE_CHECKOUT'):
    pathlib.Path('source.txt').write_text('changed during eval')
results_dir = os.environ.get('EVAL_RESULTS_DIR')
outcomes = json.loads(os.environ.get('EVAL_FAKE_OUTCOMES') or '{}')
if results_dir and outcomes:
    out = pathlib.Path(results_dir)
    out.mkdir(parents=True, exist_ok=True)
    repeat = int(args[args.index('--repeat') + 1]) if '--repeat' in args else 1
    selected = os.environ.get('EVAL_CASES')
    names = selected.split(',') if selected else list(outcomes)
    for name in names:
        pattern = outcomes[name]
        for _ in range(repeat):
            index = len(list(out.parent.rglob(name + '.*.json')))
            outcome = pattern[index % len(pattern)]
            if outcome == 'i':
                record = {'name': name, 'status': 'incomplete',
                          'error': 'Error code: 429 - Rate limit', 'metrics': []}
            else:
                ok = outcome == 'p'
                record = {'name': name, 'status': 'passed' if ok else 'failed',
                    'error': None, 'metrics': [{'name': 'Rules Correctness',
                    'score': 0.9 if ok else 0.2, 'threshold': 0.5,
                    'success': ok, 'status': 'passed' if ok else 'failed',
                    'error': None, 'reason': None if ok else 'wrong rule'}]}
            (out / f'{name}.{index}.json').write_text(json.dumps(record))
sys.exit(int(os.environ.get('POETRY_EXIT', '0')))
"""


class RunnerTests(unittest.TestCase):
    def setUp(self):
        # A real Git hook exports repository-local variables. Never let those
        # redirect fixture commits into the developer's repository.
        local_variables = subprocess.check_output(
            ["git", "rev-parse", "--local-env-vars"],
            text=True,
        ).splitlines()
        self.git_env = {
            key: value
            for key, value in os.environ.items()
            if key not in local_variables
        }
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.repo = self.directory / "repo"
        (self.repo / "backend").mkdir(parents=True)
        (self.repo / "scripts").mkdir()
        (self.repo / "scripts/tests").mkdir()
        (self.repo / "scripts/tests/test_fixture.py").write_text(
            "import unittest\n"
            "class FixtureTest(unittest.TestCase):\n"
            "    def test_fixture(self):\n"
            "        self.assertEqual(1 + 1, 2)\n"
        )
        shutil.copy(ROOT / "scripts/ci.py", self.repo / "scripts/ci.py")
        shutil.copy(
            ROOT / "scripts/eval_policy.py",
            self.repo / "scripts/eval_policy.py",
        )
        shutil.copy(ROOT / ".githooks/pre-push", self.repo / "pre-push")
        (self.repo / ".gitignore").write_text(".ci-state/\n")
        (self.repo / "backend/source.txt").write_text("initial\n")
        self.git("init", "-q")
        self.git("config", "user.name", "CI Test")
        self.git("config", "user.email", "ci@example.invalid")
        self.git("config", "core.hooksPath", "/dev/null")
        self.commit()
        self.log = self.directory / "calls.jsonl"
        executable = self.directory / "poetry"
        executable.write_text(f"#!{sys.executable}\n" + FAKE_POETRY)
        executable.chmod(0o755)
        self.env = dict(self.git_env)
        for name in (
            "CI_STATE_DIR",
            "CI_RUN_ID",
            "CI_BASELINE_PATH",
            "CI_POLICY_PATH",
            "POETRY_EXIT",
            "MUTATE_CHECKOUT",
            "EVAL_FAKE_OUTCOMES",
            "EVAL_WORKERS",
            "EVAL_CASES",
            "EVAL_VERBOSE",
            "FORCE_COLOR",
            "GITHUB_ACTIONS",
        ):
            self.env.pop(name, None)
        self.env.update(
            PATH=f"{self.directory}{os.pathsep}{os.environ['PATH']}",
            CALL_LOG=str(self.log),
            # Plain text, so assertions read the words, not color codes.
            NO_COLOR="1",
            EVAL_RETRY_PAUSE="0",
        )

    def git(self, *args):
        return subprocess.check_output(
            ["git", *args],
            cwd=self.repo,
            text=True,
            env=self.git_env,
        ).strip()

    def commit(self):
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "test")

    def run_ci(self, *command_args, expected=0, input_text=None):
        result = subprocess.run(
            [sys.executable, str(self.repo / "scripts/ci.py"), *command_args],
            # Commands must work even when invoked outside the repository.
            cwd=self.directory,
            env=self.env,
            text=True,
            input=input_text,
            capture_output=True,
        )
        self.assertEqual(
            result.returncode, expected, result.stdout + result.stderr
        )
        return result.stdout

    def calls(self):
        return (
            [json.loads(line) for line in self.log.read_text().splitlines()]
            if self.log.exists()
            else []
        )

    def test_first_run_records_success_and_second_run_skips(self):
        self.assertEqual(self.run_ci("conversation-needed"), "true\n")
        self.run_ci("scheduled-conversations")
        self.assertEqual(self.run_ci("conversation-needed"), "false\n")
        self.assertIn("Skipping", self.run_ci("scheduled-conversations"))
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_new_commit_runs_again(self):
        self.run_ci("scheduled-conversations")
        (self.repo / "backend/source.txt").write_text("new commit\n")
        self.commit()
        self.run_ci("scheduled-conversations")
        self.assertEqual(len(self.calls()), 2)

    def test_failure_is_propagated_and_not_recorded(self):
        self.env["POETRY_EXIT"] = "7"
        self.run_ci("scheduled-conversations", expected=7)
        self.assertFalse((self.repo / ".ci-state/conversations.json").exists())
        self.env.pop("POETRY_EXIT")
        self.run_ci("scheduled-conversations")
        self.assertEqual(len(self.calls()), 2)

    def test_manual_run_forces_evaluation(self):
        self.run_ci("scheduled-conversations")
        self.run_ci("eval-conversations")
        self.assertEqual(len(self.calls()), 2)

    def test_dirty_checkout_cannot_skip_or_record_success(self):
        (self.repo / "backend/source.txt").write_text("dirty\n")
        self.run_ci("scheduled-conversations", expected=1)
        self.assertEqual(self.calls(), [])
        self.run_ci("eval-conversations")
        self.assertFalse((self.repo / ".ci-state/conversations.json").exists())

    def test_untracked_files_prevent_scheduled_evaluation(self):
        (self.repo / "untracked.txt").write_text("new\n")
        self.run_ci("scheduled-conversations", expected=1)
        self.assertEqual(self.calls(), [])

    def test_changes_during_evaluation_are_not_recorded(self):
        self.env["MUTATE_CHECKOUT"] = "1"
        self.run_ci("scheduled-conversations")
        self.assertFalse((self.repo / ".ci-state/conversations.json").exists())

    def test_corrupt_state_runs_again(self):
        directory = self.repo / ".ci-state"
        directory.mkdir()
        (directory / "conversations.json").write_text("not JSON")
        self.run_ci("scheduled-conversations")
        self.assertEqual(len(self.calls()), 1)

    def test_external_state_survives_missing_local_state(self):
        self.env["CI_STATE_DIR"] = str(self.directory / "persistent-state")
        self.run_ci("scheduled-conversations")
        self.run_ci("scheduled-conversations")
        self.assertEqual(len(self.calls()), 1)
        self.assertFalse((self.repo / ".ci-state").exists())

    def test_lock_prevents_concurrent_api_calls(self):
        directory = self.repo / ".ci-state"
        directory.mkdir()
        with (directory / "conversations.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.run_ci("scheduled-conversations", expected=1)
        self.assertEqual(self.calls(), [])
        self.run_ci("scheduled-conversations")

    def test_eval_uses_backend_and_does_not_change_worker_counts(self):
        self.env["CI_RUN_ID"] = "custom-run"
        self.run_ci("eval-ci")
        self.run_ci("eval-conversations")
        for call, workers in zip(self.calls(), ["2", "1"]):
            self.assertEqual(call["cwd"], str(self.repo / "backend"))
            self.assertEqual(call["venv"], "true")
            args = call["args"]
            self.assertEqual(args[args.index("--num-processes") + 1], workers)
            self.assertEqual(args[args.index("--identifier") + 1], "custom-run")

    def test_eval_workers_configures_only_single_turn_suite(self):
        self.env["EVAL_WORKERS"] = "4"
        self.run_ci("eval")
        self.run_ci("eval-conversations")
        for call, workers in zip(self.calls(), ["4", "1"]):
            args = call["args"]
            self.assertEqual(args[args.index("--num-processes") + 1], workers)

    def test_invalid_eval_workers_fails_before_paid_calls(self):
        for value in ("0", "-1", "two"):
            with self.subTest(value=value):
                self.env["EVAL_WORKERS"] = value
                self.run_ci("eval", expected=1)
        self.assertEqual(self.calls(), [])

    def test_check_stops_on_lint_failure_without_paid_calls(self):
        self.env["POETRY_EXIT"] = "3"
        self.run_ci("check", expected=3)
        self.assertEqual([call["args"] for call in self.calls()], [["check", "--lock"]])

    def test_check_passes_without_paid_calls(self):
        self.run_ci("check")
        calls = [call["args"] for call in self.calls()]
        self.assertEqual(len(calls), 4)
        self.assertEqual(calls[-2], ["run", "pytest", "tests/monitoring", "-q"])
        self.assertEqual(
            calls[-1],
            ["run", "pytest", "tests/evals/test_result_recorder.py", "-q"],
        )
        self.assertFalse(any("deepeval" in args for args in calls))

    def test_pre_push_skips_deletions(self):
        self.run_ci(
            "pre-push", input_text=f"(delete) {'0' * 40} refs/heads/old {'a' * 40}\n"
        )
        self.assertEqual(self.calls(), [])

    def test_pre_push_rejects_other_commits(self):
        previous = self.git("rev-parse", "HEAD")
        (self.repo / "backend/source.txt").write_text("new\n")
        self.commit()
        self.run_ci(
            "pre-push",
            expected=1,
            input_text=f"refs/heads/old {previous} refs/heads/old {'0' * 40}\n",
        )
        self.assertEqual(self.calls(), [])

    def test_pre_push_rejects_dirty_checkout(self):
        head = self.git("rev-parse", "HEAD")
        (self.repo / "backend/source.txt").write_text("dirty\n")
        self.run_ci(
            "pre-push",
            expected=1,
            input_text=f"HEAD {head} refs/heads/main {'0' * 40}\n",
        )
        self.assertEqual(self.calls(), [])

    def test_pre_push_to_another_branch_runs_no_evals(self):
        head = self.git("rev-parse", "HEAD")
        self.run_ci(
            "pre-push", input_text=f"HEAD {head} refs/heads/feature {'0' * 40}\n"
        )
        self.assertFalse(any("deepeval" in call["args"] for call in self.calls()))

    def test_pre_push_to_main_runs_eval_ci_after_checks(self):
        head = self.git("rev-parse", "HEAD")
        self.run_ci(
            "pre-push", input_text=f"HEAD {head} refs/heads/main {'0' * 40}\n"
        )
        calls = [call["args"] for call in self.calls()]
        self.assertEqual(calls[0], ["check", "--lock"])
        self.assertIn("deepeval", calls[-1])
        self.assertNotIn("--repeat", calls[-1])

    def test_pre_push_to_main_is_blocked_by_eval_ci(self):
        self._write_dataset(["fireball"])
        self.commit()
        head = self.git("rev-parse", "HEAD")
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "p"})
        # No committed reference yet: eval-ci blocks, so the push is blocked.
        self.run_ci(
            "pre-push",
            expected=1,
            input_text=f"HEAD {head} refs/heads/main {'0' * 40}\n",
        )

    def test_hook_propagates_check_failure(self):
        self.env["POETRY_EXIT"] = "5"
        head = self.git("rev-parse", "HEAD")
        result = subprocess.run(
            ["sh", "pre-push"],
            cwd=self.repo,
            env=self.env,
            input=f"HEAD {head} refs/heads/main {'0' * 40}\n",
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertEqual(len(self.calls()), 1)

    def _write_dataset(self, names):
        evals_dir = self.repo / "backend/tests/evals"
        evals_dir.mkdir(parents=True, exist_ok=True)
        (evals_dir / ".dataset.json").write_text(
            json.dumps([{"name": name} for name in names]) + "\n"
        )

    def _write_policy(self, policy):
        evals_dir = self.repo / "backend/tests/evals"
        evals_dir.mkdir(parents=True, exist_ok=True)
        (evals_dir / "policy.json").write_text(json.dumps(policy) + "\n")

    def _baseline(self):
        path = self.repo / "backend/tests/evals/baselines/single-turn.json"
        return json.loads(path.read_text())

    def _deepeval_calls(self):
        return [call for call in self.calls() if "deepeval" in call["args"]]

    def test_quick_eval_reports_failures_without_failing(self):
        self._write_dataset(["fireball", "shield"])
        self.commit()
        self.env["POETRY_EXIT"] = "1"
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "f", "shield": "p"})
        output = self.run_ci("eval")
        self.assertIn("1 of 2 cases passed every metric.", output)
        self.assertIn("fireball / Rules Correctness: wrong rule", output)
        (call,) = self._deepeval_calls()
        self.assertNotIn("--repeat", call["args"])

    def test_eval_ci_without_any_reference_stops_before_paid_calls(self):
        self._write_dataset(["fireball"])
        self.commit()
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "p"})
        self.run_ci("eval-ci", expected=1)
        self.assertEqual(self._deepeval_calls(), [])

    def test_new_case_without_reference_blocks(self):
        self._write_dataset(["fireball"])
        self.commit()
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "p", "new": "p"})
        self.run_ci("eval-baseline")
        self._write_dataset(["fireball", "new"])
        self.commit()
        output = self.run_ci("eval-ci", expected=1)
        self.assertIn("NO REFERENCE", output)
        self.assertIn("make eval-baseline CASE=<name>", output)

    def test_baseline_retries_attempts_without_a_verdict(self):
        self._write_dataset(["fireball"])
        self.commit()
        # First attempt gets no verdict; the retry round fills the gap.
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "i" + "p" * 30})
        output = self.run_ci("eval-baseline")
        self.assertIn("Retrying 1 attempt(s)", output)
        entry = self._baseline()["cases"]["fireball"]
        self.assertEqual((entry["passed"], entry["attempts"]), (20, 20))
        self.assertEqual(entry["incomplete_attempts"], 1)
        self.assertEqual(self._deepeval_calls()[-1]["cases"], "fireball")

    def test_eval_cases_in_the_shell_cannot_narrow_a_full_run(self):
        self._write_dataset(["fireball", "shield"])
        self.commit()
        self.env["EVAL_CASES"] = "fireball"
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "p", "shield": "p"})
        output = self.run_ci("eval")
        self.assertIn("2 of 2 cases passed every metric.", output)
        self.assertEqual(self._deepeval_calls()[-1]["cases"], "")

    def test_baseline_commit_label_ignores_the_baseline_file(self):
        self._write_dataset(["fireball"])
        self.commit()
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "p"})
        self.run_ci("eval-baseline")
        # The new, uncommitted baseline file must not mark the next rebuild.
        self.run_ci("eval-baseline", "--case", "fireball")
        commit = self._baseline()["cases"]["fireball"]["commit"]
        self.assertEqual(commit, self.git("rev-parse", "--short", "HEAD"))

    def test_eval_baseline_records_attempts_and_reports_failing_cases(self):
        self._write_dataset(["fireball", "shield"])
        self.commit()
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps(
            {"fireball": "ppp" + "f" * 27, "shield": "p"}
        )
        output = self.run_ci("eval-baseline")
        (call,) = self._deepeval_calls()
        self.assertEqual(call["args"][call["args"].index("--repeat") + 1], "20")
        self.assertFalse(call["cases"])
        cases = self._baseline()["cases"]
        self.assertEqual((cases["fireball"]["passed"], cases["fireball"]["attempts"]), (3, 20))
        self.assertEqual(cases["shield"]["passed"], 20)
        self.assertIn("Fails in the new baseline:", output)
        self.assertIn("fireball  3/20", output)

    def test_single_case_baseline_rebuild_runs_only_that_case(self):
        self._write_dataset(["fireball", "shield"])
        self.commit()
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "f", "shield": "p"})
        self.run_ci("eval-baseline")
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "p", "shield": "f"})
        output = self.run_ci("eval-baseline", "--case", "fireball")
        self.assertEqual(self._deepeval_calls()[-1]["cases"], "fireball")
        cases = self._baseline()["cases"]
        self.assertEqual(cases["fireball"]["passed"], 20)
        self.assertEqual(cases["shield"]["passed"], 20)
        self.assertIn("Improved:", output)

    def test_unknown_case_fails_before_paid_calls(self):
        self._write_dataset(["fireball"])
        self.run_ci("eval-baseline", "--case", "nope", expected=1)
        self.assertEqual(self._deepeval_calls(), [])

    def test_failure_that_is_normal_for_the_case_does_not_block(self):
        self._write_dataset(["fireball", "shield"])
        self.commit()
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "f", "shield": "p"})
        self.run_ci("eval-baseline")
        self.env["POETRY_EXIT"] = "1"
        output = self.run_ci("eval-ci")
        self.assertEqual(len(self._deepeval_calls()), 2)  # no confirmation run
        self.assertIn("Fails in the reference", output)
        self.assertTrue(output.rstrip().endswith("Decision: ALLOW"))

    def test_confirmed_regression_blocks_after_confirmation_attempts(self):
        self._write_dataset(["fireball", "shield"])
        self.commit()
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "p", "shield": "p"})
        self.run_ci("eval-baseline")
        self.env["POETRY_EXIT"] = "1"
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "p", "shield": "f"})
        output = self.run_ci("eval-ci", expected=1)
        confirmation = self._deepeval_calls()[-1]
        self.assertEqual(confirmation["cases"], "shield")
        self.assertEqual(
            confirmation["args"][confirmation["args"].index("--repeat") + 1], "5"
        )
        self.assertIn("REGRESSION", output)
        self.assertIn("Decision: BLOCK (1 regression)", output)

    def test_unconfirmed_suspect_does_not_block(self):
        self._write_dataset(["shield"])
        self.commit()
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"shield": "p"})
        self.run_ci("eval-baseline")
        # First attempt fails, the five confirmation attempts pass.
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"shield": "fppppp"})
        output = self.run_ci("eval-ci")
        self.assertIn("not confirmed", output)
        self.assertTrue(output.rstrip().endswith("Decision: ALLOW"))

    def test_incomplete_attempt_blocks_even_when_deepeval_exits_zero(self):
        self._write_dataset(["fireball", "shield"])
        self.commit()
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "p", "shield": "p"})
        self.run_ci("eval-baseline")
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "p", "shield": "i"})
        output = self.run_ci("eval-ci", expected=1)
        self.assertIn("INCOMPLETE", output)
        self.assertIn("Rate limit exceeded (HTTP 429)", output)

    def test_eval_ci_retries_an_attempt_without_a_verdict(self):
        self._write_dataset(["fireball", "shield"])
        self.commit()
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "p", "shield": "p"})
        self.run_ci("eval-baseline")
        # The first attempt hits a rate limit; the retry gets a verdict.
        self.env["EVAL_FAKE_OUTCOMES"] = json.dumps({"fireball": "p", "shield": "ip"})
        output = self.run_ci("eval-ci")
        self.assertIn("Retrying 1 attempt(s) without a verdict for 1 case(s)", output)
        self.assertEqual(self._deepeval_calls()[-1]["cases"], "shield")
        self.assertTrue(output.rstrip().endswith("Decision: ALLOW"))

    def test_invalid_policy_fails_before_paid_eval_calls(self):
        self._write_dataset(["fireball"])
        self._write_policy({"unknown_key": True})
        self.run_ci("eval-ci", expected=1)
        self.run_ci("eval-baseline", expected=1)
        self.assertEqual(self._deepeval_calls(), [])


if __name__ == "__main__":
    unittest.main()
