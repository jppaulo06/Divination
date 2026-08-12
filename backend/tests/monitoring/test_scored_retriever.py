"""Tests that retrieval scores survive into document metadata."""

from langchain_core.documents import Document

from project.adapters.enrichers.ScoredRetriever import (
    SCORE_METADATA_KEY,
    ScoredRetriever,
)


class FakeVectorStore:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def similarity_search_with_relevance_scores(self, query, k):
        self.calls.append((query, k))
        return self.results


def test_scores_are_stamped_into_metadata():
    store = FakeVectorStore(
        [
            (Document(page_content="Fireball deals 8d6", metadata={"page": 12}), 0.91),
            (Document(page_content="unrelated", metadata={"page": 40}), 0.31),
        ]
    )
    retriever = ScoredRetriever(vectorstore=store, k=2)

    documents = retriever.invoke("fireball damage")

    assert [d.metadata[SCORE_METADATA_KEY] for d in documents] == [0.91, 0.31]


def test_existing_metadata_is_preserved():
    store = FakeVectorStore(
        [(Document(page_content="x", metadata={"page": 7}), 0.5)]
    )

    documents = ScoredRetriever(vectorstore=store).invoke("q")

    assert documents[0].metadata["page"] == 7


def test_documents_without_metadata_still_get_a_score():
    store = FakeVectorStore([(Document(page_content="x"), 0.42)])

    documents = ScoredRetriever(vectorstore=store).invoke("q")

    assert documents[0].metadata[SCORE_METADATA_KEY] == 0.42


def test_k_is_passed_through():
    store = FakeVectorStore([])

    ScoredRetriever(vectorstore=store, k=7).invoke("q")

    assert store.calls == [("q", 7)]


def test_default_k_is_used_when_unset():
    store = FakeVectorStore([])

    ScoredRetriever(vectorstore=store).invoke("q")

    assert store.calls[0][1] == 4
