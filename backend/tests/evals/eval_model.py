"""DeepEval judge model, backed by Maritaca's sabiazinho-4.

Maritaca's API is OpenAI-compatible, which DeepEval supports natively via
LocalModel (same mechanism used for vLLM/LM Studio-style custom endpoints):
https://deepeval.com/integrations/models/lmstudio
"""

import os

from deepeval.models import LocalModel
from dotenv import load_dotenv

load_dotenv()

MARITACA_BASE_URL = "https://chat.maritaca.ai/api"

maritaca_judge = LocalModel(
    model="sabiazinho-4",
    base_url=MARITACA_BASE_URL,
    api_key=os.environ["MARITACA_API_KEY"],
)
