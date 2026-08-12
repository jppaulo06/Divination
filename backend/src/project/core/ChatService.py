import time
from typing import NamedTuple

from project.ports.monitoring.InteractionSink import (
    InteractionRecord,
    NullInteractionSink,
    RetrievedChunkRecord,
)

_SCORE_METADATA_KEY = "relevance_score"


class AnswerResult(NamedTuple):
    answer: str
    #: None when monitoring is disabled or the write failed.
    interaction_id: str | None


class ChatService:
    def __init__(
        self,
        context_enricher,
        answerer,
        template,
        chat_repository,
        settings,
        interaction_sink=None,
        source: str = "production",
    ):
        self.context_enricher = context_enricher
        self.llm_answerer = answerer
        self.answer_template = template
        self.chat_repository = chat_repository
        self.project_settings = settings
        self.interaction_sink = interaction_sink or NullInteractionSink()
        self.source = source

    def get_answer(self, query, chat_id) -> AnswerResult:
        """Answer a question and record the interaction."""
        answer, _documents, interaction_id = self._answer(query, chat_id)
        return AnswerResult(answer=answer, interaction_id=interaction_id)

    def get_answer_with_context(self, query, chat_id, callbacks=None):
        """Same as get_answer(), but also returns retrieved documents and
        accepts tracing callbacks. Used by the eval suite."""
        answer, documents, _interaction_id = self._answer(
            query, chat_id, callbacks=callbacks
        )
        return answer, documents

    def _answer(self, query, chat_id, callbacks=None):
        """Single answering path, shared by both public entry points."""
        template = self.answer_template.get_template()
        history_template = self.answer_template.get_history_template()

        started = time.perf_counter()
        documents = []
        error = None
        answer = ""
        try:
            context = self.context_enricher.getData(query)
            answer, documents = self.llm_answerer.get_answer_with_context(
                chat_id,
                query,
                context,
                self.chat_repository,
                template,
                history_template,
                self.project_settings,
                callbacks=callbacks,
            )
        except Exception as failure:
            error = f"{type(failure).__name__}: {failure}"
            self._record(query, chat_id, answer, documents, started, error)
            raise

        interaction_id = self._record(
            query, chat_id, answer, documents, started, error
        )
        return answer, documents, interaction_id

    def _record(self, query, chat_id, answer, documents, started, error):
        latency_ms = int((time.perf_counter() - started) * 1000)
        record = InteractionRecord(
            chat_id=chat_id,
            question=query,
            answer=answer or "",
            source=self.source,
            model=getattr(self.llm_answerer, "model_name", ""),
            template_name=getattr(self.answer_template, "name", ""),
            template_hash=_template_hash(self.answer_template),
            corpus_version=getattr(
                self.context_enricher, "corpus_version", ""
            ),
            latency_ms=latency_ms,
            error=error,
            chunks=[
                RetrievedChunkRecord(
                    rank=rank,
                    content=document.page_content,
                    score=(document.metadata or {}).get(_SCORE_METADATA_KEY),
                    page=(document.metadata or {}).get("page"),
                )
                for rank, document in enumerate(documents or [])
            ],
        )
        return self.interaction_sink.record_interaction(record)


def _template_hash(template_enricher) -> str:
    getter = getattr(template_enricher, "template_hash", None)
    return getter() if callable(getter) else ""
