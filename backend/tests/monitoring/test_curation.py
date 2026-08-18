"""Tests for stratified sampling and review bookkeeping."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from project.adapters.monitoring.CurationStore import CurationStore
from project.adapters.monitoring.Database import in_memory_database
from project.adapters.monitoring.DetectorRunner import DetectorRunner
from project.adapters.monitoring.SqlInteractionSink import SqlInteractionSink
from project.adapters.monitoring.detectors import FormatGuardrailDetector
from project.adapters.monitoring.models import VERDICT_DEFECT, VERDICT_NOISE
from project.adapters.routers.CurationRouter import CurationRouter
from project.ports.monitoring.InteractionSink import (
    InteractionRecord,
    RetrievedChunkRecord,
)

CLEAN_ANSWER = "Fireball deals 8d6 fire damage. thanks for asking!"
FLAGGED_ANSWER = "Fireball deals 8d6 fire damage."


@pytest.fixture
def database():
    return in_memory_database()


@pytest.fixture
def store(database):
    return CurationStore(database)


@pytest.fixture
def sink(database):
    return SqlInteractionSink(database)


def record(sink, chat_id, answer=CLEAN_ANSWER, **overrides):
    return sink.record_interaction(
        InteractionRecord(
            chat_id=chat_id,
            question="How much damage does Fireball deal?",
            answer=answer,
            chunks=[
                RetrievedChunkRecord(
                    rank=0, content="deals 8d6 fire", score=0.9
                )
            ],
            **overrides,
        )
    )


def seed(sink, database, flagged=0, unflagged=0):
    """Creates interactions in each stratum, flagged via the format check."""
    flagged_ids = [
        record(sink, f"flag-{index}", answer=FLAGGED_ANSWER)
        for index in range(flagged)
    ]
    plain_ids = [record(sink, f"ok-{index}") for index in range(unflagged)]
    DetectorRunner(database, [FormatGuardrailDetector()]).backfill()
    return flagged_ids, plain_ids


class TestSampling:
    def test_draws_from_both_strata(self, sink, database, store):
        seed(sink, database, flagged=6, unflagged=6)

        sample = store.sample(size=4, flagged_share=0.5)

        strata = [item.stratum for item in sample]
        assert strata.count("flagged") == 2
        assert strata.count("unflagged") == 2

    def test_unflagged_interactions_are_reachable_at_all(
        self, sink, database, store
    ):
        # The candidate queue can only ever show flagged items, so this is
        # the only path to the defects the detectors miss.
        seed(sink, database, flagged=0, unflagged=3)

        sample = store.sample(size=3)

        assert [item.stratum for item in sample] == ["unflagged"] * 3

    def test_a_short_stratum_is_topped_up_from_the_other(
        self, sink, database, store
    ):
        seed(sink, database, flagged=1, unflagged=5)

        sample = store.sample(size=4, flagged_share=0.5)

        assert len(sample) == 4

    def test_reviewed_interactions_are_never_resampled(
        self, sink, database, store
    ):
        _, plain = seed(sink, database, flagged=0, unflagged=2)
        store.record_review(plain[0], VERDICT_NOISE)

        sample = store.sample(size=10)

        assert [item.interaction_id for item in sample] == [plain[1]]

    def test_errored_interactions_are_not_sampled(self, sink, store):
        record(sink, "broken", answer="", error="RateLimitError: boom")

        assert store.sample(size=5) == []

    def test_the_sample_carries_the_conversation_around_the_turn(
        self, sink, database, store
    ):
        record(sink, "thread", answer=CLEAN_ANSWER)
        subject = record(sink, "thread", answer=CLEAN_ANSWER)
        DetectorRunner(database, [FormatGuardrailDetector()]).backfill()

        sample = store.sample(size=10)
        reviewed = next(
            item for item in sample if item.interaction_id == subject
        )

        assert len(reviewed.thread) == 2
        assert [turn.is_subject for turn in reviewed.thread] == [False, True]

    def test_signals_travel_with_the_sample_for_reveal_after_verdict(
        self, sink, database, store
    ):
        seed(sink, database, flagged=1, unflagged=0)

        sample = store.sample(size=1, flagged_share=1.0)

        assert sample[0].signals[0]["type"] == "format_guardrail_violation"

    def test_an_empty_database_yields_an_empty_sample(self, store):
        assert store.sample(size=10) == []


class TestReviews:
    def test_recording_a_verdict_returns_its_id(self, sink, database, store):
        _, plain = seed(sink, database, unflagged=1)

        assert store.record_review(plain[0], VERDICT_DEFECT, "wrong dice") > 0

    def test_reviewing_an_unknown_interaction_raises(self, store):
        with pytest.raises(LookupError):
            store.record_review("nope", VERDICT_NOISE)


class TestStats:
    def test_precision_comes_from_the_flagged_stratum(
        self, sink, database, store
    ):
        flagged, _ = seed(sink, database, flagged=4, unflagged=0)
        store.record_review(flagged[0], VERDICT_DEFECT)
        store.record_review(flagged[1], VERDICT_NOISE)

        stats = store.stats()

        assert stats["flagged"]["reviewed"] == 2
        assert stats["flagged"]["defects"] == 1
        assert stats["precision"] == 0.5

    def test_recall_is_unknown_until_both_strata_are_reviewed(
        self, sink, database, store
    ):
        flagged, _ = seed(sink, database, flagged=2, unflagged=2)
        store.record_review(flagged[0], VERDICT_DEFECT)

        assert store.stats()["estimated_recall"] is None

    def test_recall_scales_each_stratum_back_to_its_pool(
        self, sink, database, store
    ):
        # 4 flagged, 8 unflagged. Reviewing 2 of each: both flagged are
        # defects, one unflagged is. Naively that reads 2/3 = 0.67, but the
        # unflagged pool is twice as large and was sampled at half the
        # rate, so its misses must be scaled up:
        #   true positives  = 4 * (2/2) = 4
        #   missed          = 8 * (1/2) = 4
        #   recall          = 4 / 8     = 0.5
        flagged, plain = seed(sink, database, flagged=4, unflagged=8)
        store.record_review(flagged[0], VERDICT_DEFECT)
        store.record_review(flagged[1], VERDICT_DEFECT)
        store.record_review(plain[0], VERDICT_DEFECT)
        store.record_review(plain[1], VERDICT_NOISE)

        stats = store.stats()

        assert stats["flagged"]["pool"] == 4
        assert stats["unflagged"]["pool"] == 8
        assert stats["precision"] == 1.0
        assert stats["estimated_recall"] == 0.5

    def test_perfect_recall_when_nothing_was_missed(
        self, sink, database, store
    ):
        flagged, plain = seed(sink, database, flagged=2, unflagged=4)
        store.record_review(flagged[0], VERDICT_DEFECT)
        store.record_review(plain[0], VERDICT_NOISE)

        assert store.stats()["estimated_recall"] == 1.0

    def test_no_defects_anywhere_leaves_recall_undefined(
        self, sink, database, store
    ):
        flagged, plain = seed(sink, database, flagged=2, unflagged=2)
        store.record_review(flagged[0], VERDICT_NOISE)
        store.record_review(plain[0], VERDICT_NOISE)

        assert store.stats()["estimated_recall"] is None

    def test_empty_database_reports_no_metrics(self, store):
        stats = store.stats()

        assert stats["precision"] is None
        assert stats["estimated_recall"] is None


class TestCurationApi:
    def client(self, store):
        api = FastAPI()
        api.include_router(CurationRouter(store).create())
        return TestClient(api)

    def test_sample_endpoint(self, sink, database, store):
        seed(sink, database, flagged=1, unflagged=1)

        response = self.client(store).get("/v1/curation/sample?size=2")

        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_review_endpoint_persists_the_verdict(
        self, sink, database, store
    ):
        _, plain = seed(sink, database, unflagged=1)

        response = self.client(store).post(
            "/v1/curation/reviews",
            json={
                "interactionId": plain[0],
                "verdict": "defect",
                "rationale": "inventou o dano",
            },
        )

        assert response.status_code == 200
        assert store.stats()["unflagged"]["defects"] == 1

    def test_an_unknown_verdict_is_rejected(self, sink, database, store):
        _, plain = seed(sink, database, unflagged=1)

        response = self.client(store).post(
            "/v1/curation/reviews",
            json={"interactionId": plain[0], "verdict": "maybe"},
        )

        assert response.status_code == 422

    def test_reviewing_a_missing_interaction_is_a_404(self, store):
        response = self.client(store).post(
            "/v1/curation/reviews",
            json={"interactionId": "nope", "verdict": "noise"},
        )

        assert response.status_code == 404

    def test_stats_endpoint(self, store):
        assert self.client(store).get("/v1/curation/stats").status_code == 200
