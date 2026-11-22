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
from eval_policy import paint  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
EVAL_DATASET = BACKEND / "tests/evals/.dataset.json"
EVAL_POLICY = BACKEND / "tests/evals/policy.json"
BASELINE_DIR = BACKEND / "tests/evals/baselines"
# Extra rounds that rerun baseline attempts left without a verdict.
BASELINE_RETRY_ROUNDS = 3
SUITES = ("single-turn", "conversational")
# Pushes that update this branch also run the paid eval-ci comparison.
DELIVERY_REF = "refs/heads/main"


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


def recorded_case_files(results_dir):
    return [
        path
        for path in Path(results_dir).glob("*.json")
        if not path.name.startswith(".")
    ]


def run_deepeval(*args, extra_env, results_dir, expected_total):
    """Run DeepEval through Poetry, keeping its full output in a log file.

    The terminal shows only progress; the results table and the delivery
    decision are printed afterwards. EVAL_VERBOSE=1 streams DeepEval's own
    output instead. Returns the exit code.
    """
    env = dict(os.environ, POETRY_VIRTUALENVS_IN_PROJECT="true", **extra_env)
    command = ["poetry", *args]
    if os.environ.get("EVAL_VERBOSE"):
        return subprocess.run(command, cwd=BACKEND, env=env).returncode

    log_path = Path(results_dir) / "deepeval.log"
    print(paint(f"Full DeepEval output: {display_path(log_path)}", "dim"))
    interactive = sys.stdout.isatty()
    shown = None
    with log_path.open("w") as log:
        process = subprocess.Popen(
            command, cwd=BACKEND, env=env, stdout=log, stderr=subprocess.STDOUT
        )
        while True:
            try:
                process.wait(timeout=2)
                finished = True
            except subprocess.TimeoutExpired:
                finished = False
            done = len(recorded_case_files(results_dir))
            if done != shown and (done or finished):
                line = paint(f"  {done}/{expected_total} attempts evaluated", "dim")
                print(f"\r{line}" if interactive else line,
                      end="" if interactive else "\n", flush=True)
                shown = done
            if finished:
                break
    if interactive and shown is not None:
        print()
    if process.returncode not in (0, 1):
        tail = log_path.read_text(errors="replace").splitlines()[-30:]
        print(
            paint("DeepEval failed; last lines of its output:", "red", "bold"),
            file=sys.stderr,
        )
        print("\n".join(tail), file=sys.stderr)
    return process.returncode


