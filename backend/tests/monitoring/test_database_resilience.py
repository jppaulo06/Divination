"""Tests that a database missing at boot does not disable monitoring."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from project.adapters.monitoring.CandidateQuery import CandidateQuery
from project.adapters.monitoring.Database import MonitoringDatabase
from project.adapters.monitoring.SqlInteractionSink import SqlInteractionSink
from project.adapters.routers.MonitoringRouter import MonitoringRouter
from project.ports.monitoring.InteractionSink import InteractionRecord


def unreachable_database() -> MonitoringDatabase:
    """A database that cannot be opened, standing in for a missing host.

    SQLite against an impossible path rather than a real unresolvable
    Postgres host: it reproduces the same failure (schema creation raises,
    every session fails) without putting DNS timeouts into the suite.
    """
    return MonitoringDatabase("sqlite+pysqlite:////proc/nope/monitoring.db")


def memory_database() -> MonitoringDatabase:
    return MonitoringDatabase(
        "sqlite+pysqlite:///:memory:", poolclass=StaticPool
    )


class TestDeferredSchema:
    def test_construction_does_not_require_a_reachable_database(self):
        # Previously the app called create_schema() at startup, so this
        # raised and monitoring was switched off for the whole process.
        database = unreachable_database()

        assert database.ensure_schema() is False

    def test_recording_degrades_quietly_while_unreachable(self):
        sink = SqlInteractionSink(unreachable_database())

        assert (
            sink.record_interaction(
                InteractionRecord(chat_id="c", question="q", answer="a")
            )
            is None
        )

    def test_schema_is_created_lazily_on_first_use(self):
        database = memory_database()
        assert database._schema_ready is False

        with database.session() as session:
            session.execute(text("select 1"))

        assert database._schema_ready is True

    def test_success_is_remembered_rather_than_retried(self):
        database = memory_database()
        database.ensure_schema()
        attempts = database._last_schema_attempt

        assert database.ensure_schema() is True
        # No further attempt was timed, so the fast path was taken.
        assert database._last_schema_attempt == attempts

    def test_the_first_attempt_is_never_throttled(self):
        # The retry window must not swallow the initial attempt, which a
        # 0.0 sentinel would have done shortly after boot.
        database = memory_database()

        assert database.ensure_schema() is True

    def test_failures_are_throttled_between_retries(self):
        database = unreachable_database()

        assert database.ensure_schema() is False
        first_attempt = database._last_schema_attempt
        assert database.ensure_schema() is False
        # Inside the retry window, so no second connection was attempted.
        assert database._last_schema_attempt == first_attempt

    def test_monitoring_recovers_once_the_database_appears(self, tmp_path):
        path = tmp_path / "late.db"
        database = MonitoringDatabase(f"sqlite+pysqlite:///{path}")
        sink = SqlInteractionSink(database)

        # Simulate the boot-time failure, then let it heal.
        database._schema_ready = False
        database._last_schema_attempt = None

        recorded = sink.record_interaction(
            InteractionRecord(chat_id="c", question="q", answer="a")
        )

        assert recorded is not None
        assert CandidateQuery(database).summary()["interactions"] == 1


class TestRoutesStayRegistered:
    def test_summary_reports_503_rather_than_disappearing(self):
        # The routes used to be skipped entirely when the database was
        # missing at boot, so the dashboard got a 404 and no explanation.
        api = FastAPI()
        api.include_router(
            MonitoringRouter(CandidateQuery(unreachable_database())).create()
        )
        client = TestClient(api)

        response = client.get("/v1/monitoring/summary")

        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"]

    def test_candidates_reports_503_too(self):
        api = FastAPI()
        api.include_router(
            MonitoringRouter(CandidateQuery(unreachable_database())).create()
        )

        assert (
            TestClient(api).get("/v1/monitoring/candidates").status_code == 503
        )


@pytest.mark.parametrize(
    "url,expected",
    [
        ("sqlite+pysqlite:///:memory:", "check_same_thread"),
        ("postgresql+psycopg://u:p@h:5432/d", "connect_timeout"),
    ],
)
def test_connect_args_are_dialect_appropriate(url, expected):
    # Postgres needs a connect timeout so an unreachable database fails
    # fast instead of hanging a user's request behind it; SQLite needs the
    # threadpool escape hatch instead.
    assert expected in MonitoringDatabase(url).connect_args
