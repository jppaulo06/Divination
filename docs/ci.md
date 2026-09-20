# CI without GitHub

[Back to the project overview](../README.md).

The CI commands live in [`scripts/ci.py`](../scripts/ci.py), with shortcuts in
the [`Makefile`](../Makefile). They can run on a developer's machine, in a Git
hook, or on a CI server. GitHub Actions is an optional adapter that prepares
the environment, supplies credentials, schedules runs and persists state.
The runner itself does not use the GitHub API or require GitHub credentials.

### Prepare the environment

Use Linux, macOS or WSL with Git, Python 3.10+ and Poetry 1.6.1 on `PATH`.
Python 3.10 is the version used by the Actions workflows. GNU Make is
optional; every target has an equivalent Python command. The runner uses
POSIX file locking for conversational evaluations, so native Windows is
not supported; use WSL there.

From the repository root:

```sh
pipx install poetry==1.6.1
make ci-setup
make check
```

Install `pipx` first if it is not already available. `ci-setup` verifies
`poetry.lock` and installs the backend dependencies, including the dev
group, in `backend/.venv`. Run it again after dependency changes. Checks
and hooks do not install dependencies automatically. The application Docker
images do not contain the dev dependencies required by these commands.

### Available commands

| Make target | Python equivalent | Purpose | Paid API calls |
| --- | --- | --- | --- |
| `make ci-setup` | `python3 scripts/ci.py setup` | Verify lock and install dependencies | No |
| `make check` | `python3 scripts/ci.py check` | Lock validation, Ruff, CI runner tests and monitoring tests | No |
| `make lint` | `python3 scripts/ci.py lint` | Lock validation and Ruff | No |
| `make monitoring` | `python3 scripts/ci.py monitoring` | Monitoring tests with pytest | No |
| `make runner-tests` | `python3 scripts/ci.py runner-tests` | Test CI decisions in temporary Git repositories | No |
| `make eval` | `python3 scripts/ci.py eval` | Single-turn chatbot evaluations | Yes |
| `make eval-conversations` | `python3 scripts/ci.py eval-conversations` | Always run multi-turn evaluations | Yes |
| `make eval-conversations-if-changed` | `python3 scripts/ci.py scheduled-conversations` | Multi-turn evaluations unless this commit is already recorded as successful | Only when needed |

The Python entry point also works when called by absolute path from another
directory. Each command exits with a nonzero status when a subprocess fails,
so hooks and other CI systems can use its exit status to stop integration.
`make check` stops at the first failed stage. These commands cover the
backend and CI runner; frontend tests, image builds and deployment are not
part of this pipeline.

`make runner-tests` needs only Python and Git. It substitutes the Poetry
process in disposable repositories to test scheduling, failure propagation,
locking and hook behavior without credentials or API calls.

### Credentials and paid evaluations

For local evaluations, copy `backend/.env.sample` to `backend/.env` and fill
in the API keys. Keep this ignored file out of version control. The existing
application configuration also accepts environment variables, so another
CI provider can inject them through its own secret mechanism:

- `OPENAI_API_KEY`: embeddings.
- `MARITACA_API_KEY`: chatbot, simulated users and evaluation judge.
- `LANGCHAIN_API_KEY`: tracing configuration.
- `HOST`, `PORT`, `ALLOWED_ORIGINS`, `ALLOWED_METHODS`, `ALLOWED_HEADERS`:
  application settings required by the evaluation harness. Use the JSON
  list syntax shown in `backend/.env.sample` for the `ALLOWED_*` values.

No API credentials are needed for `make check`. `make eval` uses three
workers; conversational evaluations use one to limit Maritaca traffic.
Both retain the existing DeepEval options `--ignore-errors` and
`--skip-on-missing-params`: a successful command reflects that policy and
does not guarantee that every metric was evaluated. See the
[evaluation guide](../backend/tests/evals/README.md) for datasets and metrics.

Run identifiers default to the short Git commit plus a UTC timestamp.
Set `CI_RUN_ID` to supply an identifier from another CI system.

### Optional local pre-push hook

After preparing the environment, enable the versioned hook in each clone:

```sh
git config --local core.hooksPath .githooks
```

