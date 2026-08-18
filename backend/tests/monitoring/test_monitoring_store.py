"""Tests for the monitoring store, runner and candidate query."""

import pytest

from project.adapters.monitoring.CandidateQuery import CandidateQuery
from project.adapters.monitoring.Database import in_memory_database
from project.adapters.monitoring.DetectorRunner import DetectorRunner
from project.adapters.monitoring.SqlInteractionSink import (
    NEGATIVE_FEEDBACK_SIGNAL,
    SqlInteractionSink,
)
from project.adapters.monitoring.detectors import (
    FormatGuardrailDetector,
    WeakRetrievalDetector,
)
from project.adapters.monitoring.models import (
    CurationReview,
    Signal,
    VERDICT_DEFECT,
)
from project.ports.monitoring.InteractionSink import (
    InteractionRecord,
    RetrievedChunkRecord,
)


@pytest.fixture
def database():
    return in_memory_database()


@pytest.fixture
def sink(database):
    return SqlInteractionSink(database)


def make_record(**overrides) -> InteractionRecord:
    defaults = dict(
        chat_id="c-1",
        question="How much damage does Fireball deal?",
        answer="Fireball deals 8d6 fire damage. thanks for asking!",
        model="sabia-4",
        template_name="default",
        template_hash="abc123",
        corpus_version="deadbeef-383",
        latency_ms=1200,
        chunks=[
            RetrievedChunkRecord(
                rank=0, content="Fireball deals 8d6 fire.", score=0.91, page=12
            )
        ],
    )
    defaults.update(overrides)
    return InteractionRecord(**defaults)


class TestRecordInteraction:
    def test_returns_an_id_and_stores_chunks(self, sink, database):
        interaction_id = sink.record_interaction(make_record())

        assert interaction_id is not None
        candidate_query = CandidateQuery(database)
        assert candidate_query.summary()["interactions"] == 1

    def test_turn_index_increments_within_a_chat(self, sink, database):
        sink.record_interaction(make_record(question="first"))
        sink.record_interaction(make_record(question="second"))

        from project.adapters.monitoring.models import Interaction
        from sqlalchemy import select

        with database.session() as session:
            indexes = sorted(
                session.scalars(
                    select(Interaction.turn_index).order_by(
                        Interaction.turn_index
                    )
                )
            )
        assert indexes == [0, 1]

    def test_separate_chats_index_independently(self, sink, database):
        sink.record_interaction(make_record(chat_id="a"))
        first_of_second_chat = sink.record_interaction(
            make_record(chat_id="b")
        )

        from project.adapters.monitoring.models import Interaction

        with database.session() as session:
            assert (
                session.get(Interaction, first_of_second_chat).turn_index == 0
            )

    def test_a_broken_database_does_not_raise(self):
        class ExplodingDatabase:
            def session(self):
                raise RuntimeError("database is down")

        sink = SqlInteractionSink(ExplodingDatabase())

        assert sink.record_interaction(make_record()) is None


class TestRecordFeedback:
    def test_negative_feedback_always_produces_a_signal(self, sink, database):
        interaction_id = sink.record_interaction(make_record())

        sink.record_feedback(interaction_id, rating=-1, comment="wrong")

        from sqlalchemy import select

        with database.session() as session:
            signal = session.scalar(
                select(Signal).where(
                    Signal.type == NEGATIVE_FEEDBACK_SIGNAL,
                    Signal.interaction_id == interaction_id,
                )
            )
        assert signal is not None
        assert signal.details["comment"] == "wrong"

    def test_signal_references_the_feedback_row(self, sink, database):
        interaction_id = sink.record_interaction(make_record())

        feedback_id = sink.record_feedback(interaction_id, rating=-1)

        from sqlalchemy import select

        with database.session() as session:
            signal = session.scalar(
                select(Signal).where(
                    Signal.type == NEGATIVE_FEEDBACK_SIGNAL
                )
            )
        assert signal.details["feedback_id"] == feedback_id

    def test_positive_feedback_produces_no_signal(self, sink, database):
        interaction_id = sink.record_interaction(make_record())

        sink.record_feedback(interaction_id, rating=1)

        from sqlalchemy import func, select

        with database.session() as session:
            signal_count = session.scalar(
                select(func.count()).select_from(Signal)
            )
        assert signal_count == 0

    def test_repeated_negative_feedback_keeps_every_rating(
        self, sink, database
    ):
        interaction_id = sink.record_interaction(make_record())

        sink.record_feedback(interaction_id, rating=-1, comment="first")
        sink.record_feedback(interaction_id, rating=-1, comment="second")

        from project.adapters.monitoring.models import Feedback
        from sqlalchemy import func, select

        with database.session() as session:
            feedback_count = session.scalar(
                select(func.count()).select_from(Feedback)
            )
            signal_count = session.scalar(
                select(func.count())
                .select_from(Signal)
                .where(Signal.type == NEGATIVE_FEEDBACK_SIGNAL)
            )

        assert feedback_count == 2
        assert signal_count == 1

    def test_feedback_on_an_unknown_interaction_raises(self, sink):
        with pytest.raises(LookupError):
            sink.record_feedback("does-not-exist", rating=-1)


