#!/usr/bin/env python3
"""Portable CI entry point. Requires Python 3.10+, Git and Poetry."""

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

# Avoid creating scripts/__pycache__ in minimal checkouts without it ignored.
sys.dont_write_bytecode = True

import eval_policy  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
EVAL_DATASET = BACKEND / "tests/evals/.dataset.json"
EVAL_POLICY = BACKEND / "tests/evals/policy.json"
SUITES = ("single-turn", "conversational")


def git(*args):
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
    ).strip()


def clean_commit():
    if git("status", "--porcelain", "--untracked-files=normal"):
        return None
    return git("rev-parse", "HEAD")


def poetry(*args, extra_env=None, check=True):
    env = dict(os.environ, POETRY_VIRTUALENVS_IN_PROJECT="true")
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["poetry", *args], cwd=BACKEND, env=env, check=check
    )


def lint():
    poetry("check", "--lock")
    poetry("run", "ruff", "check", ".", "../scripts")


def monitoring():
    poetry("run", "pytest", "tests/monitoring", "-q")


def eval_recorder_tests():
    poetry("run", "pytest", "tests/evals/test_result_recorder.py", "-q")


def runner_tests():
    subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "scripts/tests",
            "-q",
        ],
        cwd=ROOT,
        check=True,
    )


def state_directory():
    path = Path(os.environ.get("CI_STATE_DIR", str(ROOT / ".ci-state")))
    return path if path.is_absolute() else ROOT / path


def resolve_path(raw_path):
    path = Path(raw_path)
    return path if path.is_absolute() else ROOT / path


def write_json_atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    temporary.replace(path)


def suite_name(conversational):
    return "conversational" if conversational else "single-turn"


def baseline_path(suite):
    override = os.environ.get("CI_BASELINE_PATH")
    if override:
        return resolve_path(override)
    return state_directory() / f"baseline-{suite}.json"


def latest_report_path(suite):
    return state_directory() / f"latest-{suite}.json"


def latest_decision_path(suite):
    return state_directory() / f"latest-{suite}-decision.json"


def load_active_policy(explicit_path=None):
    override = explicit_path or os.environ.get("CI_POLICY_PATH")
    if override:
        path = resolve_path(override)
        if not path.exists():
            raise RuntimeError(f"Delivery policy file not found: {path}")
        return eval_policy.load_policy(path)
    if EVAL_POLICY.exists():
        return eval_policy.load_policy(EVAL_POLICY)
    return dict(eval_policy.DEFAULT_POLICY)


def load_baseline_report(suite, explicit_path=None):
    if explicit_path:
        path = resolve_path(explicit_path)
        if not path.exists():
            raise RuntimeError(f"Reference baseline file not found: {path}")
        return json.loads(path.read_text())
    override = os.environ.get("CI_BASELINE_PATH")
    if override:
        path = resolve_path(override)
        if not path.exists():
            raise RuntimeError(f"Reference baseline file not found: {path}")
        return json.loads(path.read_text())
    default_path = state_directory() / f"baseline-{suite}.json"
    if not default_path.exists():
        return None
    return json.loads(default_path.read_text())


