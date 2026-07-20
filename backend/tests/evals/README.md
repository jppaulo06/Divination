# DeepEval suite

Multi-turn eval suite for the Divination chatbot (`chatbot_app.py` wires the
real `ChatService` — same retriever, prompts, and LLM as the API).

The chat LLM (app and simulated users) is Maritaca's `sabia-4`; the DeepEval
judge (metrics scoring) is `sabiazinho-4` (`eval_model.py`) — both via
Maritaca's OpenAI-compatible endpoint (`https://chat.maritaca.ai/api`).
Embeddings (`VectorDatabaseEnricher`) still use OpenAI directly — Maritaca
doesn't offer an embeddings model.

## Setup

Run everything from `Divination/backend/` (relative paths for the PDF and
prompt templates depend on it, same as the app itself):

```bash
poetry install --with dev
```

`backend/.env` needs:
- `MARITACA_API_KEY` — already set.
- `OPENAI_API_KEY` — still a placeholder; needs a real key for embeddings
  (`VectorDatabaseEnricher`) to work at all, app and evals both build the
  vector store on startup.
- `LANGCHAIN_API_KEY` — unrelated LangSmith tracing, unchanged.

## 1. The dataset (`tests/evals/.dataset.json`)

`freerules-dnd.pdf` (86 pages) turned out to be D&D Beyond's **Spell
Descriptions** reference — an alphabetical A-Z spell compendium (Acid Splash
through Zone of Truth), not a general rules/combat/class document. That scope
shaped the dataset: instead of `deepeval generate`, the 25 goldens were
hand-written after reading the whole PDF, so they're grounded in specific,
verifiable spell text rather than generic sampling. They cover:

- **Numeric/table grounding** — exact damage dice, upcast scaling, save DCs
  (e.g. Fireball's 8d6 + 1d6/slot level, Divine Word's HP-threshold table).
- **Cross-spell interactions** explicit in the text — Shield vs Magic
  Missile, Daylight vs Darkness, Wall of Force vs Disintegrate, Dispel Magic
  vs Antimagic Field/Prismatic Wall's violet layer.
- **Honesty/no-hallucination checks** — questions about things this
  spells-only document doesn't cover (opportunity attacks, Action Surge,
  multiclass slots, concentrating on two spells at once). The correct
  behavior is admitting it isn't covered, not inventing an answer from
  training data.

Each golden seeds one precise opening question (`turns`) and a
`scenario`/`expected_outcome` describing the fuller goal; `ConversationSimulator`
generates realistic follow-ups toward that goal at eval time.

### Expanding the dataset later (optional)

If you add more source documents (actual rules/combat/class content) or want
broader auto-sampled coverage alongside the hand-written set, `deepeval
generate` is a CLI command and can't take a Python model object, so point it
at Maritaca via DeepEval's local-model config first (prompts for the API key,
doesn't put it in shell history):

```bash
poetry run deepeval set-local-model \
  --model=sabiazinho-4 \
  --base-url="https://chat.maritaca.ai/api" \
  --prompt-api-key \
  --save
```

This writes `LOCAL_MODEL_*` vars to `.env.local` (gitignored). Then, to
augment the existing goldens rather than overwrite them:

```bash
poetry run deepeval generate \
  --method goldens \
  --variation multi-turn \
  --goldens-file tests/evals/.dataset.json \
  --num-goldens 15 \
  --scenario-context "A Dungeon Master or player at the table asks the Divination assistant rules questions about the D&D Free Rules while running or joining a session" \
  --conversational-task "Help the user find and correctly apply the right D&D rule, resolving follow-up questions that reference earlier turns" \
  --participant-roles "User (a DM or player), Assistant (the Divination D&D rules chatbot)" \
  --output-dir ./tests/evals \
  --file-name .dataset_augmented
```

Review the output before merging it into `.dataset.json`.

## 2. Run the evals

```bash
poetry run deepeval test run tests/evals/test_divination_chat.py \
  --identifier "iterating-on-rag-grounding-round-1" \
  --num-processes 5 \
  --ignore-errors \
  --skip-on-missing-params
```

This run doesn't need `set-local-model` — `eval_model.py` builds the Maritaca
judge model explicitly in Python and both `metrics.py` and
`test_divination_chat.py` pass it in (`model=`/`simulator_model=`), so it
works regardless of whatever global CLI config is or isn't set.

## What's being checked (`metrics.py`)

- `TurnFaithfulnessMetric` — answers must be grounded in the D&D rules chunks
  actually retrieved for that turn (catches hallucinated rules/costs/stats).
- `ConversationCompletenessMetric` — the conversation resolves what the user
  came to ask, including across follow-ups.
- `RoleAdherenceMetric` — the assistant stays in its Dungeon Master Assistant
  persona.
- `Rules Answer Style` (`ConversationalGEval`) — product-specific check for
  the system prompt's format requirements (detailed, grounded, ends with
  "thanks for asking!").

## Notes

- `ChatService.get_answer_with_context` / `MaritacaLLM.get_answer_with_context`
  / `RagChain.answer_with_context` are additive siblings of the production
  `get_answer` methods, added only so the eval harness can read back
  retrieved context and attach a `deepeval.integrations.langchain.
  CallbackHandler` for tracing. They don't change existing behavior.
- `ConversationSimulator` correlates a whole simulated conversation to one
  `thread_id`; we reuse it as the app's `chat_id`, so each simulated
  conversation gets its own history in `ChatRepository`, same as a real chat.
