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
        executable.write_text(
            f"#!{sys.executable}\n"
            "import json, os, pathlib, sys\n"
            "with open(os.environ['CALL_LOG'], 'a') as log:\n"
            "    log.write(json.dumps({'args': sys.argv[1:], "
            "'cwd': os.getcwd(), "
            "'venv': os.environ.get('POETRY_VIRTUALENVS_IN_PROJECT')}) + '\\n')\n"
            "if os.environ.get('MUTATE_CHECKOUT'):\n"
            "    pathlib.Path('source.txt').write_text('changed during eval')\n"
            "sys.exit(int(os.environ.get('POETRY_EXIT', '0')))\n"
        )
        executable.chmod(0o755)
        self.env = dict(self.git_env)
        for name in ("CI_STATE_DIR", "CI_RUN_ID", "POETRY_EXIT", "MUTATE_CHECKOUT"):
            self.env.pop(name, None)
        self.env.update(
            PATH=f"{self.directory}{os.pathsep}{os.environ['PATH']}",
            CALL_LOG=str(self.log),
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

    def run_ci(self, command, *, expected=0, input_text=None):
        result = subprocess.run(
            [sys.executable, str(self.repo / "scripts/ci.py"), command],
            # Commands must work even when invoked outside the repository.
            cwd=self.directory,
            env=self.env,
            text=True,
            input=input_text,
            capture_output=True,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
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
        self.run_ci("eval")
        self.run_ci("eval-conversations")
        for call, workers in zip(self.calls(), ["3", "1"]):
            self.assertEqual(call["cwd"], str(self.repo / "backend"))
            self.assertEqual(call["venv"], "true")
            args = call["args"]
            self.assertEqual(args[args.index("--num-processes") + 1], workers)
            self.assertEqual(args[args.index("--identifier") + 1], "custom-run")

    def test_check_stops_on_lint_failure_without_paid_calls(self):
        self.env["POETRY_EXIT"] = "3"
        self.run_ci("check", expected=3)
        self.assertEqual([call["args"] for call in self.calls()], [["check", "--lock"]])

    def test_check_passes_without_paid_calls(self):
        self.run_ci("check")
        calls = [call["args"] for call in self.calls()]
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[-1], ["run", "pytest", "tests/monitoring", "-q"])
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


if __name__ == "__main__":
    unittest.main()
