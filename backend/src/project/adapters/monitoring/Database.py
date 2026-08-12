"""Engine and session factory for the monitoring tables."""

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from project.adapters.monitoring.models import Base

DEFAULT_DB_PATH = "../database/monitoring.db"
DB_URL_ENV_VAR = "MONITORING_DATABASE_URL"


def default_database_url() -> str:
    configured = os.environ.get(DB_URL_ENV_VAR)
    if configured:
        return configured

    path = Path(DEFAULT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+pysqlite:///{path}"


class MonitoringDatabase:
    def __init__(self, url: str | None = None):
        self.url = url or default_database_url()
        is_sqlite = self.url.startswith("sqlite")

        self.engine = create_engine(
            self.url,
            future=True,
            # Sync endpoints and background tasks run on a threadpool, so
            # connections are handed between threads.
            connect_args={"check_same_thread": False} if is_sqlite else {},
        )

        if is_sqlite:
            _enable_sqlite_pragmas(self.engine)

        self.session_factory = sessionmaker(
            bind=self.engine, expire_on_commit=False, future=True
        )

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> Session:
        return self.session_factory()


def _enable_sqlite_pragmas(engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        # Off by default in SQLite.
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def in_memory_database() -> MonitoringDatabase:
    """Fresh isolated database, for tests."""
    database = MonitoringDatabase.__new__(MonitoringDatabase)
    database.url = "sqlite+pysqlite:///:memory:"
    database.engine = create_engine(
        database.url,
        future=True,
        connect_args={"check_same_thread": False},
        # An in-memory database lives inside its connection, so every
        # session has to share one.
        poolclass=StaticPool,
    )
    _enable_sqlite_pragmas(database.engine)
    database.session_factory = sessionmaker(
        bind=database.engine, expire_on_commit=False, future=True
    )
    database.create_schema()
    return database