class TestDetectorRunner:
    def test_writes_signals_for_a_flagged_interaction(self, sink, database):
        interaction_id = sink.record_interaction(
            make_record(answer="No closing line here.")
        )
        runner = DetectorRunner(database, [FormatGuardrailDetector()])

        written = runner.run_for_interaction(interaction_id)

        assert written == 1

    def test_clean_interaction_yields_no_signals(self, sink, database):
        interaction_id = sink.record_interaction(make_record())
        runner = DetectorRunner(
            database, [FormatGuardrailDetector(), WeakRetrievalDetector()]
        )

        assert runner.run_for_interaction(interaction_id) == 0

    def test_rerunning_is_idempotent(self, sink, database):
        interaction_id = sink.record_interaction(
            make_record(answer="No closing line here.")
        )
        runner = DetectorRunner(database, [FormatGuardrailDetector()])

        runner.run_for_interaction(interaction_id)
        second_run = runner.run_for_interaction(interaction_id)

        assert second_run == 0

    def test_bumped_detector_version_reflags(self, sink, database):
        interaction_id = sink.record_interaction(
            make_record(answer="No closing line here.")
        )
        detector = FormatGuardrailDetector()
        DetectorRunner(database, [detector]).run_for_interaction(
            interaction_id
        )

        detector.version = "2"
        rerun = DetectorRunner(database, [detector]).run_for_interaction(
            interaction_id
        )

        assert rerun == 1

    def test_one_failing_detector_does_not_stop_the_others(
        self, sink, database
    ):
        class Broken(FormatGuardrailDetector):
            name = "broken"

            def detect(self, interaction):
                raise ValueError("boom")

        interaction_id = sink.record_interaction(
            make_record(answer="No closing line here.")
        )
        runner = DetectorRunner(
            database, [Broken(), FormatGuardrailDetector()]
        )

        assert runner.run_for_interaction(interaction_id) == 1

    def test_unknown_interaction_is_survivable(self, database):
        assert DetectorRunner(database).run_for_interaction("nope") == 0

    def test_backfill_covers_existing_interactions(self, sink, database):
        for index in range(3):
            sink.record_interaction(
                make_record(chat_id=f"c-{index}", answer="No closing.")
            )
        runner = DetectorRunner(database, [FormatGuardrailDetector()])

        assert runner.backfill() == 3

    def test_thread_scoped_signal_records_the_chat(self, sink, database):
        from project.adapters.monitoring.detectors import (
            RepeatedQuestionDetector,
        )

        sink.record_interaction(
            make_record(question="How much damage does Fireball deal?")
        )
        second = sink.record_interaction(
            make_record(question="How much fire damage does Fireball deal?")
        )
        runner = DetectorRunner(database, [RepeatedQuestionDetector()])
        runner.run_for_interaction(second)

        from sqlalchemy import select

        with database.session() as session:
            signal = session.scalar(
                select(Signal).where(Signal.type == "repeated_question")
            )
        assert signal.scope == "thread"
        assert signal.chat_id == "c-1"