def evaluate(conversational=False):
    suite = suite_name(conversational)
    test_file = (
        "test_divination_chat.py" if conversational else "test_answer_unit.py"
    )
    # Validate dataset names, policy, and baseline before spending API calls.
    expected_cases = eval_policy.load_expected_case_names(EVAL_DATASET)
    policy = load_active_policy()
    baseline = load_baseline_report(suite)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    identifier = (
        os.environ.get("CI_RUN_ID")
        or f"{git('rev-parse', '--short', 'HEAD')}-{stamp}"
    )
    run_dir = state_directory() / "runs" / f"{suite}-{identifier}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    # Simulation happens during collection: multiple workers would multiply
    # Maritaca calls. DeepEval still runs with --ignore-errors and
    # --skip-on-missing-params so one bad case does not abort the rest, but
    # per-case outcomes are recorded and checked by the delivery policy below.
    result = poetry(
        "run",
        "deepeval",
        "test",
        "run",
        f"tests/evals/{test_file}",
        "--identifier",
        identifier,
        "--num-processes",
        "1" if conversational else "3",
        "--ignore-errors",
        "--skip-on-missing-params",
        extra_env={"EVAL_RESULTS_DIR": str(run_dir)},
        check=False,
    )
    if result.returncode not in (0, 1):
        raise subprocess.CalledProcessError(result.returncode, result.args)

    recorded_files = [
        path
        for path in run_dir.glob("*.json")
        if not path.name.startswith(".")
    ]
    if not recorded_files and not expected_cases:
        if result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, result.args)
        return

    report = eval_policy.collect_run_report(
        run_dir,
        suite=suite,
        run_id=identifier,
        commit=clean_commit(),
        expected_cases=expected_cases,
        deepeval_exit_code=result.returncode,
    )
    write_json_atomic(latest_report_path(suite), report)

    decision = eval_policy.compare_and_decide(report, baseline, policy)
    decision["run_id"] = identifier
    write_json_atomic(latest_decision_path(suite), decision)
    print(eval_policy.format_report(decision))

    if not decision["allow_delivery"]:
        raise RuntimeError("Evaluation delivery policy blocked this change.")


def record_baseline(suite="single-turn", source_path=None, force=False):
    source = (
        resolve_path(source_path)
        if source_path
        else latest_report_path(suite)
    )
    if not source.exists():
        raise RuntimeError(f"Evaluation report not found: {source}")
    try:
        report = json.loads(source.read_text())
    except ValueError as error:
        raise RuntimeError(
            f"Invalid evaluation report JSON: {error}"
        ) from None

    if eval_policy.report_has_incomplete_cases(report):
        raise RuntimeError(
            "Cannot record reference baseline from a report with incomplete "
            "or missing case assessments."
        )
    if not report.get("commit") and not force:
        raise RuntimeError(
            "Cannot record reference baseline from an uncommitted checkout; "
            "commit first or pass --force."
        )
    if source_path is None and not force:
        decision_file = latest_decision_path(suite)
        if decision_file.exists():
            try:
                decision = json.loads(decision_file.read_text())
            except ValueError:
                decision = None
            if (
                isinstance(decision, dict)
                and decision.get("run_id") == report.get("run_id")
                and not decision.get("allow_delivery", True)
            ):
                raise RuntimeError(
                    "Latest evaluation decision was BLOCK; fix regressions "
                    "before updating the reference baseline, or pass --force "
                    "to accept it explicitly."
                )

    target = baseline_path(suite)
    write_json_atomic(target, report)
    case_count = len(report.get("cases", {}))
    commit = report.get("commit") or "uncommitted"
    print(
        f"Recorded {suite} reference baseline ({case_count} cases, "
        f"commit {commit}) at {target}."
    )


def eval_compare(
    suite="single-turn",
    candidate_path=None,
    baseline_file=None,
    policy_file=None,
):
    candidate_source = (
        resolve_path(candidate_path)
        if candidate_path
        else latest_report_path(suite)
    )
    if not candidate_source.exists():
        raise RuntimeError(
            f"Candidate evaluation report not found: {candidate_source}"
        )
    try:
        candidate = json.loads(candidate_source.read_text())
        baseline = load_baseline_report(suite, explicit_path=baseline_file)
        policy = load_active_policy(explicit_path=policy_file)
    except ValueError as error:
        raise RuntimeError(str(error)) from None

    decision = eval_policy.compare_and_decide(candidate, baseline, policy)
    print(eval_policy.format_report(decision))
    if not decision["allow_delivery"]:
        raise RuntimeError("Evaluation delivery policy blocked this change.")


def already_evaluated(commit):
    try:
        state = json.loads(
            (state_directory() / "conversations.json").read_text()
        )
    except (FileNotFoundError, ValueError):
        return False
    return isinstance(state, dict) and state.get("commit") == commit


