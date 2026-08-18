"""Engine and session factory for the monitoring tables."""

import logging
import os
import time
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from project.adapters.monitoring.models import Base

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "../database/monitoring.db"
DB_URL_ENV_VAR = "MONITORING_DATABASE_URL"

#: How long to wait before retrying schema creation after a failure. Short
#: enough to recover on its own, long enough that a down database does not
#: add a connection attempt to every request.
SCHEMA_RETRY_SECONDS = 10.0

#: Monitoring must never add latency, so a connection to a missing
#: database has to fail fast instead of hanging the request behind it.
CONNECT_TIMEOUT_SECONDS = 3


def default_database_url() -> str:
    configured = os.environ.get(DB_URL_ENV_VAR)
    if configured:
        return configured

    path = Path(DEFAULT_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+pysqlite:///{path}"


class MonitoringDatabase:
    def __init__(self, url: str | None = None, poolclass=None):
        self.url = url or default_database_url()
        is_sqlite = self.url.startswith("sqlite")

        if is_sqlite:
            # Sync endpoints and background tasks run on a threadpool, so
            # connections are handed between threads.
            connect_args = {"check_same_thread": False}
        else:
            connect_args = {"connect_timeout": CONNECT_TIMEOUT_SECONDS}

        # Kept as an attribute so the dialect-specific choice is
        # inspectable; SQLAlchemy merges these at connect time.
        self.connect_args = connect_args

        engine_options = {"future": True, "connect_args": connect_args}
        if poolclass is not None:
            engine_options["poolclass"] = poolclass

        self.engine = create_engine(self.url, **engine_options)

        if is_sqlite:
            _enable_sqlite_pragmas(self.engine)

        self.session_factory = sessionmaker(
            bind=self.engine, expire_on_commit=False, future=True
        )

        self._schema_ready = False
        # None rather than 0.0: monotonic() can be small right after boot,
        # and comparing against 0.0 would throttle the very first attempt.
        self._last_schema_attempt = None

    def create_schema(self) -> None:
        """Creates the tables, raising if the database is unreachable."""
        Base.metadata.create_all(self.engine)
        self._schema_ready = True

    def ensure_schema(self) -> bool:
        """Creates the tables if that has not succeeded yet.

        Deferred rather than done once at startup: `depends_on` only orders
        `compose up`, not `restart` or a daemon restart, and a database
        normally restarts independently of the app. Treating "unreachable
        at boot" as permanent would leave monitoring silently off until
        someone noticed and restarted the API.
        """
        if self._schema_ready:
            return True

        now = time.monotonic()
        if (
            self._last_schema_attempt is not None
            and now - self._last_schema_attempt < SCHEMA_RETRY_SECONDS
        ):
            return False
        self._last_schema_attempt = now

        try:
            self.create_schema()
        except Exception as failure:
            logger.warning(
                "monitoring database unavailable (%s: %s); retrying later",
                type(failure).__name__,
                failure,
            )
            return False

        logger.info("monitoring schema ready at %s", self.url)
        return True

    def session(self) -> Session:
        self.ensure_schema()
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
    """Fresh isolated database, for tests.

    StaticPool keeps every session on one connection: an in-memory
    database lives inside its connection, so pooling would hand out
    sessions that each see an empty schema.
    """
    database = MonitoringDatabase(
        "sqlite+pysqlite:///:memory:", poolclass=StaticPool
    )
    database.create_schema()
    return database