class TestCandidateQuery:
    def test_unflagged_interactions_are_not_candidates(self, sink, database):
        interaction_id = sink.record_interaction(make_record())
        written = DetectorRunner(database).run_for_interaction(interaction_id)

        assert written == 0
        assert CandidateQuery(database).pending() == []

    def test_flagged_interaction_is_returned_with_its_context(
        self, sink, database
    ):
        interaction_id = sink.record_interaction(
            make_record(answer="No closing line here.")
        )
        DetectorRunner(database, [FormatGuardrailDetector()]).backfill()

        candidates = CandidateQuery(database).pending()

        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.interaction_id == interaction_id
        assert candidate.retrieval_context == ["Fireball deals 8d6 fire."]
        assert candidate.top_score == 0.91
        assert [s.type for s in candidate.signals] == [
            "format_guardrail_violation"
        ]

    def test_feedback_is_attached(self, sink, database):
        interaction_id = sink.record_interaction(make_record())
        sink.record_feedback(interaction_id, rating=-1, comment="nope")

        candidate = CandidateQuery(database).pending()[0]

        assert [f.comment for f in candidate.feedback] == ["nope"]

    def test_reviewed_interactions_drop_out(self, sink, database):
        interaction_id = sink.record_interaction(make_record())
        sink.record_feedback(interaction_id, rating=-1)
        assert len(CandidateQuery(database).pending()) == 1

        with database.session() as session:
            session.add(
                CurationReview(
                    interaction_id=interaction_id,
                    verdict=VERDICT_DEFECT,
                    reviewer="human",
                )
            )
            session.commit()

        assert CandidateQuery(database).pending() == []

    def test_filtering_by_signal_type(self, sink, database):
        flagged = sink.record_interaction(
            make_record(chat_id="a", answer="No closing.")
        )
        rated = sink.record_interaction(make_record(chat_id="b"))
        sink.record_feedback(rated, rating=-1)
        DetectorRunner(database, [FormatGuardrailDetector()]).backfill()

        candidates = CandidateQuery(database).pending(
            signal_type="format_guardrail_violation"
        )

        assert [c.interaction_id for c in candidates] == [flagged]

    def test_summary_counts_signals_by_type(self, sink, database):
        interaction_id = sink.record_interaction(
            make_record(answer="No closing.")
        )
        sink.record_feedback(interaction_id, rating=-1)
        DetectorRunner(database, [FormatGuardrailDetector()]).backfill()

        summary = CandidateQuery(database).summary()

        assert summary["interactions"] == 1
        assert summary["pending_candidates"] == 1
        assert summary["signals_by_type"] == {
            "format_guardrail_violation": 1,
            NEGATIVE_FEEDBACK_SIGNAL: 1,
        }


class TestSummaryAggregates:
    def test_empty_database_reports_zeroes_not_errors(self, database):
        summary = CandidateQuery(database).summary()

        assert summary["interactions"] == 0
        assert summary["retrieval_scores"]["bins"] == []
        assert summary["latency_ms"] == {"p50": 0, "p95": 0, "max": 0}

    def test_flagged_and_reviewed_are_counted_separately(
        self, sink, database
    ):
        flagged = sink.record_interaction(make_record(answer="No closing."))
        sink.record_interaction(make_record(chat_id="clean"))
        DetectorRunner(database, [FormatGuardrailDetector()]).backfill()

        with database.session() as session:
            session.add(
                CurationReview(
                    interaction_id=flagged,
                    verdict=VERDICT_DEFECT,
                    reviewer="human",
                )
            )
            session.commit()

        summary = CandidateQuery(database).summary()

        assert summary["interactions"] == 2
        assert summary["flagged_interactions"] == 1
        assert summary["reviewed_interactions"] == 1
        # Reviewed drops out of the queue but stays counted as flagged.
        assert summary["pending_candidates"] == 0

    def test_feedback_is_split_by_polarity(self, sink, database):
        first = sink.record_interaction(make_record(chat_id="a"))
        second = sink.record_interaction(make_record(chat_id="b"))
        sink.record_feedback(first, rating=-1)
        sink.record_feedback(second, rating=1)

        assert CandidateQuery(database).summary()["feedback"] == {
            "positive": 1,
            "negative": 1,
        }

    def test_histogram_uses_one_row_per_interaction(self, sink, database):
        for index in range(3):
            sink.record_interaction(make_record(chat_id=f"c{index}"))

        scores = CandidateQuery(database).summary()["retrieval_scores"]

        # Three interactions with one chunk each, not three chunks.
        assert scores["count"] == 3
        assert sum(b["count"] for b in scores["bins"]) == 3

    def test_identical_scores_collapse_to_a_single_bin(self, sink, database):
        sink.record_interaction(make_record())

        bins = CandidateQuery(database).summary()["retrieval_scores"]["bins"]

        assert len(bins) == 1
        assert bins[0]["count"] == 1

    def test_scores_below_threshold_are_counted(self, sink, database):
        sink.record_interaction(
            make_record(
                chat_id="weak",
                chunks=[RetrievedChunkRecord(rank=0, content="x", score=0.2)],
            )
        )

        scores = CandidateQuery(database).summary()["retrieval_scores"]

        assert scores["below_threshold"] == 1
        assert scores["threshold"] > 0

    def test_latency_percentiles(self, sink, database):
        for index, latency in enumerate([100, 200, 900]):
            sink.record_interaction(
                make_record(chat_id=f"c{index}", latency_ms=latency)
            )

        latency = CandidateQuery(database).summary()["latency_ms"]

        assert latency["p50"] == 200
        assert latency["max"] == 900

    def test_source_breakdown(self, sink, database):
        sink.record_interaction(make_record(chat_id="a", source="production"))
        sink.record_interaction(make_record(chat_id="b", source="synthetic"))

        assert CandidateQuery(database).summary()[
            "interactions_by_source"
        ] == {"production": 1, "synthetic": 1}
