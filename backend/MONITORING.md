# Monitoring layer

Stage 2 of the CD4AI loop: record what production does, flag what looks
wrong, and hand the flagged cases to curation (stage 3, not built yet).

## Why these five tables

The schema is shaped backwards from what curation must eventually emit — a
golden in `tests/evals/.dataset.json`. `test_answer_unit.py` parametrizes
over that whole file, so promoting a confirmed production defect into a
permanent regression test is an append to it. That requirement is what
decides everything else in the schema.

| Table | Written by | Holds |
| --- | --- | --- |
| `interactions` | the app, on every request | question, answer, versions, latency |
| `retrieved_chunks` | the app, on every request | what the model was shown, with scores |
| `signals` | detectors | one row per suspicion |
| `feedback` | users | explicit ratings |
| `curation_reviews` | curation | verdicts, and which golden was promoted |

`interactions` + `retrieved_chunks` are the system of record. Every
detector is a pure function over them, so signals can be dropped and
recomputed at any time — which is what makes it safe to run detectors off
the request path.

Retrieved chunks are stored because a curated production case cannot
become a grounding regression test without the context that produced it;
`FaithfulnessMetric` needs `retrieval_context`.

Every interaction is stamped with `template_name`, `template_hash`,
`corpus_version` and `model`. `POST /v1/context` rewrites the active
prompt at runtime, so two identical questions can legitimately produce
different answers depending on when it was last called. Without the stamp,
a prompt regression is indistinguishable from model noise.

### What a signal is

A signal is one machine-generated suspicion about one interaction — not a
verdict, and not a bug report. This stage optimises for **recall** and
accepts false positives; separating noise from real defects is curation's
job. `signals.details` carries enough context that a curation prompt can
be targeted ("this answer claims 8d6 but no retrieved chunk contains it")
rather than "review this conversation".

`UniqueConstraint(interaction_id, type, detector_version)` makes re-runs
idempotent. Bumping a detector's `version` re-flags history under the new
logic.

### Feedback is the one thing that cannot be recomputed

Every other signal is derived and replayable. A thumbs-down is primary
data: no replay reconstructs it, because the person who gave it is gone.
So `SqlInteractionSink.record_feedback` writes the rating **and** its
`user_negative_feedback` signal in a single transaction, rather than
letting a later sweep derive it. Negative feedback with no signal is
therefore impossible by construction.

Consequences:

- `feedback` is append-only. A rating change adds a row, so a signal's
  `details.feedback_id` always points at a row that still says what it
  said when the signal fired.
- Repeated negative ratings on one interaction keep every rating but
  produce only one signal — one signal is enough to queue it, and a second
  insert would violate the uniqueness key and roll the rating back with
  it.
- Positive ratings produce no signal. They are kept as the only
  positive-class labels available for calibrating detector precision.
- The endpoint returns an error instead of swallowing failures, unlike
  interaction recording.

## Detectors

| Type | Fires when |
| --- | --- |
| `weak_retrieval` | best chunk scored below threshold, or nothing retrieved |
| `unsupported_claim` | answer states dice/DC absent from every chunk |
| `refusal_or_hedge` | answer says the provided material was insufficient (EN or PT) |
| `format_guardrail_violation` | answer does not end with the required closing |
| `repeated_question` | user re-asked something earlier in the thread |
| `user_negative_feedback` | thumbs-down (written transactionally, not detected) |

All are cheap and offline — no LLM, no embeddings. Two deliberate
imprecisions:

- `unsupported_claim` flags correct answers whose numbers are *derived*.
  Fireball at 5th level is 10d6, which never appears in a corpus that
  says "8d6 plus 1d6 per slot level above 3rd". Tightening this to
  silence that would cost real recall on genuine hallucinations.
- `refusal_or_hedge` mostly fires on correct behaviour — the prompt tells
  the model to admit gaps. The value is in the aggregate: a cluster of
  refusals on one subject is a corpus coverage gap.

