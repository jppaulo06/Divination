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
| **Testing** | Runs code checks and chatbot evaluations, compares case outcomes against a saved reference baseline, and enforces the delivery policy in [`backend/tests/evals/policy.json`](backend/tests/evals/policy.json). |
| **Monitoring** | Records interactions and user feedback, and flags possible failures with lightweight detectors. |
| **Curation** | Supports human review to distinguish real defects from noise. Developers manually turn confirmed defects into new regression cases. |

To close the cycle, a developer defines the expected behavior for a confirmed
problem, adds a case to the [evaluation dataset](backend/tests/evals/.dataset.json)
and runs the evaluations alongside the fix (or records it as a known limitation
in [`backend/tests/evals/policy.json`](backend/tests/evals/policy.json) while a
fix is pending). That case becomes part of future regression runs. See the
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
| `make eval` | Individual answers, compared against the saved reference baseline |
| `make eval-conversations` | Conversations with multiple turns, compared against the saved reference baseline |
| `make eval-conversations-if-changed` | Conversations, skipping the commit if it is already recorded as successfully evaluated |
| `make eval-record-baseline` | Promote the latest complete evaluation report in `.ci-state/` to the reference baseline (no API calls) |
| `make eval-compare` | Compare the latest saved report against the reference baseline offline (no API calls) |

These evaluations use paid APIs. The commands work independently of GitHub;
GitHub Actions runs the same commands for PRs and scheduled evaluations.
An optional `pre-push` hook runs the checks without paid evaluations.

## Documentation

- [CI setup, hooks and scheduling](docs/ci.md)
- [Run the application](docs/running.md)
- [Evaluation datasets and metrics](backend/tests/evals/README.md)
- [Monitoring and human curation](backend/MONITORING.md)
