"""HTTP-level tests for the feedback and monitoring endpoints."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from project.adapters.monitoring.CandidateQuery import CandidateQuery
from project.adapters.monitoring.Database import in_memory_database
from project.adapters.monitoring.DetectorRunner import DetectorRunner
from project.adapters.monitoring.SqlInteractionSink import SqlInteractionSink
from project.adapters.monitoring.detectors import FormatGuardrailDetector
from project.adapters.routers.FeedbackRouter import FeedbackRouter
from project.adapters.routers.MonitoringRouter import MonitoringRouter
from project.adapters.routers.dto.answer_dto import AnswerRequest, AnswerResponse
from project.ports.monitoring.InteractionSink import (
    InteractionRecord,
    NullInteractionSink,
    RetrievedChunkRecord,
)


@pytest.fixture
def database():
    return in_memory_database()


@pytest.fixture
def sink(database):
    return SqlInteractionSink(database)


def build_client(*routers) -> TestClient:
    api = FastAPI()
    for router in routers:
        api.include_router(router.create())
    return TestClient(api)


def record(sink, answer="Deals 8d6. thanks for asking!") -> str:
    return sink.record_interaction(
        InteractionRecord(
            chat_id="c-1",
            question="How much damage?",
            answer=answer,
            chunks=[
                RetrievedChunkRecord(rank=0, content="deals 8d6", score=0.9)
            ],
        )
    )


class TestFeedbackEndpoint:
    def test_negative_rating_is_accepted_and_flagged(self, sink, database):
        interaction_id = record(sink)
        client = build_client(FeedbackRouter(sink))

        response = client.post(
            "/v1/feedback",
            json={
                "interactionId": interaction_id,
                "rating": -1,
                "comment": "wrong dice",
            },
        )

        assert response.status_code == 200
        assert response.json()["feedbackId"] > 0
        assert CandidateQuery(database).summary()["signals_by_type"] == {
            "user_negative_feedback": 1
        }

    def test_snake_case_field_names_are_also_accepted(self, sink):
        interaction_id = record(sink)
        client = build_client(FeedbackRouter(sink))

        response = client.post(
            "/v1/feedback",
            json={"interaction_id": interaction_id, "rating": 1},
        )

        assert response.status_code == 200

    def test_unknown_interaction_is_a_404(self, sink):
        client = build_client(FeedbackRouter(sink))

        response = client.post(
            "/v1/feedback",
            json={"interactionId": "missing", "rating": -1},
        )

        assert response.status_code == 404

    def test_disabled_monitoring_is_a_503(self):
        client = build_client(FeedbackRouter(NullInteractionSink()))

        response = client.post(
            "/v1/feedback",
            json={"interactionId": "anything", "rating": -1},
        )

        assert response.status_code == 503

    def test_missing_rating_is_rejected(self, sink):
        client = build_client(FeedbackRouter(sink))

        response = client.post(
            "/v1/feedback", json={"interactionId": "x"}
        )

        assert response.status_code == 422


class TestMonitoringEndpoints:
    def test_candidates_expose_signals_and_context(self, sink, database):
        interaction_id = record(sink, answer="No closing line.")
        DetectorRunner(database, [FormatGuardrailDetector()]).backfill()
        client = build_client(MonitoringRouter(CandidateQuery(database)))

        payload = client.get("/v1/monitoring/candidates").json()

        assert len(payload) == 1
        assert payload[0]["interaction_id"] == interaction_id
        assert payload[0]["retrieval_context"] == ["deals 8d6"]
        assert payload[0]["signals"][0]["type"] == (
            "format_guardrail_violation"
        )

    def test_candidates_are_empty_when_nothing_is_flagged(
        self, sink, database
    ):
        record(sink)
        client = build_client(MonitoringRouter(CandidateQuery(database)))

        assert client.get("/v1/monitoring/candidates").json() == []

    def test_summary_reports_counts(self, sink, database):
        interaction_id = record(sink)
        sink.record_feedback(interaction_id, rating=-1)
        client = build_client(MonitoringRouter(CandidateQuery(database)))

        payload = client.get("/v1/monitoring/summary").json()

        assert payload["interactions"] == 1
        assert payload["pending_candidates"] == 1

    def test_limit_is_validated(self, database):
        client = build_client(MonitoringRouter(CandidateQuery(database)))

        assert (
            client.get("/v1/monitoring/candidates?limit=0").status_code == 422
        )


class TestAnswerDto:
    def test_response_is_serialised_with_camel_case_aliases(self):
        response = AnswerResponse.create_answer("hello", "abc-123")

        assert response.model_dump(by_alias=True) == {
            "projectAnswer": "hello",
            "interactionId": "abc-123",
        }

    def test_interaction_id_defaults_to_none(self):
        assert AnswerResponse.create_answer("hello").interaction_id is None

    def test_request_accepts_camel_case(self):
        request = AnswerRequest(userQuestion="q", chatId="c")

        assert request.user_question == "q"
        assert request.chat_id == "c"