`refusal_or_hedge` matches a structural shape — a reference to the
provided material within one sentence of a negation — rather than a list
of phrasings. Version 1 used a phrase list and missed a real refusal in
production ("o contexto fornecido **não traz**…", where the list expected
"não cobre" / "não há informações"). That answer is now a fixture in
`tests/monitoring/test_refusal_hedge.py`.

It only catches refusals the model states outright. A confident
hallucination produces no refusal signal at all, so an absence of these
is not evidence of health.

### What the first production traffic showed

`WeakRetrievalDetector`'s threshold (0.7) is still **uncalibrated, and the
first real data suggests an absolute threshold may be the wrong shape
entirely.** Across 16 stored chunks the scores spanned only 0.579–0.654,
so every interaction fell below the threshold and the signal fired on 100%
of traffic — a constant, not a signal. Worse, the query `"Bla"` scored the
highest top score of all (0.654), above a substantive rules question
(0.632). Per-query spread (0.009–0.019) did not separate them either.

Caveat: that sample contained no known-good question, so it shows the
score does not discriminate *among bad queries* — not yet that it cannot
discriminate at all. Run `scripts/generate_traffic.py`, which includes
in-scope spell questions, and compare before choosing a threshold or
replacing the approach.

The same data surfaced a corpus defect worth more than any threshold
tuning: the top-ranked chunk for a rules question was scraped website
boilerplate ("We have updated our terms and conditions. Click the link to
learn more.", page 84). Navigation and legal text in the source PDF
competes with rules content at retrieval time.

## Running it

Postgres comes up with the stack; without `MONITORING_DATABASE_URL` the
app falls back to a SQLite file at `../database/monitoring.db`, so tests
and scripts need no container.

```bash
docker compose up -d          # api + front + postgres
```

Generate traffic (the demo has no real users, so monitoring would
otherwise have nothing to flag). The bank deliberately goes outside the 25
goldens: in-scope spells, out-of-scope rules, Portuguese questions against
an English corpus, and adversarial prompts.

```bash
python scripts/generate_traffic.py --base-url http://localhost:8000
```

Inspect:

```bash
curl localhost:8000/v1/monitoring/summary
curl 'localhost:8000/v1/monitoring/candidates?limit=10'
curl 'localhost:8000/v1/monitoring/candidates?signal_type=weak_retrieval'
```

Re-run detectors after changing one (idempotent):

```bash
python scripts/run_detectors.py
```

Label a demo instance's traffic as synthetic rather than production:

```bash
MONITORING_SOURCE=synthetic docker compose up -d
```

## Curation's input contract

```sql
SELECT i.*, json_agg(s.*)
FROM interactions i
JOIN signals s ON s.interaction_id = i.id
LEFT JOIN curation_reviews r ON r.interaction_id = i.id
WHERE r.id IS NULL
GROUP BY i.id
```

Implemented as `CandidateQuery.pending()` and exposed at
`GET /v1/monitoring/candidates`. It is built now, before curation exists,
because if it were awkward to express the schema would be wrong.

"Awaiting review" is the *absence* of a `curation_reviews` row, not a
status column on `interactions` — a status column would duplicate state
the review table already implies, and the two would drift.

## Tests

```bash
poetry run pytest tests/monitoring -q
```

Offline and deterministic: detectors are pure functions and the store
tests use in-memory SQLite. Runs in CI on every PR with no API keys.

## Not done yet

- **Answers restored from history cannot be rated.** `GET /v1/chats`
  returns LangChain messages with no interaction ids, so the frontend can
  only attach a rating to answers received in the current session —
  reload the page and the buttons disappear from older turns. Fixing it
  means returning interaction ids alongside the chat history.
- **`weak_retrieval` threshold uncalibrated**, and possibly the wrong
  shape (see above).
- **`repeated_question` uses token overlap**, not embeddings, so it misses
  fully reworded repeats. Upgrading is a batch job over stored
  interactions; nothing else changes, because detectors read the database
  rather than the request.
- **Thread-level coverage is thin.** Only `repeated_question` is
  thread-scoped; the conversational eval metrics have no production
  counterpart yet.
- **Stage 1 is still a per-test gate**, not the cumulative pass-rate gate
  the pattern specifies.