def display_path(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


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


def baseline_file(suite):
    """The committed reference for a suite."""
    return BASELINE_DIR / f"{suite}.json"


def latest_report_path(suite):
    return state_directory() / f"latest-{suite}.json"


def latest_decision_path(suite):
    return state_directory() / f"latest-{suite}-decision.json"


def load_active_policy():
    override = os.environ.get("CI_POLICY_PATH")
    if override:
        path = resolve_path(override)
        if not path.exists():
            raise RuntimeError(f"Delivery policy file not found: {path}")
        return eval_policy.load_policy(path)
    if EVAL_POLICY.exists():
        return eval_policy.load_policy(EVAL_POLICY)
    return dict(eval_policy.DEFAULT_POLICY)


def load_baseline(suite):
    path = baseline_file(suite)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except ValueError as error:
        raise RuntimeError(f"Invalid baseline file {path}: {error}") from None


def code_commit():
    """The commit that produced a reference: HEAD, marked when files other
    than the baseline itself are uncommitted."""
    head = git("rev-parse", "--short", "HEAD")
    changed = git(
        "status",
        "--porcelain",
        "--untracked-files=normal",
        "--",
        ".",
        f":(exclude){BASELINE_DIR.relative_to(ROOT)}",
    )
    return f"{head}+uncommitted" if changed else head


def single_turn_workers():
    """Worker count for the single-turn suite: EVAL_WORKERS, or 2 by default.

    Two workers stay within Maritaca's output-token rate limit (three
    exceeded it); use 1 if requests are rejected with HTTP 429.
    """
    value = (os.environ.get("EVAL_WORKERS") or "2").strip()
    if not value.isdigit() or int(value) < 1:
        raise ValueError(
            f"EVAL_WORKERS must be a positive integer, got {value!r}"
        )
    return str(int(value))


def new_run_dir(suite, label=None):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    identifier = (
        os.environ.get("CI_RUN_ID")
        or f"{git('rev-parse', '--short', 'HEAD')}-{stamp}"
    )
    name = f"{suite}-{label}-{identifier}" if label else f"{suite}-{identifier}"
    run_dir = state_directory() / "runs" / name
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    return identifier, run_dir


def run_attempts(
    suite, run_dir, identifier, *, cases, case_count, attempts, workers
):
    """Run ``attempts`` attempts of each case through DeepEval.

    ``cases`` selects a subset of the dataset (None runs all ``case_count``
    cases). Each call is one round with its own subdirectory of ``run_dir``,
    holding one file per attempt and the round's DeepEval log. DeepEval runs
    with --ignore-errors and --skip-on-missing-params so one bad attempt does
    not abort the rest; attempts without a verdict are missing evidence.
    """
    rounds = sum(1 for path in run_dir.glob("round-*") if path.is_dir())
    round_dir = run_dir / f"round-{rounds + 1}"
    round_dir.mkdir(parents=True)
    test_file = (
        "test_divination_chat.py"
        if suite == "conversational"
        else "test_answer_unit.py"
    )
    extra_env = {
        "EVAL_RESULTS_DIR": str(round_dir),
        # No tracebacks or per-test summary lines. These go through
        # PYTEST_ADDOPTS because DeepEval's CLI claims "-r" for --repeat.
        "PYTEST_ADDOPTS": " ".join(
            filter(None, [os.environ.get("PYTEST_ADDOPTS"), "--tb=no -rN"])
        ),
    }
    # Always set, so a value left in the developer's shell cannot narrow a
    # full run.
    extra_env["EVAL_CASES"] = ",".join(cases) if cases is not None else ""
    repeat = ["--repeat", str(attempts)] if attempts > 1 else []
    returncode = run_deepeval(
        "run",
        "deepeval",
        "test",
        "run",
        f"tests/evals/{test_file}",
        "--identifier",
        identifier,
        "--num-processes",
        workers,
        *repeat,
        "--ignore-errors",
        "--skip-on-missing-params",
        # The full table goes to the log; the report below summarizes it.
        "--display",
        "failing",
        extra_env=extra_env,
        results_dir=round_dir,
        expected_total=case_count * attempts,
    )
    if returncode not in (0, 1):
        raise subprocess.CalledProcessError(returncode, "deepeval test run")
    return returncode


def quick_eval():
    """Run every single-turn case once and show which pass and which fail.

    Informative only: no reference comparison, no repeats, and failing cases
    do not fail the command. Only a broken run (DeepEval crashing) does.
    """
    suite = "single-turn"
    workers = single_turn_workers()
    expected_cases = eval_policy.load_expected_case_names(EVAL_DATASET)
    identifier, run_dir = new_run_dir(suite, label="quick")
    print(
        paint(
            f"Running {len(expected_cases)} {suite} cases once "
            f"with {workers} worker(s)...",
            "bold",
        )
    )
    returncode = run_attempts(
        suite,
        run_dir,
        identifier,
        cases=None,
        case_count=len(expected_cases),
        attempts=1,
        workers=workers,
    )
    if not expected_cases:
        if returncode:
            raise subprocess.CalledProcessError(returncode, "deepeval test run")
        return
    attempts = eval_policy.collect_attempts(run_dir, expected_cases)
    print()
    print(eval_policy.format_results(attempts))
    print()
    print(
        paint(
            "This run only shows results. make eval-ci compares them with "
            "the committed reference, as CI does.",
            "dim",
        )
    )


def evaluate(conversational=False):
    """Judge a run case by case against the committed reference.

    Each case runs once; a case whose attempt failed, and whose decline could
    be proven, becomes a suspect and runs ``confirmation_attempts`` more
    times before the pooled attempts are judged. Blocks only on a confirmed regression or
    on missing evidence. The conversational suite has no reference: its
    cases are reported against their own criteria and block only on missing
    evidence.
    """
    suite = suite_name(conversational)
    # Validate settings, dataset names, policy, and baseline before spending
    # API calls.
    # Conversations are simulated during collection: more workers would
    # multiply Maritaca calls.
    workers = "1" if conversational else single_turn_workers()
    expected_cases = eval_policy.load_expected_case_names(EVAL_DATASET)
    policy = load_active_policy()
    baseline = None if conversational else load_baseline(suite)
    if baseline is None and not conversational and expected_cases:
        raise RuntimeError(
            f"No committed reference ({display_path(baseline_file(suite))}). "
            "Build it with make eval-baseline and commit it first; until "
            "then every case would be blocked, so no API calls were made."
        )

    identifier, run_dir = new_run_dir(suite)
    print(
        paint(
            f"Evaluating {len(expected_cases)} {suite} cases "
            f"with {workers} worker(s)...",
            "bold",
        )
    )
    returncode = run_attempts(
        suite,
        run_dir,
        identifier,
        cases=None,
        case_count=len(expected_cases),
        attempts=1,
        workers=workers,
    )
    if not expected_cases:
        if returncode:
            raise subprocess.CalledProcessError(returncode, "deepeval test run")
        return
    attempts = eval_policy.collect_attempts(run_dir, expected_cases)

    suspects = (
        []
        if conversational
        else eval_policy.find_suspects(attempts, baseline, policy)
    )
    extra = policy["confirmation_attempts"]
    if suspects:
        print(
            paint(
                f"{len(suspects)} case(s) failed and usually pass; "
                f"confirming with {extra} more attempt(s) each...",
                "yellow",
            )
        )
        run_attempts(
            suite,
            run_dir,
            identifier,
            cases=suspects,
            case_count=len(suspects),
            attempts=extra,
            workers=workers,
        )
        attempts = eval_policy.collect_attempts(run_dir, expected_cases)

    decision = eval_policy.decide(
        attempts,
        baseline,
        policy,
        suspects=suspects,
        expected_attempts={
            name: 1 + (extra if name in suspects else 0) for name in attempts
        },
        require_reference=not conversational,
    )
    decision["run_id"] = identifier
    decision["commit"] = clean_commit()
    write_json_atomic(
        latest_report_path(suite),
        {"suite": suite, "run_id": identifier, "attempts": attempts},
    )
    write_json_atomic(latest_decision_path(suite), decision)
    print()
    print(
        eval_policy.format_decision(
            decision,
            attempts,
            suite=suite,
            reference_path=None
            if conversational
            else display_path(baseline_file(suite)),
        )
    )
    if not decision["allow_delivery"]:
        raise RuntimeError("Evaluation delivery policy blocked this change.")


def eval_baseline(cases=None):
    """Rebuild the committed reference for all cases, or only ``cases``.

    Runs ``baseline_attempts`` attempts per case, compares the result with
    the previous reference, and writes the file for the developer to review
    and commit.
    """
    suite = "single-turn"
    workers = single_turn_workers()
    policy = load_active_policy()
    expected_cases = eval_policy.load_expected_case_names(EVAL_DATASET)
    if cases:
        unknown = sorted(set(cases) - set(expected_cases))
        if unknown:
            raise ValueError(
                "Unknown evaluation case(s): " + ", ".join(unknown)
            )
        selected = [name for name in expected_cases if name in set(cases)]
    else:
        selected = expected_cases
    if not selected:
        raise RuntimeError("No evaluation cases found in the dataset.")
    previous = load_baseline(suite)
    attempts_per_case = policy["baseline_attempts"]

    identifier, run_dir = new_run_dir(suite, label="baseline")
    print(
        paint(
            f"Building the {suite} reference: {len(selected)} case(s) x "
            f"{attempts_per_case} attempts with {workers} worker(s)...",
            "bold",
        )
    )
    run_attempts(
        suite,
        run_dir,
        identifier,
        cases=selected if cases else None,
        case_count=len(selected),
        attempts=attempts_per_case,
        workers=workers,
    )
    attempts = eval_policy.collect_attempts(run_dir, selected)

    # Attempts without a verdict (usually rate limits) are rerun, so one
    # error does not leave a case out of the reference.
    for _ in range(BASELINE_RETRY_ROUNDS):
        missing = {
            name: attempts_per_case - eval_policy.tally(records)["attempts"]
            for name, records in attempts.items()
        }
        missing = {name: count for name, count in missing.items() if count > 0}
        if not missing:
            break
        print(
            paint(
                f"Retrying {sum(missing.values())} attempt(s) without a "
                f"verdict for {len(missing)} case(s)...",
                "yellow",
            )
        )
        run_attempts(
            suite,
            run_dir,
            identifier,
            cases=list(missing),
            case_count=len(missing),
            attempts=max(missing.values()),
            workers=workers,
        )
        attempts = eval_policy.collect_attempts(run_dir, selected)

    commit = code_commit()
    baseline, changes = eval_policy.build_baseline(
        attempts,
        previous,
        policy,
        suite=suite,
        commit=commit,
        recorded_at=datetime.now(timezone.utc).date().isoformat(),
        full=not cases,
    )
    target = baseline_file(suite)
    if changes["recorded"] or changes["removed"]:
        write_json_atomic(target, baseline)
    print()
    print(
        eval_policy.format_baseline_changes(
            changes, path=display_path(target), attempts_per_case=attempts_per_case
        )
    )
    if changes["not_recorded"]:
        raise RuntimeError(
            "Some cases were not recorded; rerun them with "
            "make eval-baseline CASE=<name>."
        )


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
    """Validate a push: free checks always; paid evals when it updates main.

    Pushing to the delivery branch is the integration point, so it also runs
    ``eval-ci``; pushes to other branches stay free.
    """
    head = git("rev-parse", "HEAD")
    has_updates = False
    updates_delivery_branch = False
    for line in sys.stdin:
        _, local_sha, remote_ref, _ = line.split()
        if set(local_sha) == {"0"}:  # Deleting a remote ref needs no tests.
            continue
        if git("rev-parse", f"{local_sha}^{{commit}}") != head:
            raise RuntimeError(
                "Push only the checked-out commit so the hook can validate "
                "the code being sent."
            )
        has_updates = True
        updates_delivery_branch |= remote_ref == DELIVERY_REF
    if has_updates:
        if clean_commit() is None:
            raise RuntimeError(
                "Commit or stash changes before pushing; the hook validates "
                "a clean checkout."
            )
        check()
    if updates_delivery_branch:
        print(
            paint(
                "Pushing to main: comparing the evals with the committed "
                "reference (paid API calls)...",
                "bold",
            )
        )
        evaluate()


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
        "eval-ci",
        "eval-conversations",
        "scheduled-conversations",
        "conversation-needed",
        "pre-push",
    ):
        subparsers.add_parser(name)

    baseline_parser = subparsers.add_parser("eval-baseline")
    baseline_parser.add_argument(
        "--case",
        dest="cases",
        action="append",
        default=None,
        help="Rebuild only this case (repeatable).",
    )
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
        "eval": quick_eval,
        "eval-ci": evaluate,
        "eval-conversations": lambda: conversations(only_if_changed=False),
        "scheduled-conversations": lambda: conversations(only_if_changed=True),
        "conversation-needed": lambda: print(
            str(conversation_needed()).lower()
        ),
        "pre-push": pre_push,
        "eval-baseline": lambda: eval_baseline(cases=args.cases),
    }
    try:
        commands[args.command]()
    except subprocess.CalledProcessError as error:
        return error.returncode
    except (OSError, RuntimeError, ValueError) as error:
        print(paint(f"CI: {error}", "red"), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