If this clone already uses a custom hooks directory, integrate
[`.githooks/pre-push`](../.githooks/pre-push) with the existing hook instead of
replacing its configuration. The hook runs `make check`'s Python equivalent
before a push and blocks the push when it fails. It never runs paid
evaluations. Python and Poetry must be on the Git process's `PATH`,
including when pushing from an IDE.

The hook requires a clean checkout, including untracked files, and validates
only pushes of the currently checked-out commit. Commit or stash local
changes first. If pushing another branch or several different commits,
check out and push each branch separately. Remote ref deletions are allowed
without tests. These constraints prevent testing local files that differ
from the commit being sent.

To disable this repository's setting:

```sh
git config --local --unset core.hooksPath
```

Restore any previous custom setting if applicable. Hooks are local and
optional: each clone must enable them, and `git push --no-verify` bypasses
them. They do not execute when someone merges through a hosting service's
web interface. A `pre-merge-commit` hook also misses fast-forward merges
and merges initially stopped by conflicts. See the
[Git hook documentation](https://git-scm.com/docs/githooks). For mandatory
validation, run these same commands in a controlled CI environment and
configure the hosting service to require their results before integration.

### Weekly evaluations with any scheduler

`make eval-conversations-if-changed` compares `HEAD` against
`.ci-state/conversations.json`. It records the commit only after a
successful evaluation of a checkout that remained clean. With the same
commit recorded, it exits successfully without calling Poetry or LLM APIs.
A new commit, missing state or invalid JSON causes a new evaluation;
failed commands do not advance the recorded commit. Any new commit counts,
including documentation-only changes.

Scheduled runs require a clean checkout. `make eval-conversations` always
runs, including with local edits; it records success only when the checkout
remains clean. A file lock prevents simultaneous conversational evaluations
sharing the same state directory; a competing process exits with an error.

Keep `.ci-state/` between runs. To put it on persistent storage outside the
checkout, set `CI_STATE_DIR` to an absolute directory dedicated to this
project. Relative paths are resolved from the repository root. If you use
a different directory inside the checkout, add it to your local Git ignore
configuration. Separate machines also need scheduler-level serialization.
Deleting or losing state permits another paid evaluation of the same commit.

For example, prepare a dedicated clean checkout on `main` at
`/srv/divination`, configure its `backend/.env`, and run `make ci-setup` once.
On a machine whose cron timezone is UTC, this crontab runs every Monday at
06:00 UTC (03:00 in Brasilia):

```cron
PATH=/home/ci/.local/bin:/usr/local/bin:/usr/bin:/bin
0 6 * * 1 (cd /srv/divination && git fetch origin main && git merge --ff-only origin/main && make ci-setup && make eval-conversations-if-changed) >> /srv/divination/.ci-state/weekly.log 2>&1
```

Create `/srv/divination/.ci-state` before enabling the job, and replace the
paths and branch with your installation's values. The host must be running
at the scheduled time, have Git remote access and provide the configured
Python/Poetry executables. This example updates only by fast-forward and
stops if synchronization or dependency setup fails. Without the fetch and
merge, the command evaluates only the checkout already on disk. Schedule
this independently of GitHub only if you intend to have a separate runner;
two schedulers with separate state can duplicate paid work.

### GitHub Actions adapter

The workflows now call the same Make targets:

- PRs to `main`: lint and CI runner tests, followed by monitoring tests and
  single-turn evaluations in parallel.
- Mondays at 06:00 UTC: conversational evaluations if the commit needs them.
- Manual conversational workflow dispatch: always evaluate again.

The weekly adapter downloads the state file from an artifact belonging to a
successful conversational workflow for the same commit. The portable runner
checks this file before dependency installation. After success, the adapter
uploads it again, even when evaluation was skipped, to renew its retention.
Only this storage adapter uses the GitHub API; the evaluation and skip logic
remain in the portable runner.

Keep the repository's artifact retention longer than the weekly interval
(the default is 90 days). Deleting artifacts or pausing the workflow beyond
their retention can cause re-evaluation. On another runner, keep
`CI_STATE_DIR` on persistent storage. See the
[artifact retention documentation](https://github.com/actions/upload-artifact#retention-period).

Moving to another CI service means preparing Python/Poetry, injecting the
same variables, invoking the same commands and persisting the state file.
The hooks and local commands work even if the Actions workflows are disabled.