def conversation_needed():
    commit = clean_commit()
    if commit is None:
        raise RuntimeError(
            "Scheduled evaluations require a clean checkout, including "
            "untracked files."
        )
    return not already_evaluated(commit)


def conversations(only_if_changed):
    directory = state_directory()
    directory.mkdir(parents=True, exist_ok=True)
    # flock is released automatically on exit, including crashes. Independent
    # machines must also serialize runs in their scheduler.
    with (directory / "conversations.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(
                "Another conversational evaluation is running."
            ) from None
        commit = clean_commit()
        if only_if_changed:
            if not conversation_needed():
                print(
                    "Skipping conversations: this commit was already "
                    "evaluated successfully."
                )
                return
        evaluate(conversational=True)
        # Never label uncommitted changes as a successful evaluation of HEAD.
        if commit is not None and clean_commit() == commit:
            write_json_atomic(
                directory / "conversations.json", {"commit": commit}
            )
        else:
            print(
                "Evaluation passed; checkout is modified, so no commit was "
                "recorded."
            )


def pre_push():
    head = git("rev-parse", "HEAD")
    has_updates = False
    for line in sys.stdin:
        _, local_sha, _, _ = line.split()
        if set(local_sha) == {"0"}:  # Deleting a remote ref needs no tests.
            continue
        if git("rev-parse", f"{local_sha}^{{commit}}") != head:
            raise RuntimeError(
                "Push only the checked-out commit so the hook can validate "
                "the code being sent."
            )
        has_updates = True
    if has_updates:
        if clean_commit() is None:
            raise RuntimeError(
                "Commit or stash changes before pushing; the hook validates "
                "a clean checkout."
            )
        check()


def check():
    lint()
    runner_tests()
    monitoring()
    eval_recorder_tests()


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in (
        "setup",
        "lint",
        "monitoring",
        "eval-recorder-tests",
        "runner-tests",
        "check",
        "eval",
        "eval-conversations",
        "scheduled-conversations",
        "conversation-needed",
        "pre-push",
    ):
        subparsers.add_parser(name)

    baseline_parser = subparsers.add_parser("record-baseline")
    baseline_parser.add_argument(
        "--suite", choices=SUITES, default="single-turn"
    )
    baseline_parser.add_argument("--from", dest="source_path", default=None)
    baseline_parser.add_argument("--force", action="store_true")

    compare_parser = subparsers.add_parser("eval-compare")
    compare_parser.add_argument(
        "--suite", choices=SUITES, default="single-turn"
    )
    compare_parser.add_argument("--candidate", default=None)
    compare_parser.add_argument("--baseline", default=None)
    compare_parser.add_argument("--policy", default=None)
    return parser


def main():
    args = build_parser().parse_args()
    commands = {
        "setup": lambda: (
            poetry("check", "--lock"),
            poetry("install", "--with", "dev"),
        ),
        "lint": lint,
        "monitoring": monitoring,
        "eval-recorder-tests": eval_recorder_tests,
        "runner-tests": runner_tests,
        "check": check,
        "eval": evaluate,
        "eval-conversations": lambda: conversations(only_if_changed=False),
        "scheduled-conversations": lambda: conversations(only_if_changed=True),
        "conversation-needed": lambda: print(
            str(conversation_needed()).lower()
        ),
        "pre-push": pre_push,
        "record-baseline": lambda: record_baseline(
            suite=args.suite, source_path=args.source_path, force=args.force
        ),
        "eval-compare": lambda: eval_compare(
            suite=args.suite,
            candidate_path=args.candidate,
            baseline_file=args.baseline,
            policy_file=args.policy,
        ),
    }
    try:
        commands[args.command]()
    except subprocess.CalledProcessError as error:
        return error.returncode
    except (OSError, RuntimeError, ValueError) as error:
        print(f"CI: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
