"""Tests for tagging restored chat answers with their interaction id."""

from dataclasses import dataclass

from project.adapters.monitoring.Database import in_memory_database
from project.adapters.monitoring.SqlInteractionLookup import (
    SqlInteractionLookup,
)
from project.adapters.monitoring.SqlInteractionSink import SqlInteractionSink
from project.adapters.routers.chat_history_view import serialise_history
from project.ports.monitoring.InteractionLookup import NullInteractionLookup
from project.ports.monitoring.InteractionSink import InteractionRecord


@dataclass
class StoredMessage:
    type: str
    content: str


@dataclass
class StoredHistory:
    messages: list


def history(*pairs) -> StoredHistory:
    messages = []
    for question, answer in pairs:
        messages.append(StoredMessage("human", question))
        messages.append(StoredMessage("ai", answer))
    return StoredHistory(messages)


class TestSerialiseHistory:
    def test_answers_are_tagged_and_questions_are_not(self):
        payload = serialise_history(
            history(("pergunta", "resposta")), {"resposta": ["int-1"]}
        )

        assert payload == [
            {"type": "human", "content": "pergunta"},
            {"type": "ai", "content": "resposta", "interactionId": "int-1"},
        ]

    def test_unmatched_answer_is_not_rateable(self):
        payload = serialise_history(history(("q", "sem registro")), {})

        assert payload[1]["interactionId"] is None

    def test_repeated_answers_get_distinct_ids_in_turn_order(self):
        payload = serialise_history(
            history(("q1", "mesma"), ("q2", "mesma")),
            {"mesma": ["int-1", "int-2"]},
        )

        assert [m.get("interactionId") for m in payload if m["type"] == "ai"] \
            == ["int-1", "int-2"]

    def test_more_answers_than_records_degrades_to_none(self):
        payload = serialise_history(
            history(("q1", "mesma"), ("q2", "mesma")), {"mesma": ["int-1"]}
        )

        assert [m.get("interactionId") for m in payload if m["type"] == "ai"] \
            == ["int-1", None]

    def test_empty_history(self):
        assert serialise_history(StoredHistory([]), {}) == []

    def test_history_without_messages_attribute(self):
        assert serialise_history(object(), {}) == []


class TestWithTheRealLookup:
    def test_ids_come_back_for_a_recorded_conversation(self):
        database = in_memory_database()
        sink = SqlInteractionSink(database)
        first = sink.record_interaction(
            InteractionRecord(chat_id="c-1", question="q1", answer="a1")
        )
        second = sink.record_interaction(
            InteractionRecord(chat_id="c-1", question="q2", answer="a2")
        )

        payload = serialise_history(
            history(("q1", "a1"), ("q2", "a2")),
            SqlInteractionLookup(database).ids_by_answer("c-1"),
        )

        assert [m.get("interactionId") for m in payload if m["type"] == "ai"] \
            == [first, second]

    def test_a_failed_interaction_does_not_shift_the_pairing(self):
        # The failure is recorded but never reaches the chat history.
        # Pairing by position would hand answer "a2" the failed row's id.
        database = in_memory_database()
        sink = SqlInteractionSink(database)
        sink.record_interaction(
            InteractionRecord(
                chat_id="c-1",
                question="q1",
                answer="",
                error="RateLimitError: boom",
            )
        )
        recovered = sink.record_interaction(
            InteractionRecord(chat_id="c-1", question="q2", answer="a2")
        )

        payload = serialise_history(
            history(("q2", "a2")),
            SqlInteractionLookup(database).ids_by_answer("c-1"),
        )

        assert payload[1]["interactionId"] == recovered

    def test_other_chats_are_not_mixed_in(self):
        database = in_memory_database()
        sink = SqlInteractionSink(database)
        sink.record_interaction(
            InteractionRecord(chat_id="other", question="q", answer="a1")
        )

        ids = SqlInteractionLookup(database).ids_by_answer("c-1")

        assert ids == {}

    def test_a_broken_database_degrades_instead_of_raising(self):
        class ExplodingDatabase:
            def session(self):
                raise RuntimeError("down")

        assert SqlInteractionLookup(ExplodingDatabase()).ids_by_answer("c") == {}

    def test_null_lookup_yields_no_ids(self):
        payload = serialise_history(
            history(("q", "a")), NullInteractionLookup().ids_by_answer("c-1")
        )

        assert payload[1]["interactionId"] is None
