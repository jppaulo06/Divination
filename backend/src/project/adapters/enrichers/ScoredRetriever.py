"""Retriever wrapper that keeps each document's similarity score."""

from typing import Any, List

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

DEFAULT_K = 4
SCORE_METADATA_KEY = "relevance_score"


class ScoredRetriever(BaseRetriever):
    """Unlike `Chroma.as_retriever()`, keeps the score of each hit.

    The score rides along in `Document.metadata` under
    SCORE_METADATA_KEY, so it survives the chain and can be read back off
    the documents the chain returns.
    """

    vectorstore: Any
    k: int = DEFAULT_K

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        scored = self.vectorstore.similarity_search_with_relevance_scores(
            query, k=self.k
        )

        documents = []
        for document, score in scored:
            document.metadata = {
                **(document.metadata or {}),
                SCORE_METADATA_KEY: score,
            }
            documents.append(document)
        return documents
