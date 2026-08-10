"""DeepEval judge model, backed by Maritaca's sabia-4.

Maritaca's API is OpenAI-compatible, which DeepEval supports natively via
LocalModel (same mechanism used for vLLM/LM Studio-style custom endpoints):
https://deepeval.com/integrations/models/lmstudio

Originally used the smaller/cheaper sabiazinho-4, but it periodically
returned malformed JSON for DeepEval's structured schema prompts (both the
simulator's next-user-turn schema and metric verdict schemas), which
aborts the whole collection with no retry (tenacity's retry policy doesn't
cover DeepEvalError from a JSON parse failure). sabia-4 follows the JSON
formatting instructions reliably instead.
"""

import os

from deepeval.models import LocalModel
from dotenv import load_dotenv

load_dotenv()

MARITACA_BASE_URL = "https://chat.maritaca.ai/api"

maritaca_judge = LocalModel(
    model="sabia-4",
    base_url=MARITACA_BASE_URL,
    api_key=os.environ["MARITACA_API_KEY"],
)
