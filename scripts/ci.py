#!/usr/bin/env python3
"""Portable CI entry point. Requires Python 3.10+, Git and Poetry."""

import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


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


def poetry(*args):
    env = dict(os.environ, POETRY_VIRTUALENVS_IN_PROJECT="true")
    subprocess.run(["poetry", *args], cwd=BACKEND, env=env, check=True)


def lint():
    poetry("check", "--lock")
    poetry("run", "ruff", "check", ".", "../scripts")


def monitoring():
    poetry("run", "pytest", "tests/monitoring", "-q")


def runner_tests():
    subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "scripts/tests", "-q"],
        cwd=ROOT,
        check=True,
    )


def evaluate(conversational=False):
    suite = "test_divination_chat.py" if conversational else "test_answer_unit.py"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    identifier = (
        os.environ.get("CI_RUN_ID") or f"{git('rev-parse', '--short', 'HEAD')}-{stamp}"
    )
    # Simulation happens during collection: multiple workers would multiply
    # Maritaca calls. Preserve the existing DeepEval error/skip policy.
    poetry(
        "run",
        "deepeval",
        "test",
        "run",
        f"tests/evals/{suite}",
        "--identifier",
        identifier,
        "--num-processes",
        "1" if conversational else "3",
        "--ignore-errors",
        "--skip-on-missing-params",
    )


def state_directory():
    path = Path(os.environ.get("CI_STATE_DIR", str(ROOT / ".ci-state")))
    return path if path.is_absolute() else ROOT / path


def already_evaluated(commit):
    try:
        state = json.loads((state_directory() / "conversations.json").read_text())
    except (FileNotFoundError, ValueError):
        return False
    return isinstance(state, dict) and state.get("commit") == commit


def conversation_needed():
    commit = clean_commit()
    if commit is None:
        raise RuntimeError(
            "Scheduled evaluations require a clean checkout, including untracked files."
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
                    "Skipping conversations: this commit was already evaluated successfully."
                )
                return
        evaluate(conversational=True)
        # Never label uncommitted changes as a successful evaluation of HEAD.
        if commit is not None and clean_commit() == commit:
            temporary = directory / "conversations.json.tmp"
            temporary.write_text(json.dumps({"commit": commit}) + "\n")
            temporary.replace(directory / "conversations.json")
        else:
            print("Evaluation passed; checkout is modified, so no commit was recorded.")


def pre_push():
    head = git("rev-parse", "HEAD")
    has_updates = False
    for line in sys.stdin:
        _, local_sha, _, _ = line.split()
        if set(local_sha) == {"0"}:  # Deleting a remote ref needs no tests.
            continue
        if git("rev-parse", f"{local_sha}^{{commit}}") != head:
            raise RuntimeError(
                "Push only the checked-out commit so the hook can validate the code being sent."
            )
        has_updates = True
    if has_updates:
        if clean_commit() is None:
            raise RuntimeError(
                "Commit or stash changes before pushing; the hook validates a clean checkout."
            )
        check()


def check():
    lint()
    runner_tests()
    monitoring()


def main():
    commands = {
        "setup": lambda: (
            poetry("check", "--lock"),
            poetry("install", "--with", "dev"),
        ),
        "lint": lint,
        "monitoring": monitoring,
        "runner-tests": runner_tests,
        "check": check,
        "eval": evaluate,
        "eval-conversations": lambda: conversations(only_if_changed=False),
        "scheduled-conversations": lambda: conversations(only_if_changed=True),
        "conversation-needed": lambda: print(str(conversation_needed()).lower()),
        "pre-push": pre_push,
    }
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=commands)
    args = parser.parse_args()
    try:
        commands[args.command]()
    except subprocess.CalledProcessError as error:
        return error.returncode
    except (OSError, RuntimeError) as error:
        print(f"CI: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
