"""Wires the real Divination chatbot for DeepEval multi-turn evals.

Builds the same ChatService graph as project.main._setup, so eval runs
exercise the actual retriever, prompts, and LLM the API serves in
production. Run from the backend/ directory so relative paths (PDF,
prompt templates) resolve the same way they do for the app itself.
"""

from dotenv import load_dotenv

load_dotenv()

from deepeval.integrations.langchain import CallbackHandler
from deepeval.test_case import Turn

from project.adapters.Settings import Settings
from project.adapters.answerers.MaritacaLLM import MaritacaLLM
from project.adapters.database.ChatRepository import ChatRepository
from project.adapters.enrichers.AnswerEnricher import AnswerEnricher
from project.adapters.enrichers.VectorDatabaseEnricher import (
    VectorDatabaseEnricher,
)
from project.core.ChatService import ChatService

_chat_service = ChatService(
    context_enricher=VectorDatabaseEnricher(),
    answerer=MaritacaLLM(),
    template=AnswerEnricher(),
    chat_repository=ChatRepository(),
    settings=Settings.load(),
)


def chatbot_callback(input: str, thread_id: str) -> Turn:
    answer, retrieved_docs = _chat_service.get_answer_with_context(
        query=input,
        chat_id=thread_id,
        callbacks=[CallbackHandler(thread_id=thread_id)],
    )
    return Turn(
        role="assistant",
        content=answer,
        retrieval_context=[doc.page_content for doc in retrieved_docs],
    )
