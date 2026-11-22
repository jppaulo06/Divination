# Divination — CD4AI case study

This fork applies **CD4AI (Continuous Delivery for Artificial Intelligence)**
as a practical example for a MAC0499 capstone project. Its goal is to use
problems found during real usage to improve regression tests for an AI system.

The application is Divination, a D&D assistant that uses retrieval-augmented
generation (RAG). It was originally developed by Luis Carlos; see his
[original monograph](https://luizcarlosdk.github.io/capstone-project/MonographLuizCarlos.pdf).
This fork adds testing, monitoring and curation to explore the CD4AI cycle.

## How CD4AI works here

| Stage | What this project does |
| --- | --- |
| **Testing** | Runs code checks and chatbot evaluations. Each case is compared with its own pass rate in a committed reference ([`backend/tests/evals/baselines/`](backend/tests/evals/baselines/)) using Fisher's exact test; CI blocks only on a confirmed regression or on missing evidence ([`backend/tests/evals/policy.json`](backend/tests/evals/policy.json)). |
| **Monitoring** | Records interactions and user feedback, and flags possible failures with lightweight detectors. |
| **Curation** | Supports human review to distinguish real defects from noise. Developers manually turn confirmed defects into new regression cases. |

To close the cycle, a developer defines the expected behavior for a confirmed
problem, adds a case to the [evaluation dataset](backend/tests/evals/.dataset.json)
records its reference with `make eval-baseline CASE=<name>`, and commits both.
If the case still fails because a fix is pending, its reference records that
failure rate as accepted behavior, so it is visible in every report without
blocking unrelated changes. That case becomes part of future regression runs.
See the
[manual curation guide](backend/tests/evals/README.md#adding-a-regression-case-manually).

## Try the checks

With Git, Python 3.10+, Poetry 1.6.1 and Make installed on Linux, macOS or WSL,
run from the repository root:

```sh
make ci-setup
make check
```

`make check` validates the dependency lock, runs Ruff and executes the CI runner
and monitoring tests. It needs no API keys and makes no paid API calls.

For chatbot evaluations, first configure `backend/.env` from
`backend/.env.sample` with your API keys:

| Command | Evaluation |
| --- | --- |
| `make eval` | Run every single-turn case once and show which pass and fail (informative; never blocks) |
| `make eval-ci` | What CI runs: compare each case with the committed reference, give failed cases that usually pass extra attempts, block on regressions or missing evidence |
| `make eval-baseline` | Rebuild the reference (20 attempts per case) and report failing, worse and improved cases; review and commit it |
| `make eval-baseline CASE=<name>` | Rebuild the reference for one case (new, edited or fixed) |
| `make eval-conversations` | Conversations with multiple turns, reported against their own criteria |
| `make eval-conversations-if-changed` | Conversations, skipping the commit if it is already recorded as successfully evaluated |

These evaluations use paid APIs. The commands work independently of GitHub;
GitHub Actions runs the same commands for PRs and scheduled evaluations.
An optional `pre-push` hook runs the free checks before every push and, when the push updates `main`, also `make eval-ci` (paid).

## Documentation

- [CI setup, hooks and scheduling](docs/ci.md)
- [Run the application](docs/running.md)
- [Evaluation datasets and metrics](backend/tests/evals/README.md)
- [Monitoring and human curation](backend/MONITORING.md)
